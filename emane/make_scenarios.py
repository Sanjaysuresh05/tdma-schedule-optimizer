"""Create the schedule JSONs and predictions for the EMANE experiments (runs on the planning host).

E1  optimized  : the Brain's schedule for the PDF's 4x4 grid (9 slots, collision-free)
E2  silenced   : E1 with Node_06's only TX slot removed (built by the bridge with --silence)
E3  distance1  : baseline that separates only 1-hop neighbours (DSATUR on G, 4 slots),
                 i.e. what you get WITHOUT the hidden-terminal rule

Predictions come from the slot-level simulator with the same offered load the
EMANE runner uses (Poisson, RATE packets/s per node), so EMANE's measured
per-link delivery can be compared against an independent model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdma_brain.optimizer import optimize  # noqa: E402
from tdma_brain.report import to_json  # noqa: E402
from tdma_brain.simulator import baseline_schedules, simulate  # noqa: E402
from tdma_brain.topology import Topology  # noqa: E402
from tdma_brain.verify import matrix_from_slots, verify_matrix  # noqa: E402

OUT = ROOT / "emane" / "scenarios" / "inputs"
RATE_PPS = 40.0          # offered load per node used by the EMANE runner
SLOT_S = 0.001           # 1 ms slots
DURATION_S = 20.0
SILENCED = "Node_06"


def prediction(topo: Topology, transmitters: list[list[str]], silenced: str | None = None) -> dict:
    tx = [[n for n in T if n != silenced] for T in transmitters]
    frame_s = len(tx) * SLOT_S
    frames = int(DURATION_S / frame_s)
    load = min(1.0, RATE_PPS * frame_s)
    sim = simulate(topo.G, tx, frames=frames, load=load, seed=1)
    # per directed link a->b: share of a's transmissions that b received
    per_link = {}
    for u, v in topo.G.edges:
        for a, b in ((u, v), (v, u)):
            sent = sim.per_node_tx.get(a, 0)
            per_link[f"{a}->{b}"] = sim.per_link_delivered.get((a, b), 0) / sent if sent else 0.0
    return {"frames": frames, "load_per_frame": load, "delivery_ratio": sim.delivery_ratio,
            "lost_collision": sim.lost_collision, "lost_half_duplex": sim.lost_half_duplex,
            "delivered": sim.delivered, "attempts": sim.attempts,
            "mean_access_delay_ms": sim.mean_delay_slots * SLOT_S * 1000,
            "per_link_delivery_ratio": per_link}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    coords = {k: tuple(v) for k, v in json.loads((ROOT / "inputs" / "grid_4x4.json").read_text()).items()}
    topo = Topology(coords, 500.0)

    # E1: the Brain's optimised schedule
    sched = optimize(topo)
    ver = verify_matrix(coords, 500.0, sched.names, sched.matrix(), sched.slot_of)
    e1 = to_json(topo, sched, ver)
    e1["experiment"] = "E1 optimized (Brain output, collision-free)"
    (OUT / "E1_optimized.json").write_text(json.dumps(e1, indent=2) + "\n")

    # E3: distance-1 colouring baseline (deliberately NOT collision-free):
    # DSATUR on G itself, i.e. only 1-hop neighbours are separated
    base = baseline_schedules(topo.G, topo.names)["Distance-1 colouring (no hidden-terminal rule)"]
    d1 = {n: s for s, T in enumerate(base) for n in T}
    k1 = max(d1.values()) + 1
    m1 = matrix_from_slots(sched.names, {n: {d1[n]} for n in sched.names}, k1)
    ver1 = verify_matrix(coords, 500.0, sched.names, m1, d1)
    e3 = dict(e1)
    e3.update({
        "experiment": "E3 distance-1 colouring baseline (hidden terminals NOT handled)",
        "num_slots": k1, "matrix": m1, "matrix_max_reuse": None, "slot_of": d1,
        "nodes": [{**n, "slot": d1[n["name"]], "extra_slots": []} for n in e1["nodes"]],
        "found_by": "DSATUR on G (distance-1 only) - baseline", "proven_optimal": False,
        "lower_bound": None, "optimality_reason": "baseline, not an optimiser output",
        "verification": {"ok": ver1.ok, "pairs_checked": ver1.pairs_checked,
                         "violations": [v.describe() for v in ver1.violations]},
    })
    (OUT / "E3_distance1.json").write_text(json.dumps(e3, indent=2) + "\n")

    preds = {
        "rate_pps": RATE_PPS, "duration_s": DURATION_S, "slot_s": SLOT_S,
        "E1": prediction(topo, sched.transmitters()),
        "E2": prediction(topo, sched.transmitters(), silenced=SILENCED),
        "E3": prediction(topo, [[n for n in sched.names if d1[n] == s] for s in range(k1)]),
        "E3_conflicts": [v.describe() for v in ver1.violations],
        "silenced": SILENCED,
    }
    (OUT / "predictions.json").write_text(json.dumps(preds, indent=1) + "\n")
    print(f"E1: {sched.num_slots} slots, verified={ver.ok}; E3: {k1} slots, "
          f"verified={ver1.ok} ({len(ver1.violations)} conflicts)")
    for e in ("E1", "E2", "E3"):
        print(f"  predicted {e}: delivery {100 * preds[e]['delivery_ratio']:.1f}% "
              f"(load/frame {preds[e]['load_per_frame']:.2f}, collisions {preds[e]['lost_collision']}, "
              f"half-duplex {preds[e]['lost_half_duplex']})")


if __name__ == "__main__":
    main()
