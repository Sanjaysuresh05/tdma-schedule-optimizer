# Phase 0: Understanding the problem

Source: `Vaan Megam - Wireless Developer Internship .pdf` (5 pages). I read every page, including the sample output, the Part 2 task list, the references, "Points to consider", the submission rules and the selection process. The original file is never modified.

---

## 0.1 The problem in my own words

A set of radios share one frequency. Time is split into a repeating **frame** of equal **slots**. Each radio transmits only in its own slot(s). Two radios that are too close must not transmit in the same slot:

* **1-hop conflict (direct link):** if A and B can hear each other and both transmit at once, neither receives the other's packet (half-duplex), and each other neighbour gets a collision.
* **2-hop conflict (hidden terminal):** if A and C cannot hear each other but share a neighbour B, simultaneous transmissions from A and C collide at B.

Radios more than 2 hops apart can reuse the same slot (**spatial reuse**).

**Part 1 (mandatory), the "Brain":** A Python CLI takes the (x, y) coordinates of 16 radios as a JSON string. It builds the radio graph with networkx (edge if distance is at most 500 m) and solves a **distance-2 colouring** (colour = slot). The goal is as few slots as possible, which is NP-hard in general, so heuristics are expected. It prints a node-to-slot table and a Slot × Node 0/1 matrix in the sample's ASCII format, and certifies that the schedule is conflict-free.

**Part 2 (bonus, graded on approach), the "Engine":** Run EMANE's TDMA radio model on one Linux machine (or one Docker container) with 1 ms slots. Convert the Brain's schedule into an EMANE TDMA schedule (XML file or ProtoBuf event). Show that EMANE carries or drops packets between the virtual nodes according to that schedule.

**Wrap-up:** A Git repository containing the source, a **documentation PDF** (design process, thought process, final values) and a **presentation PPT**. I must be able to explain and defend every part.

---

## 0.2 Requirements

### Explicit requirements (traced in the final traceability table)

| ID | Requirement (from the PDF) | Part |
|---|---|---|
| R1 | Python environment using **networkx**; radios = nodes, links = edges | 1 |
| R2 | Radios are linked iff they are **within 500 m** | 1 |
| R3 | **Distance-2 (two-hop) graph colouring**; colours = exclusive slots of a synchronised recurring frame | 1 |
| R4 | Direct-link interference: adjacent (1-hop) nodes get different slots | 1 |
| R5 | Hidden terminal: nodes with a common neighbour (2-hop) get different slots | 1 |
| R6 | Spatial reuse: nodes more than 2 hops apart may share a slot | 1 |
| R7 | Heuristics that **reduce the total number of slots** and enable spatial reuse wherever possible | 1 |
| R8 | A **CLI script** that takes static coordinates of **16 nodes** | 1 |
| R9 | Input via a **standardised JSON string argument** `{"Node_01":[0.0,0.0],...}` | 1 |
| R10 | Outputs an explicit **Slot × Node binary matrix** in text/ASCII | 1 |
| R11 | Also outputs a direct **Node → Slot mapping** | 1 |
| R12 | Output follows the **sample report** layout (header, frame length, assignments, matrix, verification line) | 1 |
| G1 | *Grading:* **collision avoidance** | 1 |
| G2 | *Grading:* **effectiveness of the heuristics** (fewer slots, spatial reuse) | 1 |
| R13 | Install **EMANE** on one Linux machine or in one consolidated Docker container | 2 |
| R14 | Configure EMANE's native **TDMA radio model XML** profiles (**1 ms slots**, frames, frequencies) | 2 |
| R15 | **Integration bridge:** schedule matrix → **XML or ProtoBuf** schedule event recognised by EMANE | 2 |
| R16 | EMANE **drops or permits packets** between virtual nodes **strictly per the Part 1 schedule** | 2 |
| R17 | **Documentation (PDF)** of Parts 1 and 2: design process, thought process, **final values** (MANDATORY) | both |
| R18 | **Git repository** with source code, documentation (PDF), presentation (PPT) | both |
| R19 | Every part must be explainable and defensible at the presentation | both |

### Hidden or implied requirements

| ID | Implied requirement | Why it follows |
|---|---|---|
| I1 | The "verified conflict-free" line must come from an **independent check**, not just be printed | G1 is graded; a hard-coded claim would be dishonest |
| I2 | Deterministic, reproducible output (same input gives the same schedule) | Graders rerun the CLI; the presentation demo must match the PDF |
| I3 | Robust input validation with clear errors (bad JSON, duplicate keys, wrong arity, NaN/inf, booleans) | A CLI judged by a strict panel |
| I4 | Correct for **any** 16-node layout: disconnected graphs, isolated nodes, co-located nodes, cliques, chains | "static coordinates of 16 nodes", not only the example grid |
| I5 | Should scale beyond 16 nodes | Credibility of the heuristics; Vaan Megam's MANET context |
| I6 | Report the slot count against a **lower bound**, so "effectiveness" can be measured | G2 needs a yardstick, and "lower is better" needs a floor |
| I7 | Machine-readable export (JSON) for the bridge | R15 |
| I8 | Works on Windows: **PowerShell 5.1 strips the inner double quotes** of native-command arguments | The grader may run the example command on Windows |
| I9 | Fast at N = 16 (well under 1 s) | Live demo |
| I10 | Node name ↔ EMANE NEM id mapping (NEM ids are integers ≥ 1) | EMANE schema `NodeType` pattern `[1-9][0-9]*` |
| I11 | EMANE connectivity must match the 500 m unit-disk model, otherwise the schedule's guarantee does not carry over | R16 "strictly based on the schedule" |
| I12 | A 1 ms slot must physically fit a packet: bytes per slot = datarate × (slot − overhead) | EMANE drops "too big" packets or fragments them |
| I13 | Honest reporting of what was and was not executed (Part 2 result "not expected") | User rule: never fabricate |

### Constraints

* N = 16 nodes in the target case. Range R = 500 m. Nodes are 2-D points in metres.
* The schedule is a single recurring frame, and every node needs at least one slot (it must be able to talk).
* Python and networkx are mandated. EMANE's TDMA model is mandated for Part 2.
* Environment found in Phase 0: Windows 11, Python 3.11, networkx 3.6.1. **No Docker. WSL2 Ubuntu 24.04 is present, but `sudo` needs a password I do not have.** Unprivileged user + network namespaces work, including bridge and TUN (tested).
* Deadline: 7 days from receipt. I cannot see the receipt date; I record it as a constraint the user must watch.

### Inputs and outputs

* **Input:** JSON object `{name: [x, y], ...}` given as a CLI argument. I also accept `--file` and stdin. Optional: `--range` (default 500).
* **Output (stdout):** the sample-format report. **Exit code** 0 if verified conflict-free, non-zero on invalid input or failed verification. **Optional JSON** (`--json-out`) for the bridge.
* **Part 2 outputs:** EMANE schedule XML, platform/NEM/MAC/PHY/transport XML, pathloss events, run scripts, captured EMANE statistics and per-link delivery results.

### Success metrics and scoring

1. **Collisions = 0** for every schedule produced. This is checked by a verifier that is independent of the solver, and empirically by a slot-level simulator. It is binding.
2. **Frame length K**: minimise it. It is reported next to the lower bound ω(G²), with optimality proven when K = LB or when exact search closes the gap.
3. **Spatial reuse factor** N/K (average transmitters per slot). Higher is better. At a fixed K, extra non-conflicting slots per node add capacity.
4. Runtime well under 1 s at N = 16.
5. Part 2: a schedule accepted by EMANE (`scheduler.scheduleAcceptFull`), TX only in the scheduled slots (TxSlotStatusTable), per-link delivery that matches the graph, and collisions or drops when a deliberately bad schedule is used.

---

## 0.3 Ambiguities and how I resolve them

| # | Ambiguity | Resolution | Why |
|---|---|---|---|
| A1 | "within 500 m": `<` or `≤`? | **`≤` (inclusive)**, compared on squared distances with a 1e-9 relative tolerance | "Within" includes the boundary. Squared distances avoid sqrt rounding, so (0,0)–(300,400) is exactly 500 and counts as linked. |
| A2 | **The sample output contradicts the sample input.** The input `Node_01:[0,0], Node_02:[300,0] … Node_16:[900,900]` is a 4×4 grid with 300 m spacing. The sample gives Node_01 and Node_03 the same slot, yet they share neighbour Node_02 (a 2-hop conflict). I counted **21 conflicting pairs** in the sample output. | The sample is a **format template only**. I reproduce the format, not the numbers. For the 4×4 grid the true optimum is **9 slots**: any 3×3 block of nodes is pairwise within 2 hops, giving a 9-clique in G², so K ≥ 9, and the colouring (i mod 3, j mod 3) achieves 9. | Copying "5 slots" would break R4/R5 and G1. Explaining this in the documentation shows the rule was understood. |
| A3 | The coordinates for Node_03 … Node_15 are elided ("…") | The canonical input is the 4×4 row-major grid: Node_k → (300·((k−1) mod 4), 300·⌊(k−1)/4⌋). This is the only 16-point 300 m lattice from (0,0) to (900,900) that starts with Node_02 at (300,0). | This is the most defensible completion. The CLI accepts any coordinates anyway. |
| A4 | Interference model | Protocol / unit-disk model: interference range = communication range = 500 m, broadcast transmissions (each transmission is heard by all neighbours) | The PDF defines conflicts purely by hops in the 500 m graph. Distance-2 colouring is exactly collision-free broadcast scheduling under this model. |
| A5 | "Spatial reuse wherever possible" | (a) The base schedule is a colouring, so far-apart nodes share slots. (b) Optional `--max-reuse` gives nodes **extra** slots in the same frame when no node within 2 hops uses that slot. It is shown as a separate matrix, so the required one-slot-per-node mapping is unchanged. | (a) is the literal requirement. (b) is a defensible extension that never adds collisions. |
| A6 | Must N be exactly 16? | The 16-node case is the target and is fully supported. Any N ≥ 1 is accepted, and a note goes to stderr when N ≠ 16. | Robustness and scalability. Rejecting other sizes adds nothing. |
| A7 | Slot numbering | 0-based (`Slot 0`, matrix rows `Slot 00`), as in the sample. Slots are relabelled in order of first appearance along the node order, so Node_01 is always Slot 0. | Matches the sample and gives deterministic, canonical output. |
| A8 | Node ordering and matrix column labels | Natural sort of node names (Node_2 < Node_10). Column label = the name's numeric suffix, zero-padded (`01`…`16`). If names have no numeric suffix, the column index is used and a legend is printed. | Matches the sample exactly for the standard input. |
| A9 | Which heuristic? | A **portfolio** (DSATUR, RLF, largest-first, smallest-last, randomised greedy), then iterated greedy, then **TabuCol**, plus an **exact DSATUR branch-and-bound** certificate under a time limit | "Graded on effectiveness of heuristics": run the best ones and prove how good the result is. |
| A10 | "XML or ProtoBuf schedule event" | **Both.** The bridge writes EMANE TDMA schedule XML (validated against EMANE's own XSD and parsed by EMANE's own `TDMASchedule` class). It can also build and publish `TDMAScheduleEvent` ProtoBuf events directly through EMANE's Python API. | Covers either reading of R15. |
| A11 | "Install EMANE … single Linux machine" with no root or Docker | **Rootless install:** the official Adjacent Link EMANE 1.5.3 Ubuntu 24.04 `.deb`s are extracted into a user-owned sysroot in WSL2 Ubuntu 24.04, and each node runs in an unprivileged user + network namespace. A Dockerfile is also provided, marked **not built here** because Docker is not installed. | Works within real limits without touching system configuration or bypassing sudo. |
| A12 | 1 ms slots: data rate, frequency, overhead? | `slotduration=1000 µs`, `slotoverhead=100 µs` (guard ≫ 1.7 µs propagation over 500 m), frequency 2.4 GHz, bandwidth 10 MHz, datarate 10 Mbps, so (1000−100) µs × 10 Mb/s = 1125 bytes per slot | Fits a typical IP packet in one slot, with guard time well above propagation delay. |
| A13 | How EMANE "knows" the 500 m graph | **Precomputed pathloss events** generated from the same unit-disk graph: linked pairs get a pathloss well inside the link budget, unlinked pairs get a pathloss far below the noise floor | Ties EMANE connectivity exactly to the Brain's model (I11). |
| A14 | Deliverables "PDF documentation" and "PPT" | `docs/Documentation.pdf` and `presentation/*.pptx` inside the Git repo. The repo is initialised and committed locally. **Not pushed**: pushing to a remote publishes under the user's account, which is the user's call. | Matches the submission format without taking an outward-facing action. |

---

## 0.4 Hardest parts, biggest risks, and how I handle them

1. **Proving heuristic quality, not just claiming it.** I compute the clique lower bound ω(G²) exactly and run an exact branch-and-bound to certify optimality. I benchmark against networkx's greedy colourings on hundreds of random topologies.
2. **Collision-freedom must be airtight.** The verifier recomputes the graph from raw coordinates and does not reuse the solver's graph. It checks every pair within 2 hops, then the matrix and mapping consistency. A slot-level simulator confirms zero collisions empirically. An independent reviewer subagent attacks the code.
3. **The sample output is wrong for its input (A2).** I explain it rather than imitate it.
4. **EMANE without root or Docker.** I proved in Phase 0 that unprivileged user namespaces with bridge and TUN work in WSL2, and that the EMANE 1.5.3 binaries and Python API run from the extracted sysroot (`emane --version` → 1.5.3; `from emane.events import TDMAScheduleEvent` works).
5. **EMANE timing at 1 ms with 16 NEMs on 8 cores.** I watch TxSlotStatusTable/RxSlotStatusTable quartiles and missed-slot counters, and keep traffic moderate.
6. **Windows PowerShell JSON quoting (I8).** A lenient parser repairs bare keys, and `--file`/stdin/`@file` alternatives are offered.
7. **Honesty about Part 2.** Every claim in the documentation points to a saved log or statistics file. Anything not executed is labelled as such.

---

## 0.5 State of the art and prior solutions (sources)

**Problem class.** Collision-free node-based TDMA under the 2-hop rule is the **Broadcast Scheduling Problem**. It is equivalent to distance-2 colouring of G, which is proper colouring of the square graph G² (u ~ v in G² iff 1 ≤ d_G(u,v) ≤ 2).
* Ephremides & Truong, "Scheduling broadcasts in multihop radio networks," *IEEE Trans. Commun.* 38(4):456–460, 1990. This is the classic formulation; secondary sources record that it shows broadcast scheduling is NP-complete. I confirmed this through citing works (e.g. Ramanathan & Lloyd 1993; arXiv:1712.00658), not the paywalled original.
* Ramanathan & Lloyd, "Scheduling algorithms for multihop radio networks," *IEEE/ACM Trans. Networking* 1(2), 1993 (https://www.eecis.udel.edu/~elloyd/papers.d/ramton.pdf). It gives ordering-based broadcast scheduling heuristics with bounds in terms of network "thickness".
* Krumke, Marathe & Ravi, "Models and approximation algorithms for channel assignment in radio networks," *Wireless Networks* 7, 2001 (Springer DOI 10.1023/A:1012311216333). It casts broadcast scheduling as distance-2 colouring and gives approximation algorithms on geometric graph classes.
* McCormick, "Optimal approximation of sparse Hessians and its equivalence to a graph coloring problem," *Math. Programming* 26:153–171, 1983 (DOI 10.1007/BF02592052). This is the classical distance-2 colouring reference from numerical optimisation.
* Gebremedhin, Manne & Pothen, "What color is your Jacobian? Graph coloring for computing derivatives," *SIAM Review* 47(4):629–705, 2005. It surveys distance-2 colouring variants and greedy algorithms.
* Gräf, Stumpf & Weißenfels, "On coloring unit disk graphs," *Algorithmica*, 1998 (DOI 10.1007/PL00009196). Colouring unit-disk graphs stays NP-complete for any fixed k ≥ 3; they give a 3-approximation.

**Colouring heuristics used here.**
* DSATUR: Brélaz, "New methods to color the vertices of a graph," *CACM* 22(4):251–256, 1979.
* RLF: Leighton, "A graph coloring algorithm for large scheduling problems," *J. Res. NBS* 84(6):489–506, 1979 (https://nvlpubs.nist.gov/nistpubs/jres/84/jresv84n6p489_A1b.pdf).
* Smallest-last: Matula & Beck, *J. ACM* 30(3):417–427, 1983 (DOI 10.1145/2402.322385).
* Iterated Greedy: Culberson & Luo, "Exploring the k-colorable landscape with iterated greedy," DIMACS Series vol. 26, AMS, 1996, pp. 245–284. Re-colouring in an order that respects previous colour classes never increases the colour count.
* TabuCol: Hertz & de Werra, "Using tabu search techniques for graph coloring," *Computing* 39:345–351, 1987.
* Exact DSATUR branch-and-bound: Brélaz 1979; San Segundo, "A new DSATUR-based algorithm for exact vertex coloring," *Computers & OR* 39(7):1724–1733, 2012.
* NetworkX `greedy_color` strategies (largest_first, smallest_last, DSATUR, independent_set, connected_sequential_*): https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.coloring.greedy_color.html. These serve as the **baseline** in my benchmarks.

**EMANE (primary sources).**
* TDMA radio model documentation: https://emane.io/tdma-radio-model. It covers the schedule XML (structure / multiframe / frame / slot, tx/rx/idle) and full vs update schedules. Schedules take effect at the next multiframe boundary from the epoch. Undefined slots in a full schedule default to **rx**. It also documents `emaneevent-tdmaschedule`, the scheduler accept/reject counters, Rx/TxSlotStatusTable, and the drop reasons (queue overflow, too big, rx during tx/idle, wrong frequency, SINR/POR).
* EMANE install page with the official 1.5.3 Ubuntu 24.04 bundle: https://github.com/adjacentlink/emane/wiki/Install. Release tags: https://github.com/adjacentlink/emane/tags (v1.5.3, 14 Jul 2025).
* EMANE 1.5.3 package files read locally: `emane/events/schema/tdmaschedule.xsd` (the authoritative schedule schema), `emane/events/tdmascheduleevent.py` (the ProtoBuf event API: `structure(slots, frames, slotduration, slotoverhead, bandwidth)`, `append(frameIndex, slotIndex, type=tx|rx|idle, frequency, datarate, service, power, destination)`), and `emane/events/tdmaschedule.py` (EMANE's own XML parser).

**Known pitfalls carried into the design:** 1-hop-only colouring leaves hidden-terminal collisions. Greedy colouring with a bad order can approach Δ(G²)+1 colours. The unit-disk assumption ignores the SINR-based interference tail beyond 500 m, which is a modelling limitation and is stated. EMANE needs every NEM referenced in a full schedule, and an erroneous schedule flushes all schedule state. Slot overhead must cover the propagation delay.
