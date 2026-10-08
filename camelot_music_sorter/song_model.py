"""
Song representation and key resolution.

Key sources, in priority order:
1. Key text already in the track's metadata (comments / grouping), e.g. written by
   Mixed In Key, Rekordbox or by hand.
2. A key tag embedded in the audio file (ID3 TKEY / iTunes 'initialkey').
3. Audio analysis of the local file with ffmpeg.
Tracks with none of these (streaming or DRM-protected tracks without tags) are
left with an unknown key rather than a guess.
"""

from __future__ import annotations
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .camelot import MusicalKey, extract_key
from .audio_engine import detect_key_from_audio_file, ffmpeg_available, read_key_tag_from_file

ANALYSIS_VERSION = 2


@dataclass
class Song:
    id: str                         # Unique within a playlist (duplicates get a '#n' suffix)
    title: str
    artist: str
    album: str = ""
    duration_seconds: float = 0.0
    bpm: float = 0.0
    key_tag: Optional[str] = None
    location: Optional[str] = None
    genre: str = ""
    rating: int = 0
    persistent_id: Optional[str] = None  # Music.app persistent ID used when exporting
    resolved_key: Optional[MusicalKey] = None
    key_source: str = "unknown"
    key_note: str = ""
    confidence: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.persistent_id is None:
            self.persistent_id = self.id

    def to_dict(self) -> Dict[str, Any]:
        k = self.resolved_key
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration_seconds": self.duration_seconds,
            "bpm": self.bpm,
            "has_local_file": bool(self.location),
            "key_source": self.key_source,
            "key_note": self.key_note,
            "confidence": round(self.confidence, 2),
            "resolved_key": {
                "number": k.number,
                "letter": k.letter,
                "camelot": k.camelot,
                "standard_name": k.standard_name,
            } if k else None,
        }


def default_cache_path() -> str:
    override = os.environ.get("CAMELOT_SORTER_CACHE")
    if override:
        return override
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Caches/CamelotSorter")
    else:
        base = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "camelot-sorter")
    return os.path.join(base, "keys.json")


class KeyResolver:
    def __init__(self, enable_audio_analysis: bool = True, cache_path: Optional[str] = "default", workers: int = 4):
        self.enable_audio_analysis = enable_audio_analysis
        self.workers = max(1, workers)
        self.cache_path = default_cache_path() if cache_path == "default" else cache_path
        self._lock = threading.Lock()
        self._cache: Dict[str, Dict[str, Any]] = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        if not self.cache_path or not os.path.exists(self.cache_path):
            return {}
        try:
            with open(self.cache_path, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("version") == ANALYSIS_VERSION:
                return data.get("entries", {})
        except (OSError, ValueError):
            pass
        return {}

    def save_cache(self) -> None:
        if not self.cache_path:
            return
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            tmp = self.cache_path + ".tmp"
            with self._lock, open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"version": ANALYSIS_VERSION, "entries": self._cache}, fh)
            os.replace(tmp, self.cache_path)
        except OSError:
            pass

    @staticmethod
    def _file_cache_key(path: str) -> Optional[str]:
        try:
            st = os.stat(path)
        except OSError:
            return None
        return f"{path}|{int(st.st_mtime)}|{st.st_size}"

    def extract_key_from_text(self, text: Optional[str]) -> Optional[MusicalKey]:
        return extract_key(text)

    def resolve(self, song: Song) -> Song:
        for label, text in (("key tag", song.key_tag),
                            ("comments", song.extra.get("comment")),
                            ("grouping", song.extra.get("grouping"))):
            parsed = extract_key(text)
            if parsed:
                song.resolved_key, song.key_source, song.confidence = parsed, "metadata", 0.95
                song.key_note = f"Read from {label}"
                return song

        if not song.location:
            song.resolved_key, song.key_source, song.confidence = None, "unknown", 0.0
            song.key_note = ("Streaming / cloud track with no key in comments or grouping. "
                             "Download it or add its key (e.g. '8A') to the Comments field.")
            return song

        if not os.path.exists(song.location):
            song.resolved_key, song.key_source, song.confidence = None, "unknown", 0.0
            song.key_note = "Audio file is missing on disk."
            return song

        cache_key = self._file_cache_key(song.location)
        with self._lock:
            cached = self._cache.get(cache_key) if cache_key else None
        if cached is None:
            cached = self._analyze_file(song.location)
            if cache_key and cached.get("camelot"):
                with self._lock:
                    self._cache[cache_key] = cached

        if cached.get("camelot"):
            song.resolved_key = MusicalKey.from_camelot(cached["camelot"])
            song.key_source = cached["source"]
            song.confidence = cached["confidence"]
            song.key_note = cached.get("note", "")
        else:
            song.resolved_key, song.key_source, song.confidence = None, "unknown", 0.0
            song.key_note = cached.get("note", "Could not determine key.")
        return song

    def _analyze_file(self, path: str) -> Dict[str, Any]:
        tag = read_key_tag_from_file(path)
        parsed = extract_key(tag)
        if parsed:
            return {"camelot": parsed.camelot, "source": "file_tag", "confidence": 0.95,
                    "note": f"Key tag in file: {tag}"}

        if not self.enable_audio_analysis:
            return {"note": "Audio analysis disabled."}
        if not ffmpeg_available():
            return {"note": "Install ffmpeg (brew install ffmpeg) to analyze audio files."}
        if path.lower().endswith(".m4p"):
            return {"note": "DRM-protected Apple Music download; audio can't be analyzed."}

        detected = detect_key_from_audio_file(path)
        if not detected:
            return {"note": "ffmpeg could not decode this file (it may be DRM-protected)."}
        key, conf = detected
        return {"camelot": key.camelot, "source": "audio_analysis", "confidence": round(conf, 3),
                "note": "Detected from audio"}

    def resolve_many(self, songs: List[Song], progress: Optional[Callable[[int, int, Song], None]] = None) -> List[Song]:
        done = 0
        total = len(songs)

        def work(song: Song) -> Song:
            return self.resolve(song)

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for song in pool.map(work, songs):
                done += 1
                if progress:
                    progress(done, total, song)
        self.save_cache()
        return songs
