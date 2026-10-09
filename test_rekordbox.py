import http.client
import json
import os
import tempfile
import threading
import unittest

from camelot_music_sorter.apple_music import AppleMusicBridge
from camelot_music_sorter.rekordbox import (
    RekordboxError, RekordboxLibrary, music_updates, parse_rekordbox_xml, title_keys,
)
from camelot_music_sorter.server import AppState, make_server
from camelot_music_sorter.song_model import KeyResolver, Song

XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="7.1.0" Company="AlphaTheta"/>
  <COLLECTION Entries="6">
    <TRACK TrackID="1" Name="Lose Control" Artist="MEDUZA, Becky Hill, Goodboys" TotalTime="171"
           AverageBpm="124.00" Tonality="Abm" Comments="" Location=""/>
    <TRACK TrackID="2" Name="Show Me Love (Remastered 2011)" Artist="Robin S." TotalTime="250"
           AverageBpm="120.00" Tonality="5A" Comments="Energy 6"/>
    <TRACK TrackID="3" Name="Bangarang (feat. Sirah)" Artist="Skrillex" TotalTime="215"
           AverageBpm="110.00" Tonality="" Comments="">
      <TEMPO Inizio="0.050" Bpm="110.00" Metro="4/4" Battito="1"/>
    </TRACK>
    <TRACK TrackID="4" Name="Strobe" Artist="deadmau5" TotalTime="637" AverageBpm="128.00" Tonality="Bbm"/>
    <TRACK TrackID="5" Name="Strobe" Artist="deadmau5" TotalTime="214" AverageBpm="128.00" Tonality="4A"/>
    <TRACK TrackID="6" Name="Opus" Artist="Eric Prydz" TotalTime="543" AverageBpm="126.00" Tonality="8A"
           Location="file://localhost/Users/dj/Music/Eric%20Prydz%20-%20Opus.m4a"/>
  </COLLECTION>
  <PLAYLISTS><NODE Type="0" Name="ROOT" Count="0"/></PLAYLISTS>
</DJ_PLAYLISTS>
"""


class TestParsing(unittest.TestCase):
    def test_reads_tracks_keys_bpm_and_locations(self):
        tracks = parse_rekordbox_xml(XML)
        self.assertEqual(len(tracks), 6)
        lose = tracks[0]
        self.assertEqual(lose.key.camelot, "1A")
        self.assertEqual(lose.bpm, 124.0)
        self.assertIsNone(lose.location)
        self.assertEqual(tracks[2].bpm, 110.0)
        self.assertIsNone(tracks[2].key)
        self.assertEqual(tracks[5].location, "/Users/dj/Music/Eric Prydz - Opus.m4a")

    def test_rejects_non_rekordbox_and_entity_xml(self):
        with self.assertRaises(RekordboxError):
            parse_rekordbox_xml(b"<plist><dict/></plist>")
        with self.assertRaises(RekordboxError):
            parse_rekordbox_xml(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><DJ_PLAYLISTS/>')
        with self.assertRaises(RekordboxError):
            parse_rekordbox_xml(b"not xml")

    def test_title_variants(self):
        self.assertIn("show me love", title_keys("Show Me Love (Remastered 2011)"))
        self.assertIn("bangarang", title_keys("Bangarang (feat. Sirah)"))
        self.assertIn("one more time", title_keys("One More Time - Radio Edit"))


class TestMatching(unittest.TestCase):
    def setUp(self):
        self.lib = RekordboxLibrary.from_xml(XML, "rekordbox.xml")

    def test_matches_by_title_and_any_shared_artist(self):
        self.assertEqual(self.lib.match("Lose Control", "Meduza, Becky Hill & Goodboys").key.camelot, "1A")
        self.assertEqual(self.lib.match("Show Me Love", "Robin S").tonality, "5A")
        self.assertIsNone(self.lib.match("Lose Control", "Someone Else"))

    def test_duration_picks_the_right_version_and_rejects_far_ones(self):
        self.assertEqual(self.lib.match("Strobe", "deadmau5", 213).tonality, "4A")
        self.assertEqual(self.lib.match("Strobe", "deadmau5", 640).tonality, "Bbm")
        self.assertIsNone(self.lib.match("Lose Control", "Meduza", 300))

    def test_location_wins(self):
        hit = self.lib.match("Something else", "Nobody", location="/Users/dj/Music/Eric Prydz - Opus.m4a")
        self.assertEqual(hit.title, "Opus")

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "rb", "rekordbox.json")
            self.lib.save(path)
            loaded = RekordboxLibrary.load(path)
        self.assertEqual(len(loaded.tracks), 6)
        self.assertEqual(loaded.source_name, "rekordbox.xml")
        self.assertEqual(loaded.match("Strobe", "deadmau5", 214).tonality, "4A")


class TestResolverWithRekordbox(unittest.TestCase):
    def setUp(self):
        self.resolver = KeyResolver(cache_path=None, enable_audio_analysis=False)
        self.resolver.rekordbox = RekordboxLibrary.from_xml(XML)

    def test_streaming_song_gets_key_bpm_and_energy_from_rekordbox(self):
        s = self.resolver.resolve(Song(id="1", title="Show Me Love", artist="Robin S", duration_seconds=251))
        self.assertEqual((s.resolved_key.camelot, s.key_source), ("5A", "rekordbox"))
        self.assertEqual((s.bpm, s.bpm_source), (120.0, "rekordbox"))
        self.assertEqual((s.energy, s.energy_source), (6.0, "rekordbox"))
        self.assertTrue(s.to_dict()["rekordbox_matched"])

    def test_comments_still_win_and_music_bpm_is_kept(self):
        s = self.resolver.resolve(Song(id="1", title="Lose Control", artist="Meduza", bpm=125,
                                       extra={"comment": "9A"}))
        self.assertEqual((s.resolved_key.camelot, s.key_source), ("9A", "metadata"))
        self.assertEqual((s.bpm, s.bpm_source), (125, "music"))
        self.assertTrue(s.rekordbox_matched)

    def test_matched_but_unanalyzed_song_says_so(self):
        s = self.resolver.resolve(Song(id="1", title="Bangarang", artist="Skrillex"))
        self.assertIsNone(s.resolved_key)
        self.assertEqual(s.bpm, 110.0)
        self.assertIn("hasn't analyzed", s.key_note)

    def test_music_updates_prefix_key_and_fill_missing_bpm(self):
        songs = [self.resolver.resolve(Song(id="a", title="Show Me Love", artist="Robin S", extra={"comment": "classic 4"})),
                 self.resolver.resolve(Song(id="b", title="Strobe", artist="deadmau5", duration_seconds=214, bpm=128)),
                 self.resolver.resolve(Song(id="c", title="Lose Control", artist="Meduza", extra={"comment": "9A"}))]
        self.assertEqual(music_updates(songs), [("a", "5A | classic 4", 120), ("b", "4A", None), ("c", "", 124)])
        # The written comment reads back as the same key, and the old text isn't mistaken for an energy rating.
        back = KeyResolver(cache_path=None, enable_audio_analysis=False).resolve(
            Song(id="a", title="x", artist="y", bpm=120, extra={"comment": "5A | classic 4"}))
        self.assertEqual((back.resolved_key.camelot, back.key_source, back.energy_source), ("5A", "metadata", "estimated"))


class TestRekordboxApi(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "rekordbox.json")
        self.bridge = AppleMusicBridge(demo=True)
        state = AppState(bridge=self.bridge, resolver=KeyResolver(cache_path=None), rekordbox_path=self.path)
        self.server = make_server(0, state)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.friday = next(p for p in self.bridge.get_all_playlists() if p["name"] == "Friday Night House")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.dir.cleanup()

    def post(self, path, body):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", path, body=json.dumps(body),
                     headers={"Host": f"localhost:{self.port}", "Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        conn.close()
        return resp.status, data

    def lose_control(self, data):
        return next(s for s in data["sorted_songs"] if s["title"] == "Lose Control")

    def test_import_matches_songs_persists_and_writes_back_to_music(self):
        _, before = self.post("/api/analyze", {"playlist_id": self.friday["id"]})
        self.assertIsNone(self.lose_control(before)["resolved_key"])

        status, rb = self.post("/api/rekordbox/import", {"xml": XML.decode(), "filename": "/tmp/rekordbox.xml"})
        self.assertEqual(status, 200)
        self.assertEqual((rb["track_count"], rb["keyed_count"], rb["source_name"]), (6, 5, "rekordbox.xml"))
        self.assertTrue(os.path.exists(self.path))

        _, after = self.post("/api/analyze", {"playlist_id": self.friday["id"]})
        song = self.lose_control(after)
        self.assertEqual((song["resolved_key"]["camelot"], song["key_source"]), ("1A", "rekordbox"))
        self.assertEqual(after["summary"]["unknown_key_count"], 0)

        status, w = self.post("/api/rekordbox/write", {"playlist_id": self.friday["id"]})
        self.assertEqual(status, 200)
        self.assertEqual((w["written"], w["keys"]), (1, 1))
        tracks = self.bridge.get_playlist_tracks(self.friday["id"])
        self.assertEqual(next(t for t in tracks if t.title == "Lose Control").extra["comment"], "1A")

        _, again = self.post("/api/analyze", {"playlist_id": self.friday["id"]})
        self.assertEqual(self.lose_control(again)["key_source"], "metadata")

        status, cleared = self.post("/api/rekordbox/clear", {})
        self.assertEqual(cleared, {"loaded": False})
        self.assertFalse(os.path.exists(self.path))

    def test_import_errors(self):
        status, data = self.post("/api/rekordbox/import", {"xml": "<plist/>"})
        self.assertEqual(status, 400)
        self.assertIn("rekordbox", data["error"])
        status, _ = self.post("/api/rekordbox/import", {})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
