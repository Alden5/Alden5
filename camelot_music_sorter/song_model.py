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
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .camelot import MusicalKey, extract_key
from .audio_engine import (
    compute_energy_from_pcm, detect_audio_features, detect_key_from_audio_file,
    ffmpeg_available, read_key_tag_from_file,
)

ANALYSIS_VERSION = 3

ENERGY_RE = re.compile(
    r"""(?ix)
    (?:
        \benergy(?:\s*level)?\s*[:=\-]?\s*(?P<e1>10(?:\.[0-9])?|[1-9](?:\.[0-9])?)\b
      | \bE\s*[:=\-]\s*(?P<e2>10(?:\.[0-9])?|[1-9](?:\.[0-9])?)\b
      | \bE(?P<e3>10|[1-9])\b
      | \b(?:1[0-2]|[1-9])[AB]\s*[-–—/]\s*(?P<e4>10(?:\.[0-9])?|[1-9](?:\.[0-9])?)\b
    )
    """
)


def extract_energy_from_text(text: Optional[str]) -> Optional[float]:
    """Extract an energy rating (1.0 to 10.0) from tags/comments like 'Energy 7' or '8A - 8'."""
    if not text:
        return None
    m = ENERGY_RE.search(str(text))
    if not m:
        return None
    val = next((m.group(k) for k in ("e1", "e2", "e3", "e4") if m.group(k)), None)
    if val is None:
        return None
    try:
        score = float(val)
        return round(float(np.clip(score, 1.0, 10.0)), 1)
    except ValueError:
        return None


def estimate_energy_from_metadata(bpm: float = 0.0, genre: str = "", rating: int = 0) -> float:
    """Heuristic energy level (1.0 to 10.0) from BPM, genre, and rating when audio analysis is unavailable."""
    base = 5.5
    if bpm > 0:
        effective = bpm
        while effective < 85:
            effective *= 2
        while effective > 175:
            effective /= 2
        # 85 BPM -> ~4.5, 124 BPM -> ~7.2, 130 BPM -> ~7.8, 140+ BPM -> ~8.5
        base = 3.5 + 5.5 * float(np.clip((effective - 80.0) / (140.0 - 80.0), 0.0, 1.0))

    g = (genre or "").lower()
    if any(k in g for k in ("ambient", "classical", "chill", "downtempo", "lo-fi", "lofi", "acoustic", "meditation")):
        base -= 2.0
    elif any(k in g for k in ("jazz", "soul", "r&b", "reggae", "indie", "folk", "blues")):
        base -= 0.8
    elif any(k in g for k in ("hardstyle", "hardcore", "metal", "drum and bass", "dnb", "dubstep", "edm", "big room")):
        base += 1.5
    elif any(k in g for k in ("techno", "trance", "electro", "house", "dance", "electronic", "club")):
        base += 0.8
    elif any(k in g for k in ("pop", "hip-hop", "hip hop", "rap", "rock")):
        base += 0.3

    if rating > 0:
        stars = rating / 20.0 if rating > 5 else float(rating)
        if stars >= 4:
            base += 0.3

    return round(float(np.clip(base, 1.0, 10.0)), 1)


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
    energy: Optional[float] = None
    energy_source: str = "unknown"  # "metadata", "audio_analysis", "estimated", "unknown"
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
            "energy": round(self.energy, 1) if self.energy is not None else None,
            "energy_source": self.energy_source,
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
            if data.get("version") in (2, 3):
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

    def _resolve_audio_energy(self, song: Song) -> None:
        if not song.location or not os.path.exists(song.location) or not ffmpeg_available():
            return
        cache_key = self._file_cache_key(song.location)
        with self._lock:
            cached = self._cache.get(cache_key) if cache_key else None
        if cached and cached.get("energy") is not None:
            song.energy = float(cached["energy"])
            song.energy_source = cached.get("energy_source", "audio_analysis")
            return
        detected = detect_audio_features(song.location, bpm=song.bpm)
        if detected:
            _, _, audio_energy = detected
            song.energy = audio_energy
            song.energy_source = "audio_analysis"
            if cache_key:
                with self._lock:
                    entry = self._cache.setdefault(cache_key, {})
                    entry["energy"] = audio_energy
                    entry["energy_source"] = "audio_analysis"

    def resolve(self, song: Song) -> Song:
        # 1. Check metadata for energy level
        if song.energy is None:
            for text in (song.key_tag, song.extra.get("comment"), song.extra.get("grouping")):
                e = extract_energy_from_text(text)
                if e is not None:
                    song.energy = e
                    song.energy_source = "metadata"
                    break

        # 2. Check metadata for key
        for label, text in (("key tag", song.key_tag),
                            ("comments", song.extra.get("comment")),
                            ("grouping", song.extra.get("grouping"))):
            parsed = extract_key(text)
            if parsed:
                song.resolved_key, song.key_source, song.confidence = parsed, "metadata", 0.95
                song.key_note = f"Read from {label}"
                if song.energy is None:
                    if song.location and os.path.exists(song.location) and self.enable_audio_analysis:
                        self._resolve_audio_energy(song)
                    if song.energy is None:
                        song.energy = estimate_energy_from_metadata(song.bpm, song.genre, song.rating)
                        song.energy_source = "estimated"
                return song

        if not song.location:
            song.resolved_key, song.key_source, song.confidence = None, "unknown", 0.0
            song.key_note = ("Streaming / cloud track with no key in comments or grouping. "
                             "Download it or add its key (e.g. '8A') to the Comments field.")
            if song.energy is None:
                song.energy = estimate_energy_from_metadata(song.bpm, song.genre, song.rating)
                song.energy_source = "estimated"
            return song

        if not os.path.exists(song.location):
            song.resolved_key, song.key_source, song.confidence = None, "unknown", 0.0
            song.key_note = "Audio file is missing on disk."
            if song.energy is None:
                song.energy = estimate_energy_from_metadata(song.bpm, song.genre, song.rating)
                song.energy_source = "estimated"
            return song

        cache_key = self._file_cache_key(song.location)
        with self._lock:
            cached = self._cache.get(cache_key) if cache_key else None
        if cached is None:
            cached = self._analyze_file(song.location, bpm=song.bpm)
            if cache_key and (cached.get("camelot") or cached.get("energy")):
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

        if song.energy is None and cached.get("energy") is not None:
            song.energy = float(cached["energy"])
            song.energy_source = cached.get("energy_source", "audio_analysis")
        elif song.energy is None:
            song.energy = estimate_energy_from_metadata(song.bpm, song.genre, song.rating)
            song.energy_source = "estimated"
        return song

    def _analyze_file(self, path: str, bpm: Optional[float] = None) -> Dict[str, Any]:
        tag = read_key_tag_from_file(path)
        parsed = extract_key(tag)
        energy_tag = extract_energy_from_text(tag)

        if not self.enable_audio_analysis or not ffmpeg_available() or path.lower().endswith(".m4p"):
            if parsed:
                res = {"camelot": parsed.camelot, "source": "file_tag", "confidence": 0.95,
                       "note": f"Key tag in file: {tag}"}
                if energy_tag is not None:
                    res["energy"] = energy_tag
                    res["energy_source"] = "metadata"
                return res
            if not self.enable_audio_analysis:
                return {"note": "Audio analysis disabled."}
            if not ffmpeg_available():
                return {"note": "Install ffmpeg (brew install ffmpeg) to analyze audio files."}
            return {"note": "DRM-protected Apple Music download; audio can't be analyzed."}

        detected = detect_audio_features(path, bpm=bpm)
        if not detected:
            if parsed:
                res = {"camelot": parsed.camelot, "source": "file_tag", "confidence": 0.95,
                       "note": f"Key tag in file: {tag}"}
                if energy_tag is not None:
                    res["energy"] = energy_tag
                    res["energy_source"] = "metadata"
                return res
            return {"note": "ffmpeg could not decode this file (it may be DRM-protected)."}

        key, conf, audio_energy = detected
        return {
            "camelot": (parsed.camelot if parsed else key.camelot),
            "source": ("file_tag" if parsed else "audio_analysis"),
            "confidence": (0.95 if parsed else round(conf, 3)),
            "note": (f"Key tag in file: {tag}" if parsed else "Detected from audio"),
            "energy": (energy_tag if energy_tag is not None else audio_energy),
            "energy_source": ("metadata" if energy_tag is not None else "audio_analysis"),
        }

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
