"""
Apple Music (Music.app) integration for macOS via AppleScript / osascript.
Also provides a Mock / Fallback adapter for testing and environments where Music.app is unavailable.
"""

from __future__ import annotations
import os
import sys
import subprocess
import json
from typing import List, Optional, Dict, Any

from .song_model import Song
from .camelot import MusicalKey


class AppleMusicBridge:
    """Interface for querying and creating playlists in Apple Music (macOS Music.app)."""

    def is_macos(self) -> bool:
        return sys.platform == "darwin"

    def run_applescript(self, script: str) -> str:
        """Executes an AppleScript via `osascript` on macOS."""
        if not self.is_macos():
            raise RuntimeError("AppleScript execution is only available on macOS.")

        cmd = ['osascript', '-e', script]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"osascript error ({proc.returncode}): {proc.stderr.strip()}")
        return proc.stdout.strip()

    def get_all_playlists(self) -> List[Dict[str, Any]]:
        """List user playlists from Music.app."""
        if not self.is_macos():
            return self._get_mock_playlists()

        script = """
        tell application "Music"
            set output to ""
            repeat with p in user playlists
                set pName to name of p
                set pId to id of p
                set tCount to count of tracks of p
                set output to output & pName & ":::" & pId & ":::" & (tCount as string) & linefeed
            end repeat
            return output
        end tell
        """
        try:
            raw = self.run_applescript(script)
            results = []
            for line in raw.splitlines():
                parts = line.strip().split(":::")
                if len(parts) >= 3:
                    results.append({
                        "name": parts[0],
                        "id": parts[1],
                        "track_count": int(parts[2]) if parts[2].isdigit() else 0
                    })
            return results
        except Exception as e:
            # Fall back or re-raise
            raise RuntimeError(f"Failed to query playlists from Music.app: {e}")

    def get_playlist_tracks(self, playlist_name_or_id: str) -> List[Song]:
        """Fetch all tracks from a playlist in Music.app."""
        if not self.is_macos():
            return self._get_mock_tracks(playlist_name_or_id)

        # AppleScript to extract track details (id, name, artist, album, duration, bpm, comment, grouping, location)
        escaped_name = playlist_name_or_id.replace('"', '\\"')
        script = f"""
        tell application "Music"
            try
                set targetPlaylist to (first user playlist whose name is "{escaped_name}")
            on error
                try
                    set targetPlaylist to (first user playlist whose persistent ID is "{escaped_name}")
                on error
                    error "Playlist not found: {escaped_name}"
                end try
            end try

            set trackData to ""
            set trackList to tracks of targetPlaylist
            repeat with trk in trackList
                set tId to persistent ID of trk
                set tName to name of trk
                set tArtist to artist of trk
                set tAlbum to album of trk
                set tDuration to duration of trk
                set tBpm to bpm of trk
                set tComment to comment of trk
                set tGrouping to grouping of trk
                set tLoc to ""
                try
                    set tLoc to (POSIX path of (get location of trk))
                end try

                set trackData to trackData & tId & "<TAB>" & tName & "<TAB>" & tArtist & "<TAB>" & tAlbum & "<TAB>" & (tDuration as string) & "<TAB>" & (tBpm as string) & "<TAB>" & tComment & "<TAB>" & tGrouping & "<TAB>" & tLoc & "<EOL>"
            end repeat
            return trackData
        end tell
        """

        raw = self.run_applescript(script)
        songs: List[Song] = []
        entries = raw.split("<EOL>")
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split("<TAB>")
            if len(parts) >= 9:
                s_id, title, artist, album, dur_str, bpm_str, comment, grouping, loc = parts[:9]
                try:
                    dur = float(dur_str) if dur_str else 0.0
                except ValueError:
                    dur = 0.0
                try:
                    bpm = float(bpm_str) if bpm_str else 0.0
                except ValueError:
                    bpm = 0.0

                song = Song(
                    id=s_id,
                    title=title,
                    artist=artist,
                    album=album,
                    duration_seconds=dur,
                    bpm=bpm,
                    key_tag=None,
                    location=loc if loc else None,
                    extra={"comment": comment, "grouping": grouping}
                )
                songs.append(song)

        return songs

    def create_sorted_playlist(self, original_name: str, sorted_songs: List[Song], suffix: str = "sorted") -> str:
        """
        Creates a new playlist with 'sorted' appended to the name,
        and adds the tracks in the exact sorted sequence.
        Returns the new playlist name.
        """
        new_name = f"{original_name} {suffix}".strip()

        if not self.is_macos():
            return self._mock_create_sorted_playlist(new_name, sorted_songs)

        escaped_new_name = new_name.replace('"', '\\"')
        
        # Build list of IDs
        id_list_str = '{"' + '", "'.join(s.id for s in sorted_songs) + '"}'

        script = f"""
        tell application "Music"
            -- Check if playlist with new name already exists; if so, delete or reuse
            if exists (user playlist "{escaped_new_name}") then
                delete user playlist "{escaped_new_name}"
            end if

            set newPl to (make new user playlist with properties {{name:"{escaped_new_name}"}})
            set trackIds to {id_list_str}

            repeat with tid in trackIds
                try
                    set matchedTracks to (every track of playlist 1 whose persistent ID is tid)
                    if (count of matchedTracks) > 0 then
                        duplicate (first item of matchedTracks) to newPl
                    end if
                end try
            end repeat

            return name of newPl
        end tell
        """

        res = self.run_applescript(script)
        return res or new_name

    # Mock helpers for Linux / Dev / Non-Mac testing
    def _get_mock_playlists(self) -> List[Dict[str, Any]]:
        return [
            {"name": "Friday Night House", "id": "mock_pl_001", "track_count": 8},
            {"name": "Sunset Melodic Mix", "id": "mock_pl_002", "track_count": 6},
            {"name": "Festival Warmup", "id": "mock_pl_003", "track_count": 10},
        ]

    def _get_mock_tracks(self, playlist_name_or_id: str) -> List[Song]:
        """Returns realistic mock tracks with known musical keys and Camelot values for testing and demonstration."""
        if "sunset" in playlist_name_or_id.lower():
            return [
                Song(id="trk_s1", title="Opus", artist="Eric Prydz", album="Opus", bpm=126, extra={"comment": "Key: 8A", "grouping": "8A"}),
                Song(id="trk_s2", title="Innerbloom", artist="RÜFÜS DU SOL", album="Bloom", bpm=124, extra={"comment": "9A"}),
                Song(id="trk_s3", title="Sun & Moon", artist="Above & Beyond", album="Group Therapy", bpm=128, extra={"comment": "10B"}),
                Song(id="trk_s4", title="Strobe", artist="deadmau5", album="For Lack of a Better Name", bpm=128, extra={"comment": "8A"}),
                Song(id="trk_s5", title="Adagio for Strings", artist="Tiësto", album="Just Be", bpm=140, extra={"comment": "2A"}), # outlier
                Song(id="trk_s6", title="Language", artist="Porter Robinson", album="Language", bpm=128, extra={"comment": "8B"}),
            ]
        elif "festival" in playlist_name_or_id.lower():
            return [
                Song(id="trk_f1", title="Titanium", artist="David Guetta", album="Nothing but the Beat", bpm=126, extra={"comment": "4B"}),
                Song(id="trk_f2", title="Wake Me Up", artist="Avicii", album="True", bpm=124, extra={"comment": "10A"}),
                Song(id="trk_f3", title="Animals", artist="Martin Garrix", album="Animals", bpm=128, extra={"comment": "5A"}),
                Song(id="trk_f4", title="Clarity", artist="Zedd", album="Clarity", bpm=128, extra={"comment": "4B"}),
                Song(id="trk_f5", title="Levels", artist="Avicii", album="Levels", bpm=126, extra={"comment": "3B"}),
                Song(id="trk_f6", title="Silence", artist="Marshmello", album="Silence", bpm=142, extra={"comment": "11A"}),
            ]
        else: # Default Friday Night House
            return [
                Song(id="trk_1", title="Deep Inside", artist="Hardrive", album="Strictly Rhythm", bpm=124, extra={"comment": "8A", "grouping": "8A"}),
                Song(id="trk_2", title="Cola", artist="CamelPhat & Elderbrook", album="Defected", bpm=122, extra={"comment": "9A"}),
                Song(id="trk_3", title="Show Me Love", artist="Robin S", album="Stonebridge Mix", bpm=120, extra={"comment": "8B"}),
                Song(id="trk_4", title="Losing It", artist="FISHER", album="Catch & Release", bpm=125, extra={"comment": "10A"}),
                Song(id="trk_5", title="Bangarang", artist="Skrillex", album="Bangarang", bpm=110, extra={"comment": "2B"}), # Severe harmonic outlier
                Song(id="trk_6", title="Love Story", artist="Taylor Swift", album="Fearless", bpm=119, extra={"comment": "2B"}), # Clash outlier
                Song(id="trk_7", title="Piece of Your Heart", artist="Meduza", album="Polydor", bpm=124, extra={"comment": "9B"}),
                Song(id="trk_8", title="One More Time", artist="Daft Punk", album="Discovery", bpm=123, extra={"comment": "8A"}),
            ]

    def _mock_create_sorted_playlist(self, new_name: str, sorted_songs: List[Song]) -> str:
        return new_name
