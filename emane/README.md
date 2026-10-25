# Part 2: EMANE engine (schedule enforcement)

This folder turns the Brain's schedule into a running **EMANE 1.5.3** emulation. Each of the 16 nodes runs one NEM:

`virtual transport → TDMA radio model (tdmaeventscheduler) → emulator PHY`

The experiments then measure whether packets are carried or dropped **exactly as the Part 1 schedule dictates**.

```
emane/
├── install_rootless.sh        # installs the official EMANE 1.5.3 Ubuntu 24.04 bundle (no root needed)
├── make_scenarios.py          # (planning host) writes the experiment schedule JSONs and predictions
├── bridge/
│   ├── schedule_to_emane.py   # THE BRIDGE: schedule JSON -> schedule.xml + platform/NEM/MAC/PHY XML + pathloss
│   └── publish_events.py      # publishes pathloss + TDMA schedule events (XML route or ProtoBuf route)
├── runner/
│   ├── run_experiments.sh     # runs E1, E1b, E2, E3 (each in a private user/net/mount namespace)
│   ├── inner.sh               # builds 16 network namespaces + bridge, starts 16 EMANE platforms, runs traffic
│   ├── traffic.py             # Poisson UDP broadcast probes (one per node), with one-way latency
│   └── collect.py             # pulls EMANE statistics/tables via the control port (ControlPortClient)
├── analysis/analyze.py        # delivery matrices, slot-enforcement checks, summary.md, figures
├── schema/tdmaschedule.xsd    # EMANE's own schedule schema (BSD licence, from python3-emane 1.5.3)
├── scenarios/inputs/          # E1_optimized.json, E3_distance1.json, predictions.json
├── docker/Dockerfile          # one consolidated container (provided; NOT built here because Docker is absent)
└── results/                   # raw results of every run + summary.md / summary.json
```

## Quick start (Linux / WSL2 Ubuntu 24.04, no root)

```bash
bash emane/install_rootless.sh                  # ~17 MB official bundle -> ~/vmn-emane/sysroot
python3 emane/make_scenarios.py                 # only if inputs changed (needs networkx; already committed)
bash emane/runner/run_experiments.sh 20 40      # 20 s per experiment, 40 packets/s per node
python3 emane/analysis/analyze.py               # writes emane/results/summary.md and figures
```

If you have root, install EMANE the official way instead (`dpkg -i *.deb; apt-get install -f`). Then run with `VMN_EMANE_ENV=/dev/null VMN_EMANE_SYSROOT=""`.

## What the bridge produces (`schedule_to_emane.py`)

| File | Content |
|---|---|
| `schedule.xml` | **Full** TDMA schedule. `<structure frames="1" slots="K" slotduration="1000" slotoverhead="100" bandwidth="10M"/>`, a multiframe at 2.4 GHz / 12 Mbps / 30 dBm, and one `<slot index="s" nodes="..."/>` per matrix row (a defined slot is TX for the listed NEMs; every other slot is RX by EMANE's rule). It is validated against EMANE's XSD and round-trip checked. |
| `platform-NN.xml`, `tdma-nem.xml`, `tdma-radiomodel.xml`, `transvirtual.xml` | The official EMANE TDMA template (emane-guide), parameterised. |
| `pathloss.json` | 90 dB on every 500 m link and 200 dB otherwise. Received power is −60 dBm on links (SNR 40 dB over the −100 dBm noise floor) and −170 dBm on non-links (invisible), so EMANE's connectivity **is** the Brain's unit-disk graph. |
| `nodes.json`, `scenario.json`, `schedule_matrix.txt` | The node ↔ NEM ↔ IP ↔ slot mapping, every parameter, and derived values (1350 B per slot, frame = K ms). |

**ProtoBuf route.** `publish_events.py --route protobuf` builds `TDMAScheduleEvent` messages directly from `nodes.json` and publishes them, with no XML in between. `--route xml` does exactly what `emaneevent-tdmaschedule` does. Both are exercised (E1 vs E1b).

## Experiments

| Id | Schedule | Expected if EMANE enforces the schedule |
|---|---|---|
| E1 | Brain output for the 4×4 grid (9 slots) | ≈100 % delivery on all 84 directed links, 0 % on non-links, each NEM transmits only in its slot |
| E1b | Same schedule, published via ProtoBuf | Identical to E1 |
| E2 | E1 with Node_06's TX slot removed | Node_06's packets are never transmitted (0 % delivery, queue overflow drops); everyone else is unaffected |
| E3 | Distance-1 colouring (4 slots, hidden terminals not handled) | Collisions (SINR drops) at the common neighbours, at the rate predicted by the slot-level simulator |

The results and their interpretation are in [`results/summary.md`](results/summary.md) and in `reports/stage_4_report.md`.
