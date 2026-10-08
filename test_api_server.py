import http.client
import json
import threading
import unittest

from camelot_music_sorter.apple_music import AppleMusicBridge
from camelot_music_sorter.server import AppState, make_server
from camelot_music_sorter.song_model import KeyResolver


class TestServerAndApi(unittest.TestCase):
    def setUp(self):
        state = AppState(bridge=AppleMusicBridge(demo=True), resolver=KeyResolver(cache_path=None))
        self.server = make_server(0, state)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.friday = next(p for p in state.bridge.get_all_playlists() if p["name"] == "Friday Night House")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        hdrs = {"Host": f"localhost:{self.port}"}
        if body is not None:
            hdrs["Content-Type"] = "application/json"
        hdrs.update(headers or {})
        conn.request(method, path, body=None if body is None else json.dumps(body), headers=hdrs)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        conn.close()
        return resp.status, (json.loads(raw) if resp.getheader("Content-Type", "").startswith("application/json") else raw)

    def test_index_and_status(self):
        status, html = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("Camelot DJ Sorter", html)
        status, data = self.request("GET", "/api/status")
        self.assertEqual(data["mode"], "demo")

    def test_playlists(self):
        status, data = self.request("GET", "/api/playlists")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["playlists"]), 3)
        self.assertEqual(self.friday["track_count"], 9)

    def test_analyze_exclude_and_export(self):
        status, data = self.request("POST", "/api/analyze", {"playlist_id": self.friday["id"]})
        self.assertEqual(status, 200)
        self.assertEqual(data["new_playlist_name"], "Friday Night House sorted")
        self.assertEqual(len(data["sorted_songs"]), 9)
        self.assertIsNone(data["sorted_songs"][-1]["resolved_key"])
        self.assertTrue(data["suggestions"])

        drop = [s["song"]["id"] for s in data["suggestions"]]
        start = data["sorted_songs"][3]["id"]
        status, data = self.request("POST", "/api/analyze", {
            "playlist_id": self.friday["id"], "exclude_ids": drop, "start_id": start, "strategy": "balanced"})
        self.assertEqual(status, 200)
        self.assertEqual(len(data["sorted_songs"]), 9 - len(drop))
        self.assertEqual(len(data["excluded_songs"]), len(drop))
        self.assertEqual(data["sorted_songs"][0]["id"], start)

        ids = [s["id"] for s in data["sorted_songs"]]
        status, created = self.request("POST", "/api/export", {"playlist_id": self.friday["id"], "ordered_ids": ids})
        self.assertEqual(status, 200)
        self.assertEqual(created["name"], "Friday Night House sorted")
        self.assertEqual(created["added"], len(ids))

    def test_manual_placement_keeps_songs_above_and_marks_song_manual(self):
        _, data = self.request("POST", "/api/analyze", {"playlist_id": self.friday["id"]})
        order = [s["id"] for s in data["sorted_songs"]]
        moved = order[6]
        new = [i for i in order if i != moved]
        new.insert(2, moved)
        status, data = self.request("POST", "/api/analyze", {
            "playlist_id": self.friday["id"], "keep_ids": new[:2], "manual": [{"id": moved, "position": 2}]})
        self.assertEqual(status, 200)
        out = data["sorted_songs"]
        self.assertEqual([s["id"] for s in out[:3]], new[:3])
        self.assertEqual([s["id"] for s in out if s["manual"]], [moved])
        self.assertEqual(sorted(s["id"] for s in out), sorted(order))

    def test_insert_mode_restores_song_without_reordering_others(self):
        _, data = self.request("POST", "/api/analyze", {"playlist_id": self.friday["id"]})
        order = [s["id"] for s in data["sorted_songs"]]
        back = order[4]
        rest = [i for i in order if i != back]
        status, data = self.request("POST", "/api/analyze", {
            "playlist_id": self.friday["id"], "order": rest, "insert_ids": [back],
            "manual": [{"id": rest[0], "position": 0}]})
        self.assertEqual(status, 200)
        out = [s["id"] for s in data["sorted_songs"]]
        self.assertEqual([i for i in out if i != back], rest)
        self.assertIn(back, out)
        self.assertTrue(data["sorted_songs"][out.index(rest[0])]["manual"])

    def test_export_requires_analysis(self):
        status, data = self.request("POST", "/api/export", {"playlist_id": self.friday["id"], "ordered_ids": ["x"]})
        self.assertEqual(status, 400)
        self.assertIn("Analyze", data["error"])

    def test_unknown_playlist_returns_error_message(self):
        status, data = self.request("POST", "/api/analyze", {"playlist_id": "nope"})
        self.assertEqual(status, 502)
        self.assertIn("not found", data["error"])

    def test_rejects_cross_site_and_foreign_host_requests(self):
        status, _ = self.request("POST", "/api/export", None, {"Content-Type": "text/plain", "Content-Length": "0"})
        self.assertEqual(status, 415)
        status, _ = self.request("GET", "/api/playlists", None, {"Host": "evil.example.com"})
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
