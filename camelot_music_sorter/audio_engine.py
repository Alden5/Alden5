"""
Audio key detection: chromagram analysis + Krumhansl-Kessler key profiles.
Supports any audio format ffmpeg can decode (m4a/aac, mp3, wav, aiff, flac).
DRM-protected Apple Music downloads (.m4p) cannot be decoded and return None.
"""

from __future__ import annotations
import json
import os
import shutil
import subprocess
from typing import Optional, Tuple

import numpy as np

from .camelot import MusicalKey

KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

SAMPLE_RATE = 22050
N_FFT = 8192
HOP = 4096
MIN_FREQ = 65.4    # C2
MAX_FREQ = 2093.0  # C7

KEY_TAG_NAMES = ("initialkey", "tkey", "key", "initial_key")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _pitch_class_matrix(n_fft: int, sample_rate: int) -> Tuple[np.ndarray, np.ndarray]:
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    bins = np.where((freqs >= MIN_FREQ) & (freqs <= MAX_FREQ))[0]
    midi = 69.0 + 12.0 * np.log2(freqs[bins] / 440.0)
    pcs = np.mod(np.round(midi).astype(int), 12)
    matrix = np.zeros((len(bins), 12))
    matrix[np.arange(len(bins)), pcs] = 1.0
    return bins, matrix


def compute_chroma_from_pcm(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Return a normalized 12-bin chroma vector (C = index 0) for mono samples."""
    if len(samples) == 0:
        return np.ones(12) / 12.0

    n_fft = N_FFT if len(samples) >= N_FFT else 1 << max(8, int(np.log2(len(samples))))
    hop = n_fft // 2
    if len(samples) < n_fft:
        samples = np.pad(samples, (0, n_fft - len(samples)))

    n_frames = 1 + (len(samples) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n_frames)[:, None]
    frames = samples[idx] * np.hanning(n_fft)

    bins, matrix = _pitch_class_matrix(n_fft, sample_rate)
    if len(bins) == 0:
        return np.ones(12) / 12.0

    mags = np.abs(np.fft.rfft(frames, axis=1))[:, bins]
    # Per-frame normalization keeps loud sections from dominating the profile.
    frame_energy = mags.sum(axis=1, keepdims=True)
    mags = np.divide(mags, frame_energy, out=np.zeros_like(mags), where=frame_energy > 0)
    chroma = (mags @ matrix).sum(axis=0)

    total = chroma.sum()
    return chroma / total if total > 0 else np.ones(12) / 12.0


def _standardize(v: np.ndarray) -> np.ndarray:
    return (v - v.mean()) / v.std()


def estimate_key_from_chroma(chroma: np.ndarray) -> Tuple[MusicalKey, float]:
    """
    Correlate chroma with all 24 rotated key profiles.
    Confidence reflects how clearly the best key beats the runner-up
    that is not its relative major/minor.
    """
    if np.std(chroma) < 1e-9:
        return MusicalKey.from_camelot("8B"), 0.0

    c = _standardize(chroma)
    maj, mnr = _standardize(KK_MAJOR), _standardize(KK_MINOR)
    scores = []
    for tonic in range(12):
        scores.append((float(np.dot(c, np.roll(maj, tonic)) / 12.0), MusicalKey.from_pitch_mode(tonic, "major")))
        scores.append((float(np.dot(c, np.roll(mnr, tonic)) / 12.0), MusicalKey.from_pitch_mode(tonic, "minor")))
    scores.sort(key=lambda s: s[0], reverse=True)

    best_r, best_key = scores[0]
    rival_r = next((r for r, k in scores[1:] if k.number != best_key.number), best_r)
    margin = max(0.0, best_r - rival_r)
    confidence = float(np.clip(0.4 * max(best_r, 0.0) + 2.5 * margin, 0.0, 1.0))
    return best_key, confidence


def extract_pcm_from_file(file_path: str, duration_sec: int = 120, offset_sec: int = 20) -> Optional[Tuple[np.ndarray, int]]:
    """Decode a slice of an audio file to mono float PCM via ffmpeg."""
    if not os.path.exists(file_path) or not ffmpeg_available():
        return None

    def decode(offset: int) -> bytes:
        cmd = [
            "ffmpeg", "-v", "error", "-nostdin",
            "-ss", str(offset), "-t", str(duration_sec),
            "-i", file_path,
            "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-",
        ]
        try:
            return subprocess.run(cmd, capture_output=True, timeout=60).stdout
        except (subprocess.TimeoutExpired, OSError):
            return b""

    raw = decode(offset_sec)
    if len(raw) < SAMPLE_RATE * 2 * 5:
        # Track is shorter than the offset plus a few seconds; analyze from the start.
        raw = decode(0)
    if len(raw) < 2048:
        return None

    samples = np.frombuffer(raw[: len(raw) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
    return samples, SAMPLE_RATE


def read_key_tag_from_file(file_path: str) -> Optional[str]:
    """Read a key tag (ID3 TKEY, iTunes 'initialkey', etc.) written by DJ software."""
    if not os.path.exists(file_path) or shutil.which("ffprobe") is None:
        return None
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_entries", "format_tags:stream_tags", file_path]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
        data = json.loads(out or "{}")
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None

    tag_sets = [data.get("format", {}).get("tags", {})]
    tag_sets += [s.get("tags", {}) for s in data.get("streams", [])]
    for tags in tag_sets:
        for name, value in tags.items():
            if name.lower() in KEY_TAG_NAMES and str(value).strip():
                return str(value).strip()
    return None


def detect_audio_features(file_path: str, bpm: Optional[float] = None) -> Optional[Tuple[MusicalKey, float, float]]:
    """Detect key, confidence, and energy level directly from an audio file."""
    result = extract_pcm_from_file(file_path)
    if result is None:
        return None
    samples, sample_rate = result
    key, conf = estimate_key_from_chroma(compute_chroma_from_pcm(samples, sample_rate))
    energy = compute_energy_from_pcm(samples, sample_rate, bpm=bpm)
    return key, conf, energy


def compute_energy_from_pcm(samples: np.ndarray, sample_rate: int = SAMPLE_RATE, bpm: Optional[float] = None) -> float:
    """
    Compute an energy level on a 1.0 - 10.0 scale from mono audio samples.
    Combines RMS loudness, spectral centroid/brightness, and dynamic crest factor.
    """
    if len(samples) < 512:
        return 5.0

    # 1. RMS Loudness
    rms = float(np.sqrt(np.mean(samples ** 2)))
    rms_db = 20.0 * np.log10(max(rms, 1e-6))
    # Standard mastering range: -26 dBFS (quiet/ambient) to -6 dBFS (maximally loud EDM)
    rms_score = float(np.clip((rms_db - (-26.0)) / (-6.0 - (-26.0)), 0.0, 1.0))

    # 2. Spectral Centroid / Brightness
    n_fft = 2048
    hop = 1024
    if len(samples) >= n_fft:
        n_frames = min(120, 1 + (len(samples) - n_fft) // hop)
        idx = np.arange(n_fft)[None, :] + hop * np.arange(n_frames)[:, None]
        frames = samples[idx] * np.hanning(n_fft)
        mags = np.abs(np.fft.rfft(frames, axis=1))
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
        mag_sum = mags.sum(axis=1)
        valid = mag_sum > 1e-6
        if np.any(valid):
            centroids = (mags[valid] * freqs).sum(axis=1) / mag_sum[valid]
            mean_centroid = float(np.mean(centroids))
        else:
            mean_centroid = 1500.0
    else:
        mean_centroid = 1500.0
    centroid_score = float(np.clip((mean_centroid - 800.0) / (3800.0 - 800.0), 0.0, 1.0))

    # 3. Dynamic compression (Crest factor)
    peak = float(np.max(np.abs(samples)))
    crest = peak / max(rms, 1e-6)
    crest_score = float(np.clip((6.0 - crest) / (6.0 - 2.2), 0.0, 1.0))

    # Base audio energy
    raw_energy = 0.50 * rms_score + 0.30 * centroid_score + 0.20 * crest_score

    # 4. BPM influence if available
    if bpm and bpm > 0:
        effective_bpm = bpm
        while effective_bpm < 85:
            effective_bpm *= 2
        while effective_bpm > 175:
            effective_bpm /= 2
        bpm_score = float(np.clip((effective_bpm - 85.0) / (145.0 - 85.0), 0.1, 1.0))
        raw_energy = 0.85 * raw_energy + 0.15 * bpm_score

    energy = 1.0 + 9.0 * raw_energy
    return round(float(np.clip(energy, 1.0, 10.0)), 1)


def detect_key_from_audio_file(file_path: str) -> Optional[Tuple[MusicalKey, float]]:
    """Detect key directly from an audio file on disk."""
    res = detect_audio_features(file_path)
    return (res[0], res[1]) if res else None
