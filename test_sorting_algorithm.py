import itertools
import random
import time
import unittest

import numpy as np

from camelot_music_sorter.camelot import MusicalKey, transition_score
from camelot_music_sorter.optimizer import _exact, path_cost, solve
from camelot_music_sorter.sorter import (
    SMOOTH_THRESHOLD, HarmonicPlaylistSorter, artist_names, calculate_pairwise_cost, musical_cost_matrix,
)
from test_camelot_sorter import keyed


def brute_force(C, start=None):
    n = len(C)
    perms = itertools.permutations(range(n))
    if start is not None:
        perms = (p for p in perms if p[0] == start)
    return min(path_cost(list(p), C) for p in perms)


def random_playlist(n, rng):
    return [keyed(i, f"{rng.randint(1, 12)}{rng.choice('AB')}", rng.choice([0, 100, 122, 126, 140, 174]),
                  artist=f"Artist {rng.randint(0, n // 2)}") for i in range(n)]


class TestOptimizer(unittest.TestCase):
    def test_exact_solver_matches_brute_force_on_asymmetric_costs(self):
        rng = np.random.default_rng(1)
        for trial in range(15):
            C = rng.uniform(0, 10, (7, 7))
            start = None if trial % 2 else int(rng.integers(7))
            route = _exact(C, start)
            with self.subTest(trial=trial):
                self.assertEqual(sorted(route), list(range(7)))
                if start is not None:
                    self.assertEqual(route[0], start)
                self.assertAlmostEqual(path_cost(route, C), brute_force(C, start))

    def test_local_search_reaches_exact_optimum_beyond_exact_limit(self):
        sorter = HarmonicPlaylistSorter("balanced")
        rng = random.Random(5)
        for trial in range(3):
            C = sorter.objective_matrix(random_playlist(14, rng))
            heuristic = solve(C, seed=14)          # 14 > EXACT_LIMIT, so this runs local search
            with self.subTest(trial=trial):
                self.assertAlmostEqual(path_cost(heuristic, C), path_cost(_exact(C, None), C), delta=0.6)

    def test_fixed_start_with_local_search(self):
        rng = np.random.default_rng(2)
        C = rng.uniform(0, 5, (40, 40))
        route = solve(C, start=17, seed=0)
        self.assertEqual(route[0], 17)
        self.assertEqual(sorted(route), list(range(40)))

    def test_results_are_deterministic(self):
        C = np.random.default_rng(3).uniform(0, 5, (50, 50))
        self.assertEqual(solve(C, seed=1), solve(C, seed=1))

    def test_large_playlist_finishes_within_time_budget(self):
        songs = random_playlist(400, random.Random(9))
        t = time.monotonic()
        out = HarmonicPlaylistSorter(time_limit=2.5).optimize_order(songs)
        self.assertLess(time.monotonic() - t, 6.0)
        self.assertEqual(sorted(s.id for s in out), sorted(s.id for s in songs))


class TestObjective(unittest.TestCase):
    def test_vectorized_costs_match_pairwise_function(self):
        songs = random_playlist(25, random.Random(4))
        M = musical_cost_matrix(songs)
        for i, a in enumerate(songs):
            for j, b in enumerate(songs):
                if i != j:
                    self.assertAlmostEqual(M[i, j], calculate_pairwise_cost(a, b)[0])

    def test_minimizes_number_of_clashes_first(self):
        clash = lambda order: sum(calculate_pairwise_cost(a, b)[0] > SMOOTH_THRESHOLD for a, b in zip(order, order[1:]))
        rng = random.Random(11)
        for trial in range(4):
            songs = random_playlist(8, rng)
            best = min(clash(p) for p in itertools.permutations(songs))
            with self.subTest(trial=trial):
                self.assertEqual(clash(HarmonicPlaylistSorter("balanced").optimize_order(songs)), best)

    def test_prefers_two_smooth_steps_over_one_clash(self):
        # 8A -> 10A -> 12A is two energy boosts; 8A -> 12A directly would be a clash.
        songs = [keyed(0, "8A"), keyed(1, "12A"), keyed(2, "10A")]
        out = HarmonicPlaylistSorter("balanced").optimize_order(songs)
        self.assertEqual(out[1].id, "2")

    def test_avoids_same_artist_back_to_back(self):
        songs = [keyed(0, "8A", artist="Daft Punk"), keyed(1, "8A", artist="Daft Punk"),
                 keyed(2, "8A", artist="Justice"), keyed(3, "8A", artist="Justice & Daft Punk"),
                 keyed(4, "8A", artist="Moderat")]
        out = HarmonicPlaylistSorter("balanced").optimize_order(songs)
        for a, b in zip(out, out[1:]):
            self.assertFalse(artist_names(a.artist) & artist_names(b.artist), f"{a.artist} -> {b.artist}")

    def test_duplicate_songs_are_not_adjacent(self):
        songs = [keyed(0, "8A"), keyed(1, "8A"), keyed(2, "9A")]
        songs[1].persistent_id = songs[0].persistent_id
        out = HarmonicPlaylistSorter("balanced").optimize_order(songs)
        self.assertNotEqual(out[0].persistent_id, out[1].persistent_id)
        self.assertNotEqual(out[1].persistent_id, out[2].persistent_id)

    def test_build_energy_orders_tempo_upwards(self):
        songs = [keyed(i, "8A", bpm) for i, bpm in enumerate([128, 120, 126, 122, 124])]
        out = HarmonicPlaylistSorter("gradual_build").optimize_order(songs)
        self.assertEqual([s.bpm for s in out], [120, 122, 124, 126, 128])

    def test_artist_name_splitting(self):
        self.assertEqual(artist_names("Meduza, Becky Hill & Goodboys"), {"meduza", "becky hill", "goodboys"})
        self.assertEqual(artist_names("Calvin Harris feat. Rihanna"), {"calvin harris", "rihanna"})
        self.assertEqual(artist_names("Axwell"), {"axwell"})


class TestCamelotRules(unittest.TestCase):
    def test_refined_moves(self):
        k = MusicalKey.from_camelot
        cost = lambda a, b: transition_score(k(a), k(b))[0]
        self.assertLess(cost("8A", "9B"), cost("8A", "7B"))      # minor +1 to major is the natural diagonal
        self.assertLess(cost("8B", "7A"), cost("8B", "9A"))      # major -1 to minor
        self.assertLess(cost("8A", "10A"), cost("8A", "6A"))     # energy boost vs energy drop
        self.assertLessEqual(cost("8A", "10A"), SMOOTH_THRESHOLD)
        self.assertLess(cost("8A", "3A"), cost("8A", "1A"))      # semitone lift beats other far jumps
        self.assertGreater(cost("8A", "3A"), SMOOTH_THRESHOLD)
        self.assertEqual(transition_score(k("8A"), k("3A"))[1], "Semitone lift (cut, don't blend)")


if __name__ == "__main__":
    unittest.main()
