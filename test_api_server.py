import unittest
import json
import urllib.request
import threading
import time
from http.server import HTTPServer

from camelot_music_sorter.server import CamelotServerHandler
from camelot_music_sorter.apple_music import AppleMusicBridge
from camelot_music_sorter.song_model import Song, KeyResolver
from camelot_music_sorter.sorter import HarmonicPlaylistSorter


class TestServerAndApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 8799
        cls.server = HTTPServer(('127.0.0.1', cls.port), CamelotServerHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_get_index_html(self):
        url = f"http://127.0.0.1:{self.port}/"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
            self.assertIn("Camelot DJ", body)
            self.assertIn("Apple Music", body)

    def test_get_playlists_api(self):
        url = f"http://127.0.0.1:{self.port}/api/playlists"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("playlists", data)
            self.assertIn("is_macos", data)
            self.assertGreater(len(data["playlists"]), 0)

    def test_post_sort_api(self):
        url = f"http://127.0.0.1:{self.port}/api/sort"
        payload = {
            "playlist": "Friday Night House",
            "strategy": "gradual_build",
            "exclude_ids": []
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["playlist_name"], "Friday Night House")
            self.assertIn("summary", data)
            self.assertIn("sorted_songs", data)
            self.assertIn("transitions", data)
            self.assertIn("suggestions", data)
            self.assertGreater(len(data["sorted_songs"]), 0)

    def test_post_export_api(self):
        url = f"http://127.0.0.1:{self.port}/api/export"
        payload = {
            "original_name": "Friday Night House",
            "sorted_track_ids": ["trk_1", "trk_2", "trk_3"]
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["created_playlist"], "Friday Night House sorted")
            self.assertEqual(data["track_count"], 3)


if __name__ == "__main__":
    unittest.main()
