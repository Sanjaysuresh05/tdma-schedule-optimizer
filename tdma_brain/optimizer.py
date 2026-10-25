"""Schedule optimiser: heuristic portfolio -> improvement -> exact certificate.

Pipeline (each step only runs while the best frame length K exceeds the
lower bound LB = max(omega(G^2), maxdeg(G)+1)):

1. Constructive portfolio on H = G^2: DSATUR, RLF, largest-first,
   smallest-last, connected-BFS, geometric sweep, R random-order restarts.
2. Iterated Greedy (never worse) on the best colouring.
3. TabuCol: try K-1, K-2, ... until a k-colouring cannot be found.
4. Exact DSATUR branch-and-bound: proves optimality or improves K.

The result is canonically relabelled (slots numbered by first appearance in
node order) and, optionally, augmented with extra non-conflicting slots
("max reuse") without changing the frame length.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from . import coloring as C
from .exact import exact_coloring
from .topology import Topology


@dataclass
class AlgorithmRun:
    name: str
    slots: int
    seconds: float
    note: str = ""


@dataclass
class Schedule:
    names: list[str]                      # node order (natural sort) = matrix columns
    slot_of: dict[str, int]               # primary slot of each node (the colouring)
    num_slots: int                        # frame length K
    lower_bound: int
    proven_optimal: bool
    optimality_reason: str
    found_by: str
    runs: list[AlgorithmRun]
    seconds: float
    extra_slots: dict[str, list[int]] = field(default_factory=dict)  # max-reuse additions

    def slots_of(self, include_extra: bool = False) -> dict[str, set[int]]:
        out = {n: {self.slot_of[n]} for n in self.names}
        if include_extra:
            for n, extra in self.extra_slots.items():
                out[n].update(extra)
        return out

    def matrix(self, include_extra: bool = False) -> list[list[int]]:
        owned = self.slots_of(include_extra)
        return [[1 if s in owned[n] else 0 for n in self.names] for s in range(self.num_slots)]

    def transmitters(self, include_extra: bool = False) -> list[list[str]]:
        owned = self.slots_of(include_extra)
        return [[n for n in self.names if s in owned[n]] for s in range(self.num_slots)]

    @property
    def reuse_factor(self) -> float:
        """Average number of simultaneous transmitters per slot (N / K)."""
        return len(self.names) / self.num_slots if self.num_slots else 0.0


def _adjacency(topo: Topology) -> tuple[list[set[int]], dict[str, int]]:
    idx = {n: i for i, n in enumerate(topo.names)}
    adj = [{idx[u] for u in topo.H[n]} for n in topo.names]
    return adj, idx


def augment_max_reuse(adj: list[set[int]], col: list[int], k: int) -> list[set[int]]:
    """Give nodes extra slots inside the same frame wherever no 2-hop neighbour uses them.

    Round-robin fairness: in each pass every node may gain at most one slot, and
    nodes with fewer slots (then fewer conflicts, then lower index) go first.
    Every slot's transmitter set stays pairwise >= 3 hops apart, so the
    schedule remains collision-free; K does not change.
    """
    n = len(adj)
    owned = [{col[v]} for v in range(n)]
    tx_in = [set() for _ in range(k)]
    for v in range(n):
        tx_in[col[v]].add(v)
    changed = True
    while changed:
        changed = False
        for v in sorted(range(n), key=lambda v: (len(owned[v]), len(adj[v]), v)):
            for s in range(k):
                if s not in owned[v] and not (adj[v] & tx_in[s]):
                    owned[v].add(s)
                    tx_in[s].add(v)
                    changed = True
                    break
    return owned


def optimize(topo: Topology, *, seed: int = 0, restarts: int = 64, use_exact: bool = True,
             time_limit: float = 5.0, node_limit: int = 2_000_000,  # per improvement step
             max_reuse: bool = False) -> Schedule:
    t_start = time.perf_counter()
    names = topo.names
    n = len(names)
    adj, idx = _adjacency(topo)
    points = [topo.coords[v] for v in names]
    lb = topo.lower_bound
    rng = random.Random(seed)
    runs: list[AlgorithmRun] = []
    best: list[int] | None = None
    found_by = ""

    def consider(name: str, col: list[int], seconds: float, note: str = "") -> None:
        nonlocal best, found_by
        if not C.is_proper(adj, col):  # internal safety net; never expected to trigger
            raise RuntimeError(f"{name} produced an improper colouring")
        runs.append(AlgorithmRun(name, C.num_colors(col), seconds, note))
        if best is None or C.num_colors(col) < C.num_colors(best):
            best, found_by = list(col), name

    def timed(fn):
        t0 = time.perf_counter()
        out = fn()
        return out, time.perf_counter() - t0

    # 1. constructive portfolio
    portfolio = [
        ("DSATUR", lambda: C.dsatur(adj)),
        ("RLF", lambda: C.rlf(adj)),
        ("Largest-first", lambda: C.greedy(adj, C.order_largest_first(adj))),
        ("Smallest-last", lambda: C.greedy(adj, C.order_smallest_last(adj))),
        ("Connected-BFS", lambda: C.greedy(adj, C.order_connected_bfs(adj))),
        ("Geometric sweep", lambda: C.greedy(adj, C.order_sweep(points))),
    ]
    for name, fn in portfolio:
        col, dt = timed(fn)
        consider(name, col, dt)

    def random_restarts():
        best_r = None
        order = list(range(n))
        for _ in range(restarts):
            rng.shuffle(order)
            col = C.greedy(adj, order)
            if best_r is None or C.num_colors(col) < C.num_colors(best_r):
                best_r = col
        return best_r

    if restarts > 0 and n:
        col, dt = timed(random_restarts)
        consider(f"Random greedy x{restarts}", col, dt)

    # 2-4. improvement and certification while a gap to the lower bound remains
    exact_nodes = 0
    proven = C.num_colors(best) <= lb
    if not proven:
        col, dt = timed(lambda: C.iterated_greedy(adj, best, rng, iterations=max(200, 10 * n)))
        consider("Iterated greedy", col, dt)
    if C.num_colors(best) > lb:
        deadline = time.perf_counter() + time_limit
        col, dt = timed(lambda: C.reduce_colors_tabu(adj, best, lb, rng, max_iters=max(5000, 200 * n),
                                                     deadline=deadline))
        consider("TabuCol", col, dt)
    if C.num_colors(best) > lb and use_exact:
        clique_idx = [idx[v] for v in topo.clique]
        res = exact_coloring(adj, best, lb, clique_idx, node_limit=node_limit, time_limit=time_limit)
        exact_nodes = res.nodes
        note = "search complete" if res.proven else "limit reached"
        consider("Exact B&B", res.coloring, res.seconds, f"{res.nodes} nodes, {note}")
        proven = res.proven

    k = C.num_colors(best)
    if k <= lb:
        proven, reason = True, f"K = lower bound (max 2-hop clique = {len(topo.clique)})"
    elif proven:
        reason = f"exhaustive branch-and-bound ({exact_nodes} search nodes)"
    else:
        reason = f"best found; optimum lies in [{lb}, {k}]"

    col = C.canonical(best)
    sched = Schedule(
        names=list(names),
        slot_of={names[i]: col[i] for i in range(n)},
        num_slots=k,
        lower_bound=lb,
        proven_optimal=proven,
        optimality_reason=reason,
        found_by=found_by,
        runs=runs,
        seconds=0.0,
    )
    if max_reuse and n:
        owned = augment_max_reuse(adj, col, k)
        sched.extra_slots = {names[i]: sorted(owned[i] - {col[i]})
                             for i in range(n) if len(owned[i]) > 1}
    sched.seconds = time.perf_counter() - t_start
    return sched
