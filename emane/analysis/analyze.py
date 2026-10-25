"""Analyse the EMANE experiment results (runs anywhere with Python 3; matplotlib for figures).

Evidence is taken from *physical events*, never from the installed schedule itself:

* Delivery: D[src][dst] = unique probe packets dst received from src / packets src sent
  (application layer), on the Brain's 500 m links and on non-links.
* Slot attribution (receiver side, non-circular): at receiver r, a slot s in which
  exactly one neighbour t is scheduled is "t's slot as seen by r".  EMANE's
  RxSlotStatusTable at r counts the frames r actually received in s; EMANE's PHY
  BroadcastPacketAcceptTable0 at t counts the frames t actually put on the air.
  ratio = RxValid[r][s] / PhyTx[t]  ~ 1  means t's transmissions arrived in s.
  Valid receptions in slots where *no* neighbour of r is scheduled are counted as
  "stray" (must be 0); Missed entries there are timing spill-over.
* Silenced node (E2): its PHY transmit count must be 0.
* Collisions: TDMA MAC BroadcastByteDropTable0 'SINR' bytes; RX-lock slot errors.
* Schedule installation (a sanity check, not enforcement evidence): scheduleAcceptFull,
  rejects, and the TX opportunities in TxSlotStatusTable (which only exist for slots the
  installed schedule marks TX).
* Timing health: missed TX slots, TX opportunities > 1.75 slots late, avgTimedEventLatency,
  realtime-priority errors in the EMANE logs.

Writes emane/results/summary.md, summary.json and docs/figures/emane_*.png.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "emane" / "results"
FIG = ROOT / "docs" / "figures"
EXPERIMENTS = [
    ("E1_optimized", "E1 Brain schedule (XML route)"),
    ("E1b_protobuf", "E1b same, ProtoBuf route"),
    ("E2_silenced", "E2 Node_06's TX slot removed"),
    ("E3_distance1", "E3 distance-1 colouring (wrong)"),
    ("E4_highload", "E4 E1 at 10x load"),
    ("E5_freespace", "E5 E1 over free-space channel (no 500 m cut-off)"),
]
T95_DF4 = 2.776  # two-sided 95 % Student t, 4 degrees of freedom (5 replications)


def load_exp(d: Path) -> dict | None:
    if not (d / "stats.json").exists():
        return None
    traffic = {}
    for f in d.glob("traffic-*.json"):
        t = json.loads(f.read_text())
        traffic[t["nem"]] = t
    stats = json.loads((d / "stats.json").read_text())
    rt_errors = sum(f.read_text(errors="replace").count("Unable to set Real Time Priority")
                    for f in d.glob("emane-*.log"))
    return {"dir": d, "nodes": json.loads((d / "nodes.json").read_text()), "traffic": traffic,
            "stats": stats["nems"], "stats_errors": stats["errors"], "rt_errors": rt_errors,
            "scenario": json.loads((d / "scenario.json").read_text())}


def table(layer: dict, name: str) -> tuple[list, list]:
    t = layer["tables"].get(name)
    return (t["labels"], t["rows"]) if t else ([], [])


def analyse(exp: dict) -> dict:
    nodes = {n["nem_id"]: n for n in exp["nodes"]}
    nems = sorted(nodes)
    st = exp["stats"]
    sent = {n: exp["traffic"].get(n, {}).get("sent", 0) for n in nems}
    recv = {d: {int(s): v["unique"] for s, v in exp["traffic"].get(d, {}).get("from", {}).items()} for d in nems}
    D = {s: {d: (recv[d].get(s, 0) / sent[s] if sent[s] else 0.0) for d in nems if d != s} for s in nems}
    linked = {(s, d) for s in nems for d in nodes[s]["neighbours"]}
    silenced = {n for n in nems if not nodes[n]["tx_slots"]}
    on = [D[s][d] for s, d in sorted(linked)]
    on_active = [D[s][d] for s, d in sorted(linked) if s not in silenced]
    off = [D[s][d] for s in nems for d in nems if d != s and (s, d) not in linked]

    def phy_tx(t):
        labels, rows = table(st[str(t)]["PHY"], "BroadcastPacketAcceptTable0")
        return next((r[labels.index("Num Pkts Tx")] for r in rows if r[0] == t), 0) if labels else 0

    def rx_slots(r):
        labels, rows = table(st[str(r)]["MAC"], "RxSlotStatusTable")
        if not labels:
            return {}
        return {row[labels.index("Slot")]: (row[labels.index("Valid")], row[labels.index("Missed")]) for row in rows}

    air_tx = {n: phy_tx(n) for n in nems}
    attribution, stray_valid, stray_missed = [], 0, 0
    observed = {}
    for r in nems:
        R = rx_slots(r)
        observed[r] = {s: v for s, (v, _) in R.items()}
        sched: dict[int, list[int]] = {}
        for m in nodes[r]["neighbours"]:
            for s in nodes[m]["tx_slots"]:
                sched.setdefault(s, []).append(m)
        for s, (v, mi) in R.items():
            if s not in sched:
                stray_valid += v
                stray_missed += mi
        for t in nodes[r]["neighbours"]:
            for s in nodes[t]["tx_slots"]:
                if len(sched[s]) == 1 and air_tx[t]:
                    attribution.append({"tx": t, "rx": r, "slot": s, "rx_valid": R.get(s, (0, 0))[0],
                                        "tx_frames": air_tx[t]})
    ratios = [a["rx_valid"] / a["tx_frames"] for a in attribution]

    accept = {n: st[str(n)]["MAC"]["stats"].get("scheduler.scheduleAcceptFull", 0) for n in nems}
    rejects = sum(v for n in nems for k, v in st[str(n)]["MAC"]["stats"].items() if k.startswith("scheduler.scheduleReject"))
    installed_ok = 0
    slot_counters = {k: 0 for k in ["numTxSlotValid", "numTxSlotErrorMissed", "numTxSlotErrorTooBig",
                                    "numRxSlotValid", "numRxSlotErrorMissed", "numRxSlotErrorRxDuringIdle",
                                    "numRxSlotErrorRxDuringTx", "numRxSlotErrorRxLock",
                                    "numRxSlotErrorRxTooLong", "numRxSlotErrorRxWrongFrequency"]}
    late_tx, ev_latency, mac_drop, phy_drop, overflow = 0, [], {}, {}, 0
    for n in nems:
        mac, phy = st[str(n)]["MAC"], st[str(n)]["PHY"]
        for k in slot_counters:
            slot_counters[k] += mac["stats"].get(k, 0)
        labels, rows = table(mac, "TxSlotStatusTable")
        opp = sorted({r[labels.index("Slot")] for r in rows}) if labels else []
        installed_ok += opp == sorted(nodes[n]["tx_slots"])
        if labels:
            late_tx += sum(r[labels.index(">1.75")] for r in rows)
        if "avgTimedEventLatency" in mac["stats"]:
            ev_latency.append(mac["stats"]["avgTimedEventLatency"])
        for name, target, layer in (("BroadcastByteDropTable0", mac_drop, mac), ("BroadcastPacketDropTable0", phy_drop, phy)):
            labels, rows = table(layer, name)
            for r in rows:
                for lab, val in zip(labels[1:], r[1:]):
                    target[lab] = target.get(lab, 0) + int(val)
        labels, rows = table(mac, "QueueStatusTable")
        if labels:
            overflow += sum(int(r[labels.index("Overflow")]) for r in rows)

    lat = [v["lat_ms_mean"] for d in nems for v in exp["traffic"].get(d, {}).get("from", {}).values()]
    p99 = [v["lat_ms_p99"] for d in nems for v in exp["traffic"].get(d, {}).get("from", {}).values()]
    skew = [t.get("start_skew_ms") for t in exp["traffic"].values() if t.get("start_skew_ms") is not None]
    return {
        "nems": nems, "D": D, "linked": sorted(linked), "silenced": sorted(silenced),
        "total_sent": sum(sent.values()), "rate": next(iter(exp["traffic"].values()))["rate"],
        "seed": next(iter(exp["traffic"].values())).get("seed", 0),
        "on_link_mean": statistics.mean(on), "on_link_min": min(on),
        "on_link_active_mean": statistics.mean(on_active) if on_active else 0.0,
        "on_link_active_min": min(on_active) if on_active else 0.0,
        "off_link_max": max(off) if off else 0.0, "off_link_mean": statistics.mean(off) if off else 0.0,
        "silenced_air_tx": {str(n): air_tx[n] for n in silenced},
        "air_tx": air_tx, "attribution_links": len(attribution),
        "attribution_ratio_mean": statistics.mean(ratios) if ratios else None,
        "attribution_ratio_min": min(ratios) if ratios else None,
        "attribution": attribution, "stray_valid_rx": stray_valid,
        "physical_channel": exp["scenario"].get("pathloss_model") == "fspl-all", "stray_missed_rx": stray_missed,
        "observed_rx": observed,
        "accepted": sum(1 for v in accept.values() if v >= 1), "rejects": rejects, "installed_ok": installed_ok,
        "slot_counters": slot_counters, "late_tx_opportunities": late_tx,
        "avg_timed_event_latency_us": [min(ev_latency), max(ev_latency)] if ev_latency else None,
        "rt_priority_errors": exp["rt_errors"],
        "mac_drop_bytes": mac_drop, "phy_drop_packets": phy_drop, "queue_overflow": overflow,
        "latency_ms_mean": statistics.mean(lat) if lat else None, "latency_ms_p99_max": max(p99) if p99 else None,
        "start_skew_ms_max": max(skew) if skew else None,
    }


def ci95(values: list[float]) -> tuple[float, float]:
    m = statistics.mean(values)
    h = T95_DF4 * statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else float("nan")
    return m, h


def figures(results: dict, exps: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
    ramp = LinearSegmentedColormap.from_list("blue", ["#fcfcfb", "#cde2fb", "#86b6ef", "#3987e5",
                                                       "#256abf", "#184f95", "#0d366b"])
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE, "font.size": 9, "text.color": INK,
                         "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
                         "xtick.color": MUTED, "ytick.color": MUTED})

    shown = [n for n in ("E1_optimized", "E2_silenced", "E3_distance1", "E5_freespace") if n in results]
    if shown:
        fig, axes = plt.subplots(1, len(shown), figsize=(4.1 * len(shown), 4.3))
        axes = [axes] if len(shown) == 1 else list(axes)
        for ax, name in zip(axes, shown):
            r = results[name]
            nems = r["nems"]
            M = [[(r["D"][s][d] if d != s else float("nan")) for d in nems] for s in nems]
            im = ax.imshow(M, cmap=ramp, vmin=0, vmax=1)
            for s, d in r["linked"]:
                ax.add_patch(plt.Rectangle((nems.index(d) - 0.5, nems.index(s) - 0.5), 1, 1,
                                           fill=False, edgecolor=INK2, lw=0.6))
            ax.set_xticks(range(len(nems)), [f"{n:02d}" for n in nems], fontsize=6)
            ax.set_yticks(range(len(nems)), [f"{n:02d}" for n in nems], fontsize=6)
            ax.set_xlabel("receiver NEM")
            ax.set_ylabel("sender NEM")
            ax.set_title(f"{name}: links {100 * r['on_link_mean']:.2f}%,\n"
                         f"non-links max {100 * r['off_link_max']:.1f}%", fontsize=9, loc="left")
        cb = fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02)
        cb.set_label("delivery ratio (outlined cells = 500 m links)")
        fig.savefig(FIG / "emane_delivery_matrices.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

    if "E1_optimized" in results:
        r, e = results["E1_optimized"], exps["E1_optimized"]
        nems = r["nems"]
        nodes = {n["nem_id"]: n for n in e["nodes"]}
        k = e["scenario"]["num_slots"]
        expected = [[1 if any(s in nodes[m]["tx_slots"] for m in nodes[rx]["neighbours"]) else 0 for rx in nems]
                    for s in range(k)]
        obs = [[r["observed_rx"][rx].get(s, 0) for rx in nems] for s in range(k)]
        vmax = max(max(row) for row in obs) or 1
        fig, axes = plt.subplots(1, 2, figsize=(11, 3.5))
        axes[0].imshow(expected, cmap=ramp, vmin=0, vmax=1.4, aspect="auto")
        axes[1].imshow(obs, cmap=ramp, vmin=0, vmax=vmax * 1.2, aspect="auto")
        for s in range(k):
            for j in range(len(nems)):
                axes[0].text(j, s, str(expected[s][j]), ha="center", va="center", fontsize=6.5,
                             color="white" if expected[s][j] else MUTED)
                axes[1].text(j, s, str(obs[s][j]), ha="center", va="center", fontsize=5.5,
                             color="white" if obs[s][j] > vmax * 0.5 else (MUTED if not obs[s][j] else INK))
        for ax, title in ((axes[0], "Brain plan: 1 = a neighbour of this receiver is scheduled in the slot"),
                          (axes[1], "EMANE observed: frames received per slot (RxSlotStatusTable)")):
            ax.set_xticks(range(len(nems)), [f"{n:02d}" for n in nems], fontsize=7)
            ax.set_yticks(range(k), [f"{s:02d}" for s in range(k)], fontsize=7)
            ax.set_xlabel("receiver NEM")
            ax.set_ylabel("slot")
            ax.set_title(title, fontsize=9, loc="left")
        fig.tight_layout()
        fig.savefig(FIG / "emane_slot_enforcement.png", dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(4.8, 4.2))
        xs = [a["tx_frames"] for a in r["attribution"]]
        ys = [a["rx_valid"] for a in r["attribution"]]
        lo, hi = min(xs) * 0.97, max(xs) * 1.03
        ax.plot([lo, hi], [lo, hi], color=MUTED, lw=1, zorder=1)
        ax.scatter(xs, ys, s=20, color="#2a78d6", edgecolor=SURFACE, linewidth=0.8, zorder=2)
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_xlabel("frames the sender put on the air (PHY)")
        ax.set_ylabel("frames the neighbour received in the sender's slot")
        ax.set_title(f"E1: {len(xs)} directed links, ratio {100 * r['attribution_ratio_mean']:.2f}% "
                     f"(min {100 * r['attribution_ratio_min']:.2f}%)", fontsize=9, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(FIG / "emane_slot_attribution.png", dpi=150)
        plt.close(fig)

    pred_path = ROOT / "emane" / "scenarios" / "inputs" / "predictions.json"
    if "E3_distance1" in results and pred_path.exists():
        pred = json.loads(pred_path.read_text())["E3"]["per_link_delivery_ratio"]
        names = {n["name"]: n["nem_id"] for n in exps["E3_distance1"]["nodes"]}
        r = results["E3_distance1"]
        xs, ys = [], []
        for key, p in pred.items():
            a, b = key.split("->")
            xs.append(100 * p)
            ys.append(100 * r["D"][names[a]][names[b]])
        fig, ax = plt.subplots(figsize=(4.6, 4.3))
        ax.plot([0, 100], [0, 100], color=MUTED, lw=1, zorder=1)
        ax.scatter(xs, ys, s=22, color="#2a78d6", edgecolor=SURFACE, linewidth=1, zorder=2)
        ax.set_xlabel("predicted by slot-level simulator (%)")
        ax.set_ylabel("measured in EMANE (%)")
        ax.set_title("E3: per-link delivery, 84 directed links", fontsize=9.5, loc="left")
        ax.set_xlim(0, 102)
        ax.set_ylim(0, 102)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(FIG / "emane_e3_predicted_vs_measured.png", dpi=150)
        plt.close(fig)


def main() -> int:
    exps, results = {}, {}
    for name, _ in EXPERIMENTS:
        e = load_exp(RES / name / "results")
        if e:
            exps[name], results[name] = e, analyse(e)
    reps = {}
    for base in ("E1", "E3"):
        vals = []
        for seed in range(1, 6):
            e = load_exp(RES / "replication" / f"{base}_seed{seed}" / "results")
            if e:
                vals.append(analyse(e))
        if vals:
            reps[base] = vals
    if not results:
        print("no EMANE results found under", RES)
        return 1
    preds_path = ROOT / "emane" / "scenarios" / "inputs" / "predictions.json"
    preds = json.loads(preds_path.read_text()) if preds_path.exists() else {}

    sc = exps["E1_optimized"]["scenario"] if "E1_optimized" in exps else next(iter(exps.values()))["scenario"]
    L = ["# EMANE experiment results", "",
         "Generated by `emane/analysis/analyze.py` from the raw files in `emane/results/*/results/`.", "",
         f"Setup: {sc['num_nodes']} NEMs, slot {sc['slot_duration_us']} us (overhead {sc['slot_overhead_us']} us), "
         f"{sc['frequency_hz'] / 1e9:g} GHz, {sc['datarate_bps'] / 1e6:g} Mbit/s ({sc['bytes_per_slot']} B/slot), "
         f"{sc['bandwidth_hz'] / 1e6:g} MHz, noise floor {sc['noise_floor_dbm']} dBm. Unit-disk channel (E1-E4): "
         f"{sc['tx_power_dbm']:g} dBm, pathloss {sc['link_pathloss_db']:g} dB on 500 m links and "
         f"{sc['no_link_pathloss_db']:g} dB otherwise. E5: free-space pathloss for every pair, 3 dBm. Traffic: "
         "Poisson UDP broadcast, 64 B payload, 20 s; IPv6 disabled in the nodes; traffic starts only after "
         "every NEM reports the full schedule accepted.", "",
         "## Main results", "",
         "| Experiment | Slots | Load (pkt/s/node) | Delivery on 500 m links (mean / min) | Delivery on non-links (max) | "
         "Frames received in the sender's slot / frames sent (mean, min) | Stray receptions | Schedules accepted | "
         "Mean latency | Collision (SINR) drops |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for name, label in EXPERIMENTS:
        if name not in results:
            continue
        r, e = results[name], exps[name]
        on = f"{100 * r['on_link_mean']:.2f}% / {100 * r['on_link_min']:.2f}%"
        if r["silenced"]:
            on += (f" (others {100 * r['on_link_active_mean']:.2f}% / {100 * r['on_link_active_min']:.2f}%; "
                   f"silenced node: {100 * max(r['D'][s][d] for s in r['silenced'] for d in r['D'][s]):.1f}%, "
                   f"PHY frames sent {sum(r['silenced_air_tx'].values())})")
        attr = (f"{100 * r['attribution_ratio_mean']:.2f}%, {100 * r['attribution_ratio_min']:.2f}% "
                f"({r['attribution_links']} links)") if r["attribution_ratio_mean"] is not None else "-"
        stray = f"{r['stray_valid_rx']} valid / {r['stray_missed_rx']} missed"
        if r["physical_channel"]:
            attr = "n/a (channel is not the planned 500 m graph)"
            stray = f"n/a ({r['stray_valid_rx']} frames from beyond 500 m)"
        L.append(f"| {label} | {e['scenario']['num_slots']} | {r['rate']:g} | {on} | {100 * r['off_link_max']:.2f}% | "
                 f"{attr} | {stray} | "
                 f"{r['accepted']}/16 (rejects {r['rejects']}) | {r['latency_ms_mean']:.2f} ms | "
                 f"{r['mac_drop_bytes'].get('SINR', 0)} B |")
    L += ["", "*Frames received in the sender's slot*: for every directed link (t -> r) whose slot at r is used by "
          "t alone, EMANE's RxSlotStatusTable at r (frames received in t's slot) divided by EMANE's PHY transmit "
          "count at t. It compares the Brain's plan with physical events at both ends and does not use EMANE's "
          "installed-schedule tables. *Stray "
          "receptions*: frames counted at a receiver in slots where none of its neighbours is scheduled (valid "
          "must be 0; missed = reception overlapping a slot boundary because of host timing jitter)."]
    if reps:
        L += ["", "## Replication (traffic seeds 1-5, same schedule)", "",
              "| Experiment | Delivery on links per seed | Mean +/- 95% CI | Prediction |", "|---|---|---|---|"]
        for base, vals in reps.items():
            per = [100 * v["on_link_mean"] for v in vals]
            m, h = ci95(per)
            pred = (f"{100 * preds['E3']['delivery_ratio']:.1f}% (simulator)" if base == "E3" and preds
                    else "100% (collision-free)")
            L.append(f"| {base} | {', '.join(f'{p:.2f}%' for p in per)} | {m:.2f}% +/- {h:.2f} | {pred} |")
    L += ["", "## Timing health and schedule installation", "",
          "| Experiment | TX slots missed / processed | TX opportunities > 1.75 slot late | avgTimedEventLatency (us, min-max over NEMs) | "
          "Realtime-priority errors in logs | Installed TX slots = plan (scheduler) | Start skew max |",
          "|---|---|---|---|---|---|---|"]
    for name, _ in EXPERIMENTS:
        if name in results:
            r = results[name]
            sc_ = r["slot_counters"]
            ev = r["avg_timed_event_latency_us"]
            L.append(f"| {name} | {sc_['numTxSlotErrorMissed']} / {sc_['numTxSlotValid']} "
                     f"({100 * sc_['numTxSlotErrorMissed'] / max(1, sc_['numTxSlotValid']):.2f}%) | "
                     f"{r['late_tx_opportunities']} | {ev[0]:.0f}-{ev[1]:.0f} | {r['rt_priority_errors']} | "
                     f"{r['installed_ok']}/16 | {r['start_skew_ms_max']:.1f} ms |")
    L += ["", "EMANE logs 'Unable to set Real Time Priority' in every run: realtime scheduling needs CAP_SYS_NICE "
          "in the initial user namespace, which a rootless run inside `unshare --user` cannot have. EMANE's own "
          "documentation names missed slots as the symptom of insufficient timing fidelity; the residual losses in "
          "E1/E1b are of this kind (no SINR drops, no RX-during-TX errors). TxSlotStatusTable counts TX "
          "*opportunities* of the installed schedule, so 'installed TX slots = plan' only confirms schedule "
          "installation, not transmission behaviour.", "",
          "## Slot counters (sum over all NEMs)", "",
          "| Experiment | " + " | ".join(k.replace("num", "") for k in next(iter(results.values()))["slot_counters"]) + " |",
          "|---|" + "---|" * len(next(iter(results.values()))["slot_counters"])]
    for name, _ in EXPERIMENTS:
        if name in results:
            L.append(f"| {name} | " + " | ".join(str(v) for v in results[name]["slot_counters"].values()) + " |")
    L += ["", "## Drop reasons (sum over all NEMs)", "",
          "MAC = TDMA radio model `BroadcastByteDropTable0` (bytes; SINR = destroyed by overlapping transmissions); "
          "PHY = emulator PHY `BroadcastPacketDropTable0` (packets; Rx Sensitivity = below receiver sensitivity, "
          "e.g. a non-neighbour at 200 dB).", ""]
    for name, _ in EXPERIMENTS:
        if name in results:
            r = results[name]
            mac_nz = {k: v for k, v in r["mac_drop_bytes"].items() if v}
            phy_nz = {k: v for k, v in r["phy_drop_packets"].items() if v}
            L.append(f"* {name}: MAC {mac_nz or 'none'}; PHY {phy_nz or 'none'}; queue overflow {r['queue_overflow']} packets")
    if "E3_distance1" in results and preds:
        p = preds["E3"]
        L += ["", "## E3 prediction check", "",
              f"Slot-level simulator (same load, {p['load_per_frame']:.2f} packets/frame/node) predicted "
              f"{100 * p['delivery_ratio']:.1f}% delivery on links; EMANE measured "
              f"{100 * results['E3_distance1']['on_link_mean']:.1f}% (seed 0).",
              "Conflicts in the E3 schedule (independent verifier; one common neighbour named per pair):"]
        L += [f"* {c}" for c in preds.get("E3_conflicts", [])[:30]]
    (RES / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    def slim(v):
        out = {kk: vv for kk, vv in v.items() if kk not in ("D", "observed_rx", "attribution")}
        out["delivery_matrix"] = {str(s): {str(d): round(x, 4) for d, x in row.items()} for s, row in v["D"].items()}
        return out
    summary = {k: slim(v) for k, v in results.items()}
    summary["replication"] = {b: [slim(v) for v in vals] for b, vals in reps.items()}
    (RES / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    try:
        figures(results, exps)
    except ImportError:
        print("matplotlib not available: figures skipped")
    print("\n".join(L[:20]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
