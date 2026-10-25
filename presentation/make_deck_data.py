"""Collect every number shown in the presentation from the real result files.

Writes presentation/deck_data.json, which build_deck.js reads, so the slides can
never drift from benchmarks/, outputs/ and emane/results/.
"""

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    rows = list(csv.DictReader(open(ROOT / "benchmarks" / "results" / "instances.csv", encoding="utf-8")))
    methods = [("nx largest_first", "networkx largest-first"), ("nx smallest_last", "networkx smallest-last"),
               ("nx DSATUR", "networkx DSATUR"), ("nx independent_set", "networkx independent-set"),
               ("nx connected_bfs", "networkx connected-BFS"), ("nx random_sequential", "networkx random"),
               ("ours DSATUR", "portfolio: DSATUR"), ("ours RLF", "portfolio: RLF"),
               ("ours Smallest-last", "portfolio: smallest-last"), ("ours final", "This tool (pipeline)")]

    def excess(sel):
        rs = [r for r in rows if sel(r)]
        return [round(statistics.mean(int(r[m]) - int(r["ours final"]) for r in rs), 2) for m, _ in methods]

    large = lambda r: r["n"] in ("50", "100", "200") and r["side_m"] != "ring"
    ring = lambda r: r["side_m"] == "ring"
    sim = {}
    for st in ("N16-1000m", "N16-1600m", "N50-2000m", "N200-4000m"):
        rs = [r for r in rows if r["set"] == st]
        sim[st] = {k: round(statistics.mean(float(r[k]) for r in rs), 2)
                   for k in ("sim_opt_deliv_per_slot", "sim_rr_deliv_per_slot", "sim_d1_deliv_per_slot",
                             "sim_d1_lost_frac")}
    emane = json.loads((ROOT / "emane" / "results" / "summary.json").read_text())
    preds = json.loads((ROOT / "emane" / "scenarios" / "inputs" / "predictions.json").read_text())
    grid = json.loads((ROOT / "outputs" / "grid_4x4_schedule.json").read_text())
    report = (ROOT / "outputs" / "grid_4x4_report.txt").read_text().splitlines()
    data = {
        "method_labels": [lbl for _, lbl in methods],
        "excess_large": excess(large),
        "excess_ring": excess(ring),
        "n_instances": len(rows),
        "n_proven": sum(int(r["proven_optimal"]) for r in rows),
        "n_verified": sum(int(r["verified"]) for r in rows),
        "ring_gap_instances": sum(1 for r in rows if ring(r) and int(r["ours final"]) > int(r["lower_bound"])),
        "n_ring": sum(1 for r in rows if ring(r)),
        "max_time_ms_n200": round(1000 * max(float(r["time_s"]) for r in rows if r["n"] == "200"), 1),
        "mean_time_ms_n16": round(1000 * statistics.mean(float(r["time_s"]) for r in rows
                                                         if r["n"] == "16" and r["side_m"] != "ring"), 2),
        "sim": sim,
        "grid_slots": grid["num_slots"], "grid_lb": grid["lower_bound"],
        "grid_report_lines": report,
        "emane": {k: {"on_mean": round(100 * v["on_link_mean"], 2), "on_min": round(100 * v["on_link_min"], 2),
                      "off_max": round(100 * v["off_link_max"], 2),
                      "on_active_mean": round(100 * v["on_link_active_mean"], 2),
                      "accepted": v["accepted"], "rate": v["rate"],
                      "attr_mean": (round(100 * v["attribution_ratio_mean"], 2)
                                    if v["attribution_ratio_mean"] and not v.get("physical_channel") else None),
                      "attr_min": round(100 * v["attribution_ratio_min"], 2) if v["attribution_ratio_min"] else None,
                      "attr_links": v["attribution_links"], "stray_valid": v["stray_valid_rx"],
                      "silenced_air_tx": sum(v["silenced_air_tx"].values()),
                      "latency": round(v["latency_ms_mean"], 2), "sinr_bytes": v["mac_drop_bytes"].get("SINR", 0),
                      "queue_overflow": v["queue_overflow"],
                      "tx_missed": v["slot_counters"]["numTxSlotErrorMissed"],
                      "tx_valid": v["slot_counters"]["numTxSlotValid"]}
                  for k, v in emane.items() if k != "replication"},
        "replication": {b: [round(100 * x["on_link_mean"], 2) for x in vals]
                        for b, vals in emane.get("replication", {}).items()},
        "e3_predicted": round(100 * preds["E3"]["delivery_ratio"], 1),
    }
    (ROOT / "presentation" / "deck_data.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print("deck_data.json written:", data["n_proven"], "/", data["n_instances"], "proven;",
          "E1", data["emane"]["E1_optimized"]["on_mean"], "%; E3", data["emane"]["E3_distance1"]["on_mean"],
          "% vs", data["e3_predicted"], "% predicted")


if __name__ == "__main__":
    main()
