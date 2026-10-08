"""Camelot DJ Apple Music Sorter."""

from .camelot import MusicalKey, camelot_distance, extract_key, transition_score
from .song_model import KeyResolver, Song
from .audio_engine import compute_chroma_from_pcm, detect_key_from_audio_file, estimate_key_from_chroma
from .sorter import HarmonicPlaylistSorter, SortResult
from .apple_music import AppleMusicBridge, MusicAppError

__version__ = "1.1.0"
__all__ = [
    "MusicalKey", "camelot_distance", "extract_key", "transition_score",
    "KeyResolver", "Song",
    "compute_chroma_from_pcm", "detect_key_from_audio_file", "estimate_key_from_chroma",
    "HarmonicPlaylistSorter", "SortResult",
    "AppleMusicBridge", "MusicAppError",
]
