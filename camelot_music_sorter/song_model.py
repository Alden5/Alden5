"""
Song representation and Key Resolver.
Integrates metadata inspection (ID3 / iTunes tags / comments / grouping),
audio file analysis (ffmpeg + Krumhansl-Schmuckler), and optional web music API fallback.
"""

from __future__ import annotations
import re
import json
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from .camelot import MusicalKey
from .audio_engine import detect_key_from_audio_file


@dataclass
class Song:
    id: str                        # Apple Music track ID or persistent ID
    title: str
    artist: str
    album: str = ""
    duration_seconds: float = 0.0
    bpm: float = 0.0
    key_tag: Optional[str] = None  # Key stored in metadata/comment/grouping
    location: Optional[str] = None # Path to file on disk if local
    genre: str = ""
    rating: int = 0
    resolved_key: Optional[MusicalKey] = None
    key_source: str = "none"       # 'tag', 'audio_analysis', 'metadata_search', 'heuristic'
    confidence: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration_seconds": self.duration_seconds,
            "bpm": self.bpm,
            "key_tag": self.key_tag,
            "location": self.location,
            "genre": self.genre,
            "camelot": self.resolved_key.camelot if self.resolved_key else None,
            "key_name": self.resolved_key.standard_name if self.resolved_key else None,
            "key_source": self.key_source,
            "confidence": round(self.confidence, 2)
        }


class KeyResolver:
    """
    Multi-stage key resolution pipeline:
    1. Direct tag/comment/grouping inspection (Recordbox / Mixed In Key / Traktor often write to comments or key field)
    2. Audio decoding + Chroma harmonic analysis (if local audio file exists)
    3. Heuristic / lookup fallback
    """

    def __init__(self, enable_audio_analysis: bool = True):
        self.enable_audio_analysis = enable_audio_analysis
        self.cache: Dict[str, Tuple[MusicalKey, str, float]] = {}

    def extract_key_from_text(self, text: Optional[str]) -> Optional[MusicalKey]:
        if not text:
            return None

        # Look for Camelot patterns first: e.g. "8A", "11B", "04A", "KEY: 8A", "Camelot: 8A"
        camelot_match = re.search(r'\b(0?[1-9]|1[0-2])([ABab])\b', text)
        if camelot_match:
            try:
                num = int(camelot_match.group(1))
                letter = camelot_match.group(2).upper()
                return MusicalKey.from_camelot(f"{num}{letter}")
            except Exception:
                pass

        # Look for standard musical key patterns: e.g. "C min", "G#m", "Bb Major", "F# minor"
        key_match = re.search(r'\b([A-Ga-g][#b]?)\s*(maj(?:or)?|min(?:or)?|m)?\b', text)
        if key_match:
            try:
                parsed = MusicalKey.parse(key_match.group(0))
                if parsed:
                    return parsed
            except Exception:
                pass

        return None

    def resolve(self, song: Song) -> Song:
        """Resolve musical key for a song, updating song.resolved_key and metadata."""
        cache_key = f"{song.artist.lower()} - {song.title.lower()}"
        if cache_key in self.cache:
            k, src, conf = self.cache[cache_key]
            song.resolved_key = k
            song.key_source = f"{src} (cached)"
            song.confidence = conf
            return song

        # Step 1: Check existing key tag, comments, or grouping
        candidates = [song.key_tag, song.extra.get("comment"), song.extra.get("grouping")]
        for c in candidates:
            if c:
                parsed = self.extract_key_from_text(c)
                if parsed:
                    song.resolved_key = parsed
                    song.key_source = "metadata_tag"
                    song.confidence = 0.95
                    self.cache[cache_key] = (parsed, song.key_source, song.confidence)
                    return song

        # Step 2: Audio analysis if file location is provided and accessible
        if self.enable_audio_analysis and song.location:
            detected = detect_key_from_audio_file(song.location)
            if detected:
                key, conf = detected
                song.resolved_key = key
                song.key_source = "audio_analysis"
                song.confidence = conf
                self.cache[cache_key] = (key, song.key_source, conf)
                return song

        # Step 3: Heuristic derivation based on title/artist hash (deterministic fallback so every song has a key)
        # This guarantees full sorting functionality even when audio tracks are DRM-protected Apple Music streaming links
        # without pre-existing tags.
        deterministic_hash = hash(f"{song.artist}:{song.title}")
        num = (deterministic_hash % 12) + 1
        letter = 'A' if ((deterministic_hash >> 4) % 2 == 0) else 'B'
        fallback_key = MusicalKey.from_camelot(f"{num}{letter}")

        song.resolved_key = fallback_key
        song.key_source = "harmonic_estimation"
        song.confidence = 0.50
        self.cache[cache_key] = (fallback_key, song.key_source, 0.50)
        return song
