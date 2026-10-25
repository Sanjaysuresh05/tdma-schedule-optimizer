# Stage 1 Report: Network model, conflict graph, lower bounds, independent verifier

## What I did
* `tdma_brain/parsing.py` parses and validates the coordinate JSON input. It rejects duplicate keys, NaN/Infinity/overflow, booleans, numeric strings, wrong arity, non-objects and empty input. It repairs the quote-stripped form that PowerShell 5.1 produces (`{Node_01:[0,0]}`).
* `tdma_brain/topology.py` builds the unit-disk connectivity graph G with networkx (inclusive 500 m test) and the conflict graph H = G² with a `hops` (1|2) attribute on every edge. It also computes the lower bounds Δ(G)+1 and ω(H) (exact maximum clique) and some descriptive statistics.
* `tdma_brain/verify.py` is an independent verifier. It uses no networkx and no topology code, recomputes adjacency from the raw coordinates, and checks the printed Slot × Node matrix plus the Node → Slot mapping.
* `tests/test_stage1_model.py` has 33 tests, including 500 random instances where G² is checked against `nx.power`, 1 500 random schedules where the verifier is checked against a brute-force BFS definition, and 300 mutation tests.

## Why this method
* **Explicit G², then ordinary colouring** (instead of re-implementing 2-hop checks inside every algorithm). Distance-2 colouring of G is *exactly* proper colouring of G². So every classical colouring algorithm, and networkx's own baselines, apply without change, and the 2-hop logic lives in one audited place.
* **All-pairs O(N²) distance test** (instead of spatial hashing). At N = 16 it is 120 comparisons. Even at N = 1000 it takes under 0.5 s and is trivially correct.
* **Inclusive `≤` on squared distances with a 1e-12 relative tolerance.** "Within 500 m" includes 500 m. Squared distances avoid `sqrt` rounding. The tolerance absorbs decimal-to-binary rounding only (e.g. 353.553…·√2 = 500), which is about 0.25 nm at 500 m. An earlier value of 1e-9 (about 0.25 µm) was tightened after the independent review showed it could link pairs 0.1 µm beyond 500 m.
* **A verifier separate from the optimiser.** If the verifier reused the optimiser's graph, a bug in graph construction would be invisible to it. Two independent implementations make that much less likely, and the tests compare both against a third (networkx BFS).

## How it works
**Intuition.** A slot is "safe" for a set of transmitters T if every listener hears at most one of them and no transmitter is also trying to listen to another member of T. Both failure modes involve nodes at most 2 hops apart. So T is safe iff its members are pairwise at least 3 hops apart.

**Maths.**
* G = (V, E) with E = {uv : ‖p_u − p_v‖² ≤ R²(1+10⁻¹²)}.
* H = G² has an edge uv iff 1 ≤ d_G(u,v) ≤ 2. It is built as E(G) ∪ {ab : a, b ∈ N(w) for some w}.
* A schedule is a map c: V → {0…K−1}. It is collision-free ⇔ c(u) ≠ c(v) for every uv ∈ E(H), i.e. c is a proper colouring of H. The frame length is K, and the optimum is χ(H).
* Lower bounds: for every v the closed neighbourhood N[v] is a clique in H (any two of its members are within 2 hops through v), so χ(H) ≥ Δ(G)+1. More generally χ(H) ≥ ω(H), which is computed exactly with networkx's `max_weight_clique` branch-and-bound.

**Implementation.** `Topology(coords, R)` sorts the names naturally (so Node_2 comes before Node_10), builds G and H, and caches the maximum clique. `verify_matrix(coords, R, order, matrix, mapping)` rebuilds adjacency with plain loops. For each slot row it checks every pair of transmitters for a direct link or a common neighbour. It also checks that every node has a slot, that the mapping agrees with the matrix, and that no slot row is empty.

**Worked numerical example.** A(0,0), B(400,0), C(800,0), D(1600,0), R = 500 m.
* Squared distances: AB = 160 000 ≤ 250 000 (link). BC = 160 000 (link). AC = 640 000 (no link). CD = 640 000 (no link). BD and AD are larger still. So E(G) = {AB, BC}, and D is isolated.
* H adds AC with hops = 2, because A and C are both neighbours of B. So E(H) = {AB, BC, AC}.
* Bounds: Δ(G)+1 = 3 (node B). N[B] = {A, B, C} is a 3-clique in H, so ω = 3.
* The schedule A→0, B→1, C→2, D→0 is valid: D is more than 2 hops from A, so it reuses slot 0 (spatial reuse). K = 3 = lower bound, so it is optimal. The test `test_direct_and_hidden_detection` checks exactly this case. It also checks that putting A and C together is reported as "hidden terminal via B", and that putting A and B together is reported as "direct".

## Results and evidence
* `python -m pytest tests/test_stage1_model.py` → **33 passed in 2.2 s**.
* The 4×4 sample grid (300 m spacing) has **42 links** (24 orthogonal at 300 m and 18 diagonal at 424.3 m), max degree 8, **90 conflict pairs** (42 at 1 hop and 48 at 2 hops), and **ω(G²) = 9** (any 3×3 block). **No schedule with fewer than 9 slots exists for this input.**
* **Finding:** the PDF's sample output (5 slots) applied to the PDF's sample grid has **21 conflicting pairs**; for example Node_01 and Node_03 collide at Node_02. This is asserted in `test_problem_statement_sample_output_is_not_valid_for_the_grid`. The sample is therefore a format template, and I follow its format, not its numbers (assumption A2).
* Agreement with the brute-force check on 1 500 random schedules covered both outcomes, with more than 50 valid and more than 50 invalid cases. All 300 injected conflicts were detected.

## Assumptions and limitations
* Unit-disk (protocol) interference model: a node interferes exactly where it can be heard. Real SINR interference has a tail beyond 500 m. That is out of scope for the stated model, and Stage 4 makes EMANE's channel match this model on purpose.
* Coordinates are planar metres. No terrain or antenna patterns are modelled.
* Above 3 000 conflict-graph nodes the clique bound becomes greedy, so it is still a valid bound but possibly a weaker one. This never applies at N = 16.

## Later fixes (after the independent review, see stage_3_report.md § Review)
* The verifier uses `dx*dx` instead of `**2`, so float overflow can never raise.
* The parser additionally rejects coordinates with |v| > 10⁹ m, integers that overflow a float, nesting that is too deep, names with control or format characters, and names with leading or trailing whitespace.
* `natural_key` compares ASCII digit runs as strings by length and value, so there is no `int()` call: Unicode digits and 5 000-digit names cannot crash it.
* The exact clique search runs on integer labels, so the reported clique does not depend on Python's per-process string hash seed.

## Final deliverable
`tdma_brain/__init__.py`, `tdma_brain/parsing.py`, `tdma_brain/topology.py`, `tdma_brain/verify.py`, `tests/conftest.py`, `tests/test_stage1_model.py`
