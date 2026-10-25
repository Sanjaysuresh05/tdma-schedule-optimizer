"""Network model: unit-disk connectivity graph G, conflict graph H = G^2, bounds.

Model
-----
* Radios are vertices; an undirected edge joins two radios whose Euclidean
  distance is at most the radio range R (inclusive, "within 500 m").
* Two radios conflict (must not share a TDMA slot) iff their hop distance in G
  is 1 (direct link / half-duplex) or 2 (hidden terminal at a common
  neighbour).  The conflict graph H therefore equals the square graph G^2, and
  a distance-2 colouring of G is exactly a proper vertex colouring of H.
* Lower bounds on the number of slots K: every closed neighbourhood N[v] is a
  clique in H, so K >= max_deg(G) + 1; more generally K >= omega(H).
"""

from __future__ import annotations

import itertools
import math
import re
from dataclasses import dataclass, field

import networkx as nx

from . import DEFAULT_RANGE_M
from .parsing import Coordinates

# Relative tolerance on the squared-distance test (d^2 <= R^2 (1 + tol)) so that
# points that are exactly R apart in decimal (e.g. 500 m along a diagonal,
# 353.5533905932738 m per axis) are linked despite binary floating-point
# rounding (~1e-16 relative).  1e-12 on d^2 means ~0.25 nm at R = 500 m: it
# absorbs rounding only and has no physical effect.
RANGE_REL_TOL = 1e-12

# max_weight_clique is exact branch-and-bound; beyond this size we fall back
# to a greedy clique (still a valid, possibly weaker, lower bound).
EXACT_CLIQUE_NODE_LIMIT = 3000


def natural_key(name: str) -> tuple:
    """Sort key so that Node_2 < Node_10 (numeric runs compared as numbers).

    The raw name is the final tie-breaker, so the order is total and
    deterministic even for names such as Node_01 / Node_1.
    """
    def num(tok: str) -> tuple:
        # compare digit runs by value without int() (no 4300-digit limit)
        s = tok.lstrip("0") or "0"
        return (0, len(s), s, "")

    parts = tuple(
        num(tok) if _ASCII_DIGITS.fullmatch(tok) else (1, 0, "", tok.lower())
        for tok in _ASCII_DIGITS.split(name)
        if tok != ""
    )
    return parts, name


_ASCII_DIGITS = re.compile(r"([0-9]+)")


def within_range(p: tuple[float, float], q: tuple[float, float], radio_range: float) -> bool:
    dx, dy = p[0] - q[0], p[1] - q[1]
    return dx * dx + dy * dy <= radio_range * radio_range * (1.0 + RANGE_REL_TOL)


def build_connectivity_graph(coords: Coordinates, radio_range: float = DEFAULT_RANGE_M) -> nx.Graph:
    """Unit-disk graph: edge iff distance <= radio_range.  O(N^2) pairs."""
    if not (radio_range > 0 and math.isfinite(radio_range)):
        raise ValueError("radio range must be a positive finite number")
    names = sorted(coords, key=natural_key)
    G = nx.Graph()
    for n in names:
        G.add_node(n, pos=coords[n])
    for u, v in itertools.combinations(names, 2):
        if within_range(coords[u], coords[v], radio_range):
            G.add_edge(u, v, distance=math.dist(coords[u], coords[v]))
    return G


def build_conflict_graph(G: nx.Graph) -> nx.Graph:
    """H = G^2.  Edge attribute ``hops`` is 1 (direct) or 2 (via a common neighbour)."""
    H = nx.Graph()
    H.add_nodes_from(G.nodes)
    for u, v in G.edges:
        H.add_edge(u, v, hops=1)
    for w in G.nodes:
        for a, b in itertools.combinations(G[w], 2):
            if not H.has_edge(a, b):
                H.add_edge(a, b, hops=2)
    return H


def max_clique(H: nx.Graph) -> tuple[list, bool]:
    """Return (clique, exact).  Exact for graphs up to EXACT_CLIQUE_NODE_LIMIT nodes."""
    if H.number_of_nodes() == 0:
        return [], True
    if H.number_of_nodes() <= EXACT_CLIQUE_NODE_LIMIT:
        # Run on integer labels: networkx iterates sets internally, and the order
        # of sets of *strings* changes with Python's per-process hash seed; ints
        # hash deterministically, so the returned clique is reproducible.
        names = list(H.nodes)
        Hi = nx.convert_node_labels_to_integers(H, ordering="default")
        clique, _ = nx.max_weight_clique(Hi, weight=None)
        return [names[i] for i in sorted(clique)], True
    # Greedy fallback: grow a clique from each vertex in degree order.
    best: list = []
    adj = {v: set(H[v]) for v in H}
    for v in sorted(H, key=H.degree, reverse=True)[:200]:
        cand, clique = set(adj[v]), [v]
        while cand:
            u = max(cand, key=lambda x: len(adj[x] & cand))
            clique.append(u)
            cand &= adj[u]
        if len(clique) > len(best):
            best = clique
    return best, False


@dataclass
class Topology:
    """Everything the optimiser and the report need about one network."""

    coords: Coordinates
    radio_range: float
    names: list[str] = field(init=False)
    G: nx.Graph = field(init=False)
    H: nx.Graph = field(init=False)
    clique: list = field(init=False)
    clique_exact: bool = field(init=False)

    def __post_init__(self) -> None:
        self.names = sorted(self.coords, key=natural_key)
        self.G = build_connectivity_graph(self.coords, self.radio_range)
        self.H = build_conflict_graph(self.G)
        self.clique, self.clique_exact = max_clique(self.H)

    # ---- bounds ---------------------------------------------------------
    @property
    def degree_bound(self) -> int:
        """max_deg(G) + 1 (size of the largest closed neighbourhood)."""
        return (max((d for _, d in self.G.degree), default=-1) + 1) if self.names else 0

    @property
    def lower_bound(self) -> int:
        return max(len(self.clique), self.degree_bound)

    @property
    def upper_bound_trivial(self) -> int:
        """max_deg(H) + 1: what any greedy colouring of H is guaranteed not to exceed."""
        return max((d for _, d in self.H.degree), default=-1) + 1

    # ---- descriptive statistics ----------------------------------------
    def stats(self) -> dict:
        G, H = self.G, self.H
        n = G.number_of_nodes()
        hop2 = sum(1 for _, _, h in H.edges(data="hops") if h == 2)
        return {
            "nodes": n,
            "links": G.number_of_edges(),
            "components": nx.number_connected_components(G) if n else 0,
            "isolated_nodes": sorted(nx.isolates(G), key=natural_key),
            "max_degree": max((d for _, d in G.degree), default=0),
            "avg_degree": (2.0 * G.number_of_edges() / n) if n else 0.0,
            "conflict_pairs": H.number_of_edges(),
            "conflict_pairs_1hop": H.number_of_edges() - hop2,
            "conflict_pairs_2hop": hop2,
            "max_conflict_degree": max((d for _, d in H.degree), default=0),
            "clique_lower_bound": len(self.clique),
            "clique_exact": self.clique_exact,
            "max_clique": sorted(self.clique, key=natural_key),
            "degree_lower_bound": self.degree_bound,
        }
