# FINAL REPORT: TDMA Schedule Planner & Optimizer (Vaan Megam Networks task)

This is the engineering record of the whole job. The submission documents are `docs/Documentation.pdf` (mandatory documentation) and `presentation/TDMA_Schedule_Optimizer.pptx`. The per-stage detail is in `reports/`.

---

## 1. Problem understanding
The task is a centralised TDMA scheduler (the "Brain", Part 1, mandatory) and an EMANE emulation (the "Engine", Part 2, bonus, graded on approach).

* **Part 1.** The Brain gives every radio a time slot so that no two radios within 2 hops transmit together:
  * 1-hop: direct link and half-duplex;
  * 2-hop: hidden terminal at a common neighbour.
  * Radios are linked within **500 m**. The Brain minimises the number of slots while maximising spatial reuse, and prints a Node→Slot mapping and a Slot × Node 0/1 matrix in the PDF's sample format, from a 16-node JSON string argument.
* **Part 2.** The Engine installs EMANE, configures its TDMA radio model with 1 ms slots, converts the schedule into EMANE's XML or ProtoBuf schedule format, and shows packets being permitted or dropped per the schedule.
* **Submission.** A Git repository with source, a documentation PDF and a PPT.
* **Model.** Collision-free node scheduling is proper colouring of the square graph G² (broadcast scheduling, NP-complete). I therefore use heuristics plus a lower bound and an exact certificate.
* **Key finding.** The PDF's sample output (5 slots) is invalid for its own sample input. That input is a 4×4 grid with 300 m spacing; the sample assignment has 21 two-hop conflicts. Any 3×3 block is a 9-clique of G², so **9 slots is the proven minimum**.

Full Phase 0 analysis (requirements, ambiguities A1–A14, risks, sources): `reports/00_UNDERSTANDING.md`.

## 2. Master plan (summary of `00_PLAN.md`)
Five stages, ordered by distance from the binding grading criterion (collision avoidance):

1. model + independent verifier → 2. optimiser → 3. CLI, simulator, tests, benchmarks → 4. EMANE → 5. documentation, presentation, packaging.

* **Parallel work.** The EMANE environment was prepared during Phase 0, and the independent reviewers ran in the background.
* **Risk register.** It is in `00_PLAN.md`. The two risks that mattered were no root/Docker for EMANE (solved: rootless install) and the invalid sample output (documented, never copied).

## 3. Stage summaries

| Stage | What | Why this way | How (core idea) | Result |
|---|---|---|---|---|
| 1 Model & verifier | JSON parsing; unit-disk graph G (networkx); H = G²; lower bound ω(G²); an independent verifier (plain Python, no networkx) | Reducing to ordinary colouring lets every classical algorithm apply; a separate verifier cannot share a graph bug | edge iff d² ≤ R²(1+10⁻¹²); H = E(G) ∪ {pairs with a common neighbour}; K ≥ ω(H) ≥ Δ+1 | 33 tests; G² = `nx.power` on 500 graphs; verifier = brute-force BFS on 1 500 schedules |
| 2 Optimiser | DSATUR, RLF, largest-first, smallest-last, connected-BFS, sweep, 64 random orders → iterated greedy → TabuCol → exact DSATUR branch-and-bound; optional max-reuse | No single heuristic wins on every graph; only an exact search can prove optimality | every step runs only while K > LB; clique pre-colouring for symmetry breaking | B&B = ILP on 120 instances; grid: 9 = LB in 1.4 ms |
| 3 CLI, simulator, benchmarks | the mandated CLI (sample layout, `--sample-format` byte-exact); JSON export; slot-level simulator; 638-instance benchmark | the format is graded; the simulator decides collision questions exactly; a proven optimum makes "effectiveness" measurable | reception ok iff the receiver is not transmitting and has exactly one transmitting neighbour | 638/638 networks optimal **with proof**; 0 losses; 1.78× throughput vs round-robin on the grid |
| 4 EMANE | rootless EMANE 1.5.3; XML **and** ProtoBuf bridge; 16-NEM namespace testbed; 6 experiments + 10 replications | the only way to run EMANE here without root/Docker; precomputed pathloss reproduces the task's channel | receiver-side slot attribution vs sender PHY transmissions; negative controls | E1 99.88 % (99.91 ± 0.06 over 5 seeds), 0 % off-links, 99.89 % of frames in the planned slot, 0 stray; E2 0 frames; E3 84.8 % vs 83.9 % predicted |
| 5 Docs & packaging | `docs/Documentation.pdf` (18 pages, built from Markdown, appendix filled from real outputs); 19-slide PPTX (numbers read from result files); README; Git | a single source of truth; nothing typed by hand can drift | `docs/build_docs.py`, `presentation/make_deck_data.py` + `build_deck.js` | PDF and PPTX built and visually checked; PPTX passes structural validation |

## 4. Decisions and assumptions (all recorded with reasons)
* **A1** "within 500 m" is inclusive, with a 10⁻¹² relative rounding tolerance (≈ 0.25 nm). It was 10⁻⁹ until reviewer 1 showed that admitted pairs about 0.1 µm beyond 500 m.
* **A2** The sample output is a format template only (21 conflicts); 9 slots is proven optimal for the sample grid.
* **A3** The elided sample coordinates are taken as the row-major 4×4 grid with 300 m spacing.
* **A4** Interference model = the protocol / unit-disk model at 500 m, as the task defines. E5 quantifies its limits.
* **A5** "Spatial reuse wherever possible": the base schedule is a colouring (one slot per node), plus optional `--max-reuse` extra slots shown in a separate matrix.
* **A6** Any N ≥ 1 is accepted, with a note when N ≠ 16.
* **A7/A8** Slots are 0-based and canonically relabelled; nodes are naturally sorted; matrix columns are labelled by numeric suffix.
* **A9** A heuristic portfolio plus an exact certificate (§3).
* **A10** Both XML and ProtoBuf routes.
* **A11** Rootless EMANE (no Docker, no sudo); a Dockerfile is provided but not built.
* **A12** 1 ms slots, 100 µs guard, 2.4 GHz, 10 MHz, 12 Mbit/s (1350 B/slot), 30 dBm.
* **A13** The 500 m graph is encoded in EMANE as 90/200 dB pathloss (unit-disk channel by construction).
* **A14** The repository is pushed to GitHub as a **private** repository on the user's account. Visibility is the user's choice, and making it public is one command (`gh repo edit --visibility public`).
* **Determinism.** My algorithms use integer indices and seeded RNGs; output is identical under different Python hash seeds (tested). networkx baselines depend on the hash seed, so the benchmark pins `PYTHONHASHSEED=0`.
* **EMANE evidence.** Enforcement is judged only from physical events (receiver per-slot receptions, sender PHY transmissions), never from EMANE's installed-schedule tables.

## 5. Models, skills, connectors and tools used, and why
* **Claude Opus 5.5 (this session)** did all the design, code, experiments and reports.
* **Two independent reviewer subagents (Opus, fresh context, read-only).** They were used for the high-stakes parts.
  * **Reviewer 1 (Part 1).** 320 fuzzed CLI runs with its own checker and ILP. It found **no collision and no false optimality claim**, and **8 input/output robustness defects**, all fixed with regression tests.
  * **Reviewer 2 (Part 2).** It recomputed every EMANE number from the raw files. It found the evidence flaw (`TxSlotStatusTable` = TX *opportunities*) plus runner-robustness issues and two wrong claims, all fixed (`reports/stage_4_report.md`).
* **Skills:**
  * `pdf`: reading the task PDF and building the documentation PDF (headless Chrome print of Markdown → HTML, checked with pypdf/pypdfium2);
  * `pptx`: building the deck with pptxgenjs, structural validation, and visual QA via a PowerPoint COM export;
  * `dataviz`: chart rules and a palette validated with its script; no log-scale bars, single-hue sequential ramps.
* **Connectors / web:** WebSearch and WebFetch for primary sources (EMANE docs, the EMANE GitHub wiki and tags, NetworkX docs) and to verify every literature citation. Consensus, alphaXiv, Drive, Notion, Canva and Figma were not needed: the deliverable is files in a Git repo, and the citations were resolved directly.
* **Tools:**
  * Windows Python 3.11 with networkx 3.6.1, scipy (the ILP cross-check), matplotlib and lxml;
  * WSL2 Ubuntu 24.04 running EMANE 1.5.3 from the official Adjacent Link bundle (SHA-256 verified);
  * GitHub CLI for the push.

## 6. Requirements traceability

| ID | Requirement | Where satisfied | Evidence |
|---|---|---|---|
| R1 | networkx: radios = nodes, links = edges | `tdma_brain/topology.py` | `test_conflict_graph_equals_square_graph` |
| R2 | link iff within 500 m | `topology.within_range` (inclusive) | `test_range_boundary`, `test_range_tolerance_is_rounding_only` |
| R3 | distance-2 colouring as slots of a recurring frame | `build_conflict_graph` + `optimizer.optimize` | every schedule verified; Stage 2 report |
| R4 | 1-hop neighbours differ | conflict graph hops = 1; `verify.py` "direct" | `test_direct_and_hidden_detection`, mutation tests |
| R5 | 2-hop (hidden terminal) differ | hops = 2; `verify.py` "hidden" | same tests; simulator: losses iff conflicts (1 000 cases) |
| R6 | spatial reuse beyond 2 hops | colouring reuses slots; `--max-reuse` | grid: 10 same-slot pairs at ≥ 3 hops; `docs/figures/grid_4x4_slots.png` |
| R7 | heuristics reduce slots | portfolio + IG + TabuCol + exact B&B | 638/638 optimal with proof; `benchmarks/results/summary.md` |
| R8 | CLI with 16 node coordinates | `tdma_scheduler.py` | `test_script_entry_point_runs_as_subprocess` |
| R9 | standardised JSON string argument | positional JSON (also `--file`, `@file`, stdin; PowerShell repair) | `test_input_forms_agree`; tested live on PowerShell 5.1 |
| R10 | Slot × Node binary matrix in ASCII | `report.format_matrix` | `outputs/grid_4x4_report.txt`; re-parse test |
| R11 | Node → Slot mapping | `render_report` | same |
| R12 | sample report layout | default layout + `--sample-format` (byte-exact) | `test_grid_report_matches_sample_layout`, `test_sample_format_matches_pdf_layout` |
| G1 | collision avoidance | independent verifier, simulator, EMANE | 0 conflicts in every produced schedule; EMANE E1 0 SINR drops, 0 stray receptions |
| G2 | heuristic effectiveness | §3, benchmark | excess-over-optimum figure; ring cases need the exact proof |
| R13 | install EMANE on one Linux machine or one container | `emane/install_rootless.sh` (WSL2 Ubuntu 24.04); `emane/docker/Dockerfile` (not built) | `emane --version` → 1.5.3; checksum OK |
| R14 | TDMA XML profiles: 1 ms slots, frames, frequencies | bridge output: `schedule.xml`, `tdma-radiomodel.xml`, `tdma-nem.xml`, `platform-NN.xml` | XSD-valid; `scheduleAcceptFull` 16/16 in every run; `StructureInfoTable` slotduration = 1000 |
| R15 | bridge: matrix → XML or ProtoBuf event | `schedule_to_emane.py` + `publish_events.py --route xml|protobuf` | E1 vs E1b identical; `tests/test_stage4_bridge.py` |
| R16 | EMANE drops or permits packets strictly per the schedule | experiments E1–E3 (+ E4, E5, replication) | 99.89 % of frames heard in the planned slot, 0 stray; silenced node 0 frames; wrong schedule collides as predicted |
| R17 | documentation PDF: design, thought process, final values | `docs/Documentation.pdf` | 18 pages; §1 final values, §4 decisions |
| R18 | Git repo with source, PDF, PPT | this repository (pushed to GitHub) | see §10 |
| R19 | explainable, defensible | per-stage reports with worked examples; speaker notes in the PPTX | `reports/stage_*_report.md` |
| I1 | verified line comes from a real check | `verify_matrix` drives the exit code | exit 2 path tested |
| I2 | deterministic | integer-index algorithms, seeded RNG | `test_output_identical_across_hash_seeds` |
| I3 | robust input validation | `parsing.py`, `cli.py` | 20 robustness regression tests |
| I4 | any 16-node layout | 6 example topologies + fuzzing | `outputs/*`; reviewer's 320 runs |
| I5 | scales beyond 16 | N up to 200 benchmarked (reviewer: 3 500) | ≤ 44 ms at N = 200 |
| I6 | slots reported against a lower bound | report header line | "PROVEN OPTIMAL (…)" |
| I7 | machine-readable export | `--json-out` (schema `vmn-tdma-schedule/1`) | `test_json_export_round_trip` |
| I8 | works on Windows | PowerShell quote repair, encoding-safe output | `test_non_ascii_names_with_redirected_output` |
| I9 | fast at N = 16 | 1–2 ms optimiser; ~0.65 s CLI (Python start-up) | benchmark |
| I10 | node ↔ NEM mapping | `nodes[].nem_id` = natural-order index + 1 | `nodes.json` |
| I11 | EMANE connectivity = 500 m graph | pathloss 90/200 dB from the same links (cross-checked) | 0 % off-link delivery in E1–E4 |
| I12 | packet fits a slot | 1350 B/slot ≫ 106 B probe frame; fragmentation on | `TxSlotErrorTooBig` = 0 |
| I13 | honest reporting | untested items labelled (Dockerfile, realtime `-r`) | this report, §8 |

## 7. Verification evidence (headline)
* `python -m pytest tests -q` → **91 passed**.
* **Benchmarks:** 638 instances, every result verified and proven optimal. The summary tables are identical across runs (timings excepted).
* **EMANE** (`emane/results/summary.md`):

| Experiment | Result |
|---|---|
| E1 | 99.88 % delivery on links; 99.89 % of each sender's frames heard in its planned slot (min 99.70 %); 0 stray receptions; 0 % off-links; 0 SINR drops |
| Replication (5 seeds) | E1 99.91 % ± 0.06; E3 84.78 % ± 0.13 vs 83.9 % predicted |
| E2 | silenced node: 0 PHY frames, 532 = 787 − 255 queue overflows |
| E3 | 532 kB SINR drops at the hidden-terminal receivers |
| E4 (10× load) | 96.6 %, 0 collisions |
| E5 (free-space channel) | 83.4 %; shows the unit-disk limitation |

* **Two independent reviews**, with every finding fixed or explicitly answered (§5).

## 8. Known limitations
* The unit-disk interference model (as the task defines) is used throughout; E5 shows that a physical free-space channel breaks it. The remedy is a larger planning radius, power control or a lower data rate.
* EMANE ran rootless without realtime priority, missing 0.13–0.47 % of TX slots. That causes the 0.1 % residual loss in E1 and the 3.4 % loss in E4. A real-root or Docker run can use `-r` (`VMN_EMANE_REALTIME=1`), but this is untested here.
* The Dockerfile has not been built (no Docker on the development machine). Only broadcast traffic was emulated; unicast/ARP and mobility were not exercised.
* NP-hardness: if the exact search hits its limits at large N, the tool reports "optimum in [LB, K]". This never happened up to N = 200.
* The 7-day deadline runs from when the task was received, which is outside this record. Check it before sharing the link.

## 9. Sources
The primary sources and verified citations are listed in `reports/00_UNDERSTANDING.md` §0.5 and `docs/Documentation.pdf` §15. They include:
* EMANE: https://emane.io/tdma-radio-model, https://github.com/adjacentlink/emane/wiki/Install, https://github.com/adjacentlink/emane/tags, and the EMANE 1.5.3 `tdmaschedule.xsd` / Python API;
* NetworkX `greedy_color` docs;
* Ephremides & Truong 1990; Ramanathan & Lloyd 1993; Krumke, Marathe & Ravi 2001; McCormick 1983; Gebremedhin, Manne & Pothen 2005; Brélaz 1979; Leighton 1979; Matula & Beck 1983; Culberson & Luo 1996; Hertz & de Werra 1987; San Segundo 2012; Gräf, Stumpf & Weißenfels 1998.

## 10. Deliverables (paths)
* **CLI (Part 1):** `tdma_scheduler.py`, `tdma_brain/`
* **Documentation (mandatory):** `docs/Documentation.pdf` (source `docs/Documentation.md`, build `docs/build_docs.py`)
* **Presentation:** `presentation/TDMA_Schedule_Optimizer.pptx` (build `presentation/build_deck.js`)
* **Part 2:** `emane/` (see `emane/README.md`); results in `emane/results/summary.md`
* **Evidence:** `outputs/`, `benchmarks/results/`, `docs/figures/`, `tests/`
* **Process records:** `00_PLAN.md`, `reports/00_UNDERSTANDING.md`, `reports/stage_1_report.md` … `stage_4_report.md`, this file
