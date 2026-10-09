"""
Local HTTP server: REST API plus the single-page web UI.

Only listens on 127.0.0.1. Mutating requests must be JSON with a localhost
Host header, which stops other websites from driving Music.app through the
browser (cross-site requests can't send JSON without a CORS preflight, and
the server never grants one).
"""

from __future__ import annotations
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

from .apple_music import AppleMusicBridge, MusicAppError
from .audio_engine import ffmpeg_available
from .rekordbox import RekordboxError, RekordboxLibrary, default_library_path, music_updates
from .song_model import KeyResolver, Song
from .sorter import HarmonicPlaylistSorter, SortResult
from .web_ui import WEB_UI_HTML

ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
MAX_BODY_BYTES = 200 * 1024 * 1024  # a rekordbox XML export of a large collection can be tens of MB


class AppState:
    def __init__(self, bridge: Optional[AppleMusicBridge] = None, resolver: Optional[KeyResolver] = None,
                 rekordbox_path: Optional[str] = "default"):
        self.bridge = bridge or AppleMusicBridge()
        self.resolver = resolver or KeyResolver()
        self.music_lock = threading.Lock()
        self.progress_lock = threading.Lock()
        self.progress: Dict[str, Any] = {"active": False, "done": 0, "total": 0, "current": ""}
        self.tracks: Dict[str, List[Song]] = {}
        self.rekordbox_path = default_library_path() if rekordbox_path == "default" else rekordbox_path
        if self.rekordbox_path and self.resolver.rekordbox is None:
            self.resolver.rekordbox = RekordboxLibrary.load(self.rekordbox_path)

    def rekordbox_status(self) -> Dict[str, Any]:
        lib = self.resolver.rekordbox
        return lib.summary() if lib else {"loaded": False}

    def set_rekordbox(self, lib: Optional[RekordboxLibrary]) -> None:
        self.resolver.rekordbox = lib
        self.tracks.clear()  # songs are re-resolved with the new analysis on next open
        if not self.rekordbox_path:
            return
        try:
            if lib:
                lib.save(self.rekordbox_path)
            elif os.path.exists(self.rekordbox_path):
                os.remove(self.rekordbox_path)
        except OSError:
            pass

    def set_progress(self, **kw: Any) -> None:
        with self.progress_lock:
            self.progress.update(kw)

    def load_tracks(self, playlist_id: str, refresh: bool) -> List[Song]:
        if not refresh and playlist_id in self.tracks:
            return self.tracks[playlist_id]
        self.set_progress(active=True, done=0, total=0, current="Reading playlist from Music…")
        with self.music_lock:
            songs = self.bridge.get_playlist_tracks(playlist_id)
        self.set_progress(total=len(songs), current="Calculating keys…")

        def on_progress(done: int, total: int, song: Song) -> None:
            self.set_progress(done=done, total=total, current=f"{song.artist} – {song.title}")

        self.resolver.resolve_many(songs, on_progress)
        self.tracks[playlist_id] = songs
        return songs


def _parse_manual(raw: Any) -> Dict[str, int]:
    """Accept manual pins as [{"id", "position"}] or {"id": position}."""
    items = raw.items() if isinstance(raw, dict) else (
        (m.get("id"), m.get("position")) for m in raw if isinstance(m, dict)) if isinstance(raw, list) else ()
    manual = {}
    for sid, pos in items:
        try:
            manual[str(sid)] = int(pos)
        except (TypeError, ValueError):
            continue
    return manual


def serialize_result(playlist: Dict[str, Any], result: SortResult, excluded: List[Song],
                     manual_ids: Optional[set] = None) -> Dict[str, Any]:
    manual_ids = manual_ids or set()
    return {
        "playlist": playlist,
        "new_playlist_name": f"{playlist['name']} sorted",
        "summary": result.summary(),
        "sorted_songs": [{**s.to_dict(), "manual": s.id in manual_ids} for s in result.sorted_songs],
        "original_order_ids": [s.id for s in result.original_songs],
        "transitions": [
            {"penalty": round(t.penalty, 2), "description": t.description,
             "is_smooth": t.is_smooth, "is_unknown": t.is_unknown,
             "compatibility_score": t.compatibility_score,
             "energy_delta": t.energy_delta}
            for t in result.transitions
        ],
        "suggestions": [
            {"song": sug.song.to_dict(), "reason": sug.reason,
             "isolated_clash_score": sug.isolated_clash_score,
             "alternative_suggestion": sug.alternative_suggestion}
            for sug in result.suggestions_to_remove
        ],
        "excluded_songs": [s.to_dict() for s in excluded],
    }


class CamelotServerHandler(BaseHTTPRequestHandler):
    state: AppState = None  # assigned by make_server

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in ALLOWED_HOSTS

    def do_GET(self):
        if not self._host_ok():
            return self._send_json({"error": "Forbidden host"}, 403)
        path = self.path.split("?", 1)[0]
        try:
            if path in ("/", "/index.html"):
                body = WEB_UI_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/status":
                self._send_json({"mode": self.state.bridge.mode, "ffmpeg": ffmpeg_available(),
                                 "rekordbox": self.state.rekordbox_status()})
            elif path == "/api/playlists":
                with self.state.music_lock:
                    playlists = self.state.bridge.get_all_playlists()
                self._send_json({"mode": self.state.bridge.mode, "playlists": playlists})
            elif path == "/api/progress":
                with self.state.progress_lock:
                    self._send_json(dict(self.state.progress))
            else:
                self._send_json({"error": "Not found"}, 404)
        except MusicAppError as e:
            self._send_json({"error": str(e)}, 502)
        except Exception as e:  # noqa: BLE001 - surface unexpected failures to the UI
            self._send_json({"error": f"Unexpected error: {e}"}, 500)

    def do_POST(self):
        if not self._host_ok():
            return self._send_json({"error": "Forbidden host"}, 403)
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._send_json({"error": "Content-Type must be application/json"}, 415)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY_BYTES:
                return self._send_json({"error": "Request is too large."}, 413)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return self._send_json({"error": "Invalid JSON body"}, 400)

        try:
            if self.path == "/api/analyze":
                self._analyze(payload)
            elif self.path == "/api/removal_plan":
                self._removal_plan(payload)
            elif self.path == "/api/export":
                self._export(payload)
            elif self.path == "/api/rekordbox/import":
                self._rekordbox_import(payload)
            elif self.path == "/api/rekordbox/clear":
                self.state.set_rekordbox(None)
                self._send_json(self.state.rekordbox_status())
            elif self.path == "/api/rekordbox/write":
                self._rekordbox_write(payload)
            else:
                self._send_json({"error": "Not found"}, 404)
        except MusicAppError as e:
            self._send_json({"error": str(e)}, 502)
        except Exception as e:  # noqa: BLE001
            self._send_json({"error": f"Unexpected error: {e}"}, 500)
        finally:
            self.state.set_progress(active=False)

    def _playlist(self, playlist_id: str) -> Dict[str, Any]:
        with self.state.music_lock:
            playlist = self.state.bridge.find_playlist(playlist_id)
        if not playlist:
            raise MusicAppError("Playlist not found in Music. Refresh the playlist list.")
        return playlist

    def _analyze(self, payload: Dict[str, Any]) -> None:
        playlist_id = payload.get("playlist_id") or ""
        if not playlist_id:
            return self._send_json({"error": "Choose a playlist first."}, 400)
        playlist = self._playlist(playlist_id)
        songs = self.state.load_tracks(playlist["id"], bool(payload.get("refresh")))
        if not songs:
            return self._send_json({"error": f"“{playlist['name']}” has no tracks."}, 400)

        exclude = set(payload.get("exclude_ids") or [])
        kept = [s for s in songs if s.id not in exclude]
        excluded = [s for s in songs if s.id in exclude]
        by_id = {s.id: s for s in kept}
        manual = _parse_manual(payload.get("manual"))
        if payload.get("start_id"):
            manual.setdefault(payload["start_id"], 0)
        manual = {i: p for i, p in manual.items() if i in by_id}
        sorter = HarmonicPlaylistSorter(energy_flow_preference=payload.get("strategy") or "gradual_build")

        order = payload.get("order")
        if isinstance(order, list):
            # Insert mode: keep the current order and slot songs in at their cheapest position.
            insert_ids = set(payload.get("insert_ids") or [])
            base = [by_id[i] for i in dict.fromkeys(order) if i in by_id and i not in insert_ids]
            placed = {s.id for s in base}
            result = sorter.analyze_order(kept, sorter.insert(base, [s for s in kept if s.id not in placed]))
        else:
            result = sorter.arrange(kept, keep_ids=payload.get("keep_ids") or (), manual=manual)
        self._send_json(serialize_result(playlist, result, excluded, set(manual)))

    def _removal_plan(self, payload: Dict[str, Any]) -> None:
        playlist = self._playlist(payload.get("playlist_id") or "")
        songs = self.state.tracks.get(playlist["id"])
        if songs is None:
            return self._send_json({"error": "Analyze the playlist first."}, 400)
        exclude = set(payload.get("exclude_ids") or [])
        by_id = {s.id: s for s in songs if s.id not in exclude}
        order = [by_id[i] for i in dict.fromkeys(payload.get("order") or []) if i in by_id]
        placed = {s.id for s in order}
        order += [s for s in songs if s.id in by_id and s.id not in placed]
        try:
            budget = max(0, min(50, int(payload.get("max_remove", 3))))
        except (TypeError, ValueError):
            return self._send_json({"error": "max_remove must be a number."}, 400)

        sorter = HarmonicPlaylistSorter(energy_flow_preference=payload.get("strategy") or "gradual_build")
        manual_ids = [i for i in _parse_manual(payload.get("manual")) if i in by_id]
        plan = sorter.plan_removals(order, budget, manual_ids)
        self._send_json({
            "max_remove": plan.budget,
            "headline": plan.headline(),
            "hint": plan.hint,
            "hint_budget": plan.hint_budget,
            "stopped_early": plan.stopped_early,
            "baseline": plan.baseline.to_dict(),
            "after": plan.after.to_dict(),
            "steps": [{"song": st.song.to_dict(), "reason": st.reason, "gain": round(st.gain, 2),
                       "metrics": st.metrics.to_dict()} for st in plan.steps],
            "final_order_ids": [s.id for s in plan.final_order],
        })

    def _export(self, payload: Dict[str, Any]) -> None:
        playlist = self._playlist(payload.get("playlist_id") or "")
        songs = self.state.tracks.get(playlist["id"])
        if songs is None:
            return self._send_json({"error": "Analyze the playlist before creating the sorted copy."}, 400)
        by_id = {s.id: s for s in songs}
        ordered = [by_id[i] for i in payload.get("ordered_ids") or [] if i in by_id]
        if not ordered:
            return self._send_json({"error": "No tracks to add."}, 400)
        self.state.set_progress(active=True, done=0, total=len(ordered), current="Creating playlist in Music…")
        with self.state.music_lock:
            created = self.state.bridge.create_sorted_playlist(playlist["id"], playlist["name"], ordered)
        self._send_json({"status": "success", **created})

    def _rekordbox_import(self, payload: Dict[str, Any]) -> None:
        xml = payload.get("xml")
        if not isinstance(xml, str) or not xml.strip():
            return self._send_json({"error": "Choose the XML file exported from rekordbox."}, 400)
        try:
            lib = RekordboxLibrary.from_xml(xml.encode("utf-8"), os.path.basename(str(payload.get("filename") or "")))
        except RekordboxError as e:
            return self._send_json({"error": str(e)}, 400)
        self.state.set_rekordbox(lib)
        self._send_json(self.state.rekordbox_status())

    def _rekordbox_write(self, payload: Dict[str, Any]) -> None:
        playlist = self._playlist(payload.get("playlist_id") or "")
        songs = self.state.tracks.get(playlist["id"])
        if songs is None:
            return self._send_json({"error": "Analyze the playlist first."}, 400)
        updates = music_updates(songs)
        if not updates:
            return self._send_json({"written": 0, "keys": 0, "bpms": 0})
        self.state.set_progress(active=True, done=0, total=len(updates), current="Saving keys to Music…")
        with self.state.music_lock:
            written = self.state.bridge.write_track_metadata(updates)
        self.state.tracks.pop(playlist["id"], None)
        self._send_json({"written": written, "keys": sum(1 for _, c, _ in updates if c),
                         "bpms": sum(1 for _, _, b in updates if b)})

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def make_server(port: int = 8765, state: Optional[AppState] = None) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (CamelotServerHandler,), {"state": state or AppState()})
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def run_web_server(port: int = 8765, demo: Optional[bool] = None, open_browser: bool = True) -> None:
    state = AppState(bridge=AppleMusicBridge(demo=demo))
    try:
        httpd = make_server(port, state)
    except OSError:
        print(f"Port {port} is already in use. Is the app already running? Try --port {port + 1}.")
        return
    url = f"http://localhost:{port}"
    print(f"Camelot DJ Sorter running at {url}  (Ctrl+C to quit)")
    if state.bridge.demo:
        print("Demo mode: using a built-in sample library instead of Music.app.")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server…")
    finally:
        httpd.server_close()
