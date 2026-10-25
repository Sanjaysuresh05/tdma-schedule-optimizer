# TDMA Schedule Planner & Optimizer (Vaan Megam Networks — Wireless Protocol Development task)

A centralized Python **"Brain"** that turns static radio coordinates into a **collision-free TDMA schedule** by distance-2 graph colouring, minimises the number of time slots (with a proof of optimality), and an **EMANE "Engine"** that enforces that schedule on 16 emulated radios.

| | Result on the problem statement's 16-node sample grid (300 m spacing, 500 m range) |
|---|---|
| Frame length | **9 slots — proven optimal** (a 3×3 block of nodes is pairwise within 2 hops ⇒ ≥ 9) |
| Collisions | **0** (independent verifier + slot-level simulator + EMANE) |
| Spatial reuse | 1.78 transmitters/slot (16 nodes in 9 slots instead of 16) |
| EMANE (Part 2) | schedule accepted by all 16 NEMs; each NEM transmits only in its planned slot; **99.96 %** delivery on links, **0 %** off-links; a deliberately wrong schedule collides exactly as predicted |

> Note: the sample output in the problem statement shows 5 slots; for its own sample input that assignment has 21 two-hop conflicts (e.g. Node_01 and Node_03 share slot 0 but both neighbour Node_02). This tool follows the sample's *format*, and proves 9 is the minimum. Details: `docs/Documentation.pdf` §3.

## Quick start (Part 1)

Requirements: Python ≥ 3.10 and networkx (`pip install -r requirements.txt`).

```bash
python tdma_scheduler.py '{"Node_01":[0.0,0.0],"Node_02":[300.0,0.0],"Node_03":[600.0,0.0],"Node_04":[900.0,0.0],"Node_05":[0.0,300.0],"Node_06":[300.0,300.0],"Node_07":[600.0,300.0],"Node_08":[900.0,300.0],"Node_09":[0.0,600.0],"Node_10":[300.0,600.0],"Node_11":[600.0,600.0],"Node_12":[900.0,600.0],"Node_13":[0.0,900.0],"Node_14":[300.0,900.0],"Node_15":[600.0,900.0],"Node_16":[900.0,900.0]}'
```

Other ways to pass the same input (useful on Windows PowerShell 5.1, which strips quotes from arguments — the CLI also repairs that automatically):

```bash
python tdma_scheduler.py --file inputs/grid_4x4.json
```

Useful options: `--verbose` (topology, heuristic portfolio, per-slot reuse), `--max-reuse` (extra non-conflicting slots in the same frame), `--simulate 100` (slot-level simulation vs baselines), `--json-out schedule.json` (input for the EMANE bridge), `--sample-format` (exact layout of the PDF sample), `--range 500`. Exit status: 0 verified conflict-free, 1 invalid input, 2 verification failed, 3 output not written.

## Part 2 (EMANE)

```bash
bash emane/install_rootless.sh                 # official EMANE 1.5.3 bundle, no root needed
bash emane/runner/run_experiments.sh 20 40     # 16 NEMs, experiments E1/E1b/E2/E3
python3 emane/analysis/analyze.py              # -> emane/results/summary.md + figures
```

See [`emane/README.md`](emane/README.md).

## Repository layout

```
tdma_scheduler.py        CLI entry point (Part 1 deliverable)
tdma_brain/              parsing, topology (G, G^2, bounds), coloring heuristics, exact B&B,
                         optimizer pipeline, independent verifier, simulator, report/JSON
tests/                   91 pytest tests (python -m pytest tests -q)
inputs/                  6 example 16-node topologies (+ generator)
outputs/                 CLI reports and schedule JSON for every input (+ regenerate.py)
benchmarks/              638-instance benchmark vs networkx baselines (+ results)
emane/                   Part 2: bridge, runner, analysis, Dockerfile, raw results
docs/                    Documentation.pdf (mandatory documentation), sources, figures
presentation/            TDMA_Schedule_Optimizer.pptx
reports/                 Phase 0 analysis and per-stage engineering reports
00_PLAN.md               master plan          FINAL_REPORT.md   final engineering report
```

## Reproduce everything

```bash
python -m pytest tests -q                 # 91 tests
python outputs/regenerate.py              # CLI outputs for all inputs
python benchmarks/run_benchmarks.py       # benchmark tables (pins PYTHONHASHSEED for networkx baselines)
python emane/make_scenarios.py            # EMANE experiment inputs + simulator predictions
python docs/make_figures.py               # figures
python docs/build_docs.py                 # Documentation.pdf
```

AI assistance (Claude) was used to develop this project, as permitted by the task; every design decision, number and limitation is documented so that it can be explained and defended.
