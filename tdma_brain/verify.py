"""Independent schedule verifier.

Deliberately shares no graph code with the optimiser: it recomputes the
500 m adjacency from the raw coordinates with plain Python (no networkx) and
checks the *Slot x Node matrix* that is actually printed.

A schedule is conflict-free iff, in every slot, the set of transmitters T
satisfies: no two members of T are adjacent (direct-link / half-duplex
conflict) and no two members of T share a neighbour (hidden-terminal
conflict).  Equivalently every pair in T is at hop distance >= 3.

Additional structural checks on the printed artefacts:
* every node owns at least one slot (otherwise it can never transmit);
* the Node -> Slot mapping agrees with the matrix;
* no slot row is empty (an empty slot would inflate the frame length).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Part of the *specification* (inclusive 500 m rule with rounding tolerance), so it
# must equal topology.RANGE_REL_TOL; asserted in the test-suite.  The
# implementation below is separate (plain loops, no networkx, no shared code).
RANGE_REL_TOL = 1e-12


@dataclass(frozen=True)
class Violation:
    slot: int
    node_a: str
    node_b: str
    kind: str        # "direct" (1-hop) or "hidden" (2-hop)
    via: str | None  # the common neighbour for hidden-terminal conflicts

    def describe(self) -> str:
        if self.kind == "direct":
            return f"slot {self.slot}: {self.node_a} and {self.node_b} are 1-hop neighbours"
        return (f"slot {self.slot}: {self.node_a} and {self.node_b} collide at common "
                f"neighbour {self.via} (hidden terminal)")


@dataclass
class VerificationResult:
    violations: list[Violation] = field(default_factory=list)
    unscheduled_nodes: list[str] = field(default_factory=list)
    mapping_mismatches: list[str] = field(default_factory=list)
    empty_slots: list[int] = field(default_factory=list)
    pairs_checked: int = 0

    @property
    def conflict_free(self) -> bool:
        return not self.violations

    @property
    def ok(self) -> bool:
        return (self.conflict_free and not self.unscheduled_nodes
                and not self.mapping_mismatches and not self.empty_slots)

    def problems(self) -> list[str]:
        out = [v.describe() for v in self.violations]
        out += [f"node {n} has no transmit slot" for n in self.unscheduled_nodes]
        out += self.mapping_mismatches
        out += [f"slot {s} is empty (no transmitter)" for s in self.empty_slots]
        return out


def _adjacency(coords: dict[str, tuple[float, float]], radio_range: float) -> dict[str, set[str]]:
    names = list(coords)
    limit = radio_range * radio_range * (1.0 + RANGE_REL_TOL)
    adj: dict[str, set[str]] = {n: set() for n in names}
    for i, u in enumerate(names):
        ux, uy = coords[u]
        for v in names[i + 1:]:
            dx, dy = ux - coords[v][0], uy - coords[v][1]
            if dx * dx + dy * dy <= limit:  # float * never raises (overflow -> inf)
                adj[u].add(v)
                adj[v].add(u)
    return adj


def verify_matrix(
    coords: dict[str, tuple[float, float]],
    radio_range: float,
    node_order: list[str],
    matrix: list[list[int]],
    mapping: dict[str, int] | None = None,
) -> VerificationResult:
    """Verify a Slot x Node 0/1 matrix (rows = slots, columns = ``node_order``).

    ``mapping`` (node -> primary slot), if given, must agree with the matrix:
    the node's column has a 1 in that row.
    """
    res = VerificationResult()
    if sorted(node_order) != sorted(coords):
        res.mapping_mismatches.append("matrix columns do not match the input node set")
        return res
    for r, row in enumerate(matrix):
        if len(row) != len(node_order) or any(x not in (0, 1) for x in row):
            res.mapping_mismatches.append(f"matrix row {r} is malformed")
            return res

    adj = _adjacency(coords, radio_range)

    for s, row in enumerate(matrix):
        tx = [node_order[j] for j, bit in enumerate(row) if bit]
        if not tx:
            res.empty_slots.append(s)
        for i, a in enumerate(tx):
            for b in tx[i + 1:]:
                res.pairs_checked += 1
                if b in adj[a]:
                    res.violations.append(Violation(s, a, b, "direct", None))
                    continue
                common = adj[a] & adj[b]
                if common:
                    res.violations.append(Violation(s, a, b, "hidden", min(common)))

    for j, n in enumerate(node_order):
        if not any(row[j] for row in matrix):
            res.unscheduled_nodes.append(n)

    if mapping is not None:
        for j, n in enumerate(node_order):
            s = mapping.get(n)
            if s is None or not (0 <= s < len(matrix)) or matrix[s][j] != 1:
                res.mapping_mismatches.append(
                    f"mapping says {n} -> slot {s}, but the matrix disagrees")
    return res


def matrix_from_slots(node_order: list[str], slots_of: dict[str, set[int]], num_slots: int) -> list[list[int]]:
    """Build the Slot x Node 0/1 matrix from node -> set(slots)."""
    return [[1 if s in slots_of[n] else 0 for n in node_order] for s in range(num_slots)]
