"""
Apple Music (Music.app) integration for macOS via AppleScript.

Scripts are fed to `osascript -` on stdin and receive user data (playlist
names, track IDs) through `argv`, so no value is ever interpolated into
script source.

On other platforms, or with demo=True, an in-memory demo library is used.
"""

from __future__ import annotations
import subprocess
import sys
from typing import Any, Dict, List, Optional

from .song_model import Song

FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"
APP_MARKER = "Created by Camelot DJ Sorter"


class MusicAppError(RuntimeError):
    pass


_HELPERS = """
on fmt(v)
    if v is missing value then return ""
    try
        return v as text
    on error
        return ""
    end try
end fmt
"""

LIST_PLAYLISTS_SCRIPT = _HELPERS + """
on run argv
    set sep to character id 31
    set out to {}
    tell application "Music"
        repeat with pRef in (every user playlist)
            set p to contents of pRef
            try
                if special kind of p is none then
                    set end of out to my fmt(name of p) & sep & my fmt(persistent ID of p) & sep & my fmt(count of tracks of p) & sep & my fmt(smart of p)
                end if
            end try
        end repeat
    end tell
    set AppleScript's text item delimiters to (character id 30)
    return out as text
end run
"""

GET_TRACKS_SCRIPT = _HELPERS + """
on run argv
    set pid to item 1 of argv
    set sep to character id 31
    set out to {}
    tell application "Music"
        with timeout of 900 seconds
            set pl to (first user playlist whose persistent ID is pid)
            set trks to every track of pl
            repeat with tRef in trks
                set t to contents of tRef
                set loc to ""
                try
                    if class of t is file track then
                        set l to location of t
                        if l is not missing value then set loc to POSIX path of l
                    end if
                end try
                set end of out to my fmt(persistent ID of t) & sep & my fmt(name of t) & sep & my fmt(artist of t) & sep & my fmt(album of t) & sep & my fmt(duration of t) & sep & my fmt(bpm of t) & sep & my fmt(comment of t) & sep & my fmt(grouping of t) & sep & my fmt(genre of t) & sep & loc
            end repeat
        end timeout
    end tell
    set AppleScript's text item delimiters to (character id 30)
    return out as text
end run
"""

CREATE_PLAYLIST_SCRIPT = _HELPERS + """
on run argv
    set srcId to item 1 of argv
    set baseName to item 2 of argv
    set marker to item 3 of argv
    if (count of argv) > 3 then
        set trackIds to items 4 thru -1 of argv
    else
        set trackIds to {}
    end if
    set sep to character id 31
    tell application "Music"
        with timeout of 900 seconds
            set src to (first user playlist whose persistent ID is srcId)
            set newName to baseName
            set replaced to false
            set n to 1
            repeat
                set clash to (every user playlist whose name is newName)
                if (count of clash) is 0 then exit repeat
                set ours to true
                repeat with pRef in clash
                    set d to ""
                    try
                        set d to my fmt(description of (contents of pRef))
                    end try
                    if d does not contain marker then set ours to false
                end repeat
                if ours then
                    repeat with pRef in clash
                        delete (contents of pRef)
                    end repeat
                    set replaced to true
                    exit repeat
                end if
                set n to n + 1
                set newName to baseName & " (" & n & ")"
            end repeat

            set newPl to make new user playlist with properties {name:newName}
            try
                set description of newPl to marker
            end try
            set added to 0
            repeat with tid in trackIds
                try
                    set t to (first track of src whose persistent ID is (tid as text))
                    duplicate t to newPl
                    set added to added + 1
                end try
            end repeat
            return newName & sep & (added as text) & sep & (replaced as text)
        end timeout
    end tell
end run
"""


def _to_float(value: str) -> float:
    try:
        return float(value.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return 0.0


def _split_records(raw: str) -> List[List[str]]:
    raw = raw.rstrip("\n")
    if not raw:
        return []
    return [rec.split(FIELD_SEP) for rec in raw.split(RECORD_SEP) if rec.strip()]


def _dedupe_ids(songs: List[Song]) -> List[Song]:
    seen: Dict[str, int] = {}
    for s in songs:
        count = seen.get(s.persistent_id, 0) + 1
        seen[s.persistent_id] = count
        if count > 1:
            s.id = f"{s.persistent_id}#{count}"
    return songs


class AppleMusicBridge:
    def __init__(self, demo: Optional[bool] = None):
        self.demo = (sys.platform != "darwin") if demo is None else demo
        self._demo_library = _build_demo_library() if self.demo else {}

    def is_macos(self) -> bool:
        return sys.platform == "darwin"

    @property
    def mode(self) -> str:
        return "demo" if self.demo else "music_app"

    def run_applescript(self, script: str, *args: str) -> str:
        try:
            proc = subprocess.run(["osascript", "-", *args], input=script, capture_output=True,
                                  text=True, encoding="utf-8", timeout=1000)
        except FileNotFoundError:
            raise MusicAppError("osascript not found; Apple Music control requires macOS.")
        except subprocess.TimeoutExpired:
            raise MusicAppError("Music.app did not respond in time.")
        if proc.returncode != 0:
            err = proc.stderr.strip()
            if "-1743" in err or "Not authorized" in err:
                raise MusicAppError(
                    "macOS blocked access to Music. Open System Settings → Privacy & Security → "
                    "Automation and allow your Terminal app to control Music, then try again.")
            if "-1728" in err or "Can’t get" in err or "Can't get" in err:
                raise MusicAppError("Playlist not found in Music. It may have been renamed or deleted; refresh the list.")
            raise MusicAppError(f"Music.app error: {err or 'unknown error'}")
        return proc.stdout.rstrip("\n")

    def get_all_playlists(self) -> List[Dict[str, Any]]:
        if self.demo:
            return [{"name": p["name"], "id": pid, "track_count": len(p["tracks"]), "smart": False}
                    for pid, p in self._demo_library.items()]

        playlists = []
        for parts in _split_records(self.run_applescript(LIST_PLAYLISTS_SCRIPT)):
            if len(parts) >= 3 and parts[1]:
                playlists.append({
                    "name": parts[0],
                    "id": parts[1],
                    "track_count": int(_to_float(parts[2])),
                    "smart": len(parts) > 3 and parts[3].strip().lower() == "true",
                })
        return playlists

    def find_playlist(self, name_or_id: str) -> Optional[Dict[str, Any]]:
        playlists = self.get_all_playlists()
        for p in playlists:
            if p["id"] == name_or_id:
                return p
        for p in playlists:
            if p["name"] == name_or_id:
                return p
        lowered = name_or_id.lower()
        return next((p for p in playlists if p["name"].lower() == lowered), None)

    def get_playlist_tracks(self, playlist_id: str) -> List[Song]:
        if self.demo:
            pl = self._demo_library.get(playlist_id) or next(
                (p for p in self._demo_library.values() if p["name"] == playlist_id), None)
            if pl is None:
                raise MusicAppError(f"Playlist not found: {playlist_id}")
            return _dedupe_ids([Song(**{**t, "extra": dict(t.get("extra", {}))}) for t in pl["tracks"]])

        songs = []
        for parts in _split_records(self.run_applescript(GET_TRACKS_SCRIPT, playlist_id)):
            if len(parts) < 10:
                continue
            pid, title, artist, album, dur, bpm, comment, grouping, genre, loc = parts[:10]
            songs.append(Song(
                id=pid, persistent_id=pid, title=title, artist=artist, album=album,
                duration_seconds=_to_float(dur), bpm=_to_float(bpm), genre=genre,
                location=loc or None, extra={"comment": comment, "grouping": grouping},
            ))
        return _dedupe_ids(songs)

    def create_sorted_playlist(self, source_playlist_id: str, source_name: str,
                               sorted_songs: List[Song], suffix: str = "sorted") -> Dict[str, Any]:
        """
        Create '<source_name> sorted' with tracks in the given order. A previous
        playlist of that name is replaced only if this app created it; otherwise
        ' (2)', ' (3)', ... is appended.
        """
        base_name = f"{source_name} {suffix}".strip()
        track_ids = [s.persistent_id for s in sorted_songs]

        if self.demo:
            return self._demo_create(base_name, sorted_songs)

        raw = self.run_applescript(CREATE_PLAYLIST_SCRIPT, source_playlist_id, base_name, APP_MARKER, *track_ids)
        parts = raw.split(FIELD_SEP)
        return {
            "name": parts[0] if parts and parts[0] else base_name,
            "added": int(_to_float(parts[1])) if len(parts) > 1 else len(track_ids),
            "requested": len(track_ids),
            "replaced": len(parts) > 2 and parts[2].strip().lower() == "true",
        }

    def _demo_create(self, base_name: str, songs: List[Song]) -> Dict[str, Any]:
        name, n, replaced = base_name, 1, False
        while True:
            clash = [pid for pid, p in self._demo_library.items() if p["name"] == name]
            if not clash:
                break
            if all(self._demo_library[pid].get("ours") for pid in clash):
                for pid in clash:
                    del self._demo_library[pid]
                replaced = True
                break
            n += 1
            name = f"{base_name} ({n})"
        pid = f"demo_sorted_{len(self._demo_library) + 1}_{abs(hash(name)) % 10000}"
        self._demo_library[pid] = {
            "name": name, "ours": True,
            "tracks": [{k: v for k, v in vars(s).items()
                        if k in ("id", "persistent_id", "title", "artist", "album", "bpm", "extra", "location")}
                       | {"id": s.persistent_id} for s in songs],
        }
        return {"name": name, "added": len(songs), "requested": len(songs), "replaced": replaced}


def _t(pid: str, title: str, artist: str, bpm: float, comment: str = "", album: str = "") -> Dict[str, Any]:
    return {"id": pid, "persistent_id": pid, "title": title, "artist": artist, "album": album,
            "bpm": bpm, "extra": {"comment": comment, "grouping": ""}}


def _build_demo_library() -> Dict[str, Dict[str, Any]]:
    return {
        "DEMO000000000001": {"name": "Friday Night House", "tracks": [
            _t("D1A0000000000001", "Deep Inside", "Hardrive", 124, "8A - Energy 5"),
            _t("D1A0000000000002", "Cola", "CamelPhat & Elderbrook", 122, "9A - Energy 6"),
            _t("D1A0000000000003", "Show Me Love", "Robin S", 120, "Key: C major"),
            _t("D1A0000000000004", "Losing It", "FISHER", 125, "10A - Energy 8"),
            _t("D1A0000000000005", "Bangarang", "Skrillex", 110, "2B"),
            _t("D1A0000000000006", "Love Story", "Taylor Swift", 119, "2B"),
            _t("D1A0000000000007", "Piece of Your Heart", "Meduza", 124, "9B"),
            _t("D1A0000000000008", "One More Time", "Daft Punk", 123, "Am"),
            _t("D1A0000000000009", "Lose Control", "Meduza, Becky Hill & Goodboys", 124, ""),
        ]},
        "DEMO000000000002": {"name": "Sunset Melodic Mix", "tracks": [
            _t("D2A0000000000001", "Opus", "Eric Prydz", 126, "8A"),
            _t("D2A0000000000002", "Innerbloom", "RÜFÜS DU SOL", 124, "9A - Energy 6"),
            _t("D2A0000000000003", "Sun & Moon", "Above & Beyond", 128, "10B"),
            _t("D2A0000000000004", "Strobe", "deadmau5", 128, "8A"),
            _t("D2A0000000000005", "Adagio for Strings", "Tiësto", 140, "2A - Energy 9"),
            _t("D2A0000000000006", "Language", "Porter Robinson", 128, "8B"),
        ]},
        "DEMO000000000003": {"name": "Festival Warmup", "tracks": [
            _t("D3A0000000000001", "Titanium", "David Guetta", 126, "4B"),
            _t("D3A0000000000002", "Wake Me Up", "Avicii", 124, "10A"),
            _t("D3A0000000000003", "Animals", "Martin Garrix", 128, "5A - Energy 9"),
            _t("D3A0000000000004", "Clarity", "Zedd", 128, "4B"),
            _t("D3A0000000000005", "Levels", "Avicii", 126, "3B"),
            _t("D3A0000000000006", "Silence", "Marshmello", 142, "11A"),
            _t("D3A0000000000007", "Don't You Worry Child", "Swedish House Mafia", 129, "3B"),
            _t("D3A0000000000008", "Lean On", "Major Lazer", 98, "6A"),
        ]},
    }
