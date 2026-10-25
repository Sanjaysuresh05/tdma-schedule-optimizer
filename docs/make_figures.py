"""Generate the documentation figures from real outputs (deterministic).

Inputs : inputs/*.json, benchmarks/results/instances.csv, emane/results/*.json (if present)
Outputs: docs/figures/*.png
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tdma_brain.optimizer import optimize  # noqa: E402
from tdma_brain.topology import Topology  # noqa: E402

FIG = ROOT / "docs" / "figures"

# Reference palette (dataviz skill, light mode); first three slots validate all-pairs.
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"], "font.size": 10,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
    "text.color": INK,
})


def load(name: str) -> dict:
    return {k: tuple(v) for k, v in json.loads((ROOT / "inputs" / f"{name}.json").read_text()).items()}


def short(n: str) -> str:
    return n.split("_")[-1]


def draw_topology(ax, topo: Topology, sched=None, show_range_of: str | None = None) -> None:
    G = topo.G
    for u, v in G.edges:
        (x1, y1), (x2, y2) = topo.coords[u], topo.coords[v]
        ax.plot([x1, x2], [y1, y2], color=AXIS, lw=1.2, zorder=1, solid_capstyle="round")
    if show_range_of:
        cx, cy = topo.coords[show_range_of]
        ax.add_patch(Circle((cx, cy), topo.radio_range, facecolor=S1, alpha=0.08,
                            edgecolor=S1, lw=1.0, ls="-", zorder=0))
        ax.annotate("500 m radio range", (cx + topo.radio_range * 0.72, cy + topo.radio_range * 0.72),
                    color=INK2, fontsize=8.5, ha="left")
    for n in topo.names:
        x, y = topo.coords[n]
        ax.add_patch(Circle((x, y), 62, facecolor="white", edgecolor=INK2, lw=1.4, zorder=3))
        label = short(n) if sched is None else f"{short(n)}\nS{sched.slot_of[n]}"
        ax.text(x, y, label, ha="center", va="center", fontsize=7.5 if sched else 8.5,
                color=INK, zorder=4, linespacing=0.95)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")


def fig_grid_topology() -> None:
    coords = load("grid_4x4")
    topo = Topology(coords, 500.0)
    sched = optimize(topo)
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    draw_topology(ax, topo, sched, show_range_of="Node_06")
    ax.set_xlim(-250, 1150)
    ax.set_ylim(-250, 1150)
    ax.set_title("4x4 sample grid (300 m spacing): 42 links, node label = id / slot",
                 fontsize=10.5, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "grid_topology.png", dpi=170)
    plt.close(fig)


def fig_slot_panels(name: str, cols: int) -> None:
    """Small multiples: one panel per slot; filled = transmitting, wash = its 500 m coverage."""
    coords = load(name)
    topo = Topology(coords, 500.0)
    sched = optimize(topo)
    tx = sched.transmitters()
    k = len(tx)
    rows = -(-k // cols)
    xs = [p[0] for p in coords.values()]
    ys = [p[1] for p in coords.values()]
    pad = 560
    fig, axes = plt.subplots(rows, cols, figsize=(2.55 * cols, 2.55 * rows))
    axes = list(axes.flat) if hasattr(axes, "flat") else [axes]
    for s, ax in enumerate(axes):
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        if s >= k:
            ax.set_visible(False)
            continue
        for u, v in topo.G.edges:
            (x1, y1), (x2, y2) = coords[u], coords[v]
            ax.plot([x1, x2], [y1, y2], color=GRID, lw=0.9, zorder=1)
        for n in tx[s]:
            ax.add_patch(Circle(coords[n], 500.0, facecolor=S1, alpha=0.10, edgecolor="none", zorder=0))
        for n in topo.names:
            on = n in tx[s]
            ax.add_patch(Circle(coords[n], 70, facecolor=S1 if on else "white",
                                edgecolor=SURFACE if on else MUTED, lw=1.6 if on else 1.0, zorder=3))
        ax.set_xlim(min(xs) - pad, max(xs) + pad)
        ax.set_ylim(min(ys) - pad, max(ys) + pad)
        ax.set_aspect("equal")
        ax.set_title(f"Slot {s}: " + ", ".join(short(n) for n in tx[s]), fontsize=8.5, color=INK)
    fig.suptitle(f"{name}: transmitters per slot (filled) and their 500 m coverage. "
                 "No receiver is covered by two transmitters of the same slot.",
                 fontsize=9.5, color=INK2, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIG / f"{name}_slots.png", dpi=150)
    plt.close(fig)


def fig_random_topology() -> None:
    coords = load("random_16")
    topo = Topology(coords, 500.0)
    sched = optimize(topo)
    fig, ax = plt.subplots(figsize=(6.0, 5.6))
    draw_topology(ax, topo, sched)
    ax.set_title(f"random_16: {topo.G.number_of_edges()} links, {sched.num_slots} slots (proven optimal)",
                 fontsize=10.5, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "random16_topology.png", dpi=170)
    plt.close(fig)


def read_bench() -> list[dict]:
    path = ROOT / "benchmarks" / "results" / "instances.csv"
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def hbar(ax, labels, values, title, xmax):
    ypos = range(len(labels))[::-1]
    ax.barh(list(ypos), values, height=0.55, color=S1, zorder=2)
    for y, v in zip(ypos, values):
        ax.text(v + xmax * 0.015, y, f"{v:.2f}", va="center", fontsize=8, color=INK2)
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(labels, fontsize=8.5, color=INK2)
    ax.set_xlim(0, xmax)
    ax.xaxis.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_title(title, fontsize=9.5, color=INK, loc="left")
    ax.tick_params(axis="y", length=0)


def fig_benchmark_excess(rows: list[dict]) -> None:
    methods = ["nx largest_first", "nx smallest_last", "nx DSATUR", "nx independent_set",
               "nx connected_bfs", "nx random_sequential",
               "ours DSATUR", "ours RLF", "ours Smallest-last", "ours final"]
    groups = [("N = 16 (500 instances, 5 densities)", lambda r: r["n"] == "16" and r["side_m"] != "ring"),
              ("N = 50 / 100 / 200 (110 instances)", lambda r: r["n"] in ("50", "100", "200")),
              ("Rings, N = 13..40 (28 instances)", lambda r: r["side_m"] == "ring")]
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2), sharey=True)
    data = []
    for _, sel in groups:
        rs = [r for r in rows if sel(r)]
        data.append([statistics.mean(int(r[m]) - int(r["ours final"]) for r in rs) for m in methods])
    xmax = max(max(d) for d in data) * 1.22
    for ax, (title, _), vals in zip(axes, groups, data):
        hbar(ax, [m.replace("nx ", "networkx ").replace("ours final", "THIS TOOL (pipeline)")
                  .replace("ours ", "portfolio: ") for m in methods], vals, title, xmax)
        ax.set_xlabel("mean extra slots vs proven optimum")
    fig.suptitle("Heuristic effectiveness: extra slots over the proven optimum (0 = optimal)",
                 fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG / "benchmark_excess.png", dpi=150)
    plt.close(fig)


def fig_simulation(rows: list[dict]) -> None:
    sets = list(dict.fromkeys(r["set"] for r in rows))
    series = [("This tool (distance-2, optimised)", "sim_opt_deliv_per_slot", S1),
              ("Round-robin TDMA (no reuse)", "sim_rr_deliv_per_slot", S2),
              ("Distance-1 colouring (hidden terminals)", "sim_d1_deliv_per_slot", S3)]
    fig, (ax, axb, ax2) = plt.subplots(1, 3, figsize=(13.5, 4.4),
                                       gridspec_kw={"width_ratios": [1.5, 1.2, 1]})
    w = 0.26
    small = [st for st in sets if st.startswith("N16")]
    large = [st for st in sets if not st.startswith("N16")]
    for axis, group, title in ((ax, small, "N = 16: deliveries per slot"),
                               (axb, large, "Larger networks and rings")):
        for i, (label, key, color) in enumerate(series):
            vals = [statistics.mean(float(r[key]) for r in rows if r["set"] == st) for st in group]
            axis.bar([j + (i - 1) * (w + 0.02) for j in range(len(group))], vals, width=w, color=color,
                     label=label, zorder=2)
        axis.set_xticks(range(len(group)))
        axis.set_xticklabels(group, rotation=25, ha="right", fontsize=8.5)
        axis.yaxis.grid(True, color=GRID, lw=0.8, zorder=0)
        axis.set_title(title, fontsize=9.5, loc="left")
    ax.set_ylabel("successful receptions per slot")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    lost = [100 * statistics.mean(float(r["sim_d1_lost_frac"]) for r in rows if r["set"] == st) for st in sets]
    ypos = list(range(len(sets)))[::-1]
    ax2.barh(ypos, lost, height=0.55, color=S3, zorder=2)
    for y, v in zip(ypos, lost):
        ax2.text(v + 1.5, y, f"{v:.0f}%", va="center", fontsize=8, color=INK2)
    ax2.set_yticks(ypos)
    ax2.set_yticklabels(sets, fontsize=8.5, color=INK2)
    ax2.set_xlim(0, 110)
    ax2.xaxis.grid(True, color=GRID, lw=0.8, zorder=0)
    ax2.tick_params(axis="y", length=0)
    ax2.set_xlabel("receptions lost (%)")
    ax2.set_title("Distance-1 colouring loses receptions;\nthis tool loses 0 on every instance",
                  fontsize=9.5, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "simulation_throughput.png", dpi=150)
    plt.close(fig)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig_grid_topology()
    fig_slot_panels("grid_4x4", cols=3)
    fig_random_topology()
    fig_slot_panels("random_16", cols=4)
    rows = read_bench()
    fig_benchmark_excess(rows)
    fig_simulation(rows)
    print("figures written to", FIG)


if __name__ == "__main__":
    main()
