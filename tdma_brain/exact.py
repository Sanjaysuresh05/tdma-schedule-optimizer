"""Exact minimum colouring by DSATUR-based branch-and-bound (Brelaz 1979; San Segundo 2012).

Search
    At each node of the search tree pick the uncoloured vertex of maximum
    saturation (ties: max uncoloured degree, then index) and branch over every
    feasible existing colour, then over one new colour (only if that new colour
    count is still below the incumbent).  A complete colouring found this way
    uses fewer colours than the incumbent, which is then replaced.
Bounds / symmetry breaking
    The incumbent (upper bound) comes from the heuristics; the search stops as
    soon as it equals the lower bound.  The vertices of a maximum clique are
    pre-coloured 0..|Q|-1, which removes the k! colour-permutation symmetry
    for those colours and is valid because a clique needs distinct colours.
Termination
    ``node_limit`` (deterministic) and ``time_limit`` (wall-clock safety).  If
    either is hit, the incumbent is returned with ``proven=False``.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass

from .coloring import Adj, num_colors


@dataclass
class ExactResult:
    coloring: list[int]
    proven: bool          # True iff the search space was exhausted (or UB == LB)
    nodes: int            # search-tree nodes expanded
    seconds: float


class _Stop(Exception):
    pass


def exact_coloring(adj: Adj, incumbent: list[int], lower_bound: int, clique: list[int],
                   node_limit: int = 2_000_000, time_limit: float = 10.0) -> ExactResult:
    n = len(adj)
    t0 = time.perf_counter()
    best = list(incumbent)
    best_k = num_colors(best)
    if n == 0 or best_k <= lower_bound:
        return ExactResult(best, True, 0, 0.0)

    kmax = best_k  # colours never exceed the incumbent count
    col = [-1] * n
    cnt = [[0] * kmax for _ in range(n)]   # cnt[v][c] = coloured neighbours of v with colour c
    sat = [0] * n                           # number of distinct neighbour colours
    udeg = [len(a) for a in adj]
    nodes = 0

    def assign(v: int, c: int) -> None:
        col[v] = c
        for u in adj[v]:
            udeg[u] -= 1
            if cnt[u][c] == 0:
                sat[u] += 1
            cnt[u][c] += 1

    def unassign(v: int) -> None:
        c = col[v]
        col[v] = -1
        for u in adj[v]:
            udeg[u] += 1
            cnt[u][c] -= 1
            if cnt[u][c] == 0:
                sat[u] -= 1

    used = 0
    for c, v in enumerate(sorted(clique)):
        assign(v, c)
        used = c + 1
    colored = len(clique)

    def search(colored: int, used: int) -> None:
        nonlocal best, best_k, nodes
        nodes += 1
        if nodes > node_limit or (nodes & 1023 == 0 and time.perf_counter() - t0 > time_limit):
            raise _Stop
        if colored == n:
            best, best_k = list(col), used
            return
        v, key = -1, None
        for u in range(n):
            if col[u] < 0:
                k_u = (sat[u], udeg[u], -u)
                if key is None or k_u > key:
                    v, key = u, k_u
        for c in range(used):
            if cnt[v][c] == 0:
                assign(v, c)
                search(colored + 1, used)
                unassign(v)
                if best_k <= lower_bound:
                    return
                if used >= best_k:
                    return  # incumbent improved below the current colour count
        if used + 1 < best_k:
            assign(v, used)
            search(colored + 1, used + 1)
            unassign(v)

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, 4 * n + 1000))
    proven = True
    try:
        search(colored, used)
    except _Stop:
        proven = False
    finally:
        sys.setrecursionlimit(old_limit)
    if best_k <= lower_bound:
        proven = True
    return ExactResult(best, proven, nodes, time.perf_counter() - t0)
