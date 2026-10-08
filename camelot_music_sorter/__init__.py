"""
Camelot DJ Apple Music Sorter package.
"""

from .camelot import MusicalKey, transition_score, camelot_distance
from .song_model import Song, KeyResolver
from .audio_engine import detect_key_from_audio_file, compute_chroma_from_pcm, estimate_key_from_chroma
from .sorter import HarmonicPlaylistSorter, SortResult
from .apple_music import AppleMusicBridge
from .server import run_web_server

__version__ = "1.0.0"
__all__ = [
    "MusicalKey",
    "transition_score",
    "camelot_distance",
    "Song",
    "KeyResolver",
    "detect_key_from_audio_file",
    "compute_chroma_from_pcm",
    "estimate_key_from_chroma",
    "HarmonicPlaylistSorter",
    "SortResult",
    "AppleMusicBridge",
    "run_web_server",
]
