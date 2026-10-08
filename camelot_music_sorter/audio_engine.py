"""
Audio key detection using Chromagram Analysis & Krumhansl-Schmuckler Pitch Class Profiles.
Supports any audio format decodable by ffmpeg (e.g. m4a, mp3, aac, wav, aiff, flac).
"""

from __future__ import annotations
import os
import subprocess
import tempfile
import struct
from typing import Optional, Tuple, Dict, Any
import numpy as np

from .camelot import MusicalKey

# Krumhansl-Kessler / Temperley / Albrecht key profiles
# Krumhansl-Kessler key profiles (standard perceptual weights for 12 pitch classes relative to tonic)
# Pitch classes: [tonic, +1, +2, +3, +4, +5, +6, +7, +8, +9, +10, +11]
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Temperley Key Profiles (often performs better with modern music)
TEMPERLEY_MAJOR = np.array([5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0])
TEMPERLEY_MINOR = np.array([5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0])


def compute_chroma_from_pcm(samples: np.ndarray, sample_rate: int = 22050) -> np.ndarray:
    """
    Computes a 12-dimensional chroma vector from mono floating point audio samples.
    Uses Short-Time Fourier Transform (STFT) with pitch class binning.
    """
    if len(samples) == 0:
        return np.ones(12) / 12.0

    # Resample or chunk into frames
    n_fft = 4096
    hop_length = 2048
    window = np.hanning(n_fft)

    n_frames = max(1, (len(samples) - n_fft) // hop_length)
    if n_frames < 1:
        # Pad with zeros
        padded = np.pad(samples, (0, n_fft - len(samples)))
        frames = [padded]
    else:
        frames = [
            samples[i * hop_length : i * hop_length + n_fft] * window
            for i in range(n_frames)
        ]

    # Compute FFT magnitudes
    chroma = np.zeros(12, dtype=np.float64)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)

    # Focus on the most pitch-relevant frequency range (approx 65 Hz to 2100 Hz: C2 to C7)
    min_freq = 65.4   # C2
    max_freq = 2093.0 # C7

    valid_bins = np.where((freqs >= min_freq) & (freqs <= max_freq))[0]
    if len(valid_bins) == 0:
        return np.ones(12) / 12.0

    valid_freqs = freqs[valid_bins]
    # MIDI note number: 69 + 12 * log2(f / 440.0)
    midi_notes = 69.0 + 12.0 * np.log2(valid_freqs / 440.0)
    # Pitch class 0..11 where C = 0 (MIDI 60 is C4 -> 60 % 12 = 0)
    pitch_classes = np.mod(np.round(midi_notes).astype(int), 12)

    for frame in frames:
        fft_mag = np.abs(np.fft.rfft(frame))
        valid_mags = fft_mag[valid_bins]
        for pc in range(12):
            chroma[pc] += np.sum(valid_mags[pitch_classes == pc])

    # Normalize chroma vector
    total = np.sum(chroma)
    if total > 0:
        chroma = chroma / total
    else:
        chroma = np.ones(12) / 12.0

    return chroma


def estimate_key_from_chroma(chroma: np.ndarray) -> Tuple[MusicalKey, float]:
    """
    Correlates a 12-dimensional chroma vector with major and minor profiles.
    Returns the best matching MusicalKey and the confidence score (Pearson r).
    """
    # Normalize chroma
    chroma_norm = chroma - np.mean(chroma)
    std_c = np.std(chroma)
    if std_c > 1e-9:
        chroma_norm = chroma_norm / std_c
    else:
        # Uniform pitch energy, default to 8B (C Major) with 0 confidence
        return MusicalKey.from_camelot("8B"), 0.0

    best_corr = -2.0
    best_key = MusicalKey.from_camelot("8B")

    # Standardized profiles
    def norm_profile(p: np.ndarray) -> np.ndarray:
        p_norm = p - np.mean(p)
        return p_norm / np.std(p_norm)

    maj_prof = norm_profile(KK_MAJOR)
    min_prof = norm_profile(KK_MINOR)

    for tonic in range(12):
        # Rotate profiles so that index 0 aligns with tonic
        rotated_maj = np.roll(maj_prof, tonic)
        rotated_min = np.roll(min_prof, tonic)

        corr_maj = float(np.dot(chroma_norm, rotated_maj) / 12.0)
        corr_min = float(np.dot(chroma_norm, rotated_min) / 12.0)

        if corr_maj > best_corr:
            best_corr = corr_maj
            best_key = MusicalKey.from_pitch_mode(tonic, 'major')

        if corr_min > best_corr:
            best_corr = corr_min
            best_key = MusicalKey.from_pitch_mode(tonic, 'minor')

    confidence = max(0.0, min(1.0, (best_corr + 1.0) / 2.0))
    return best_key, confidence


def extract_pcm_from_file(file_path: str, duration_sec: int = 60, offset_sec: int = 30) -> Optional[Tuple[np.ndarray, int]]:
    """
    Uses ffmpeg to decode a slice of an audio file to raw 16-bit mono PCM.
    Returns (samples_array, sample_rate) or None on failure.
    """
    if not os.path.exists(file_path):
        return None

    sample_rate = 22050
    cmd = [
        'ffmpeg',
        '-v', 'error',
        '-ss', str(offset_sec),
        '-t', str(duration_sec),
        '-i', file_path,
        '-f', 's16le',
        '-acodec', 'pcm_s16le',
        '-ac', '1',
        '-ar', str(sample_rate),
        '-'
    ]

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        raw_bytes = proc.stdout
        if not raw_bytes or len(raw_bytes) < 1000:
            # Maybe the track is shorter than offset_sec, try from the start
            cmd[3] = '0'
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            raw_bytes = proc.stdout

        if not raw_bytes:
            return None

        # Convert to numpy array
        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return samples, sample_rate
    except Exception:
        return None


def detect_key_from_audio_file(file_path: str) -> Optional[Tuple[MusicalKey, float]]:
    """Detect key directly from audio file on disk via ffmpeg + chromagram analysis."""
    result = extract_pcm_from_file(file_path)
    if result is None:
        return None
    samples, sample_rate = result
    chroma = compute_chroma_from_pcm(samples, sample_rate)
    return estimate_key_from_chroma(chroma)
