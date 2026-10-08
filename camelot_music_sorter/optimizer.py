"""
Open-path, asymmetric travelling-salesperson solver used to order playlists.

- Up to EXACT_LIMIT songs: exact Held-Karp dynamic programming.
- Larger: multi-start nearest neighbour, then iterated local search
  (best-improvement 2-opt + Or-opt with segment reversal, vectorized with
  numpy, kicked by double-bridge perturbations). The RNG is seeded, so the
  same playlist always produces the same order.

Costs are asymmetric (C[i][j] != C[j][i]), so reversing a segment accounts
for the cost of traversing its internal edges backwards.
"""

from __future__ import annotations
import random
import time
from typing import List, Optional

import numpy as np

EXACT_LIMIT = 13


def path_cost(route: List[int], C: np.ndarray) -> float:
    if len(route) < 2:
        return 0.0
    r = np.asarray(route)
    return float(C[r[:-1], r[1:]].sum())


def solve(C: np.ndarray, start: Optional[int] = None, seed: int = 0,
          time_limit: float = 2.5, iterations: Optional[int] = None) -> List[int]:
    """Return the visiting order (indices into C) with the lowest path cost found."""
    C = np.asarray(C, dtype=float)
    n = len(C)
    if n <= 1:
        return list(range(n))
    if n <= EXACT_LIMIT:
        return _exact(C, start)

    deadline = time.monotonic() + time_limit
    fixed = start is not None
    Cp = np.zeros((n + 1, n + 1))
    Cp[:n, :n] = C

    seeds = sorted(_nearest_neighbour_routes(C, start), key=lambda r: path_cost(r, C))[:3]
    best, best_cost = None, float("inf")
    for route in seeds:
        route = _local_search(route, Cp, fixed, deadline)
        cost = path_cost(route, C)
        if cost < best_cost:
            best, best_cost = route, cost

    rng = random.Random(seed)
    for _ in range(iterations if iterations is not None else _default_iterations(n)):
        if time.monotonic() > deadline or n - (1 if fixed else 0) < 4:
            break
        cand = _local_search(_double_bridge(best, rng, fixed), Cp, fixed, deadline)
        cost = path_cost(cand, C)
        if cost < best_cost - 1e-9:
            best, best_cost = cand, cost
    return best


def solve_slots(C: np.ndarray, slots: List[Optional[int]], free: List[int], seed: int = 0,
                time_limit: float = 2.5) -> List[int]:
    """
    Fill the empty (None) positions of `slots` with the songs in `free`,
    keeping every pre-filled position where it is, so the whole sequence has
    the lowest path cost found.
    """
    C = np.asarray(C, dtype=float)
    N = len(slots)
    free_pos = [p for p, s in enumerate(slots) if s is None]
    if len(free_pos) != len(free):
        raise ValueError("number of free songs must match number of empty slots")
    if not free:
        return list(slots)

    first = free_pos[0]
    if free_pos == list(range(first, N)):
        # Only the tail is open: an ordinary path problem starting from the last fixed song.
        if first == 0:
            route = solve(C[np.ix_(free, free)], seed=seed, time_limit=time_limit)
            return [free[i] for i in route]
        nodes = [slots[first - 1]] + list(free)
        route = solve(C[np.ix_(nodes, nodes)], start=0, seed=seed, time_limit=time_limit)
        return list(slots[:first]) + [nodes[i] for i in route[1:]]

    deadline = time.monotonic() + time_limit
    seq = list(slots)
    remaining = set(free)
    for p in free_pos:
        prev = seq[p - 1] if p > 0 else None
        nxt = slots[p + 1] if p + 1 < N else None

        def score(j: int) -> float:
            return (C[prev, j] if prev is not None else 0.0) + (C[j, nxt] if nxt is not None else 0.0)

        pick = min(sorted(remaining), key=score)
        seq[p] = pick
        remaining.remove(pick)
    return _anneal(seq, free_pos, C, random.Random(seed), deadline)


def _anneal(seq: List[int], free_pos: List[int], C: np.ndarray, rng: random.Random, deadline: float) -> List[int]:
    """Simulated annealing over the free positions: swaps anywhere, reversals inside a gap."""
    N = len(seq)
    Cl = C.tolist()
    gaps, run = [], [free_pos[0]]
    for p in free_pos[1:]:
        if p == run[-1] + 1:
            run.append(p)
        else:
            gaps.append(run)
            run = [p]
    gaps.append(run)
    long_gaps = [g for g in gaps if len(g) >= 2]

    def edges(ts) -> float:
        return sum(Cl[seq[t]][seq[t + 1]] for t in ts if 0 <= t < N - 1)

    cur = edges(range(N - 1))
    best, best_seq = cur, list(seq)
    iterations = min(150_000, 4000 * len(free_pos))
    t_start, t_end = 3.0, 0.02
    for it in range(iterations):
        if it % 2048 == 0 and time.monotonic() > deadline:
            break
        temp = t_start * (t_end / t_start) ** (it / iterations)
        if len(free_pos) < 2:
            break
        swap = not long_gaps or rng.random() < 0.5
        if swap:
            a, b = rng.sample(free_pos, 2)
            touched = {a - 1, a, b - 1, b}
            before = edges(touched)
            seq[a], seq[b] = seq[b], seq[a]
        else:
            a, b = sorted(rng.sample(rng.choice(long_gaps), 2))
            touched = range(a - 1, b + 1)
            before = edges(touched)
            seq[a:b + 1] = seq[a:b + 1][::-1]
        delta = edges(touched) - before
        if delta <= 0 or rng.random() < np.exp(-delta / temp):
            cur += delta
            if cur < best - 1e-9:
                best, best_seq = cur, list(seq)
        elif swap:
            seq[a], seq[b] = seq[b], seq[a]
        else:
            seq[a:b + 1] = seq[a:b + 1][::-1]
    return best_seq


def _default_iterations(n: int) -> int:
    if n <= 80:
        return 400
    if n <= 150:
        return 300
    if n <= 300:
        return 100
    if n <= 600:
        return 30
    return 10


def _exact(C: np.ndarray, start: Optional[int]) -> List[int]:
    n = len(C)
    full = 1 << n
    dp = np.full((full, n), np.inf)
    parent = np.full((full, n), -1, dtype=np.int8)
    for s in ([start] if start is not None else range(n)):
        dp[1 << s, s] = 0.0
    bits = 1 << np.arange(n)

    # dp[mask, j]: cheapest path visiting exactly `mask` and ending at j. Each
    # (mask | bit_j, j) is reached only from `mask`, so assignment suffices.
    for mask in range(1, full):
        row = dp[mask]
        if not np.isfinite(row).any():
            continue
        cand = row[:, None] + C
        best = cand.min(axis=0)
        arg = cand.argmin(axis=0)
        js = np.nonzero((mask & bits) == 0)[0]
        targets = mask | bits[js]
        dp[targets, js] = best[js]
        parent[targets, js] = arg[js]

    mask, j = full - 1, int(np.argmin(dp[full - 1]))
    route = []
    while j != -1:
        route.append(j)
        prev = int(parent[mask, j])
        mask ^= 1 << j
        j = prev
    return route[::-1]


def _nearest_neighbour_routes(C: np.ndarray, start: Optional[int]) -> List[List[int]]:
    n = len(C)
    if start is not None:
        starts = [start]
    elif n <= 60:
        starts = range(n)
    else:
        starts = sorted({round(i * (n - 1) / 11) for i in range(12)})
    routes = []
    for s in starts:
        visited = np.zeros(n, dtype=bool)
        visited[s] = True
        route = [s]
        for _ in range(n - 1):
            row = np.where(visited, np.inf, C[route[-1]])
            nxt = int(np.argmin(row))
            visited[nxt] = True
            route.append(nxt)
        routes.append(route)
    return routes


def _double_bridge(route: List[int], rng: random.Random, fixed: bool) -> List[int]:
    lo = 1 if fixed else 0
    a, b, c = sorted(rng.sample(range(lo, len(route)), 3))
    return route[:a] + route[b:c] + route[a:b] + route[c:]


def _local_search(route: List[int], Cp: np.ndarray, fixed: bool, deadline: float) -> List[int]:
    """
    Best-improvement descent. The route is padded with a zero-cost dummy node
    at both ends (index n) so moves touching the first/last song need no
    special cases. With a fixed start, position 1 never moves.
    """
    n = len(route)
    if n < 3:
        return list(route)
    P = np.array([n, *route, n])
    lo = 2 if fixed else 1
    klo = 1 if fixed else 0

    I2 = np.arange(lo, n + 1)[:, None]
    J2 = np.arange(1, n + 1)[None, :]
    two_opt_invalid = J2 <= I2
    K = np.arange(klo, n + 1)[None, :]
    or_invalid = {}
    for L in (1, 2, 3):
        Is = np.arange(lo, n - L + 2)[:, None]
        or_invalid[L] = ~((K < Is - 1) | (K > Is + L - 1))

    while time.monotonic() < deadline:
        # Q[x, y] = cost from the song at position x to the song at position y,
        # so every term below is a slice rather than a gather.
        Q = Cp[np.ix_(P, P)]
        e = np.diagonal(Q, 1)
        F = np.concatenate(([0.0], np.cumsum(e)))
        G = np.concatenate(([0.0], np.cumsum(np.diagonal(Q, -1))))
        best_delta, move = -1e-9, None

        # 2-opt: reverse P[i..j] for lo <= i < j <= n.
        delta = (Q[lo - 1:n, 1:n + 1] + Q[lo:n + 1, 2:n + 2]
                 + (G[None, 1:n + 1] - G[lo:n + 1, None])
                 - e[lo - 1:n, None] - e[None, 1:n + 1]
                 - (F[None, 1:n + 1] - F[lo:n + 1, None]))
        delta[two_opt_invalid] = np.inf
        idx = int(np.argmin(delta))
        if delta.flat[idx] < best_delta:
            best_delta = delta.flat[idx]
            row, col = divmod(idx, delta.shape[1])
            move = ("2opt", lo + row, 1 + col)

        # Or-opt: move the segment P[i..i+L-1] between P[k] and P[k+1], optionally reversed.
        for L in (1, 2, 3):
            hi = n - L + 2
            if hi <= lo:
                break
            removal_gain = e[lo - 1:hi - 1] + e[lo + L - 1:hi + L - 1] - np.diagonal(Q, L + 1)[lo - 1:hi - 1]
            base = -e[None, klo:n + 1] - removal_gain[:, None]
            orientations = [(False, Q[klo:n + 1, lo:hi].T + Q[lo + L - 1:hi + L - 1, klo + 1:n + 2])]
            if L > 1:
                internal = ((G[lo + L - 1:hi + L - 1] - G[lo:hi]) - (F[lo + L - 1:hi + L - 1] - F[lo:hi]))[:, None]
                orientations.append((True, Q[klo:n + 1, lo + L - 1:hi + L - 1].T + Q[lo:hi, klo + 1:n + 2] + internal))
            for rev, insert in orientations:
                d = insert + base
                d[or_invalid[L]] = np.inf
                idx = int(np.argmin(d))
                if d.flat[idx] < best_delta:
                    best_delta = d.flat[idx]
                    row, col = divmod(idx, d.shape[1])
                    move = ("oropt", lo + row, lo + row + L - 1, klo + col, rev)

        if move is None:
            break
        if move[0] == "2opt":
            _, i, j = move
            P[i:j + 1] = P[i:j + 1][::-1].copy()
        else:
            _, i, end, k, rev = move
            seg = P[i:end + 1][::-1] if rev else P[i:end + 1]
            if k < i - 1:
                P = np.concatenate((P[:k + 1], seg, P[k + 1:i], P[end + 1:]))
            else:
                P = np.concatenate((P[:i], P[end + 1:k + 1], seg, P[k + 1:]))

    return [int(x) for x in P[1:-1]]
