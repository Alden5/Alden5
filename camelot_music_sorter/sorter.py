"""
Harmonic playlist ordering and removal suggestions based on Camelot DJ rules.

Ordering is an open-path travelling-salesperson problem over transition costs,
solved with multi-start nearest neighbour followed by 2-opt and Or-opt local
search. Costs may be asymmetric (the energy-build preference rewards moving
up the wheel), so segment reversals account for the reversed internal edges.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .camelot import camelot_distance, transition_score
from .song_model import Song

SMOOTH_THRESHOLD = 2.5


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


class HarmonicPlaylistSorter:
    def __init__(self, energy_flow_preference: str = "gradual_build", max_passes: int = 50):
        """
        energy_flow_preference:
        - 'gradual_build': slightly prefers moving up the wheel (7A -> 8A -> 9A) for rising energy
        - 'balanced': minimizes friction in either direction
        """
        self.energy_flow_preference = energy_flow_preference
        self.max_passes = max_passes

    def _cost_matrix(self, songs: List[Song]) -> List[List[float]]:
        n = len(songs)
        costs = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                c, _ = calculate_pairwise_cost(songs[i], songs[j])
                if self.energy_flow_preference == "gradual_build":
                    k1, k2 = songs[i].resolved_key, songs[j].resolved_key
                    if (k2.number - k1.number) % 12 == 1:
                        c -= 0.1
                costs[i][j] = c
        return costs

    @staticmethod
    def _route_cost(route: List[int], costs: List[List[float]]) -> float:
        return sum(costs[a][b] for a, b in zip(route, route[1:]))

    @staticmethod
    def _nearest_neighbour(start: int, costs: List[List[float]]) -> List[int]:
        n = len(costs)
        visited = [False] * n
        route = [start]
        visited[start] = True
        for _ in range(n - 1):
            cur = route[-1]
            nxt = min((j for j in range(n) if not visited[j]), key=lambda j: costs[cur][j])
            visited[nxt] = True
            route.append(nxt)
        return route

    @staticmethod
    def _two_opt_pass(route: List[int], costs: List[List[float]], fixed_start: bool = False) -> bool:
        n = len(route)
        improved = False
        a = 1 if fixed_start else 0
        while a < n - 1:
            fwd = [0.0] * n
            rev = [0.0] * n
            for t in range(n - 1):
                fwd[t + 1] = fwd[t] + costs[route[t]][route[t + 1]]
                rev[t + 1] = rev[t] + costs[route[t + 1]][route[t]]
            applied = False
            for b in range(a + 1, n):
                old = fwd[b] - fwd[a]
                new = rev[b] - rev[a]
                if a > 0:
                    old += costs[route[a - 1]][route[a]]
                    new += costs[route[a - 1]][route[b]]
                if b < n - 1:
                    old += costs[route[b]][route[b + 1]]
                    new += costs[route[a]][route[b + 1]]
                if new - old < -1e-9:
                    route[a:b + 1] = route[a:b + 1][::-1]
                    improved = applied = True
                    break
            if not applied:
                a += 1
        return improved

    @staticmethod
    def _or_opt_pass(route: List[int], costs: List[List[float]], fixed_start: bool = False) -> bool:
        def edge(u: Optional[int], v: Optional[int]) -> float:
            return costs[u][v] if u is not None and v is not None else 0.0

        n = len(route)
        improved = False
        first = 1 if fixed_start else 0
        for i in range(first, n):
            node = route[i]
            prev = route[i - 1] if i > 0 else None
            nxt = route[i + 1] if i < n - 1 else None
            remove_delta = edge(prev, nxt) - edge(prev, node) - edge(node, nxt)
            rest = route[:i] + route[i + 1:]
            best_j, best_delta = None, -1e-9
            for j in range(first, len(rest) + 1):
                if j == i:
                    continue
                u = rest[j - 1] if j > 0 else None
                v = rest[j] if j < len(rest) else None
                delta = remove_delta + edge(u, node) + edge(node, v) - edge(u, v)
                if delta < best_delta:
                    best_j, best_delta = j, delta
            if best_j is not None:
                route[:] = rest[:best_j] + [node] + rest[best_j:]
                improved = True
        return improved

    def optimize_order(self, songs: List[Song], start_id: Optional[str] = None) -> List[Song]:
        """Order songs with known keys for the smoothest harmonic path, optionally from a fixed opener."""
        n = len(songs)
        start_idx = next((i for i, s in enumerate(songs) if s.id == start_id), None) if start_id else None
        if n <= 2:
            if n == 2 and start_idx is None:
                c01, _ = calculate_pairwise_cost(songs[0], songs[1])
                c10, _ = calculate_pairwise_cost(songs[1], songs[0])
                return list(songs) if c01 <= c10 else [songs[1], songs[0]]
            if n == 2 and start_idx == 1:
                return [songs[1], songs[0]]
            return list(songs)

        costs = self._cost_matrix(songs)
        if start_idx is not None:
            starts = [start_idx]
        else:
            starts = range(n) if n <= 60 else [round(i * (n - 1) / 11) for i in range(12)]
        route = min((self._nearest_neighbour(s, costs) for s in starts), key=lambda r: self._route_cost(r, costs))

        fixed = start_idx is not None
        for _ in range(self.max_passes):
            changed = self._two_opt_pass(route, costs, fixed)
            changed = self._or_opt_pass(route, costs, fixed) or changed
            if not changed:
                break
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

    def sort_and_analyze(self, songs: List[Song], start_id: Optional[str] = None) -> SortResult:
        known = [s for s in songs if s.resolved_key]
        unknown = [s for s in songs if not s.resolved_key]

        init_penalty, _ = evaluate_playlist_order(known)
        ordered = self.optimize_order(known, start_id) + unknown
        final_penalty, transitions = evaluate_playlist_order(ordered)

        improvement = 0.0
        if init_penalty > 0:
            improvement = max(0.0, (init_penalty - final_penalty) / init_penalty * 100.0)

        return SortResult(
            original_songs=songs,
            sorted_songs=ordered,
            transitions=transitions,
            suggestions_to_remove=self.detect_removal_suggestions(ordered),
            initial_total_penalty=init_penalty,
            final_total_penalty=final_penalty,
            improvement_percent=improvement,
            unknown_key_songs=unknown,
        )
