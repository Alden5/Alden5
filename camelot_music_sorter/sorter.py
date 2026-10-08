"""
Harmonic playlist ordering and outlier suggestion engine based on Camelot DJ rules.

Key Capabilities:
1. Optimal Harmonic Path Ordering:
   Solves an Asymmetric / Symmetric Traveling Salesperson Problem (TSP) using 2-opt / nearest-neighbor
   with DJ harmonic mixing transition heuristics (same key, relative major/minor, adjacent hour step +1/-1,
   energy boost +2, BPM progression penalty).
2. Outlier / Removal Suggestion:
   Identifies songs that severely clash with the playlist's dominant harmonic cluster
   or cause large harmonic ruptures that cannot be smoothed out.
"""

from __future__ import annotations
import math
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

from .camelot import MusicalKey, transition_score, camelot_distance
from .song_model import Song


@dataclass
class TransitionInfo:
    from_song: Song
    to_song: Song
    penalty: float
    description: str
    is_smooth: bool


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

    def summary(self) -> Dict[str, Any]:
        return {
            "track_count": len(self.sorted_songs),
            "initial_penalty": round(self.initial_total_penalty, 2),
            "final_penalty": round(self.final_total_penalty, 2),
            "improvement_percent": round(self.improvement_percent, 1),
            "removals_suggested": len(self.suggestions_to_remove),
            "smooth_transitions": sum(1 for t in self.transitions if t.is_smooth),
            "rough_transitions": sum(1 for t in self.transitions if not t.is_smooth),
        }


def calculate_pairwise_cost(s1: Song, s2: Song) -> Tuple[float, str]:
    """Calculate musical mixing cost between s1 and s2."""
    if not s1.resolved_key or not s2.resolved_key:
        return 5.0, "Unknown key"

    cost, desc = transition_score(s1.resolved_key, s2.resolved_key)

    # Optional BPM penalty if BPM is known (> 0)
    if s1.bpm > 0 and s2.bpm > 0:
        bpm_ratio = s2.bpm / s1.bpm
        # Check normal or half/double time
        diff_normal = abs(s2.bpm - s1.bpm)
        diff_double = abs(s2.bpm - 2 * s1.bpm)
        diff_half = abs(s2.bpm - 0.5 * s1.bpm)
        min_bpm_diff = min(diff_normal, diff_double, diff_half)

        if min_bpm_diff > 15:
            cost += min(3.0, (min_bpm_diff - 15) * 0.1)
            desc += f" (BPM shift: {s1.bpm:.0f}->{s2.bpm:.0f})"

    return cost, desc


def evaluate_playlist_order(songs: List[Song]) -> Tuple[float, List[TransitionInfo]]:
    """Evaluates the total harmonic penalty and transition list for a given sequence of songs."""
    if len(songs) <= 1:
        return 0.0, []

    total_cost = 0.0
    transitions = []
    for i in range(len(songs) - 1):
        cost, desc = calculate_pairwise_cost(songs[i], songs[i+1])
        total_cost += cost
        is_smooth = cost <= 2.5
        transitions.append(TransitionInfo(
            from_song=songs[i],
            to_song=songs[i+1],
            penalty=cost,
            description=desc,
            is_smooth=is_smooth
        ))

    return total_cost, transitions


class HarmonicPlaylistSorter:
    def __init__(self, energy_flow_preference: str = "gradual_build"):
        """
        energy_flow_preference:
        - 'gradual_build': prefers ascending Camelot numbers (e.g. 7A -> 8A -> 9A) for uplifting energy
        - 'balanced': minimizes transition friction in any direction
        """
        self.energy_flow_preference = energy_flow_preference

    def optimize_order(self, songs: List[Song]) -> List[Song]:
        """
        Finds the best track sequence to minimize harmonic clash using Nearest Neighbor + 2-Opt local search.
        """
        n = len(songs)
        if n <= 2:
            return list(songs)

        # Precompute cost matrix
        costs = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    c, _ = calculate_pairwise_cost(songs[i], songs[j])
                    # Bias slightly towards upward Camelot progression if gradual_build is requested
                    if self.energy_flow_preference == "gradual_build":
                        k1 = songs[i].resolved_key
                        k2 = songs[j].resolved_key
                        if k1 and k2 and (k2.number - k1.number) % 12 == 1:
                            c -= 0.1  # reward forward movement
                    costs[i][j] = c

        # Multiple restarts of Nearest Neighbor from different starting points to find the best seed
        best_route: Optional[List[int]] = None
        best_route_cost = float('inf')

        # Try starting from each song (or a representative sample if n is very large)
        start_indices = range(n) if n <= 40 else [0, n // 4, n // 2, 3 * n // 4]
        for start in start_indices:
            visited = [False] * n
            route = [start]
            visited[start] = True

            curr = start
            for _ in range(n - 1):
                next_song = -1
                next_cost = float('inf')
                for candidate in range(n):
                    if not visited[candidate] and costs[curr][candidate] < next_cost:
                        next_cost = costs[curr][candidate]
                        next_song = candidate
                route.append(next_song)
                visited[next_song] = True
                curr = next_song

            # Calculate total route cost
            route_cost = sum(costs[route[k]][route[k+1]] for k in range(n - 1))
            if route_cost < best_route_cost:
                best_route_cost = route_cost
                best_route = route

        if best_route is None:
            best_route = list(range(n))

        # 2-Opt Local Search optimization
        improved = True
        iterations = 0
        max_iterations = 200

        while improved and iterations < max_iterations:
            improved = False
            iterations += 1
            for i in range(n - 1):
                for j in range(i + 2, n):
                    # Cost before reversal of segment [i+1 : j]
                    # Old edges: (i -> i+1) and (j -> j+1 if j+1 < n)
                    curr_edges_cost = costs[best_route[i]][best_route[i+1]]
                    new_edges_cost = costs[best_route[i]][best_route[j]]

                    if j + 1 < n:
                        curr_edges_cost += costs[best_route[j]][best_route[j+1]]
                        new_edges_cost += costs[best_route[i+1]][best_route[j+1]]

                    # Inner segment reversal cost change
                    # If pairwise costs are symmetric or near-symmetric:
                    diff = new_edges_cost - curr_edges_cost
                    if diff < -1e-5:
                        # Reverse route from i+1 to j
                        best_route[i+1:j+1] = reversed(best_route[i+1:j+1])
                        best_route_cost += diff
                        improved = True
                        break
                if improved:
                    break

        return [songs[idx] for idx in best_route]

    def detect_removal_suggestions(self, sorted_songs: List[Song]) -> List[RemovalSuggestion]:
        """
        Suggests songs to remove:
        1. Severe Harmonic Outliers: A song whose key is far from all neighboring tracks (> 3 steps)
           and acts as a jarring bottleneck.
        2. Cluster Outliers: A lone song with an incompatible key compared to the playlist's dominant tonal center.
        """
        n = len(sorted_songs)
        if n < 4:
            return []

        suggestions: List[RemovalSuggestion] = []

        # Find global Camelot distribution and cluster center
        wheel_nums = [s.resolved_key.number for s in sorted_songs if s.resolved_key]
        if not wheel_nums:
            return []

        # Calculate average wheel distance of each song from the rest of the playlist
        for i, song in enumerate(sorted_songs):
            if not song.resolved_key:
                continue

            k = song.resolved_key
            prev_song = sorted_songs[i - 1] if i > 0 else None
            next_song = sorted_songs[i + 1] if i < n - 1 else None

            # Calculate isolated clash (how much friction this song introduces to neighbors)
            clash_penalty = 0.0
            num_neighbors = 0

            if prev_song and prev_song.resolved_key:
                cost_prev, _ = transition_score(prev_song.resolved_key, k)
                clash_penalty += cost_prev
                num_neighbors += 1

            if next_song and next_song.resolved_key:
                cost_next, _ = transition_score(k, next_song.resolved_key)
                clash_penalty += cost_next
                num_neighbors += 1

            avg_clash = clash_penalty / max(1, num_neighbors)

            # Check cluster compatibility: average distance to all other songs in the playlist
            other_distances = [
                camelot_distance(k, s.resolved_key)
                for s in sorted_songs
                if s.id != song.id and s.resolved_key
            ]
            avg_cluster_dist = sum(other_distances) / max(1, len(other_distances))

            # Case A: Track is sandwiched between two tracks and creates a bottleneck
            bridge_cost = 0.0
            if prev_song and next_song and prev_song.resolved_key and next_song.resolved_key:
                bridge_cost, _ = transition_score(prev_song.resolved_key, next_song.resolved_key)

            if prev_song and next_song and avg_clash >= 4.0 and bridge_cost < avg_clash - 1.5:
                reason = (
                    f"Harmonic bottleneck: Key {k.camelot} clashes with surrounding tracks "
                    f"({prev_song.resolved_key.camelot} and {next_song.resolved_key.camelot}). "
                    f"Removing this track allows a smooth direct mix."
                )
                alt = f"Move to a set centered around {k.camelot} or use a bridge track."
                suggestions.append(RemovalSuggestion(
                    song=song,
                    reason=reason,
                    isolated_clash_score=round(avg_clash, 2),
                    alternative_suggestion=alt
                ))
            # Case B: Track is placed at end/beginning or boundary but is an extreme cluster outlier
            # (e.g. 4+ Camelot steps away from the rest of the playlist)
            elif avg_clash >= 5.5 and avg_cluster_dist >= 3.5:
                reason = (
                    f"Harmonic outlier: Key {k.camelot} ({k.standard_name}) is {avg_cluster_dist:.1f} steps "
                    f"away from the playlist's core tonal cluster."
                )
                alt = f"Better suited for a separate playlist or energy shift."
                suggestions.append(RemovalSuggestion(
                    song=song,
                    reason=reason,
                    isolated_clash_score=round(avg_clash + avg_cluster_dist, 2),
                    alternative_suggestion=alt
                ))
            elif avg_clash >= 7.0:
                reason = (
                    f"Extreme clash: Transition into or out of key {k.camelot} ({k.standard_name}) "
                    f"has high dissonance with adjacent track."
                )
                alt = f"Reposition or replace with a harmonically adjacent song."
                suggestions.append(RemovalSuggestion(
                    song=song,
                    reason=reason,
                    isolated_clash_score=round(avg_clash, 2),
                    alternative_suggestion=alt
                ))

        # Sort suggestions by clash score descending
        suggestions.sort(key=lambda x: x.isolated_clash_score, reverse=True)
        return suggestions

    def sort_and_analyze(self, songs: List[Song]) -> SortResult:
        """Runs complete sorting pipeline, evaluation, and outlier detection."""
        init_penalty, _ = evaluate_playlist_order(songs)
        sorted_tracks = self.optimize_order(songs)
        final_penalty, transitions = evaluate_playlist_order(sorted_tracks)

        improvement = 0.0
        if init_penalty > 0:
            improvement = max(0.0, ((init_penalty - final_penalty) / init_penalty) * 100.0)

        suggestions = self.detect_removal_suggestions(sorted_tracks)

        return SortResult(
            original_songs=songs,
            sorted_songs=sorted_tracks,
            transitions=transitions,
            suggestions_to_remove=suggestions,
            initial_total_penalty=init_penalty,
            final_total_penalty=final_penalty,
            improvement_percent=improvement
        )
