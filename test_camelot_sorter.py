import unittest
import numpy as np
from camelot_music_sorter.camelot import (
    MusicalKey,
    camelot_distance,
    transition_score,
    MAJOR_TO_CAMELOT,
    MINOR_TO_CAMELOT,
)
from camelot_music_sorter.song_model import Song, KeyResolver
from camelot_music_sorter.sorter import HarmonicPlaylistSorter, evaluate_playlist_order
from camelot_music_sorter.audio_engine import compute_chroma_from_pcm, estimate_key_from_chroma
from camelot_music_sorter.apple_music import AppleMusicBridge


class TestCamelotWheel(unittest.TestCase):
    def test_camelot_parsing(self):
        k8a = MusicalKey.from_camelot("8A")
        self.assertEqual(k8a.number, 8)
        self.assertEqual(k8a.letter, "A")
        self.assertEqual(k8a.mode, "minor")
        self.assertEqual(k8a.camelot, "8A")
        self.assertIn("A minor", k8a.standard_name)

        k11b = MusicalKey.from_camelot("11B")
        self.assertEqual(k11b.number, 11)
        self.assertEqual(k11b.letter, "B")
        self.assertEqual(k11b.mode, "major")
        self.assertEqual(k11b.camelot, "11B")
        self.assertIn("A major", k11b.standard_name)

    def test_flexible_key_parsing(self):
        # Standard notation
        self.assertEqual(MusicalKey.parse("Am").camelot, "8A")
        self.assertEqual(MusicalKey.parse("A minor").camelot, "8A")
        self.assertEqual(MusicalKey.parse("C maj").camelot, "8B")
        self.assertEqual(MusicalKey.parse("C major").camelot, "8B")
        self.assertEqual(MusicalKey.parse("F#m").camelot, "11A")
        self.assertEqual(MusicalKey.parse("Db major").camelot, "3B")
        # Direct camelot
        self.assertEqual(MusicalKey.parse("4A").camelot, "4A")
        self.assertEqual(MusicalKey.parse("12B").camelot, "12B")

    def test_camelot_distance(self):
        # 8A and 9A distance is 1
        self.assertEqual(camelot_distance(MusicalKey.from_camelot("8A"), MusicalKey.from_camelot("9A")), 1)
        # 8A and 7A distance is 1
        self.assertEqual(camelot_distance(MusicalKey.from_camelot("8A"), MusicalKey.from_camelot("7A")), 1)
        # 12A and 1A wrap around
        self.assertEqual(camelot_distance(MusicalKey.from_camelot("12A"), MusicalKey.from_camelot("1A")), 1)
        # 8A and 2A (opposite)
        self.assertEqual(camelot_distance(MusicalKey.from_camelot("8A"), MusicalKey.from_camelot("2A")), 6)

    def test_transition_scoring(self):
        k8a = MusicalKey.from_camelot("8A")
        k8b = MusicalKey.from_camelot("8B")
        k9a = MusicalKey.from_camelot("9A")
        k2a = MusicalKey.from_camelot("2A")

        # Same key
        p0, d0 = transition_score(k8a, k8a)
        self.assertEqual(p0, 0.0)

        # Relative major/minor
        p_rel, _ = transition_score(k8a, k8b)
        self.assertLessEqual(p_rel, 0.5)

        # Harmonic adjacent step
        p_step, _ = transition_score(k8a, k9a)
        self.assertEqual(p_step, 0.5)

        # Opposite clash
        p_clash, _ = transition_score(k8a, k2a)
        self.assertGreaterEqual(p_clash, 8.0)


class TestAudioKeyEngine(unittest.TestCase):
    def test_chroma_and_key_estimation_synthetic_c_major(self):
        # Generate synthetic C major chord (C4=261.63Hz, E4=329.63Hz, G4=392.00Hz)
        sr = 22050
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        c4 = np.sin(2 * np.pi * 261.63 * t)
        e4 = np.sin(2 * np.pi * 329.63 * t)
        g4 = np.sin(2 * np.pi * 392.00 * t)
        chord = (c4 + e4 + g4) / 3.0

        chroma = compute_chroma_from_pcm(chord, sr)
        self.assertEqual(len(chroma), 12)
        # C, E, G are pitch classes 0, 4, 7. They should have substantial energy
        self.assertGreater(chroma[0] + chroma[4] + chroma[7], 0.4)

        key, conf = estimate_key_from_chroma(chroma)
        # Should detect C Major (8B) or closely related (e.g. A minor 8A / E minor 9A)
        self.assertIn(key.camelot, ["8B", "8A", "9A"])
        self.assertGreater(conf, 0.5)


class TestHarmonicSorter(unittest.TestCase):
    def test_sorting_and_outlier_detection(self):
        # Create a playlist with smooth flow except one massive outlier
        songs = [
            Song(id="1", title="Track 1", artist="Artist A", extra={"comment": "8A"}),
            Song(id="2", title="Track Outlier", artist="Artist Clasher", extra={"comment": "2B"}), # Outlier
            Song(id="3", title="Track 2", artist="Artist B", extra={"comment": "9A"}),
            Song(id="4", title="Track 3", artist="Artist C", extra={"comment": "10A"}),
            Song(id="5", title="Track 4", artist="Artist D", extra={"comment": "10B"}),
        ]
        resolver = KeyResolver()
        for s in songs:
            resolver.resolve(s)

        sorter = HarmonicPlaylistSorter(energy_flow_preference="gradual_build")
        result = sorter.sort_and_analyze(songs)

        # Check that sorting improved or equaled penalty
        self.assertLessEqual(result.final_total_penalty, result.initial_total_penalty)
        # The outlier (Track Outlier 2B) should be flagged for removal
        removal_ids = [s.song.id for s in result.suggestions_to_remove]
        self.assertIn("2", removal_ids)

    def test_apple_music_mock_integration(self):
        bridge = AppleMusicBridge()
        playlists = bridge.get_all_playlists()
        self.assertGreater(len(playlists), 0)

        first_pl = playlists[0]["name"]
        tracks = bridge.get_playlist_tracks(first_pl)
        self.assertGreater(len(tracks), 0)

        # Test creating sorted playlist
        created_name = bridge.create_sorted_playlist(first_pl, tracks, suffix="sorted")
        self.assertEqual(created_name, f"{first_pl} sorted")


if __name__ == "__main__":
    unittest.main()
