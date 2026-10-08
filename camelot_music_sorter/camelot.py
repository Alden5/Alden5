"""
Camelot Wheel definitions, musical key parsing, and harmonic mixing rules.

Camelot System:
- 12 Pitch Classes:
  1B: B major / 1A: G# minor (Ab minor)
  2B: F# major (Gb major) / 2A: D# minor (Eb minor)
  3B: Db major (C# major) / 3A: Bb minor (A# minor)
  4B: Ab major (G# major) / 4A: F minor
  5B: Eb major (D# major) / 5A: C minor
  6B: Bb major (A# major) / 6A: G minor
  7B: F major / 7A: D minor
  8B: C major / 8A: A minor
  9B: G major / 9A: E minor
  10B: D major / 10A: B minor
  11B: A major / 11A: F# minor (Gb minor)
  12B: E major / 12A: C# minor (Db minor)
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List

# Pitch class standard pitch names to semitone 0-11 (C = 0, C# = 1, D = 2, ...)
NOTE_TO_SEMITONE = {
    'C': 0, 'B#': 0,
    'C#': 1, 'DB': 1,
    'D': 2,
    'D#': 3, 'EB': 3,
    'E': 4, 'FB': 4,
    'F': 5, 'E#': 5,
    'F#': 6, 'GB': 6,
    'G': 7,
    'G#': 8, 'AB': 8,
    'A': 9,
    'A#': 10, 'BB': 10,
    'B': 11, 'CB': 11,
}

SEMITONE_TO_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
SEMITONE_TO_FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

# Standard mapping: (semitone, is_minor) -> (camelot_number 1-12, camelot_letter 'A'/'B')
# Major keys:
# B (11) -> 1B, F# (6) -> 2B, Db (1) -> 3B, Ab (8) -> 4B, Eb (3) -> 5B, Bb (10) -> 6B,
# F (5) -> 7B, C (0) -> 8B, G (7) -> 9B, D (2) -> 10B, A (9) -> 11B, E (4) -> 12B
MAJOR_TO_CAMELOT: Dict[int, int] = {
    11: 1,   # B
    6: 2,    # F# / Gb
    1: 3,    # C# / Db
    8: 4,    # Ab / G#
    3: 5,    # Eb / D#
    10: 6,   # Bb / A#
    5: 7,    # F
    0: 8,    # C
    7: 9,    # G
    2: 10,   # D
    9: 11,   # A
    4: 12,   # E
}

# Minor keys:
# G# (8) -> 1A, D# (3) -> 2A, Bb (10) -> 3A, F (5) -> 4A, C (0) -> 5A, G (7) -> 6A,
# D (2) -> 7A, A (9) -> 8A, E (4) -> 9A, B (11) -> 10A, F# (6) -> 11A, C# (1) -> 12A
MINOR_TO_CAMELOT: Dict[int, int] = {
    8: 1,    # G# / Abm
    3: 2,    # D# / Ebm
    10: 3,   # A# / Bbm
    5: 4,    # Fm
    0: 5,    # Cm
    7: 6,    # Gm
    2: 7,    # Dm
    9: 8,    # Am
    4: 9,    # Em
    11: 10,  # Bm
    6: 11,   # F#m
    1: 12,   # C#m
}

# Reverse lookup: (number, letter) -> semitone
CAMELOT_TO_SEMITONE: Dict[Tuple[int, str], int] = {}
for semi, num in MAJOR_TO_CAMELOT.items():
    CAMELOT_TO_SEMITONE[(num, 'B')] = semi
for semi, num in MINOR_TO_CAMELOT.items():
    CAMELOT_TO_SEMITONE[(num, 'A')] = semi


@dataclass(frozen=True)
class MusicalKey:
    """Represents a musical key with both standard and Camelot representations."""
    number: int        # 1 - 12
    letter: str        # 'A' (minor) or 'B' (major)
    pitch_class: int   # 0 - 11 (C = 0)
    mode: str          # 'major' or 'minor'

    @property
    def camelot(self) -> str:
        return f"{self.number}{self.letter}"

    @property
    def standard_name(self) -> str:
        names = SEMITONE_TO_SHARP if self.pitch_class in (1, 6, 8, 10) else SEMITONE_TO_FLAT
        root = names[self.pitch_class]
        if self.letter == 'A':
            # Preferred minor naming
            minor_display = {
                'C': 'C minor', 'C#': 'C# minor', 'D': 'D minor', 'D#': 'Eb minor',
                'E': 'E minor', 'F': 'F minor', 'F#': 'F# minor', 'G': 'G minor',
                'G#': 'G# minor', 'A': 'A minor', 'A#': 'Bb minor', 'B': 'B minor'
            }
            return minor_display.get(SEMITONE_TO_SHARP[self.pitch_class], f"{root} minor")
        else:
            major_display = {
                'C': 'C major', 'C#': 'Db major', 'D': 'D major', 'D#': 'Eb major',
                'E': 'E major', 'F': 'F major', 'F#': 'F# major', 'G': 'G major',
                'G#': 'Ab major', 'A': 'A major', 'A#': 'Bb major', 'B': 'B major'
            }
            return major_display.get(SEMITONE_TO_SHARP[self.pitch_class], f"{root} major")

    def __str__(self) -> str:
        return f"{self.camelot} ({self.standard_name})"

    @classmethod
    def from_camelot(cls, code: str) -> MusicalKey:
        """Parse string like '8A', '8a', '11B', '04A'."""
        cleaned = code.strip().upper()
        match = re.match(r'^0*([1-9]|1[0-2])([AB])$', cleaned)
        if not match:
            raise ValueError(f"Invalid Camelot code: {code}")
        number = int(match.group(1))
        letter = match.group(2)
        semitone = CAMELOT_TO_SEMITONE[(number, letter)]
        mode = 'minor' if letter == 'A' else 'major'
        return cls(number=number, letter=letter, pitch_class=semitone, mode=mode)

    @classmethod
    def from_pitch_mode(cls, pitch_class: int, mode: str) -> MusicalKey:
        """Create MusicalKey from pitch class (0-11) and mode ('major'/'minor')."""
        pitch_class = pitch_class % 12
        is_minor = mode.lower().startswith('min') or mode.lower() == 'm'
        if is_minor:
            number = MINOR_TO_CAMELOT[pitch_class]
            letter = 'A'
            mode_str = 'minor'
        else:
            number = MAJOR_TO_CAMELOT[pitch_class]
            letter = 'B'
            mode_str = 'major'
        return cls(number=number, letter=letter, pitch_class=pitch_class, mode=mode_str)

    @classmethod
    def from_open_key(cls, code: str) -> MusicalKey:
        """Parse Traktor Open Key notation ('1m' = A minor, '1d' = C major)."""
        match = re.match(r'^0*([1-9]|1[0-2])([dm])$', code.strip().lower())
        if not match:
            raise ValueError(f"Invalid Open Key code: {code}")
        number = (int(match.group(1)) + 6) % 12 + 1
        return cls.from_camelot(f"{number}{'A' if match.group(2) == 'm' else 'B'}")

    @classmethod
    def parse(cls, text: str) -> Optional[MusicalKey]:
        """
        Parse a whole field that contains only a key: Camelot ('8A', '08a', '8 A'),
        Open Key ('1m', '6d') or a key name ('C', 'F#m', 'Ab minor', 'Bb maj').
        """
        if not text:
            return None
        raw = text.strip().replace('♯', '#').replace('♭', 'b')

        for parser in (cls.from_camelot, cls.from_open_key):
            try:
                return parser(raw.replace(' ', ''))
            except ValueError:
                pass

        match = re.match(r'^([A-Ga-g])([#b]?)\s*(maj(?:or)?|min(?:or)?|m)?$', raw, re.IGNORECASE)
        if not match:
            return None
        pitch = NOTE_TO_SEMITONE[(match.group(1) + match.group(2)).upper()]
        mode_part = (match.group(3) or '').lower()
        mode = 'minor' if mode_part.startswith('min') or mode_part == 'm' else 'major'
        return cls.from_pitch_mode(pitch, mode)


_CAMELOT_IN_TEXT = re.compile(r'(?<![\w#.])0?([1-9]|1[0-2])([AB])(?![\w#])')
# Note letter must be uppercase and a mode is required, so ordinary words
# ("a great song", "Bass") are never mistaken for keys.
_KEYNAME_IN_TEXT = re.compile(r'(?<![\w#])([A-G])([#b♯♭]?)\s?(major|minor|maj|min|m)(?![\w#])')


def extract_key(text: Optional[str]) -> Optional[MusicalKey]:
    """Find a key inside free text such as a comment ('8A - Energy 6', 'Key: F# minor')."""
    if not text:
        return None
    whole = MusicalKey.parse(text)
    if whole:
        return whole
    match = _CAMELOT_IN_TEXT.search(text)
    if match:
        return MusicalKey.from_camelot(match.group(1) + match.group(2))
    match = _KEYNAME_IN_TEXT.search(text)
    if match:
        return MusicalKey.parse(''.join(match.groups()))
    return None


# Transition evaluation and scoring
def camelot_distance(k1: MusicalKey, k2: MusicalKey) -> int:
    """Number of steps on the 12-hour wheel (ignoring mode). 0 to 6."""
    diff = abs(k1.number - k2.number)
    return min(diff, 12 - diff)


def transition_score(k1: MusicalKey, k2: MusicalKey) -> Tuple[float, str]:
    """
    Score the musical compatibility between two keys.
    Returns (penalty, description). Lower penalty = smoother transition.

    Camelot DJ Rules:
    - Same Key (e.g. 8A -> 8A): 0 penalty ("Exact Key Match")
    - Relative Major/Minor (e.g. 8A <-> 8B): 0.2 penalty ("Relative Major/Minor")
    - Adjacent step on wheel, same mode (e.g. 8A -> 9A or 8A -> 7A): 0.5 penalty ("Harmonic Step +1 / -1")
    - Diagonal step (e.g. 8A -> 9B or 8A -> 7B): 1.5 penalty ("Diagonal Step")
    - Energy Boost / Half-Step (+7 semitones / +1 on Camelot or pitch shifts):
      - 2 steps on wheel (e.g. 8A -> 10A): 2.5 penalty ("Energy Boost / Two Steps")
    - 3-5 steps on wheel: 4.0 - 7.0 penalty
    - Opposite wheel (6 steps, e.g. 8A -> 2A): 8.0 penalty ("Tritone / Opposite Key")
    """
    if k1 == k2:
        return 0.0, "Exact key match"

    wheel_dist = camelot_distance(k1, k2)
    same_mode = (k1.letter == k2.letter)

    if wheel_dist == 0 and not same_mode:
        return 0.2, "Relative major/minor"

    if wheel_dist == 1:
        if same_mode:
            step_dir = "+1" if (k2.number - k1.number) % 12 == 1 else "-1"
            return 0.5, f"Harmonic step ({step_dir})"
        else:
            return 1.4, "Diagonal harmonic step"

    if wheel_dist == 2:
        if same_mode:
            return 2.5, "Two-step energy jump"
        else:
            return 3.2, "Two-step mode shift"

    if wheel_dist == 3:
        return 4.5, "Three-step shift"

    if wheel_dist == 4:
        return 6.0, "Four-step shift"

    if wheel_dist == 5:
        return 7.0, "Five-step shift"

    # wheel_dist == 6
    return 8.5, "Opposite wheel clash"
