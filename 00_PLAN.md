# 00_PLAN — Master plan

Companion to [`reports/00_UNDERSTANDING.md`](reports/00_UNDERSTANDING.md) (Phase 0: restatement, requirements R1–R19 / I1–I13, ambiguities A1–A14, risks, sources).

## Why this stage breakdown

The work has one hard correctness core (the graph model and the verifier), one optimisation core (the slot minimiser), one user-facing layer (CLI/report/simulator), one systems-integration layer (EMANE), and the mandated paperwork. These layers have **strictly increasing distance from the grading criterion G1 (collision avoidance)**: an error in Stage 1 invalidates everything above it, so it is built and verified first and in isolation; an error in Stage 4 cannot invalidate Part 1. Splitting this way also means each stage has a crisp, testable acceptance criterion and the EMANE environment (slow, risky) can be prepared in parallel with the algorithm work.

| Stage | Name | Depends on | Can run in parallel with |
|---|---|---|---|
| 1 | Network model, conflict graph, bounds, independent verifier | – | EMANE env prep (done in Phase 0) |
| 2 | Slot optimiser: heuristic portfolio + improvement + exact certificate + max-reuse | 1 | – |
| 3 | CLI + report + JSON export + slot-level simulator + tests + benchmarks | 1, 2 | independent review of 1–2 (subagent) |
| 4 | EMANE engine: profiles, bridge (XML + ProtoBuf), pathloss, rootless 16-node run, experiments | 3 (JSON interface only) | independent review of 3 (subagent) |
| 5 | Documentation PDF, presentation PPTX, README, Git packaging | 1–4 | – |
| P3 | Integration, traceability, red-team, optimisation, FINAL_REPORT | 1–5 | red-team subagent |

## Tooling, skills, connectors, models

* **Me (Opus 5.5)**: design, algorithms, EMANE integration, verification logic, all reports.
* **Independent reviewer subagents (Opus, fresh context, no access to my reasoning)**: (a) after Stage 3, review Part 1 code + attack the CLI with adversarial inputs + independently re-derive the 4×4 optimum; (b) after Stage 4, review the EMANE bridge/config against EMANE's XSD and docs; (c) Phase 3 red-team of the full deliverable vs. the PDF. Opus because these are high-stakes correctness judgements.
* **Skills**: `pdf` (read input – done; build documentation PDF), `pptx` (presentation). `docx`/`xlsx` not needed.
* **Connectors**: Web search/fetch for primary sources (done); Consensus/alphaXiv not needed beyond the verified citations (WebSearch already resolved every reference I rely on). Drive/Notion/Canva/Figma: not used — the PDF requires files in a Git repo, not cloud documents. Gmail: never (no messages are sent).
* **Execution environments**: Windows Python 3.11 + networkx 3.6.1 for Part 1; WSL2 Ubuntu 24.04 rootless sysroot for EMANE 1.5.3 (official Adjacent Link `.deb`s extracted with `dpkg-deb -x`, no root, no system changes).

---

## Stage 1 — Network model, conflict graph, bounds, verifier

* **Goal**: exact, robust translation from coordinates to the conflict structure; an independent oracle that decides "conflict-free" for any schedule.
* **Method**: parse/validate JSON (strict, with duplicate-key detection and PowerShell-quote repair); build `networkx.Graph` G with edge iff `dx²+dy² ≤ R²(1+1e-9)`; build conflict graph H = G² explicitly (neighbour + neighbour-of-neighbour); lower bounds `Δ(G)+1` and `ω(H)` (exact max clique; Bron–Kerbosch via networkx). Verifier recomputes distances itself from raw coordinates and checks all pairs with hop distance 1 or 2 (BFS depth 2), plus matrix ↔ mapping consistency.
* **Why (alternatives compared)**:
  * *Explicit G² + ordinary colouring* vs *on-the-fly 2-hop checks inside each algorithm*: explicit G² reduces distance-2 colouring to standard vertex colouring, so every classical algorithm (and networkx baselines) applies unchanged, and the model is inspectable. On-the-fly checks duplicate the 2-hop logic in every algorithm (more places to be wrong). → explicit.
  * *O(N²) all-pairs distance* vs *spatial hashing*: at N = 16 (target) and ≤ 1000 (benchmarks) all-pairs is exact, trivially correct and < 0.5 s; hashing adds code for no measurable gain here. → all-pairs, complexity stated.
  * *`≤` vs `<`* (A1): `≤` with squared distances.
* **Inputs/outputs**: JSON → `Topology` object (names, coords, G, H, bounds); `verify(topology, schedule) → Report`.
* **Acceptance**: unit tests for every input edge case; G² equals `nx.power(G,2)` on 500 random instances; verifier flags every injected conflict (mutation test) and accepts known-good schedules; 4×4 grid gives |E(G)| = 42, ω(H) = 9.

## Stage 2 — Slot optimiser

* **Goal**: minimum number of slots K with zero conflicts; certify optimality when possible; optional extra-slot spatial reuse.
* **Method (pipeline)**: (1) lower bound LB = ω(H); (2) constructive portfolio on H: DSATUR, RLF, largest-first, smallest-last, connected-BFS, plus R seeded random-order greedy restarts → best UB; (3) if UB > LB: Iterated Greedy (Culberson & Luo) then TabuCol (Hertz & de Werra) trying K = UB−1, UB−2, … ; (4) if still UB > LB: exact DSATUR branch-and-bound (max-clique pre-colouring for symmetry breaking, time limit) → proves optimality or improves; (5) canonical relabelling (first appearance in node order); (6) optional `--max-reuse`: greedily grant each node additional slots not used within its 2-hop neighbourhood (fairness: fewest-slots-first).
* **Why (alternatives compared)**:
  * *Single heuristic (e.g. networkx greedy)* vs *portfolio*: no constructive heuristic dominates on all graphs (well documented in the colouring literature); a portfolio costs milliseconds at N = 16. → portfolio.
  * *Metaheuristic only* vs *heuristic + exact certificate*: metaheuristics can't tell you they're optimal; an exact B&B on 16 nodes runs in milliseconds and turns "we think 9 is good" into "9 is provably minimal". → both, exact under a time limit so large N degrade gracefully to heuristics.
  * *Exact via ILP (scipy HiGHS)* vs *custom DSATUR B&B*: ILP adds a solver dependency to the runtime path; B&B is self-contained. ILP is kept **in the test-suite only** as an independent cross-check of the B&B optimum.
* **Acceptance**: every result passes the Stage-1 verifier; K = LB on the 4×4 grid (9); B&B optimum equals ILP optimum on ≥ 100 random instances; portfolio never worse than the best networkx strategy on the benchmark set; runtime at N = 16 < 1 s.

## Stage 3 — CLI, report, JSON export, simulator, tests, benchmarks

* **Goal**: the mandated CLI deliverable in the sample format, plus evidence.
* **Method**: `tdma_scheduler.py` — positional JSON string (also `--file`, `@file`, `-` stdin), `--range`, `--json-out`, `--max-reuse`, `--simulate F`, `--verbose`, `--seed`, `--time-limit`; output mirrors the sample (header, Node→Slot list, `Slot \ Node | 01 | …` matrix, final verification line) plus a short "optimality" block. Exit code reflects verification. **Slot-level simulator**: F frames of saturated broadcast traffic; a reception at r from t in slot s succeeds iff r ∈ N(t), r is not transmitting in s, and t is the only transmitting neighbour of r; counts deliveries, hidden-terminal collisions, half-duplex losses; compares optimised vs naive (1-hop-only colouring; round-robin one-node-per-slot). **Benchmarks**: random uniform topologies (N = 16 at several densities; N = 50/100/200), slots vs LB vs networkx baselines, optimality rate, time.
* **Why**: slot-level simulation vs ns-3/packet-level: the claims are about slot-sharing, so a slot-level model is exact for them, transparent and fast; EMANE (Stage 4) supplies the realistic packet-level check.
* **Acceptance**: pytest green; CLI output for the 4×4 grid matches the sample layout line by line (format) with K = 9; simulator shows 0 collisions for every optimised schedule over the benchmark set and > 0 for 1-hop-only colourings on graphs with hidden terminals; independent reviewer subagent finds no unresolved defect.

## Stage 4 — EMANE engine (Part 2)

* **Goal**: EMANE TDMA model enforces the Brain's schedule; packets are carried in scheduled slots and lost when the schedule is violated.
* **Method**: bridge `emane/bridge/schedule_to_emane.py` reads the Stage-3 JSON and writes (a) `schedule.xml` (EMANE TDMA schedule: structure 1 frame × K slots × 1000 µs, overhead 100 µs, bandwidth 10 MHz; multiframe frequency 2.4 GHz, datarate 10 Mbps, power 0 dBm; one `<slot index="s" nodes="…"><tx/></slot>` per slot; unlisted slots default to rx), validated against EMANE's `tdmaschedule.xsd` and parsed by EMANE's own `TDMASchedule` class; (b) optionally publishes `TDMAScheduleEvent` ProtoBuf events directly; (c) platform / NEM / TDMA MAC / PHY / virtual-transport XML per node; (d) precomputed pathloss events from the unit-disk graph. Runner: 16 unprivileged network namespaces bridged on a hub namespace (OTA + event multicast), one `emane` per node with a TAP device, UDP broadcast probes per node, `emanesh` statistics capture. Experiments: E1 optimised schedule; E2 a node with its TX slot removed (packets must be dropped/queued); E3 a conflicting (1-hop-only) schedule (hidden-terminal / half-duplex losses).
* **Why (alternatives compared)**: Docker (not installed) vs native root install (no sudo) vs **rootless sysroot + user namespaces** (proven to work) → rootless; Dockerfile also supplied for graders (marked untested). Pathloss: location events + free-space (500 m edge depends on tuned power/sensitivity, fuzzy) vs **precomputed pathloss from the same graph** (exactly the Brain's model) → precomputed. XML vs ProtoBuf → both (A10).
* **Acceptance**: XML passes XSD + EMANE parser; on a real EMANE run: `scheduleAcceptFull` = 1 per NEM, TX activity only in each node's assigned slot index, per-link delivery ≈ 100 % on graph links and 0 % off-graph for E1, observable drops for E2/E3. If the run cannot be completed, the stage still ships validated configs + bridge + a precise account of what failed (Part 2 is approach-graded).

## Stage 5 — Documentation, presentation, packaging

* **Goal**: mandated `docs/Documentation.pdf` (design process, thought process, final values) and `presentation/*.pptx`; README with exact run commands; local Git repository with a clean history.
* **Method**: documentation authored in Markdown → HTML (python-markdown) → PDF (headless Edge print, or the pdf-skill route if better), with figures generated by matplotlib from real outputs (topology + slot colouring, benchmark charts, EMANE slot tables). Presentation via the `pptx` skill.
* **Why**: Markdown keeps a single source of truth that is also readable on Git; HTML→PDF gives good typography without a LaTeX package-install dependency.
* **Acceptance**: PDF opens, all figures present, every number in it traceable to a file in `outputs/`, `benchmarks/` or `emane/results/`; PPTX opens and renders; `git status` clean after commit.

## Phase 3 — Integration and final review

Requirements-traceability table (R1–R19, I1–I13 → file + evidence), adversarial red-team (subagent + my own), efficiency pass (profiling the CLI), `FINAL_REPORT.md`.

---

## Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| K1 | Copying the sample's "5 slots" (invalid for its own input) | – | High | Documented in A2; tests assert 9 on the grid and 0 conflicts |
| K2 | Floating-point edge at exactly 500 m | Med | Med | Squared distances + relative tolerance; boundary unit tests |
| K3 | PowerShell 5.1 strips quotes in JSON argument | High (Windows graders) | Med | Lenient bare-key repair + `--file`/`@file`/stdin; documented |
| K4 | Exact solver blows up for large N | Med (N ≥ 200) | Low | Time limit; heuristic result always returned; status "best found" vs "proven optimal" |
| K5 | No root / no Docker for EMANE | Certain | High | Rootless sysroot + user namespaces (proven in Phase 0); Dockerfile for graders |
| K6 | EMANE 1 ms timing unstable under WSL with 16 NEMs | Med | Med | Inspect slot-timing quartiles and missed-slot counters; moderate traffic; report honestly |
| K7 | Packet larger than slot capacity | Med | Med | 10 Mbps × 0.9 ms = 1125 B per slot; probes 64 B payload; fragmentation enabled |
| K8 | EMANE connectivity ≠ Brain graph | Med | High | Precomputed pathloss events derived from the same graph; verify via delivery matrix |
| K9 | Over-claiming results | Low | High | Every number in docs comes from a saved artefact; untested items labelled |
| K10 | Pushing to GitHub needs the user's account | Certain | Low | Local repo + commit; push instructions in README; user decides |
| K11 | Misreading "spatial reuse wherever possible" | Low | Med | Base colouring (literal) + optional `--max-reuse` extension, clearly separated |
| K12 | Deadline (7 days from receipt) | Unknown | High | Outside my control; noted in FINAL_REPORT |
