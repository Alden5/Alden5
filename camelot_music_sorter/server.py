"""
HTTP server providing REST API and serving Web UI for Camelot DJ Sorter.
"""

from __future__ import annotations
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List

from .apple_music import AppleMusicBridge
from .song_model import KeyResolver, Song
from .sorter import HarmonicPlaylistSorter
from .web_ui import WEB_UI_HTML


class CamelotServerHandler(BaseHTTPRequestHandler):
    bridge = AppleMusicBridge()
    resolver = KeyResolver(enable_audio_analysis=True)
    sorter = HarmonicPlaylistSorter()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(WEB_UI_HTML.encode("utf-8"))
            return

        if self.path == "/api/playlists":
            playlists = self.bridge.get_all_playlists()
            data = {
                "is_macos": self.bridge.is_macos(),
                "playlists": playlists
            }
            self._send_json(data)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if self.path == "/api/sort":
            playlist_name = payload.get("playlist")
            strategy = payload.get("strategy", "gradual_build")
            exclude_ids = set(payload.get("exclude_ids", []))

            # Fetch tracks
            tracks = self.bridge.get_playlist_tracks(playlist_name)
            
            # Filter excluded if requested
            filtered_tracks = [t for t in tracks if t.id not in exclude_ids]

            # Resolve keys for all songs
            for t in filtered_tracks:
                self.resolver.resolve(t)

            # Sort
            sorter = HarmonicPlaylistSorter(energy_flow_preference=strategy)
            sort_result = sorter.sort_and_analyze(filtered_tracks)

            response_data = {
                "playlist_name": playlist_name,
                "summary": sort_result.summary(),
                "sorted_songs": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "artist": s.artist,
                        "album": s.album,
                        "bpm": s.bpm,
                        "key_source": s.key_source,
                        "confidence": s.confidence,
                        "resolved_key": {
                            "number": s.resolved_key.number,
                            "letter": s.resolved_key.letter,
                            "camelot": s.resolved_key.camelot,
                            "standard_name": s.resolved_key.standard_name
                        } if s.resolved_key else None
                    }
                    for s in sort_result.sorted_songs
                ],
                "transitions": [
                    {
                        "from_title": t.from_song.title,
                        "to_title": t.to_song.title,
                        "penalty": round(t.penalty, 2),
                        "description": t.description,
                        "is_smooth": t.is_smooth
                    }
                    for t in sort_result.transitions
                ],
                "suggestions": [
                    {
                        "song": {
                            "id": sug.song.id,
                            "title": sug.song.title,
                            "artist": sug.song.artist,
                            "resolved_key": {
                                "camelot": sug.song.resolved_key.camelot,
                                "number": sug.song.resolved_key.number,
                                "standard_name": sug.song.resolved_key.standard_name
                            } if sug.song.resolved_key else None
                        },
                        "reason": sug.reason,
                        "isolated_clash_score": sug.isolated_clash_score,
                        "alternative_suggestion": sug.alternative_suggestion
                    }
                    for sug in sort_result.suggestions_to_remove
                ]
            }

            self._send_json(response_data)
            return

        if self.path == "/api/export":
            original_name = payload.get("original_name")
            sorted_track_ids = payload.get("sorted_track_ids", [])

            # Reconstruct songs list in sorted order
            all_tracks = self.bridge.get_playlist_tracks(original_name)
            track_map = {t.id: t for t in all_tracks}
            sorted_songs = [track_map[tid] for tid in sorted_track_ids if tid in track_map]

            created_name = self.bridge.create_sorted_playlist(original_name, sorted_songs, suffix="sorted")
            self._send_json({
                "status": "success",
                "created_playlist": created_name,
                "track_count": len(sorted_songs)
            })
            return

        self.send_error(404, "Not Found")

    def _send_json(self, data: Dict[str, Any]):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def log_message(self, format, *args):
        # Clean logging
        pass


def run_web_server(port: int = 8765):
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, CamelotServerHandler)
    print(f"🎛️  Camelot DJ Apple Music Sorter running at: http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()
