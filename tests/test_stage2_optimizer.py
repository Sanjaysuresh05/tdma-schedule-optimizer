"""Stage 2: colouring heuristics, exact certificate, optimiser pipeline, max-reuse."""

import itertools
import random

import networkx as nx
import numpy as np
import pytest

from tdma_brain import coloring as C
from tdma_brain.exact import exact_coloring
from tdma_brain.optimizer import augment_max_reuse, optimize
from tdma_brain.topology import Topology
from tdma_brain.verify import verify_matrix

GRID = {f"Node_{i + 1:02d}": (300.0 * (i % 4), 300.0 * (i // 4)) for i in range(16)}
NX_STRATEGIES = ["largest_first", "smallest_last", "DSATUR", "independent_set",
                 "connected_sequential_bfs", "connected_sequential_dfs", "random_sequential"]


def random_coords(rng, n, side):
    return {f"Node_{i + 1:02d}": (rng.uniform(0, side), rng.uniform(0, side)) for i in range(n)}


def adj_of(topo):
    idx = {v: i for i, v in enumerate(topo.names)}
    return [{idx[u] for u in topo.H[v]} for v in topo.names], idx


def ilp_chromatic_number(adj):
    """Independent exact optimum via scipy's HiGHS MILP (test-only dependency)."""
    from scipy.optimize import Bounds, LinearConstraint, milp
    n = len(adj)
    K = C.num_colors(C.dsatur(adj))
    nx_, ny = n * K, K
    X = lambda v, c: v * K + c
    Y = lambda c: nx_ + c
    rows, lo, hi = [], [], []

    def row(entries, l, h):
        r = np.zeros(nx_ + ny)
        for j, a in entries:
            r[j] += a
        rows.append(r); lo.append(l); hi.append(h)

    for v in range(n):
        row([(X(v, c), 1) for c in range(K)], 1, 1)
        for c in range(K):
            row([(X(v, c), 1), (Y(c), -1)], -np.inf, 0)
    for u in range(n):
        for v in adj[u]:
            if u < v:
                for c in range(K):
                    row([(X(u, c), 1), (X(v, c), 1), (Y(c), -1)], -np.inf, 0)
    for c in range(K - 1):
        row([(Y(c), -1), (Y(c + 1), 1)], -np.inf, 0)
    cost = np.concatenate([np.zeros(nx_), np.ones(ny)])
    res = milp(cost, constraints=LinearConstraint(np.array(rows), lo, hi),
               integrality=np.ones(nx_ + ny), bounds=Bounds(0, 1))
    assert res.success
    return int(round(res.fun))


def brute_force_chromatic(adj):
    n = len(adj)
    for k in range(1, n + 1):
        for col in itertools.product(range(k), repeat=n):
            if C.is_proper(adj, list(col)):
                return k
    return 0


# ------------------------------------------------------------ heuristics
def test_every_heuristic_is_proper_on_random_graphs():
    rng = random.Random(10)
    for _ in range(300):
        topo = Topology(random_coords(rng, rng.randint(1, 40), rng.choice([400, 900, 1500, 3000])), 500.0)
        adj, _ = adj_of(topo)
        pts = [topo.coords[v] for v in topo.names]
        cols = [
            C.dsatur(adj), C.rlf(adj),
            C.greedy(adj, C.order_largest_first(adj)),
            C.greedy(adj, C.order_smallest_last(adj)),
            C.greedy(adj, C.order_connected_bfs(adj)),
            C.greedy(adj, C.order_sweep(pts)),
        ]
        for col in cols:
            assert C.is_proper(adj, col)
            assert len(topo.clique) <= C.num_colors(col) <= topo.upper_bound_trivial
        ig = C.iterated_greedy(adj, cols[0], rng, 50)
        assert C.is_proper(adj, ig) and C.num_colors(ig) <= C.num_colors(cols[0])


def test_smallest_last_order_is_a_permutation():
    rng = random.Random(11)
    topo = Topology(random_coords(rng, 30, 1200), 500.0)
    adj, _ = adj_of(topo)
    assert sorted(C.order_smallest_last(adj)) == list(range(30))
    assert sorted(C.order_connected_bfs(adj)) == list(range(30))


def test_tabucol_finds_known_colourings_and_returns_only_proper_ones():
    rng = random.Random(12)
    for _ in range(100):
        topo = Topology(random_coords(rng, 20, 1000), 500.0)
        adj, _ = adj_of(topo)
        k = C.num_colors(C.dsatur(adj))
        out = C.tabucol(adj, k, [0] * len(adj), rng, 20000)
        assert out is not None and C.is_proper(adj, out) and C.num_colors(out) <= k
        lb = len(topo.clique)
        if lb > 1:
            assert C.tabucol(adj, lb - 1, [0] * len(adj), rng, 300) is None  # impossible k


# ------------------------------------------------------------ exact certificate
def test_exact_matches_brute_force_on_tiny_graphs():
    rng = random.Random(13)
    for _ in range(150):
        topo = Topology(random_coords(rng, rng.randint(1, 7), rng.choice([400, 800, 1500])), 500.0)
        adj, idx = adj_of(topo)
        res = exact_coloring(adj, C.greedy(adj, list(range(len(adj)))), len(topo.clique),
                             [idx[v] for v in topo.clique])
        assert res.proven and C.is_proper(adj, res.coloring)
        assert C.num_colors(res.coloring) == brute_force_chromatic(adj)


def test_exact_matches_ilp_on_random_instances():
    pytest.importorskip("scipy")
    rng = random.Random(14)
    gaps_closed = 0
    for i in range(120):
        n = rng.randint(8, 20)
        topo = Topology(random_coords(rng, n, rng.choice([700, 1000, 1400])), 500.0)
        adj, idx = adj_of(topo)
        # deliberately weak incumbent so the B&B has real work to do
        start = C.greedy(adj, list(range(n))[::-1])
        res = exact_coloring(adj, start, len(topo.clique), [idx[v] for v in topo.clique])
        assert res.proven and C.is_proper(adj, res.coloring)
        assert C.num_colors(res.coloring) == ilp_chromatic_number(adj), f"instance {i}"
        gaps_closed += C.num_colors(res.coloring) < C.num_colors(start)
    assert gaps_closed > 0


def test_exact_reports_unproven_when_limit_hit():
    # A weak lower bound (1) and a 5-node search limit force the search to stop early.
    rng = random.Random(15)
    topo = Topology(random_coords(rng, 60, 1400), 500.0)
    adj, idx = adj_of(topo)
    start = C.greedy(adj, list(range(len(adj))))
    res = exact_coloring(adj, start, 1, [], node_limit=5)   # artificially weak LB
    assert not res.proven and C.is_proper(adj, res.coloring)


# ------------------------------------------------------------ optimiser pipeline
def test_grid_is_solved_optimally_with_nine_slots():
    topo = Topology(GRID, 500.0)
    s = optimize(topo)
    assert s.num_slots == 9 and s.lower_bound == 9 and s.proven_optimal
    assert s.slot_of["Node_01"] == 0                   # canonical labelling
    assert verify_matrix(GRID, 500.0, s.names, s.matrix(), s.slot_of).ok
    assert s.seconds < 1.0


def test_optimizer_beats_or_ties_every_networkx_strategy():
    rng = random.Random(16)
    strictly_better = 0
    for _ in range(300):
        n = rng.choice([16, 16, 16, 30, 50])
        coords = random_coords(rng, n, rng.choice([800, 1200, 1600, 2500]))
        topo = Topology(coords, 500.0)
        s = optimize(topo, time_limit=2.0)
        assert verify_matrix(coords, 500.0, s.names, s.matrix(), s.slot_of).ok
        best_nx = min(max(nx.greedy_color(topo.H, strategy=st).values()) + 1 for st in NX_STRATEGIES)
        assert s.num_slots <= best_nx
        assert s.lower_bound <= s.num_slots
        strictly_better += s.num_slots < best_nx
    assert strictly_better > 0


@pytest.mark.parametrize("coords, k", [
    ({"Solo": (0.0, 0.0)}, 1),
    ({f"N{i}": (0.0, 0.0) for i in range(16)}, 16),                      # all co-located: clique
    ({f"N{i}": (1000.0 * i, 0.0) for i in range(16)}, 1),               # all isolated: full reuse
    ({f"N{i}": (400.0 * i, 0.0) for i in range(16)}, 3),                # chain: 3 slots
    ({**{f"C{i}": (0.0, 0.0) for i in range(5)}, "Far": (5000.0, 0.0)}, 5),
])
def test_edge_cases(coords, k):
    topo = Topology(coords, 500.0)
    s = optimize(topo)
    assert s.num_slots == k and s.proven_optimal
    assert verify_matrix(coords, 500.0, s.names, s.matrix(), s.slot_of).ok


def test_deterministic_for_fixed_seed():
    rng = random.Random(17)
    coords = random_coords(rng, 40, 1300)
    a = optimize(Topology(coords, 500.0), seed=3)
    b = optimize(Topology(coords, 500.0), seed=3)
    assert a.slot_of == b.slot_of and a.num_slots == b.num_slots


# ------------------------------------------------------------ max-reuse augmentation
def test_max_reuse_keeps_schedule_collision_free():
    rng = random.Random(18)
    gained = 0
    for _ in range(200):
        coords = random_coords(rng, 16, rng.choice([900, 1500, 2500]))
        topo = Topology(coords, 500.0)
        s = optimize(topo, max_reuse=True)
        m = s.matrix(include_extra=True)
        res = verify_matrix(coords, 500.0, s.names, m, s.slot_of)
        assert res.ok
        assert len(m) == s.num_slots
        gained += sum(len(v) for v in s.extra_slots.values())
    assert gained > 0


def test_max_reuse_on_grid_adds_nothing():
    s = optimize(Topology(GRID, 500.0), max_reuse=True)
    assert s.extra_slots == {}     # every 2-hop neighbourhood already uses all 9 slots


def test_augment_is_maximal():
    rng = random.Random(19)
    for _ in range(50):
        topo = Topology(random_coords(rng, 25, 1500), 500.0)
        adj, _ = adj_of(topo)
        col = C.dsatur(adj)
        k = C.num_colors(col)
        owned = augment_max_reuse(adj, col, k)
        tx = [{v for v in range(len(adj)) if s in owned[v]} for s in range(k)]
        for v in range(len(adj)):
            for s in range(k):
                if s not in owned[v]:
                    assert adj[v] & tx[s], "a free slot was left unassigned"
