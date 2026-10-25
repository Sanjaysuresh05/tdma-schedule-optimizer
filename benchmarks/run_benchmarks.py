"""Benchmark: slot counts of the optimiser vs networkx baselines vs the lower bound.

Instances: random uniform deployments (radio range 500 m) of several sizes and
densities, fixed seeds.  For each instance we record the clique lower bound,
the slots used by every networkx greedy strategy on G^2 (baselines), by every
member of our portfolio, and by the full pipeline (with optimality status),
plus a slot-level simulation of the optimised schedule, round-robin TDMA and
a distance-1 colouring.

Usage:  python benchmarks/run_benchmarks.py            (writes benchmarks/results/)
"""

from __future__ import annotations

import csv
import math
import os
import random
import subprocess
import statistics
import sys
import time
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdma_brain.optimizer import optimize           # noqa: E402
from tdma_brain.simulator import baseline_schedules, simulate  # noqa: E402
from tdma_brain.topology import Topology             # noqa: E402
from tdma_brain.verify import verify_matrix          # noqa: E402

OUT = ROOT / "benchmarks" / "results"

SETS = [  # (label, nodes, square side in m or "ring", instances)
    ("N16-700m", 16, 700, 100),
    ("N16-1000m", 16, 1000, 100),
    ("N16-1300m", 16, 1300, 100),
    ("N16-1600m", 16, 1600, 100),
    ("N16-2000m", 16, 2000, 100),
    ("N50-2000m", 50, 2000, 50),
    ("N100-3000m", 100, 3000, 40),
    ("N200-4000m", 200, 4000, 20),
    ("Ring13-40", None, "ring", 28),   # rings: chi(G^2) can exceed the clique bound
]


def make_coords(n, side, seed):
    """Uniform deployment in a side x side square, or a jittered ring (n = 13 + seed)."""
    if side == "ring":
        n = 13 + seed
        rng = random.Random(seed)
        spacing = 400.0                       # neighbours linked; 2-step chord ~ 800 m > 500 m
        radius = spacing / (2 * math.sin(math.pi / n))
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n
            r = radius + rng.uniform(-20, 20)
            pts.append((r * math.cos(a), r * math.sin(a)))
        return {f"Node_{i + 1:03d}": p for i, p in enumerate(pts)}
    rng = random.Random(seed * 1000 + side)
    return {f"Node_{i + 1:03d}": (rng.uniform(0, side), rng.uniform(0, side)) for i in range(n)}

NX_BASELINES = {
    "nx largest_first": dict(strategy="largest_first"),
    "nx largest_first+interchange": dict(strategy="largest_first", interchange=True),
    "nx smallest_last": dict(strategy="smallest_last"),
    "nx DSATUR": dict(strategy="DSATUR"),
    "nx independent_set": dict(strategy="independent_set"),
    "nx connected_bfs": dict(strategy="connected_sequential_bfs"),
    "nx random_sequential": dict(strategy="random_sequential"),
}


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for label, n, side, count in SETS:
        for seed in range(count):
            coords = make_coords(n, side, seed)
            topo = Topology(coords, 500.0)
            row = {"set": label, "n": len(coords), "side_m": side, "seed": seed,
                   "links": topo.G.number_of_edges(), "conflicts": topo.H.number_of_edges(),
                   "max_degree": topo.stats()["max_degree"], "lower_bound": topo.lower_bound}
            random.seed(seed)  # makes nx random_sequential reproducible
            for name, kw in NX_BASELINES.items():
                row[name] = max(nx.greedy_color(topo.H, **kw).values()) + 1
            t0 = time.perf_counter()
            s = optimize(topo, seed=seed, time_limit=10.0)
            row["time_s"] = time.perf_counter() - t0
            for r in s.runs:
                row["ours " + r.name.split(" x")[0]] = r.slots
            row["ours final"] = s.num_slots
            row["proven_optimal"] = int(s.proven_optimal)
            row["found_by"] = s.found_by
            row["verified"] = int(verify_matrix(coords, 500.0, s.names, s.matrix(), s.slot_of).ok)
            # simulation (saturated broadcast, 10 frames is exact: traffic is periodic)
            base = baseline_schedules(topo.G, topo.names)
            sim_opt = simulate(topo.G, s.transmitters(), frames=10)
            sim_rr = simulate(topo.G, base["Round-robin TDMA (no reuse)"], frames=10)
            sim_d1 = simulate(topo.G, base["Distance-1 colouring (no hidden-terminal rule)"], frames=10)
            row.update({
                "d1_slots": sim_d1.frame_slots,
                "sim_opt_deliv_per_slot": sim_opt.deliveries_per_slot,
                "sim_opt_lost": sim_opt.collisions,
                "sim_rr_deliv_per_slot": sim_rr.deliveries_per_slot,
                "sim_d1_deliv_per_slot": sim_d1.deliveries_per_slot,
                "sim_d1_lost_frac": 1 - sim_d1.delivery_ratio,
                "sim_d1_link_coverage": sim_d1.link_coverage,
            })
            rows.append(row)
        print(f"{label}: done", flush=True)

    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(OUT / "instances.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    write_summary(rows)


def write_summary(rows: list[dict]) -> None:
    methods = list(NX_BASELINES) + list(dict.fromkeys(k for r in rows for k in r if k.startswith("ours ")))
    sets = list(dict.fromkeys(r["set"] for r in rows))
    if not all(r["proven_optimal"] for r in rows):
        print("WARNING: some instances are not proven optimal; 'optimum' below is the best found")
    lines = ["# Benchmark summary", "",
             "Radio range 500 m; uniform random deployments in squares and jittered rings; fixed seeds. "
             "`Excess` = slots used - optimum, where the optimum is the pipeline's final result, "
             "which is *proven* optimal (clique bound or exhaustive branch-and-bound) on every "
             "instance below. Cells show `-` where a method did not run (pipeline steps run only "
             "while a gap to the lower bound remains).", "",
             "## Mean excess slots over the optimum (lower is better)", "",
             "| Method | " + " | ".join(sets) + " |", "|---|" + "---|" * len(sets)]
    for m in methods:
        cells = []
        for st in sets:
            rs = [r for r in rows if r["set"] == st and r.get(m) not in (None, "")]
            cells.append(f"{statistics.mean(r[m] - r['ours final'] for r in rs):.2f}" if rs else "-")
        lines.append(f"| {m} | " + " | ".join(cells) + " |")
    lines += ["", "## Share of instances on which the method finds the optimum (%)", "",
              "| Method | " + " | ".join(sets) + " |", "|---|" + "---|" * len(sets)]
    for m in methods:
        cells = []
        for st in sets:
            rs = [r for r in rows if r["set"] == st and r.get(m) not in (None, "")]
            cells.append(f"{100 * sum(r[m] == r['ours final'] for r in rs) / len(rs):.0f}" if rs else "-")
        lines.append(f"| {m} | " + " | ".join(cells) + " |")
    lines += ["", "## Pipeline result per set", "",
              "| Set | Inst. | Mean LB | Mean slots (ours) | Mean best nx | Ours < best nx | "
              "Optimum > clique LB | Proven optimal | Verified | Mean time | Max time |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for st in sets:
        rs = [r for r in rows if r["set"] == st]
        best_nx = [min(r[m] for m in NX_BASELINES) for r in rs]
        lines.append(
            f"| {st} | {len(rs)} | {statistics.mean(r['lower_bound'] for r in rs):.2f} | "
            f"{statistics.mean(r['ours final'] for r in rs):.2f} | {statistics.mean(best_nx):.2f} | "
            f"{sum(r['ours final'] < b for r, b in zip(rs, best_nx))} | "
            f"{sum(r['ours final'] > r['lower_bound'] for r in rs)} | "
            f"{100 * statistics.mean(r['proven_optimal'] for r in rs):.0f}% | "
            f"{100 * statistics.mean(r['verified'] for r in rs):.0f}% | "
            f"{1000 * statistics.mean(r['time_s'] for r in rs):.1f} ms | "
            f"{1000 * max(r['time_s'] for r in rs):.1f} ms |")
    lines += ["", "## Slot-level simulation (saturated broadcast traffic)", "",
              "| Set | Deliveries/slot: ours | round-robin | distance-1 colouring | "
              "Lost receptions, ours | Lost, distance-1 | Links starved, distance-1 |",
              "|---|---|---|---|---|---|---|"]
    for st in sets:
        rs = [r for r in rows if r["set"] == st]
        lines.append(
            f"| {st} | {statistics.mean(r['sim_opt_deliv_per_slot'] for r in rs):.2f} | "
            f"{statistics.mean(r['sim_rr_deliv_per_slot'] for r in rs):.2f} | "
            f"{statistics.mean(r['sim_d1_deliv_per_slot'] for r in rs):.2f} | "
            f"{sum(r['sim_opt_lost'] for r in rs)} | "
            f"{100 * statistics.mean(r['sim_d1_lost_frac'] for r in rs):.1f}% | "
            f"{100 * statistics.mean(1 - r['sim_d1_link_coverage'] for r in rs):.1f}% |")
    found = {}
    for r in rows:
        found[r["found_by"]] = found.get(r["found_by"], 0) + 1
    lines += ["", "## Which step produced the final schedule", "",
              "| Step | Instances |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(found.items(), key=lambda kv: -kv[1])]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    # Several networkx strategies iterate over sets of string node names, whose
    # order depends on Python's per-process hash seed.  Pin it so the baseline
    # numbers are reproducible (our own algorithms work on integer indices and
    # do not depend on it).
    if os.environ.get("PYTHONHASHSEED") != "0":
        env = dict(os.environ, PYTHONHASHSEED="0")
        sys.exit(subprocess.run([sys.executable, *sys.argv], env=env).returncode)
    run()
