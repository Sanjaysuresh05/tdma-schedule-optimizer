"""ASCII report (layout of the problem statement's sample output) and JSON export.

All text generated here is ASCII; only user-supplied node names can contain
other characters (the CLI escapes those if the console cannot encode them).

Two matrix styles:
* default  : cells right-aligned under their column labels (reads cleanly in a
             monospace terminal);
* sample   : byte-for-byte the spacing of the PDF's sample ("Slot 00 | 1 | 0 |",
             89-dash rule for 16 nodes) and no extra header lines.
"""

from __future__ import annotations

import json
import re

import networkx as nx

from . import __version__
from .optimizer import Schedule
from .simulator import SimResult
from .topology import Topology
from .verify import VerificationResult

WIDE = "=" * 64
THIN = "-" * 65

JSON_SCHEMA = "vmn-tdma-schedule/1"


def column_labels(names: list[str]) -> tuple[list[str], bool]:
    """Matrix column labels: numeric suffix of each name ("Node_07" -> "07").

    Falls back to 1-based column indices when suffixes are missing or not
    unique; the second return value says whether a legend is needed.
    """
    width = max(2, len(str(len(names))))
    suffixes = []
    for n in names:
        m = re.search(r"([0-9]+)$", n)
        suffixes.append(m.group(1) if m else None)
    if all(suffixes) and len(set(s.lstrip("0") for s in suffixes)) == len(names) \
            and max(len(s) for s in suffixes) <= 6:
        w = max(width, max(len(s) for s in suffixes))
        return [s.zfill(w) for s in suffixes], False
    return [str(i + 1).zfill(width) for i in range(len(names))], True


def format_matrix(names: list[str], matrix: list[list[int]], title: str,
                  sample_style: bool = False) -> list[str]:
    labels, legend = column_labels(names)
    w = len(labels[0]) if labels else 2
    if sample_style:  # exact spacing of the problem statement's sample output
        header = "Slot \\ Node | " + " | ".join(labels)
        rule = "-" * (len(header) - 2)
        out = [title, header, rule]
        out += [f"Slot {s:02d} | " + " | ".join(map(str, row)) for s, row in enumerate(matrix)]
        out.append(rule)
    else:
        row_w = max(len("Slot \\ Node"), len(f"Slot {len(matrix) - 1:02d}"))
        header = "Slot \\ Node".ljust(row_w) + " | " + " | ".join(labels)
        rule = "-" * max(len(header), len(THIN))
        out = [title, header, rule]
        for s, row in enumerate(matrix):
            out.append(f"Slot {s:02d}".ljust(row_w) + " | " + " | ".join(str(b).rjust(w) for b in row))
        out.append(rule)
    if legend:
        out.append("Column legend: " + ", ".join(f"{l}={n}" for l, n in zip(labels, names)))
    return out


def min_coslot_hops(G: nx.Graph, transmitters: list[list[str]]) -> float | None:
    """Smallest hop distance between two nodes sharing a slot.

    None if no two nodes share a slot; inf if all sharing pairs are in
    different connected components.
    """
    best = None
    for T in transmitters:
        for i, a in enumerate(T):
            lengths = nx.single_source_shortest_path_length(G, a)
            for b in T[i + 1:]:
                d = lengths.get(b, float("inf"))
                if best is None or d < best:
                    best = d
    return best


def describe_min_hops(mh: float | None) -> str:
    if mh is None:
        return "no two nodes share a slot"
    if mh == float("inf"):
        return "co-slot nodes are in different components (unreachable)"
    return f"{int(mh)} hops (>= 3 required)"


def render_report(topo: Topology, sched: Schedule, ver: VerificationResult, *,
                  ver_reuse: VerificationResult | None = None, verbose: bool = False,
                  sims: list[SimResult] | None = None, sample_format: bool = False) -> str:
    n, k = len(sched.names), sched.num_slots
    L: list[str] = []
    L += [WIDE, " TDMA TOPOLOGY OPTIMIZATION REPORT ", WIDE]
    L.append(f"Total Nodes Processed : {n}")
    L.append(f"Configured Radio Range : {topo.radio_range:.1f} meters")
    L.append(f"Optimized Frame Length : {k} unique timeslots (Lower is better)")
    if sched.proven_optimal and k <= sched.lower_bound:
        status = "PROVEN OPTIMAL (frame length = lower bound)"
    elif sched.proven_optimal:
        status = (f"PROVEN OPTIMAL (exhaustive branch-and-bound: no {k - 1}-slot "
                  f"schedule exists)")
    else:
        status = f"best found; optimum lies in [{sched.lower_bound}, {k}]"
    bound = "largest 2-hop clique" if topo.clique_exact else "greedy 2-hop clique bound"
    if not sample_format:
        L.append(f"Theoretical Lower Bound: {sched.lower_bound} timeslots ({bound}) -> {status}")
        L.append(f"Spatial Reuse Factor   : {sched.reuse_factor:.2f} transmitters/slot "
                 f"({n} nodes in {k} slots; one-node-per-slot TDMA would need {n})")
        L.append(f"Selected Heuristic     : {sched.found_by} "
                 f"(portfolio of {len(sched.runs)} runs, {sched.seconds * 1000:.1f} ms)")
    L.append(THIN)
    L.append("NODE -> SLOT ASSIGNMENTS:")
    for name in sched.names:
        extra = sched.extra_slots.get(name)
        suffix = f"   (+ max-reuse slots {', '.join(map(str, extra))})" if extra else ""
        L.append(f" {name}: Slot {sched.slot_of[name]}{suffix}")
    L.append("")
    L += format_matrix(sched.names, sched.matrix(), "STRUCTURAL TDMA SCHEDULE MATRIX (Slot x Node Boolean Matrix):",
                       sample_style=sample_format)

    if sched.extra_slots or ver_reuse is not None:
        L.append("")
        L += format_matrix(sched.names, sched.matrix(include_extra=True),
                           "MAX-REUSE SCHEDULE MATRIX (same frame, extra non-conflicting slots):",
                           sample_style=sample_format)
        tot = sum(map(sum, sched.matrix(include_extra=True)))
        L.append(f"Transmissions per frame: {tot} (base schedule: {n}); "
                 f"reuse factor {tot / k:.2f} transmitters/slot")

    if verbose:
        st = topo.stats()
        L.append("")
        L.append("TOPOLOGY:")
        L.append(f" Links (<= {topo.radio_range:.1f} m)       : {st['links']}   "
                 f"(avg degree {st['avg_degree']:.2f}, max degree {st['max_degree']})")
        L.append(f" Conflict pairs (G^2)     : {st['conflict_pairs']}   "
                 f"(1-hop {st['conflict_pairs_1hop']}, 2-hop {st['conflict_pairs_2hop']})")
        L.append(f" Connected components     : {st['components']}"
                 + (f"   isolated: {', '.join(st['isolated_nodes'])}" if st['isolated_nodes'] else ""))
        L.append(f" {'Largest' if topo.clique_exact else 'Greedy'} 2-hop clique     : "
                 f"{len(st['max_clique'])} -> {', '.join(st['max_clique'])}")
        L.append(f" Optimality               : {sched.optimality_reason}")
        L.append("")
        L.append("HEURISTIC PORTFOLIO (slots found; lower is better):")
        for r in sched.runs:
            note = f"  [{r.note}]" if r.note else ""
            L.append(f" {r.name:<22} {r.slots:>4} slots  {r.seconds * 1000:8.2f} ms{note}")
        L.append("")
        L.append("SPATIAL REUSE (transmitters sharing each slot):")
        tx = sched.transmitters()
        for s, T in enumerate(tx):
            L.append(f" Slot {s:02d}: {', '.join(T)}")
        L.append(" Minimum hop distance between co-slot transmitters: "
                 + describe_min_hops(min_coslot_hops(topo.G, tx)))

    if sims:
        L.append("")
        L.append(f"SLOT-LEVEL SIMULATION ({sims[0].frames} frames, saturated broadcast traffic):")
        L.append(f" {'Schedule':<46} {'Slots':>5} {'Deliv/frame':>11} {'Deliv/slot':>10} "
                 f"{'Lost/frame':>10} {'Delivery':>8} {'Links OK':>8}")
        for r in sims:
            L.append(f" {r.label:<46} {r.frame_slots:>5} {r.delivered / r.frames:>11.1f} "
                     f"{r.deliveries_per_slot:>10.2f} {r.collisions / r.frames:>10.1f} "
                     f"{100 * r.delivery_ratio:>7.1f}% {100 * r.link_coverage:>7.1f}%")
        L.append(" (Lost = receptions destroyed by collisions/hidden terminals or half-duplex; "
                 "Links OK = directed links with >= 1 delivery)")

    if not sample_format:
        L.append(f"Independent verification: {ver.pairs_checked} same-slot pairs checked, "
                 f"{len(ver.violations)} conflicts (1-hop and 2-hop)")
    if ver_reuse is not None:
        L.append(f"Max-reuse verification  : {ver_reuse.pairs_checked} same-slot pairs checked, "
                 f"{len(ver_reuse.violations)} conflicts")
    if ver.ok and (ver_reuse is None or ver_reuse.ok):
        L.append("Execution finalized cleanly. Schedule verified conflict-free.")
    else:
        L.append("SCHEDULE VERIFICATION FAILED:")
        for p in ver.problems() + (ver_reuse.problems() if ver_reuse else []):
            L.append(f" - {p}")
    L.append(WIDE[:-1])
    return "\n".join(L)


def to_json(topo: Topology, sched: Schedule, ver: VerificationResult) -> dict:
    """Machine-readable schedule consumed by the EMANE bridge (Part 2)."""
    nodes = []
    for i, name in enumerate(sched.names):
        x, y = topo.coords[name]
        nodes.append({
            "name": name, "nem_id": i + 1, "x": x, "y": y,
            "slot": sched.slot_of[name],
            "extra_slots": sched.extra_slots.get(name, []),
        })
    links = [[u, v, round(d, 6)] for u, v, d in topo.G.edges(data="distance")]
    return {
        "schema": JSON_SCHEMA,
        "generator": f"tdma_brain {__version__}",
        "radio_range_m": topo.radio_range,
        "num_nodes": len(sched.names),
        "num_slots": sched.num_slots,
        "lower_bound": sched.lower_bound,
        "proven_optimal": sched.proven_optimal,
        "optimality_reason": sched.optimality_reason,
        "found_by": sched.found_by,
        "node_order": sched.names,
        "nodes": nodes,
        "slot_of": sched.slot_of,
        "matrix": sched.matrix(),
        "matrix_max_reuse": sched.matrix(include_extra=True) if sched.extra_slots else None,
        "links": links,
        "verification": {
            "ok": ver.ok,
            "pairs_checked": ver.pairs_checked,
            "violations": [v.describe() for v in ver.violations],
        },
    }


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=2)
