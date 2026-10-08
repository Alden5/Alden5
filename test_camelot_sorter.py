import itertools
import os
import random
import subprocess
import tempfile
import unittest
import wave
from unittest import mock

import numpy as np

from camelot_music_sorter.apple_music import (
    APP_MARKER, FIELD_SEP, RECORD_SEP, AppleMusicBridge, MusicAppError,
)
from camelot_music_sorter.audio_engine import (
    compute_chroma_from_pcm, detect_key_from_audio_file, estimate_key_from_chroma, ffmpeg_available,
)
from camelot_music_sorter.camelot import MusicalKey, camelot_distance, extract_key, transition_score
from camelot_music_sorter.song_model import KeyResolver, Song
from camelot_music_sorter.sorter import HarmonicPlaylistSorter, calculate_pairwise_cost


def keyed(i, camelot, bpm=0.0, title=None):
    s = Song(id=str(i), title=title or f"Track {i}", artist="Artist", bpm=bpm)
    s.resolved_key = MusicalKey.from_camelot(camelot) if camelot else None
    return s


SR = 22050


def progression(tonic, minor, seconds):
    def tone(midi, dur):
        t = np.arange(int(SR * dur)) / SR
        f = 440 * 2 ** ((midi - 69) / 12)
        return sum(np.sin(2 * np.pi * f * h * t) / h for h in (1, 2, 3, 4))

    def chord(root, is_minor):
        return tone(root, 1) + tone(root + (3 if is_minor else 4), 1) + tone(root + 7, 1) + tone(root - 12, 1)

    seq = [(0, minor), (5, minor), (7, False), (0, minor)]
    parts = []
    while sum(len(p) for p in parts) < SR * seconds:
        parts += [chord(60 + tonic + off - (12 if off > 6 else 0), m) for off, m in seq]
    x = np.concatenate(parts)[: SR * seconds]
    return (x / np.abs(x).max() * 0.6 * 32767).astype(np.int16)


class TestCamelotWheel(unittest.TestCase):
    def test_camelot_parsing(self):
        k = MusicalKey.from_camelot("8A")
        self.assertEqual((k.number, k.letter, k.mode), (8, "A", "minor"))
        self.assertEqual(k.standard_name, "A minor")
        self.assertEqual(MusicalKey.from_camelot("11B").standard_name, "A major")
        self.assertEqual(MusicalKey.from_camelot("08a").camelot, "8A")

    def test_whole_field_parsing(self):
        cases = {
            "Am": "8A", "A minor": "8A", "C maj": "8B", "C": "8B", "F#m": "11A", "F#": "2B",
            "Db major": "3B", "Abm": "1A", "Ebm": "2A", "Bb": "6B", "4A": "4A", "12B": "12B",
            "1m": "8A", "1d": "8B", "6d": "1B", "F♯ minor": "11A",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(MusicalKey.parse(text).camelot, expected)

    def test_key_in_free_text(self):
        self.assertEqual(extract_key("8A - Energy 6").camelot, "8A")
        self.assertEqual(extract_key("Key: C# minor").camelot, "12A")
        self.assertEqual(extract_key("great opener, F# minor, peak").camelot, "11A")

    def test_ordinary_words_are_not_keys(self):
        for text in ("a great song", "Bass heavy", "Remix 2024", "Love this track", "vol. 2a", "Dance", "", None):
            with self.subTest(text=text):
                self.assertIsNone(extract_key(text))

    def test_every_key_round_trips(self):
        for n in range(1, 13):
            for letter in "AB":
                k = MusicalKey.from_camelot(f"{n}{letter}")
                self.assertEqual(MusicalKey.from_pitch_mode(k.pitch_class, k.mode), k)
                self.assertEqual(MusicalKey.parse(k.standard_name).camelot, k.camelot)

    def test_camelot_distance(self):
        d = lambda a, b: camelot_distance(MusicalKey.from_camelot(a), MusicalKey.from_camelot(b))
        self.assertEqual(d("8A", "9A"), 1)
        self.assertEqual(d("12A", "1A"), 1)
        self.assertEqual(d("8A", "2A"), 6)

    def test_transition_scoring(self):
        k = MusicalKey.from_camelot
        self.assertEqual(transition_score(k("8A"), k("8A"))[0], 0.0)
        self.assertLessEqual(transition_score(k("8A"), k("8B"))[0], 0.5)
        self.assertEqual(transition_score(k("8A"), k("9A"))[0], 0.5)
        self.assertGreaterEqual(transition_score(k("8A"), k("2A"))[0], 8.0)

    def test_large_tempo_jump_is_not_smooth(self):
        a, b = keyed(1, "8A", 128), keyed(2, "9A", 98)
        self.assertGreater(calculate_pairwise_cost(a, b)[0], 2.5)
        self.assertLessEqual(calculate_pairwise_cost(keyed(3, "8A", 87), keyed(4, "9A", 174))[0], 0.5)


class TestAudioKeyEngine(unittest.TestCase):
    def test_synthetic_c_major_chord(self):
        t = np.linspace(0, 1.0, SR, endpoint=False)
        chord = sum(np.sin(2 * np.pi * f * t) for f in (261.63, 329.63, 392.00)) / 3
        chroma = compute_chroma_from_pcm(chord, SR)
        self.assertEqual(len(chroma), 12)
        key, conf = estimate_key_from_chroma(chroma)
        self.assertIn(key.camelot, ["8B", "8A", "9A"])

    def test_silence_has_zero_confidence(self):
        _, conf = estimate_key_from_chroma(compute_chroma_from_pcm(np.zeros(SR), SR))
        self.assertEqual(conf, 0.0)

    @unittest.skipUnless(ffmpeg_available(), "ffmpeg not installed")
    def test_detects_keys_from_encoded_files_including_short_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            for tonic, minor, seconds, ext in ((9, True, 12, "m4a"), (7, False, 60, "mp3"), (6, True, 45, "m4a")):
                wav = os.path.join(tmp, "x.wav")
                with wave.open(wav, "wb") as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(SR)
                    f.writeframes(progression(tonic, minor, seconds).tobytes())
                out = os.path.join(tmp, f"x.{ext}")
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, out], check=True)
                expected = MusicalKey.from_pitch_mode(tonic, "minor" if minor else "major")
                with self.subTest(key=expected.camelot, seconds=seconds):
                    key, _ = detect_key_from_audio_file(out)
                    self.assertEqual(key, expected)

    @unittest.skipUnless(ffmpeg_available(), "ffmpeg not installed")
    def test_reads_key_tag_embedded_in_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tagged.mp3")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=3",
                            "-metadata", "TKEY=Abm", path], check=True)
            song = KeyResolver(cache_path=None).resolve(Song(id="1", title="t", artist="a", location=path))
            self.assertEqual((song.resolved_key.camelot, song.key_source), ("1A", "file_tag"))


class TestKeyResolver(unittest.TestCase):
    def test_metadata_comment_wins(self):
        s = KeyResolver(cache_path=None).resolve(Song(id="1", title="t", artist="a", extra={"comment": "Energy 7 - 4A"}))
        self.assertEqual((s.resolved_key.camelot, s.key_source), ("4A", "metadata"))

    def test_streaming_track_without_tags_is_unknown_not_guessed(self):
        s = KeyResolver(cache_path=None).resolve(Song(id="1", title="Untagged", artist="Someone"))
        self.assertIsNone(s.resolved_key)
        self.assertEqual(s.key_source, "unknown")
        self.assertIn("Comments", s.key_note)

    def test_analysis_results_are_cached_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "a.wav")
            open(audio, "wb").close()
            cache = os.path.join(tmp, "cache.json")
            fake = {"camelot": "5A", "source": "audio_analysis", "confidence": 0.8, "note": ""}
            with mock.patch.object(KeyResolver, "_analyze_file", return_value=fake) as analyze:
                KeyResolver(cache_path=cache).resolve_many([Song(id="1", title="t", artist="a", location=audio)])
                song = KeyResolver(cache_path=cache).resolve(Song(id="1", title="t", artist="a", location=audio))
            self.assertEqual(analyze.call_count, 1)
            self.assertEqual(song.resolved_key.camelot, "5A")


class TestHarmonicSorter(unittest.TestCase):
    def test_finds_optimal_order_for_small_playlists(self):
        rng = random.Random(7)
        sorter = HarmonicPlaylistSorter(energy_flow_preference="balanced")
        for trial in range(25):
            songs = [keyed(i, f"{rng.randint(1, 12)}{rng.choice('AB')}", rng.choice([0, 122, 126, 140]))
                     for i in range(7)]
            cost = lambda order: sum(calculate_pairwise_cost(a, b)[0] for a, b in zip(order, order[1:]))
            best = min(cost(p) for p in itertools.permutations(songs))
            with self.subTest(trial=trial):
                self.assertAlmostEqual(cost(sorter.optimize_order(songs)), best, delta=0.5)

    def test_keeps_every_song_exactly_once(self):
        rng = random.Random(3)
        songs = [keyed(i, f"{rng.randint(1, 12)}{rng.choice('AB')}") for i in range(120)]
        out = HarmonicPlaylistSorter().optimize_order(songs)
        self.assertEqual(sorted(s.id for s in out), sorted(s.id for s in songs))

    def test_unknown_keys_go_last(self):
        songs = [keyed(1, "8A"), keyed(2, None), keyed(3, "9A"), keyed(4, "8B")]
        result = HarmonicPlaylistSorter().sort_and_analyze(songs)
        self.assertEqual(result.sorted_songs[-1].id, "2")
        self.assertEqual(result.summary()["unknown_key_count"], 1)
        self.assertEqual(result.summary()["scored_transitions"], 2)

    def test_start_track_is_respected(self):
        songs = [keyed(i, k) for i, k in enumerate(["8A", "9A", "10A", "11A", "12A", "3B"])]
        for start in ("3", "5"):
            out = HarmonicPlaylistSorter().optimize_order(songs, start_id=start)
            self.assertEqual(out[0].id, start)
            self.assertEqual(len(out), len(songs))

    def test_single_outlier_is_flagged(self):
        songs = [keyed(1, "8A"), keyed(2, "2B"), keyed(3, "9A"), keyed(4, "10A"), keyed(5, "10B")]
        result = HarmonicPlaylistSorter().sort_and_analyze(songs)
        self.assertEqual([s.song.id for s in result.suggestions_to_remove], ["2"])

    def test_small_group_of_outliers_is_flagged(self):
        songs = [keyed(i, k) for i, k in enumerate(["8A", "8A", "9A", "8B", "9B", "10A", "2B", "2B"])]
        flagged = {s.song.id for s in HarmonicPlaylistSorter().sort_and_analyze(songs).suggestions_to_remove}
        self.assertEqual(flagged, {"6", "7"})

    def test_wide_but_smooth_playlist_has_no_suggestions(self):
        songs = [keyed(i, f"{i}A") for i in range(1, 13)]
        self.assertEqual(HarmonicPlaylistSorter().sort_and_analyze(songs).suggestions_to_remove, [])


class FakeProc:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


class TestMusicAppBridge(unittest.TestCase):
    def setUp(self):
        self.bridge = AppleMusicBridge(demo=False)

    def test_parses_tracks_with_locale_decimals_and_duplicates(self):
        rec = lambda *f: FIELD_SEP.join(f)
        out = RECORD_SEP.join([
            rec("AAA", "Song, \"One\"", "Art", "Alb", "245,5", "124", "8A", "", "House", "/Music/a.m4a"),
            rec("BBB", "Two", "Art", "", "180.0", "0", "", "Am", "", ""),
            rec("AAA", "Song, \"One\"", "Art", "Alb", "245,5", "124", "8A", "", "House", "/Music/a.m4a"),
        ]) + "\n"
        with mock.patch.object(self.bridge, "run_applescript", return_value=out) as run:
            songs = self.bridge.get_playlist_tracks("PL1")
        run.assert_called_once()
        self.assertEqual(run.call_args.args[1], "PL1")
        self.assertEqual([s.id for s in songs], ["AAA", "BBB", "AAA#2"])
        self.assertEqual([s.persistent_id for s in songs], ["AAA", "BBB", "AAA"])
        self.assertEqual(songs[0].duration_seconds, 245.5)
        self.assertEqual(songs[0].bpm, 124)
        self.assertEqual(songs[0].title, 'Song, "One"')
        self.assertIsNone(songs[1].location)

    def test_lists_playlists(self):
        out = RECORD_SEP.join([FIELD_SEP.join(["Mix \"A\"", "P1", "12", "false"]),
                               FIELD_SEP.join(["Smart", "P2", "3", "true"])])
        with mock.patch.object(self.bridge, "run_applescript", return_value=out):
            pls = self.bridge.get_all_playlists()
        self.assertEqual(pls[0], {"name": 'Mix "A"', "id": "P1", "track_count": 12, "smart": False})
        self.assertTrue(pls[1]["smart"])

    def test_create_passes_values_as_arguments_not_script_source(self):
        songs = [Song(id="X#2", persistent_id="X", title="t", artist="a"), Song(id="Y", title="t", artist="a")]
        with mock.patch.object(self.bridge, "run_applescript",
                               return_value=FIELD_SEP.join(['My "Mix" sorted', "2", "false"])) as run:
            created = self.bridge.create_sorted_playlist("PL1", 'My "Mix"', songs)
        script, *args = run.call_args.args
        self.assertNotIn('My "Mix"', script)
        self.assertEqual(args, ["PL1", 'My "Mix" sorted', APP_MARKER, "X", "Y"])
        self.assertEqual(created, {"name": 'My "Mix" sorted', "added": 2, "requested": 2, "replaced": False})

    def test_permission_error_has_helpful_message(self):
        with mock.patch("subprocess.run", return_value=FakeProc(stderr="execution error: Not authorized to send Apple events to Music. (-1743)", returncode=1)):
            with self.assertRaises(MusicAppError) as ctx:
                self.bridge.get_all_playlists()
        self.assertIn("Automation", str(ctx.exception))

    def test_demo_library_creates_and_replaces_sorted_copy(self):
        demo = AppleMusicBridge(demo=True)
        pl = demo.find_playlist("Friday Night House")
        tracks = demo.get_playlist_tracks(pl["id"])
        first = demo.create_sorted_playlist(pl["id"], pl["name"], tracks)
        second = demo.create_sorted_playlist(pl["id"], pl["name"], tracks[:3])
        self.assertEqual(first["name"], "Friday Night House sorted")
        self.assertTrue(second["replaced"])
        names = [p["name"] for p in demo.get_all_playlists()]
        self.assertEqual(names.count("Friday Night House sorted"), 1)
        self.assertEqual(len(demo.get_playlist_tracks("Friday Night House sorted")), 3)


if __name__ == "__main__":
    unittest.main()
