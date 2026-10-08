"""
Harmonic playlist ordering and removal suggestions based on Camelot DJ rules.

Ordering is an open-path, asymmetric travelling-salesperson problem solved by
`optimizer.solve`. The objective is lexicographic in practice: every clash
(a transition above SMOOTH_THRESHOLD) carries a large fixed penalty, so the
solver first minimizes the number of clashes, then total key/tempo friction,
then soft preferences (no back-to-back artists, rising tempo when building
energy).
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .camelot import MusicalKey, transition_score
from .optimizer import solve, solve_slots
from .song_model import Song

SMOOTH_THRESHOLD = 2.5
CLASH_WEIGHT = 10.0
SAME_ARTIST_PENALTY = 0.6
DUPLICATE_PENALTY = 25.0
BUILD_STEP_BONUS = 0.15
TEMPO_DROP_PENALTY = 0.1


@dataclass
class TransitionInfo:
    from_song: Song
    to_song: Song
    penalty: float
    description: str
    is_smooth: bool
    is_unknown: bool = False


@dataclass
class RemovalSuggestion:
    song: Song
    reason: str
    isolated_clash_score: float
    alternative_suggestion: str


@dataclass
class SortResult:
    original_songs: List[Song]
    sorted_songs: List[Song]
    transitions: List[TransitionInfo]
    suggestions_to_remove: List[RemovalSuggestion]
    initial_total_penalty: float
    final_total_penalty: float
    improvement_percent: float
    unknown_key_songs: List[Song] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        scored = [t for t in self.transitions if not t.is_unknown]
        return {
            "track_count": len(self.sorted_songs),
            "known_key_count": len(self.sorted_songs) - len(self.unknown_key_songs),
            "unknown_key_count": len(self.unknown_key_songs),
            "initial_penalty": round(self.initial_total_penalty, 2),
            "final_penalty": round(self.final_total_penalty, 2),
            "improvement_percent": round(self.improvement_percent, 1),
            "removals_suggested": len(self.suggestions_to_remove),
            "scored_transitions": len(scored),
            "smooth_transitions": sum(1 for t in scored if t.is_smooth),
            "rough_transitions": sum(1 for t in scored if not t.is_smooth),
        }


def calculate_pairwise_cost(s1: Song, s2: Song) -> Tuple[float, str]:
    """Mixing cost from s1 into s2 (key compatibility plus a tempo penalty)."""
    if not s1.resolved_key or not s2.resolved_key:
        return 5.0, "Key unknown"

    cost, desc = transition_score(s1.resolved_key, s2.resolved_key)

    if s1.bpm > 0 and s2.bpm > 0:
        # Half/double time mixes are fine (e.g. 87 -> 174).
        bpm_diff = min(abs(s2.bpm - s1.bpm), abs(s2.bpm - 2 * s1.bpm), abs(s2.bpm - 0.5 * s1.bpm))
        pct = bpm_diff / s1.bpm
        # Up to ~6% can be beatmatched without audible pitch/tempo artifacts.
        if pct > 0.06:
            cost += min(4.0, (pct - 0.06) * 25)
            desc += f" (tempo jump {s1.bpm:.0f}→{s2.bpm:.0f} BPM)"

    return cost, desc


def evaluate_playlist_order(songs: List[Song]) -> Tuple[float, List[TransitionInfo]]:
    """Total penalty over transitions between songs with known keys, plus the transition list."""
    total = 0.0
    transitions = []
    for a, b in zip(songs, songs[1:]):
        unknown = not a.resolved_key or not b.resolved_key
        cost, desc = calculate_pairwise_cost(a, b)
        if not unknown:
            total += cost
        transitions.append(TransitionInfo(a, b, cost, desc, (not unknown) and cost <= SMOOTH_THRESHOLD, unknown))
    return total, transitions


def _key_index(k: MusicalKey) -> int:
    return (k.number - 1) * 2 + (0 if k.letter == "A" else 1)


_KEYS = [MusicalKey.from_camelot(f"{n}{l}") for n in range(1, 13) for l in "AB"]
_KEY_COST = np.array([[transition_score(a, b)[0] for b in _KEYS] for a in _KEYS])
_ARTIST_SPLIT = re.compile(r"\s*(?:,|&|\+|/|\bfeat\.?|\bft\.?|\bfeaturing\b|\bwith\b|\bx\b|\bvs\.?|\band\b)\s*")


def artist_names(artist: str) -> frozenset:
    return frozenset(p for p in (x.strip() for x in _ARTIST_SPLIT.split((artist or "").lower())) if p)


def _key_known_mask(songs: List[Song]) -> np.ndarray:
    has = np.array([s.resolved_key is not None for s in songs], dtype=bool)
    return has[:, None] & has[None, :]


def musical_cost_matrix(songs: List[Song]) -> np.ndarray:
    """Vectorized calculate_pairwise_cost for every ordered pair of songs."""
    k = np.array([_key_index(s.resolved_key) if s.resolved_key else 0 for s in songs], dtype=int)
    cost = _KEY_COST[k[:, None], k[None, :]].copy()
    bpm = np.array([s.bpm for s in songs], dtype=float)
    a, b = bpm[:, None], bpm[None, :]
    known = (a > 0) & (b > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = np.minimum.reduce([np.abs(b - a), np.abs(b - 2 * a), np.abs(b - 0.5 * a)]) / a
    cost += np.where(known & (pct > 0.06), np.minimum(4.0, (pct - 0.06) * 25), 0.0)
    cost = np.where(_key_known_mask(songs), cost, 5.0)
    np.fill_diagonal(cost, 0.0)
    return cost


class HarmonicPlaylistSorter:
    def __init__(self, energy_flow_preference: str = "gradual_build", time_limit: float = 2.5):
        """
        energy_flow_preference:
        - 'gradual_build': prefers stepping up the wheel (7A -> 8A -> 9A) and rising tempo
        - 'balanced': smoothest mixing in either direction
        """
        self.energy_flow_preference = energy_flow_preference
        self.time_limit = time_limit

    def objective_matrix(self, songs: List[Song]) -> np.ndarray:
        musical = musical_cost_matrix(songs)
        keyed = _key_known_mask(songs)
        obj = musical + CLASH_WEIGHT * ((musical > SMOOTH_THRESHOLD) & keyed)

        names = [artist_names(s.artist) for s in songs]
        pids = [s.persistent_id for s in songs]
        n = len(songs)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                if pids[i] == pids[j]:
                    obj[i, j] += DUPLICATE_PENALTY
                elif names[i] & names[j]:
                    obj[i, j] += SAME_ARTIST_PENALTY

        if self.energy_flow_preference == "gradual_build":
            num = np.array([s.resolved_key.number if s.resolved_key else 0 for s in songs])
            obj -= BUILD_STEP_BONUS * ((((num[None, :] - num[:, None]) % 12) == 1) & keyed)
            bpm = np.array([s.bpm for s in songs], dtype=float)
            a, b = bpm[:, None], bpm[None, :]
            with np.errstate(divide="ignore", invalid="ignore"):
                drop = (a > 0) & (b > 0) & (b < 0.995 * a) & (np.abs(b - 0.5 * a) > 0.03 * a)
                obj += np.where(drop, TEMPO_DROP_PENALTY + np.minimum(0.9, (a - b) / a * 8), 0.0)

        np.fill_diagonal(obj, 0.0)
        return obj

    def optimize_order(self, songs: List[Song], start_id: Optional[str] = None) -> List[Song]:
        """Order songs with known keys for the smoothest harmonic path, optionally from a fixed opener."""
        if len(songs) <= 1:
            return list(songs)
        start = next((i for i, s in enumerate(songs) if s.id == start_id), None) if start_id else None
        route = solve(self.objective_matrix(songs), start=start, seed=len(songs), time_limit=self.time_limit)
        return [songs[i] for i in route]

    def detect_removal_suggestions(self, sorted_songs: List[Song]) -> List[RemovalSuggestion]:
        """
        Flag songs that can't be mixed in smoothly:
        - Tonal outliers: a small minority of songs 4+ wheel steps from the
          playlist's tonal center with no compatible partner among the rest.
        - Bottlenecks: songs whose neighbours mix well with each other but
          both clash with the song in between.
        """
        known = [s for s in sorted_songs if s.resolved_key]
        n = len(known)
        if n < 4:
            return []

        def dist_to(hour: int, s: Song) -> int:
            d = abs(hour - s.resolved_key.number)
            return min(d, 12 - d)

        center = min(range(1, 13), key=lambda h: (sum(dist_to(h, s) for s in known), h))
        far = [s for s in known if dist_to(center, s) >= 4]
        suggestions: Dict[str, RemovalSuggestion] = {}

        if far and len(far) <= max(1, int(0.25 * n)):
            far_ids = {s.id for s in far}
            core = [s for s in known if s.id not in far_ids]
            for s in far:
                best = min(min(transition_score(s.resolved_key, o.resolved_key)[0],
                               transition_score(o.resolved_key, s.resolved_key)[0]) for o in core)
                if best >= SMOOTH_THRESHOLD:
                    k = s.resolved_key
                    if len(far) == 1:
                        why = " and no other song mixes into it smoothly."
                    else:
                        keys = ", ".join(sorted({f.resolved_key.camelot for f in far}, key=lambda c: (int(c[:-1]), c)))
                        why = (f". It's one of {len(far)} songs in distant keys ({keys}); "
                               f"reaching them from the rest of the set forces a key clash.")
                    suggestions[s.id] = RemovalSuggestion(
                        song=s,
                        reason=(f"{k.camelot} ({k.standard_name}) is {dist_to(center, s)} steps from this "
                                f"playlist's tonal center ({center}A/{center}B){why}"),
                        isolated_clash_score=round(best + dist_to(center, s), 2),
                        alternative_suggestion=(f"Move it to a set around {k.camelot}, or add a bridge track in "
                                                f"{self._bridge_hint(center, k.number)}."),
                    )

        for i in range(1, len(known) - 1):
            prev, song, nxt = known[i - 1], known[i], known[i + 1]
            if song.id in suggestions:
                continue
            c_in, _ = transition_score(prev.resolved_key, song.resolved_key)
            c_out, _ = transition_score(song.resolved_key, nxt.resolved_key)
            bridge, _ = transition_score(prev.resolved_key, nxt.resolved_key)
            if min(c_in, c_out) >= 4.0 and bridge <= SMOOTH_THRESHOLD:
                k = song.resolved_key
                suggestions[song.id] = RemovalSuggestion(
                    song=song,
                    reason=(f"{k.camelot} clashes with both neighbours ({prev.resolved_key.camelot} and "
                            f"{nxt.resolved_key.camelot}), which mix smoothly into each other without it."),
                    isolated_clash_score=round((c_in + c_out) / 2, 2),
                    alternative_suggestion="Remove it, or swap in a track in a compatible key.",
                )

        return sorted(suggestions.values(), key=lambda x: x.isolated_clash_score, reverse=True)

    @staticmethod
    def _bridge_hint(center: int, target: int) -> str:
        diff = (target - center) % 12
        step = 1 if diff <= 6 else -1
        mid = (center - 1 + step * (min(diff, 12 - diff) // 2)) % 12 + 1
        return f"{mid}A/{mid}B"

    def arrange_order(self, songs: List[Song], keep_ids: Sequence[str] = (),
                      manual: Optional[Dict[str, int]] = None) -> List[Song]:
        """
        Order `songs` top to bottom while respecting the user's choices:
        - `keep_ids` stay, in that order, at the top of the playlist;
        - each `manual` song is pinned at its requested position (clamped to
          the nearest position that is still open);
        - every other song is placed by the optimizer around them, with
          unknown-key songs at the bottom of the open positions.
        """
        by_id = {s.id: s for s in songs}
        index = {s.id: i for i, s in enumerate(songs)}
        n = len(songs)
        slots: List[Optional[int]] = [None] * n
        taken = set()

        for pos, sid in enumerate(i for i in dict.fromkeys(keep_ids) if i in by_id):
            slots[pos] = index[sid]
            taken.add(sid)

        pins = sorted(((p, sid) for sid, p in (manual or {}).items() if sid in by_id and sid not in taken),
                      key=lambda x: (x[0], x[1]))
        for want, sid in pins:
            open_pos = [p for p in range(n) if slots[p] is None]
            want = min(max(int(want), 0), n - 1)
            pos = min(open_pos, key=lambda p: (abs(p - want), p))
            slots[pos] = index[sid]
            taken.add(sid)

        free_known = [index[s.id] for s in songs if s.id not in taken and s.resolved_key]
        free_unknown = [index[s.id] for s in songs if s.id not in taken and not s.resolved_key]
        open_pos = [p for p in range(n) if slots[p] is None]
        if free_unknown:
            for p, i in zip(open_pos[len(open_pos) - len(free_unknown):], free_unknown):
                slots[p] = i
            open_pos = open_pos[:len(open_pos) - len(free_unknown)]

        route = slots
        if free_known:
            # Only the edge into the first filled slot after the last open one can
            # affect placement, and edges into unknown-key songs all cost the same.
            cut = open_pos[-1] + 1
            if cut < n and songs[slots[cut]].resolved_key:
                cut += 1
            route = solve_slots(self.objective_matrix(songs), slots[:cut], free_known,
                                seed=n, time_limit=self.time_limit) + slots[cut:]
        return [songs[i] for i in route]

    def insert(self, ordered: List[Song], new_songs: List[Song]) -> List[Song]:
        """Add songs one at a time at their cheapest position, leaving the rest of the order untouched."""
        result = list(ordered)
        for song in new_songs:
            seq = result + [song]
            C = self.objective_matrix(seq)
            m = len(result)
            best_pos, best_delta = m, None
            for pos in range(m + 1):
                prev = pos - 1 if pos > 0 else None
                nxt = pos if pos < m else None
                delta = (C[prev, m] if prev is not None else 0.0) + (C[m, nxt] if nxt is not None else 0.0)
                if prev is not None and nxt is not None:
                    delta -= C[prev, nxt]
                if best_delta is None or delta < best_delta - 1e-9:
                    best_pos, best_delta = pos, delta
            result.insert(best_pos, song)
        return result

    def analyze_order(self, original: List[Song], ordered: List[Song]) -> SortResult:
        init_penalty, _ = evaluate_playlist_order([s for s in original if s.resolved_key])
        final_penalty, transitions = evaluate_playlist_order(ordered)

        improvement = 0.0
        if init_penalty > 0:
            improvement = max(0.0, (init_penalty - final_penalty) / init_penalty * 100.0)

        return SortResult(
            original_songs=original,
            sorted_songs=ordered,
            transitions=transitions,
            suggestions_to_remove=self.detect_removal_suggestions(ordered),
            initial_total_penalty=init_penalty,
            final_total_penalty=final_penalty,
            improvement_percent=improvement,
            unknown_key_songs=[s for s in ordered if not s.resolved_key],
        )

    def arrange(self, songs: List[Song], keep_ids: Sequence[str] = (),
                manual: Optional[Dict[str, int]] = None) -> SortResult:
        return self.analyze_order(songs, self.arrange_order(songs, keep_ids, manual))

    def sort_and_analyze(self, songs: List[Song], start_id: Optional[str] = None) -> SortResult:
        manual = {start_id: 0} if start_id and any(s.id == start_id for s in songs) else None
        return self.arrange(songs, manual=manual)
