import itertools
import random
import time
import unittest

import numpy as np

from camelot_music_sorter.camelot import MusicalKey, transition_score
from camelot_music_sorter.optimizer import _exact, path_cost, solve, solve_slots
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


class TestManualOrdering(unittest.TestCase):
    def test_solve_slots_keeps_fixed_positions_and_is_optimal(self):
        rng = np.random.default_rng(3)
        for trial in range(25):
            n = 8
            C = rng.random((n, n)) * 5
            np.fill_diagonal(C, 0)
            r = random.Random(trial)
            ids = r.sample(range(n), 3)
            positions = r.sample(range(n), 3)
            slots = [None] * n
            for p, i in zip(positions, ids):
                slots[p] = i
            free = [i for i in range(n) if i not in ids]
            out = solve_slots(C, slots, free, seed=0, time_limit=1.0)
            self.assertEqual(sorted(out), list(range(n)))
            for p, i in zip(positions, ids):
                self.assertEqual(out[p], i)
            free_pos = [p for p in range(n) if slots[p] is None]
            best = min(path_cost([dict(zip(free_pos, perm)).get(p, slots[p]) for p in range(n)], C)
                       for perm in itertools.permutations(free))
            self.assertAlmostEqual(path_cost(out, C), best, places=6)

    def test_manual_song_stays_put_prefix_is_kept_and_rest_re_sorts(self):
        songs = random_playlist(30, random.Random(11))
        sorter = HarmonicPlaylistSorter(time_limit=0.5)
        order = [s.id for s in sorter.arrange(songs).sorted_songs]
        moved = order[25]
        new = [i for i in order if i != moved]
        new.insert(4, moved)
        result = sorter.arrange(songs, keep_ids=new[:4], manual={moved: 4, order[20]: 20})
        out = [s.id for s in result.sorted_songs]
        self.assertEqual(out[:5], new[:5])
        self.assertEqual(out[20], order[20])
        self.assertEqual(sorted(out), sorted(order))

    def test_out_of_range_and_colliding_pins_are_clamped(self):
        songs = [keyed(i, c) for i, c in enumerate(["8A", "9A", "10A", "3B", "4B"])]
        out = HarmonicPlaylistSorter().arrange_order(songs, keep_ids=["0", "1"], manual={"3": 0, "4": 99})
        ids = [s.id for s in out]
        self.assertEqual(ids[:3], ["0", "1", "3"])
        self.assertEqual(ids[-1], "4")

    def test_unknown_keys_go_last_unless_placed(self):
        songs = [keyed(0, "8A"), keyed(1, None), keyed(2, "9A"), keyed(3, "8B"), keyed(4, None)]
        sorter = HarmonicPlaylistSorter()
        ids = [s.id for s in sorter.arrange_order(songs)]
        self.assertEqual(set(ids[-2:]), {"1", "4"})
        ids = [s.id for s in sorter.arrange_order(songs, manual={"1": 0})]
        self.assertEqual(ids[0], "1")
        self.assertEqual(ids[-1], "4")

    def test_insert_uses_cheapest_spot_without_moving_others(self):
        base = [keyed(0, "6A"), keyed(1, "7A"), keyed(3, "9A"), keyed(4, "10A")]
        out = HarmonicPlaylistSorter(energy_flow_preference="balanced").insert(base, [keyed(2, "8A")])
        self.assertEqual([s.id for s in out], ["0", "1", "2", "3", "4"])

    def test_start_id_still_supported(self):
        songs = random_playlist(12, random.Random(5))
        result = HarmonicPlaylistSorter().sort_and_analyze(songs, start_id="7")
        self.assertEqual(result.sorted_songs[0].id, "7")


class TestRemovalPlanner(unittest.TestCase):
    def setUp(self):
        self.sorter = HarmonicPlaylistSorter()

    def core(self):
        return [keyed(i, c, 124) for i, c in enumerate(["8A", "9A", "8B", "9B", "10A", "10B", "9A", "8A"])]

    def test_removes_lone_outlier_first_and_reports_improvement(self):
        songs = self.core() + [keyed(20, "2B", 124)]
        plan = self.sorter.plan_removals(self.sorter.arrange_order(songs), 3)
        self.assertEqual(plan.steps[0].song.id, "20")
        self.assertGreater(plan.baseline.clashes, 0)
        self.assertEqual(plan.after.clashes, 0)
        self.assertLess(plan.after.friction, plan.baseline.friction)
        self.assertIn("fixes the key clash", plan.headline())

    def test_never_exceeds_budget_and_stops_when_nothing_helps(self):
        plan = self.sorter.plan_removals(self.sorter.arrange_order(self.core()), 5)
        self.assertEqual(plan.steps, [])
        self.assertTrue(plan.stopped_early)
        self.assertIn("Nothing worth removing", plan.headline())

        songs = self.core() + [keyed(20, "2B", 124), keyed(21, "3A", 90), keyed(22, "4B", 160)]
        plan = self.sorter.plan_removals(self.sorter.arrange_order(songs), 1)
        self.assertLessEqual(len(plan.steps), 1)

    def test_pair_of_outliers_removed_together_or_hinted(self):
        songs = self.core() + [keyed(20, "2B", 124), keyed(21, "2B", 124)]
        order = self.sorter.arrange_order(songs)
        plan = self.sorter.plan_removals(order, 1)
        self.assertEqual(plan.steps, [])
        self.assertEqual(plan.hint_budget, 2)
        self.assertIn("Allowing 2 removals", plan.hint)
        plan = self.sorter.plan_removals(order, 3)
        self.assertEqual({s.song.id for s in plan.steps}, {"20", "21"})
        self.assertEqual(plan.after.clashes, 0)

    def test_manual_songs_are_never_removed_and_keep_their_position(self):
        songs = self.core() + [keyed(20, "2B", 124)]
        order = self.sorter.arrange_order(songs, manual={"20": 3})
        plan = self.sorter.plan_removals(order, 3, manual_ids=["20"])
        removed = {s.song.id for s in plan.steps}
        self.assertNotIn("20", removed)
        pos = [s.id for s in plan.final_order].index("20")
        self.assertTrue(3 - len(removed) <= pos <= 3)

    def test_energy_flow_affects_sorting_order(self):
        # Two tracks with identical harmonic compatibility into opener (8A -> 9A)
        # One has smooth rising energy (5.0 -> 6.0), the other drops steeply (5.0 -> 1.0)
        s0 = keyed(0, "8A", 124)
        s0.energy = 5.0
        s1 = keyed(1, "9A", 124)
        s1.energy = 6.0
        s2 = keyed(2, "9A", 124)
        s2.energy = 1.0

        sorter = HarmonicPlaylistSorter(energy_flow_preference="gradual_build")
        res = sorter.optimize_order([s0, s1, s2], start_id="0")
        self.assertEqual(res[0].id, "0")
        # In gradual build, s1 (rising energy 6.0) is preferred right after s0 (5.0) over s2 (energy drop to 1.0)
        self.assertEqual(res[1].id, "1")
        self.assertEqual(res[2].id, "2")


if __name__ == "__main__":
    unittest.main()
