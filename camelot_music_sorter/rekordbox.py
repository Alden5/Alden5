"""
Import track analysis from a rekordbox XML export (File > Export Collection in xml format).

rekordbox can analyze Apple Music tracks it streams, but keeps the results in its
own database. The XML export carries each track's key (Tonality), BPM and
comments, which are matched back to the songs in Music by file location or by
title, artist and duration.
"""

from __future__ import annotations
import json
import os
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional
from urllib.parse import unquote, urlparse

from .camelot import MusicalKey, extract_key

LIBRARY_VERSION = 1
DURATION_TOLERANCE = 6.0

_FEAT = re.compile(r"\s*[\(\[]?\b(?:feat\.?|ft\.?|featuring|with)\b.*$", re.IGNORECASE)
_BRACKETS = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
_DASH_SUFFIX = re.compile(r"\s+-\s+.*$")
_NON_WORD = re.compile(r"[^\w]+")
_ARTIST_SPLIT = re.compile(r"\s*(?:,|&|\+|/|;|\bfeat\.?|\bft\.?|\bfeaturing\b|\bwith\b|\bx\b|\bvs\.?|\band\b)\s*",
                           re.IGNORECASE)


class RekordboxError(ValueError):
    pass


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return _NON_WORD.sub(" ", text).strip()


def title_keys(title: str) -> List[str]:
    """Match keys for a title, strictest first: as-is, then without '(feat. …)', '(Remastered)', ' - Radio Edit'."""
    keys = [_fold(title)]
    for simplified in (_FEAT.sub("", title or ""), _BRACKETS.sub("", title or ""),
                       _DASH_SUFFIX.sub("", _BRACKETS.sub("", title or ""))):
        k = _fold(simplified)
        if k and k not in keys:
            keys.append(k)
    return [k for k in keys if k]


def artist_set(artist: str) -> frozenset:
    return frozenset(p for p in (_fold(x) for x in _ARTIST_SPLIT.split(artist or "")) if p)


def _location_to_path(location: str) -> Optional[str]:
    if not location:
        return None
    parsed = urlparse(location)
    if parsed.scheme != "file":
        return None
    path = unquote(parsed.path)
    # Windows exports look like file://localhost/C:/Music/...
    if re.match(r"^/[A-Za-z]:/", path):
        path = path[1:]
    return path or None


def _num(value: Optional[str]) -> float:
    try:
        return float(value) if value not in (None, "") else 0.0
    except ValueError:
        return 0.0


@dataclass
class RekordboxTrack:
    title: str
    artist: str
    album: str = ""
    duration_seconds: float = 0.0
    bpm: float = 0.0
    tonality: str = ""
    comments: str = ""
    location: Optional[str] = None

    @property
    def key(self) -> Optional[MusicalKey]:
        return extract_key(self.tonality)


def parse_rekordbox_xml(data: bytes) -> List[RekordboxTrack]:
    """Read the COLLECTION of a rekordbox XML export."""
    head = data[:4096].lower()
    if b"<!doctype" in head or b"<!entity" in head:
        raise RekordboxError("This XML file contains a DOCTYPE, which rekordbox exports never do.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise RekordboxError(f"Could not read the XML file ({e}).") from None
    if root.tag != "DJ_PLAYLISTS":
        raise RekordboxError("This isn't a rekordbox XML export. In rekordbox, use "
                             "File > Export Collection in xml format.")
    collection = root.find("COLLECTION")
    if collection is None:
        raise RekordboxError("The rekordbox XML file has no COLLECTION section.")

    tracks = []
    for el in collection.iter("TRACK"):
        a = el.attrib
        bpm = _num(a.get("AverageBpm"))
        if not bpm:
            tempo = el.find("TEMPO")
            bpm = _num(tempo.get("Bpm")) if tempo is not None else 0.0
        tracks.append(RekordboxTrack(
            title=a.get("Name", "").strip(),
            artist=a.get("Artist", "").strip(),
            album=a.get("Album", "").strip(),
            duration_seconds=_num(a.get("TotalTime")),
            bpm=round(bpm, 2),
            tonality=a.get("Tonality", "").strip(),
            comments=a.get("Comments", "").strip(),
            location=_location_to_path(a.get("Location", "")),
        ))
    return [t for t in tracks if t.title]


class RekordboxLibrary:
    def __init__(self, tracks: List[RekordboxTrack], source_name: str = "", imported_at: float = 0.0):
        self.tracks = tracks
        self.source_name = source_name
        self.imported_at = imported_at or time.time()
        self._by_location: Dict[str, RekordboxTrack] = {}
        self._by_title: Dict[str, List[RekordboxTrack]] = {}
        for t in tracks:
            if t.location:
                self._by_location.setdefault(os.path.normcase(t.location), t)
            for k in title_keys(t.title):
                self._by_title.setdefault(k, []).append(t)

    @classmethod
    def from_xml(cls, data: bytes, source_name: str = "") -> "RekordboxLibrary":
        tracks = parse_rekordbox_xml(data)
        if not tracks:
            raise RekordboxError("The rekordbox XML export has no tracks.")
        return cls(tracks, source_name)

    @property
    def keyed_count(self) -> int:
        return sum(1 for t in self.tracks if t.key)

    def summary(self) -> Dict[str, object]:
        return {"loaded": True, "source_name": self.source_name, "imported_at": self.imported_at,
                "track_count": len(self.tracks), "keyed_count": self.keyed_count}

    def match(self, title: str, artist: str, duration_seconds: float = 0.0,
              location: Optional[str] = None) -> Optional[RekordboxTrack]:
        if location:
            hit = self._by_location.get(os.path.normcase(location))
            if hit:
                return hit

        artists = artist_set(artist)
        for k in title_keys(title):
            candidates = [t for t in self._by_title.get(k, ()) if artists & artist_set(t.artist)]
            if duration_seconds > 0:
                timed = [t for t in candidates if t.duration_seconds > 0]
                close = [t for t in timed if abs(t.duration_seconds - duration_seconds) <= DURATION_TOLERANCE]
                if timed and not close and len(timed) == len(candidates):
                    continue
                if close:
                    candidates = sorted(close, key=lambda t: abs(t.duration_seconds - duration_seconds))
            if candidates:
                # Prefer an analyzed copy when the same song is in the collection twice.
                return next((t for t in candidates if t.key), candidates[0])
        return None

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"version": LIBRARY_VERSION, "source_name": self.source_name,
                       "imported_at": self.imported_at, "tracks": [asdict(t) for t in self.tracks]}, fh)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str) -> Optional["RekordboxLibrary"]:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return None
        if data.get("version") != LIBRARY_VERSION:
            return None
        tracks = [RekordboxTrack(**t) for t in data.get("tracks", [])]
        return cls(tracks, data.get("source_name", ""), data.get("imported_at", 0.0))


def music_updates(songs) -> List[tuple]:
    """
    (persistent_id, comment, bpm) for songs whose key or BPM came from rekordbox.
    The key is put in front of any existing comment, separated by ' | ' so a
    number later in the comment isn't read as an energy rating.
    """
    updates, seen = [], set()
    for s in songs:
        if s.persistent_id in seen:
            continue
        comment = ""
        if s.key_source == "rekordbox" and s.resolved_key:
            existing = (s.extra.get("comment") or "").strip()
            comment = f"{s.resolved_key.camelot} | {existing}" if existing else s.resolved_key.camelot
        bpm = int(round(s.bpm)) if s.bpm_source == "rekordbox" and s.bpm > 0 else None
        if comment or bpm:
            updates.append((s.persistent_id, comment, bpm))
            seen.add(s.persistent_id)
    return updates


def default_library_path() -> str:
    from .song_model import default_cache_path
    return os.path.join(os.path.dirname(default_cache_path()), "rekordbox.json")
