"""Vertex-colouring algorithms on the conflict graph H (= G^2).

All functions work on an integer adjacency list ``adj`` (vertex i -> set of
neighbours) and return a colouring as a list ``col`` with ``col[i]`` in
0..k-1.  Ties are always broken by vertex index, so every algorithm is
deterministic for a given input (randomised ones take an explicit RNG).

Constructive heuristics
    greedy (any order), largest-first (Welsh-Powell), smallest-last
    (Matula & Beck 1983), DSATUR (Brelaz 1979), RLF (Leighton 1979),
    connected-BFS, geometric sweep, random-order restarts.
Improvement
    Iterated Greedy (Culberson & Luo 1996): re-colour greedily in an order
    that keeps previous colour classes contiguous; never uses more colours.
    TabuCol (Hertz & de Werra 1987, tenure rule of Galinier & Hao 1999):
    k-fixed local search minimising the number of conflicting edges.
"""

from __future__ import annotations

import random
import time
from collections import deque

Adj = list[set[int]]


def num_colors(col: list[int]) -> int:
    return (max(col) + 1) if col else 0


def is_proper(adj: Adj, col: list[int]) -> bool:
    return all(col[u] != col[v] for u in range(len(adj)) for v in adj[u])


# --------------------------------------------------------------- greedy
def greedy(adj: Adj, order: list[int]) -> list[int]:
    """Sequential greedy: each vertex takes the smallest colour free among its neighbours."""
    col = [-1] * len(adj)
    for v in order:
        used = {col[u] for u in adj[v] if col[u] >= 0}
        c = 0
        while c in used:
            c += 1
        col[v] = c
    return col


def order_largest_first(adj: Adj) -> list[int]:
    return sorted(range(len(adj)), key=lambda v: (-len(adj[v]), v))


def order_smallest_last(adj: Adj) -> list[int]:
    """Matula-Beck degeneracy order: repeatedly remove a minimum-degree vertex."""
    n = len(adj)
    deg = [len(a) for a in adj]
    removed = [False] * n
    stack = []
    for _ in range(n):
        v = min((u for u in range(n) if not removed[u]), key=lambda u: (deg[u], u))
        removed[v] = True
        stack.append(v)
        for u in adj[v]:
            if not removed[u]:
                deg[u] -= 1
    return stack[::-1]


def order_connected_bfs(adj: Adj) -> list[int]:
    """BFS from the max-degree vertex of each component (neighbours in degree order)."""
    n = len(adj)
    seen = [False] * n
    order = []
    for root in order_largest_first(adj):
        if seen[root]:
            continue
        seen[root] = True
        q = deque([root])
        while q:
            v = q.popleft()
            order.append(v)
            for u in sorted(adj[v], key=lambda x: (-len(adj[x]), x)):
                if not seen[u]:
                    seen[u] = True
                    q.append(u)
    return order


def order_sweep(points: list[tuple[float, float]]) -> list[int]:
    """Geometric sweep (lexicographic x, then y): a classic order for unit-disk graphs."""
    return sorted(range(len(points)), key=lambda v: (points[v][0], points[v][1], v))


# --------------------------------------------------------------- DSATUR
def dsatur(adj: Adj) -> list[int]:
    """Brelaz DSATUR: colour the vertex with most distinct neighbour colours next.

    Ties: larger degree in the uncoloured subgraph, then smaller index.
    """
    n = len(adj)
    col = [-1] * n
    neigh_colors: list[set[int]] = [set() for _ in range(n)]
    udeg = [len(a) for a in adj]
    for _ in range(n):
        v = max((u for u in range(n) if col[u] < 0),
                key=lambda u: (len(neigh_colors[u]), udeg[u], -u))
        c = 0
        while c in neigh_colors[v]:
            c += 1
        col[v] = c
        for u in adj[v]:
            if col[u] < 0:
                neigh_colors[u].add(c)
                udeg[u] -= 1
    return col


# --------------------------------------------------------------- RLF
def rlf(adj: Adj) -> list[int]:
    """Leighton's Recursive Largest First: build one maximal independent set per colour.

    Each class starts with the uncoloured vertex of maximum degree in the
    uncoloured subgraph; then repeatedly adds the candidate with the most
    neighbours among vertices already excluded from the class (W), ties broken
    by fewest neighbours among remaining candidates (U), then index.
    """
    n = len(adj)
    col = [-1] * n
    uncolored = set(range(n))
    c = 0
    while uncolored:
        U = set(uncolored)
        W: set[int] = set()
        first = max(U, key=lambda v: (len(adj[v] & U), -v))
        chosen = first
        while True:
            col[chosen] = c
            U.discard(chosen)
            moved = adj[chosen] & U
            U -= moved
            W |= moved
            if not U:
                break
            chosen = max(U, key=lambda v: (len(adj[v] & W), -len(adj[v] & U), -v))
        uncolored = {v for v in uncolored if col[v] < 0}
        c += 1
    return col


# --------------------------------------------------------------- utilities
def canonical(col: list[int], order: list[int] | None = None) -> list[int]:
    """Relabel colours in order of first appearance along ``order`` (default 0..n-1)."""
    order = order if order is not None else list(range(len(col)))
    remap: dict[int, int] = {}
    for v in order:
        if col[v] not in remap:
            remap[col[v]] = len(remap)
    return [remap[c] for c in col]


def classes_of(col: list[int]) -> list[list[int]]:
    k = num_colors(col)
    cls: list[list[int]] = [[] for _ in range(k)]
    for v, c in enumerate(col):
        cls[c].append(v)
    return cls


# --------------------------------------------------------------- iterated greedy
def iterated_greedy(adj: Adj, col: list[int], rng: random.Random, iterations: int) -> list[int]:
    """Culberson & Luo iterated greedy.  Never returns more colours than ``col``.

    Re-running greedy on any vertex order in which each old colour class is
    contiguous gives at most as many colours (each class stays independent,
    so the j-th class can always be placed in a colour <= j).
    """
    best = list(col)
    cur = list(col)
    for it in range(iterations):
        cls = classes_of(cur)
        mode = it % 4
        if mode == 0:
            cls.reverse()
        elif mode == 1:
            cls.sort(key=len, reverse=True)
        elif mode == 2:
            cls.sort(key=lambda c: sum(len(adj[v]) for v in c), reverse=True)
        else:
            rng.shuffle(cls)
        order = [v for c in cls for v in c]
        cur = greedy(adj, order)
        if num_colors(cur) < num_colors(best):
            best = list(cur)
    return best


# --------------------------------------------------------------- TabuCol
def tabucol(adj: Adj, k: int, init: list[int], rng: random.Random, max_iters: int,
            deadline: float | None = None) -> list[int] | None:
    """Search for a proper k-colouring starting from ``init`` (values clipped to 0..k-1).

    Objective f = number of monochromatic edges.  Each iteration applies the best
    non-tabu move (v, c) for a conflicting vertex v (aspiration: tabu moves are
    allowed if they beat the best f seen).  Reverting v to its old colour is tabu
    for  tenure = rand(0..9) + 0.6 * |conflicting vertices|.
    Returns a proper colouring or None if not found within ``max_iters`` (or
    before ``deadline``, a time.perf_counter() value).
    """
    n = len(adj)
    if k <= 0:
        return None if n else []
    col = [c if c < k else rng.randrange(k) for c in init]
    # gamma[v][c] = number of neighbours of v with colour c
    gamma = [[0] * k for _ in range(n)]
    for v in range(n):
        for u in adj[v]:
            gamma[v][col[u]] += 1
    f = sum(gamma[v][col[v]] for v in range(n)) // 2
    best_f = f
    tabu = [[0] * k for _ in range(n)]
    for it in range(1, max_iters + 1):
        if f == 0:
            return col
        if deadline is not None and it & 255 == 0 and time.perf_counter() > deadline:
            return None
        conflicting = [v for v in range(n) if gamma[v][col[v]] > 0]
        best_delta, moves = None, []
        for v in conflicting:
            gv, cv = gamma[v], col[v]
            for c in range(k):
                if c == cv:
                    continue
                delta = gv[c] - gv[cv]
                if tabu[v][c] >= it and f + delta >= best_f:
                    continue  # tabu and no aspiration
                if best_delta is None or delta < best_delta:
                    best_delta, moves = delta, [(v, c)]
                elif delta == best_delta:
                    moves.append((v, c))
        if not moves:  # everything tabu: random perturbation of a conflicting vertex
            v = rng.choice(conflicting)
            c = rng.choice([x for x in range(k) if x != col[v]] or [col[v]])
            best_delta = gamma[v][c] - gamma[v][col[v]]
            moves = [(v, c)]
        v, c = rng.choice(moves)
        old = col[v]
        col[v] = c
        for u in adj[v]:
            gamma[u][old] -= 1
            gamma[u][c] += 1
        f += best_delta
        tabu[v][old] = it + rng.randint(0, 9) + int(0.6 * len(conflicting))
        if f < best_f:
            best_f = f
    return col if f == 0 else None


def reduce_colors_tabu(adj: Adj, col: list[int], lower_bound: int, rng: random.Random,
                       max_iters: int, deadline: float | None = None) -> list[int]:
    """Repeatedly try k-1 colours with TabuCol until it fails or the lower bound is met."""
    best = list(col)
    while num_colors(best) > lower_bound:
        k = num_colors(best) - 1
        # start: recolour the vertices of the highest class randomly into 0..k-1
        start = [c if c < k else rng.randrange(k) for c in best]
        found = tabucol(adj, k, start, rng, max_iters, deadline)
        if found is None:
            break
        best = found
    return best
