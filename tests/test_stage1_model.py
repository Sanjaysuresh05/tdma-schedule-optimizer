"""Stage 1: input parsing, network model, conflict graph, bounds, verifier."""

import itertools
import json
import math
import random

import networkx as nx
import pytest

from tdma_brain import topology, verify
from tdma_brain.parsing import InputError, parse_coordinates
from tdma_brain.topology import Topology, build_conflict_graph, build_connectivity_graph, natural_key
from tdma_brain.verify import matrix_from_slots, verify_matrix

GRID = {f"Node_{i + 1:02d}": (300.0 * (i % 4), 300.0 * (i // 4)) for i in range(16)}


def random_coords(rng, n, side):
    return {f"N{i + 1}": (rng.uniform(0, side), rng.uniform(0, side)) for i in range(n)}


# ---------------------------------------------------------------- parsing
class TestParsing:
    def test_sample_format(self):
        p = parse_coordinates('{"Node_01":[0.0,0.0],"Node_02":[300.0,0.0],"Node_16":[900.0,900.0]}')
        assert p.coords == {"Node_01": (0.0, 0.0), "Node_02": (300.0, 0.0), "Node_16": (900.0, 900.0)}
        assert not p.repaired_quotes

    def test_integers_and_whitespace_and_bom(self):
        p = parse_coordinates('﻿  { "A" : [ 1 , 2 ] }  ')
        assert p.coords == {"A": (1.0, 2.0)}

    def test_powershell_stripped_quotes_are_repaired(self):
        p = parse_coordinates("{Node_01:[0.0,0.0],Node_02:[300.0,0.0]}")
        assert p.coords == {"Node_01": (0.0, 0.0), "Node_02": (300.0, 0.0)}
        assert p.repaired_quotes

    @pytest.mark.parametrize("text, fragment", [
        ('{"A":[0,0],"A":[1,1]}', "duplicate"),
        ('{"A":[NaN,0]}', "non-finite"),
        ('{"A":[Infinity,0]}', "non-finite"),
        ('{"A":[true,0]}', "must be a number"),
        ('{"A":["1",0]}', "must be a number"),
        ('{"A":[1,2,3]}', "expected [x, y]"),
        ('{"A":[1]}', "expected [x, y]"),
        ('{"A":5}', "expected [x, y]"),
        ('[[0,0],[1,1]]', "must be an object"),
        ('{}', "no nodes"),
        ('', "empty input"),
        ('{"A":[0,0]', "invalid JSON"),
        ('{" ":[0,0]}', "non-empty"),
        ('{"A":[1e400,0]}', "not finite"),
    ])
    def test_rejections(self, text, fragment):
        with pytest.raises(InputError, match=None) as e:
            parse_coordinates(text)
        assert fragment in str(e.value)


# ---------------------------------------------------------------- model
class TestModel:
    def test_natural_sort(self):
        names = ["Node_10", "Node_2", "Node_1", "alpha", "Node_01", "node_3"]
        assert sorted(names, key=natural_key) == ["alpha", "Node_01", "Node_1", "Node_2",
                                                  "node_3", "Node_10"]

    @pytest.mark.parametrize("q, linked", [
        ((500.0, 0.0), True),            # exactly on the boundary: "within" is inclusive
        ((300.0, 400.0), True),          # 3-4-5 triangle, exactly 500 m
        ((500.000001, 0.0), False),
        ((353.5533905932738, 353.5533905932738), True),  # 500 m along the diagonal
        ((0.0, 0.0), True),              # co-located radios hear each other
    ])
    def test_range_boundary(self, q, linked):
        G = build_connectivity_graph({"A": (0.0, 0.0), "B": q}, 500.0)
        assert G.has_edge("A", "B") is linked

    def test_tolerance_constants_agree(self):
        assert topology.RANGE_REL_TOL == verify.RANGE_REL_TOL

    def test_grid_structure(self):
        t = Topology(GRID, 500.0)
        # 4x4 king's graph: 24 orthogonal (300 m) + 18 diagonal (424 m) links
        assert t.G.number_of_edges() == 42
        assert t.stats()["max_degree"] == 8
        assert len(t.clique) == 9 and t.clique_exact      # any 3x3 block
        assert t.lower_bound == 9
        assert not t.G.has_edge("Node_01", "Node_03")      # 600 m apart
        assert t.H.has_edge("Node_01", "Node_03")          # ...but 2 hops via Node_02
        assert t.H["Node_01"]["Node_03"]["hops"] == 2

    def test_conflict_graph_equals_square_graph(self):
        rng = random.Random(1)
        for _ in range(500):
            n = rng.randint(1, 30)
            coords = random_coords(rng, n, rng.choice([300, 800, 1500, 3000]))
            G = build_connectivity_graph(coords, 500.0)
            H = build_conflict_graph(G)
            P = nx.power(G, 2)
            assert set(map(frozenset, H.edges)) == set(map(frozenset, P.edges))
            dist = dict(nx.all_pairs_shortest_path_length(G, cutoff=2))
            for u, v, h in H.edges(data="hops"):
                assert dist[u][v] == h

    def test_degree_bound_le_clique_bound(self):
        rng = random.Random(2)
        for _ in range(200):
            t = Topology(random_coords(rng, 16, rng.choice([500, 1000, 2000])), 500.0)
            assert t.degree_bound <= len(t.clique) <= t.upper_bound_trivial
            assert nx.is_isomorphic(t.H.subgraph(t.clique), nx.complete_graph(len(t.clique)))


# ---------------------------------------------------------------- verifier
def brute_force_conflict_free(coords, slots_of):
    G = nx.Graph()
    G.add_nodes_from(coords)
    for u, v in itertools.combinations(coords, 2):
        if math.dist(coords[u], coords[v]) <= 500.0 + 1e-7:
            G.add_edge(u, v)
    dist = dict(nx.all_pairs_shortest_path_length(G, cutoff=2))
    for u, v in itertools.combinations(coords, 2):
        if slots_of[u] & slots_of[v] and v in dist[u]:
            return False
    return True


class TestVerifier:
    def test_grid_mod3_schedule_is_valid(self):
        order = sorted(GRID, key=natural_key)
        slot = {n: (int(x // 300) % 3) * 3 + int(y // 300) % 3 for n, (x, y) in GRID.items()}
        m = matrix_from_slots(order, {n: {s} for n, s in slot.items()}, 9)
        res = verify_matrix(GRID, 500.0, order, m, slot)
        assert res.ok and res.pairs_checked > 0

    def test_problem_statement_sample_output_is_not_valid_for_the_grid(self):
        # The PDF's sample assignment (5 slots) applied to its own sample grid.
        sample = [0, 1, 0, 1, 2, 3, 2, 3, 0, 1, 4, 1, 2, 3, 2, 3]
        order = sorted(GRID, key=natural_key)
        slot = dict(zip(order, sample))
        m = matrix_from_slots(order, {n: {s} for n, s in slot.items()}, 5)
        res = verify_matrix(GRID, 500.0, order, m, slot)
        assert not res.conflict_free
        assert len(res.violations) == 21
        assert any(v.kind == "hidden" and {v.node_a, v.node_b} == {"Node_01", "Node_03"}
                   for v in res.violations)

    def test_direct_and_hidden_detection(self):
        coords = {"A": (0.0, 0.0), "B": (400.0, 0.0), "C": (800.0, 0.0), "D": (1600.0, 0.0)}
        order = ["A", "B", "C", "D"]
        # A,B direct conflict
        r = verify_matrix(coords, 500, order, [[1, 1, 0, 0], [0, 0, 1, 1]])
        assert [v.kind for v in r.violations] == ["direct"]
        # A,C hidden terminal at B; D is > 2 hops away and may reuse
        r = verify_matrix(coords, 500, order, [[1, 0, 1, 1], [0, 1, 0, 0]])
        assert [(v.kind, v.via) for v in r.violations] == [("hidden", "B"), ]
        # valid: A & D share (spatial reuse), B, C separate
        r = verify_matrix(coords, 500, order, [[1, 0, 0, 1], [0, 1, 0, 0], [0, 0, 1, 0]])
        assert r.ok

    def test_structural_checks(self):
        coords = {"A": (0.0, 0.0), "B": (100.0, 0.0)}
        r = verify_matrix(coords, 500, ["A", "B"], [[1, 0], [0, 0]])
        assert r.unscheduled_nodes == ["B"] and r.empty_slots == [1] and not r.ok
        r = verify_matrix(coords, 500, ["A", "B"], [[1, 0], [0, 1]], {"A": 1, "B": 1})
        assert r.conflict_free and not r.ok and r.mapping_mismatches

    def test_agrees_with_brute_force_on_random_schedules(self):
        rng = random.Random(3)
        seen = {True: 0, False: 0}
        for _ in range(1500):
            n = rng.randint(2, 16)
            coords = random_coords(rng, n, rng.choice([600, 1200, 2500]))
            k = rng.randint(1, n)
            order = sorted(coords, key=natural_key)
            slots_of = {u: {rng.randrange(k)} for u in order}
            if rng.random() < 0.3:  # sometimes multi-slot nodes
                u = rng.choice(order)
                slots_of[u].add(rng.randrange(k))
            m = matrix_from_slots(order, slots_of, k)
            got = verify_matrix(coords, 500.0, order, m).conflict_free
            want = brute_force_conflict_free(coords, slots_of)
            assert got == want
            seen[want] += 1
        assert seen[True] > 50 and seen[False] > 50  # both outcomes exercised

    def test_mutation_valid_colouring_then_inject_conflict(self):
        rng = random.Random(4)
        detected = 0
        for _ in range(300):
            coords = random_coords(rng, 16, rng.choice([700, 1200]))
            t = Topology(coords, 500.0)
            col = nx.greedy_color(t.H, strategy="largest_first")
            order = t.names
            k = max(col.values()) + 1
            m = matrix_from_slots(order, {n: {c} for n, c in col.items()}, k)
            assert verify_matrix(coords, 500.0, order, m, col).ok
            if t.H.number_of_edges() == 0:
                continue
            u, v = rng.choice(list(t.H.edges))
            col2 = dict(col)
            col2[v] = col2[u]
            m2 = matrix_from_slots(order, {n: {c} for n, c in col2.items()}, k)
            r = verify_matrix(coords, 500.0, order, m2)
            assert not r.conflict_free
            assert any({x.node_a, x.node_b} == {u, v} for x in r.violations)
            detected += 1
        assert detected > 250
