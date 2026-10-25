// Build presentation/TDMA_Schedule_Optimizer.pptx (pptxgenjs).
//
//   python presentation/make_deck_data.py          # numbers from the real result files
//   NODE_PATH=<dir with pptxgenjs> node presentation/build_deck.js
//
// Optional: APPLY_THEME_JS=<path to apply_theme.js> writes the palette into the
// deck's theme (only matters when adding new content in PowerPoint; every colour
// used below is explicit hex, so the deck renders identically without it).
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..");
const FIG = (f) => path.join(ROOT, "docs", "figures", f);
const D = JSON.parse(fs.readFileSync(path.join(__dirname, "deck_data.json"), "utf8"));
const OUT = path.join(__dirname, "TDMA_Schedule_Optimizer.pptx");

// ---- palette: deep teal-ink (dominant), teal = collision-free, amber = slots/time, coral = conflict
const K = {
  dark: "0B2A33", teal: "12877F", tealLight: "D7ECEA", amber: "E8A33D", coral: "D9533A",
  ink: "1E2A30", muted: "5B6B70", tint: "EEF5F4", white: "FFFFFF", grey: "9AA5A8", rule: "D5DEDF",
};
const THEME = {
  name: "VMN TDMA", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: K.ink, lt1: K.white, dk2: K.dark, lt2: K.tint, accent1: K.teal, accent2: K.amber,
            accent3: K.coral, accent4: "3E7CB1", accent5: "7A9E7E", accent6: K.grey, hlink: K.teal, folHlink: K.muted },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.author = "Sanjay Suresh";
pres.title = "TDMA Schedule Planner & Optimizer";
pres.subject = "Vaan Megam Networks - Wireless Protocol Development internship task";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };

const W = 13.333, H = 7.5, MX = 0.6;

// ---- motif: a TDMA frame strip (9 slot tiles), used small on every content slide
function frameStrip(slideOrMaster, x, y, size, gap, colors, objects) {
  const out = [];
  for (let i = 0; i < 9; i++) {
    out.push({ rect: { x: x + i * (size + gap), y, w: size, h: size, fill: { color: colors[i % colors.length] },
                       line: { color: colors[i % colors.length], width: 0 } } });
  }
  return out;
}
const STRIP_COLORS = [K.teal, K.teal, K.amber, K.teal, K.teal, K.teal, K.amber, K.teal, K.teal];

pres.defineSlideMaster({
  title: "DARK_TITLE",
  background: { color: K.dark },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 1.1, w: 9.4, h: 1.65,
        fontFace: "Cambria", fontSize: 40, bold: true, color: K.white, valign: "top", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: MX, y: 2.85, w: 9.4, h: 0.9,
        fontFace: "Calibri", fontSize: 20, color: K.tealLight, valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: K.white },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    ...frameStrip(null, W - MX - 9 * 0.14 - 8 * 0.05, 0.55, 0.14, 0.05, STRIP_COLORS),
    { text: { text: "Vaan Megam Networks  ·  TDMA Schedule Planner & Optimizer",
              options: { x: MX, y: H - 0.45, w: 8, h: 0.3, fontFace: "Calibri", fontSize: 10, color: K.muted, margin: 0 } } },
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.35, w: 10.6, h: 0.75,
        fontFace: "Cambria", fontSize: 28, bold: true, color: K.dark, valign: "middle", align: "left", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: W - MX - 0.6, y: H - 0.45, w: 0.6, h: 0.3, fontFace: "Calibri", fontSize: 10, color: K.muted, align: "right" },
});
pres.defineSlideMaster({
  title: "SECTION",
  background: { color: K.dark },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 2.7, w: 11, h: 1.0,
        fontFace: "Cambria", fontSize: 40, bold: true, color: K.white, align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: MX, y: 3.75, w: 11, h: 0.8,
        fontFace: "Calibri", fontSize: 20, color: K.tealLight, align: "left", margin: 0 }, text: "" } },
  ],
});

// ---- helpers ----------------------------------------------------------------------------
const txt = (slide, text, o) => slide.addText(text, { isTextBox: true, fontFace: "Calibri", color: K.ink, margin: 0, ...o });

function card(slide, x, y, w, h, fill = K.tint) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill, width: 0 } });
}
function stat(slide, x, y, w, value, label, color = K.teal, valueSize = 44, onDark = false) {
  txt(slide, value, { x, y, w, h: 0.85, fontFace: "Cambria", fontSize: valueSize, bold: true, color });
  txt(slide, label, { x, y: y + 0.85, w, h: 0.75, fontSize: 14, color: onDark ? K.tealLight : K.muted, valign: "top" });
}
function numberBadge(slide, x, y, n, color = K.teal) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color }, line: { color, width: 0 } });
  txt(slide, String(n), { x, y, w: 0.42, h: 0.42, fontSize: 14, bold: true, color: K.white, align: "center", valign: "middle" });
}
function iconRows(slide, x, y, w, rows, gap = 0.95, color = K.teal) {
  rows.forEach(([head, body], i) => {
    numberBadge(slide, x, y + i * gap, i + 1, Array.isArray(color) ? color[i] : color);
    txt(slide, head, { x: x + 0.6, y: y + i * gap - 0.04, w: w - 0.6, h: 0.36, fontSize: 16, bold: true, color: K.ink });
    txt(slide, body, { x: x + 0.6, y: y + i * gap + 0.3, w: w - 0.6, h: 0.55, fontSize: 14, color: K.muted, valign: "top" });
  });
}
function node(slide, x, y, label, fill = K.white, line = K.dark, r = 0.32) {
  slide.addShape(pres.shapes.OVAL, { x: x - r, y: y - r, w: 2 * r, h: 2 * r, fill: { color: fill }, line: { color: line, width: 2 } });
  txt(slide, label, { x: x - r, y: y - r, w: 2 * r, h: 2 * r, fontSize: 16, bold: true, align: "center", valign: "middle",
                      color: fill === K.white ? K.dark : K.white });
}
function arrow(slide, x1, y1, x2, y2, color = K.dark, both = false, width = 2) {
  slide.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001,
    flipH: x2 < x1, flipV: y2 < y1, line: { color, width, endArrowType: "triangle", beginArrowType: both ? "triangle" : undefined } });
}
function flowBox(slide, x, y, w, h, head, body, fill = K.tint, headColor = K.dark) {
  card(slide, x, y, w, h, fill);
  txt(slide, head, { x: x + 0.15, y: y + 0.12, w: w - 0.3, h: 0.45, fontSize: 16, bold: true, color: headColor, valign: "top" });
  txt(slide, body, { x: x + 0.15, y: y + 0.6, w: w - 0.3, h: h - 0.7, fontSize: 14, color: K.ink, valign: "top" });
}

// =========================================================================================
pres.addSection({ title: "Introduction" });
// 1. Title
{
  const s = pres.addSlide({ masterName: "DARK_TITLE", sectionTitle: "Introduction" });
  s.addText("TDMA Schedule Planner & Optimizer", { placeholder: "title" });
  s.addText("Distance-2 graph colouring for collision-free TDMA, enforced in an EMANE emulation", { placeholder: "body" });
  txt(s, "Sanjay Suresh  ·  Vaan Megam Networks, Wireless Protocol Development internship task  ·  October 2026",
      { x: MX, y: 3.85, w: 11, h: 0.4, fontSize: 14, color: K.grey });
  // frame strip as hero graphic
  for (let i = 0; i < 9; i++) {
    const c = [K.teal, K.teal, K.amber, K.teal, K.teal, K.teal, K.amber, K.teal, K.teal][i];
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 10.35 + (i % 3) * 0.78, y: 1.25 + Math.floor(i / 3) * 0.78, w: 0.66, h: 0.66,
      rectRadius: 0.06, fill: { color: c }, line: { color: c, width: 0 } });
    txt(s, "S" + i, { x: 10.35 + (i % 3) * 0.78, y: 1.25 + Math.floor(i / 3) * 0.78, w: 0.66, h: 0.66, fontSize: 14, bold: true,
                      color: K.white, align: "center", valign: "middle" });
  }
  const stats = [[`${D.grid_slots} slots`, "proven optimal for the PDF's 16-node sample grid"],
                 ["0 collisions", "independent verifier, simulator and EMANE agree"],
                 [`${D.emane.E1_optimized.on_mean} %`, "EMANE delivery on scheduled links (0 % off-links)"]];
  stats.forEach(([v, l], i) => {
    const x = MX + i * 4.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 4.7, w: 3.8, h: 1.9, rectRadius: 0.08, fill: { color: "133B46" }, line: { color: "133B46", width: 0 } });
    txt(s, v, { x: x + 0.3, y: 4.9, w: 3.3, h: 0.8, fontFace: "Cambria", fontSize: 34, bold: true, color: i === 0 ? K.amber : K.white });
    txt(s, l, { x: x + 0.3, y: 5.75, w: 3.3, h: 0.7, fontSize: 14, color: K.tealLight, valign: "top" });
  });
  s.addNotes("Opening: the task is a centralised TDMA scheduler (Part 1, mandatory) plus EMANE enforcement (Part 2, bonus). " +
    "Three headline numbers: 9 slots, proven minimal, for the sample grid; zero collisions confirmed three independent ways; " +
    "and in EMANE the schedule is enforced, 99.96 % delivery on links and 0 % off-links.");
}

// 2. The problem
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
  s.addText("Radios share one channel by taking turns", { placeholder: "title" });
  txt(s, [
    { text: "Time is a repeating frame of slots; each radio transmits only in its own slot.", options: { bullet: true, breakLine: true } },
    { text: "Direct link (1 hop): A and B cannot both talk; each would miss the other.", options: { bullet: true, breakLine: true } },
    { text: "Hidden terminal (2 hops): A and C cannot hear each other, but collide at B.", options: { bullet: true, breakLine: true } },
    { text: "More than 2 hops apart: the same slot is safe. That is spatial reuse.", options: { bullet: true } },
  ], { x: MX, y: 1.5, w: 5.9, h: 3.4, fontSize: 18, paraSpaceAfter: 12, valign: "top" });
  card(s, MX, 5.2, 5.9, 1.3);
  txt(s, "Goal: give every radio a slot so that no receiver ever hears two transmitters at once, using as few slots as possible.",
      { x: MX + 0.25, y: 5.3, w: 5.4, h: 1.1, fontSize: 16, bold: true, color: K.dark, valign: "middle" });
  // diagram 1: direct
  txt(s, "Distance-1: direct link", { x: 7.3, y: 1.45, w: 5.3, h: 0.4, fontSize: 16, bold: true, color: K.dark });
  node(s, 8.2, 2.45, "A"); node(s, 10.6, 2.45, "B");
  arrow(s, 8.55, 2.45, 10.25, 2.45, K.coral, true, 2.5);
  txt(s, "different slots required", { x: 8.4, y: 2.85, w: 2.1, h: 0.35, fontSize: 12, color: K.coral, align: "center" });
  // diagram 2: hidden terminal
  txt(s, "Distance-2: hidden terminal", { x: 7.3, y: 3.6, w: 5.3, h: 0.4, fontSize: 16, bold: true, color: K.dark });
  node(s, 7.9, 4.75, "A"); node(s, 9.75, 4.75, "B", K.coral, K.coral); node(s, 11.6, 4.75, "C");
  arrow(s, 8.25, 4.75, 9.4, 4.75, K.dark); arrow(s, 11.25, 4.75, 10.1, 4.75, K.dark);
  txt(s, "A and C collide at B", { x: 8.7, y: 5.2, w: 2.1, h: 0.35, fontSize: 12, color: K.coral, align: "center" });
  txt(s, "500 m radio range: radios within 500 m are linked", { x: 7.3, y: 6.0, w: 5.3, h: 0.35, fontSize: 12, color: K.muted });
  s.addNotes("These are the two collision mechanisms from the problem statement. Distance-2 colouring means two nodes that are " +
    "adjacent, or share a neighbour, get different slots. Everything further apart may reuse a slot.");
}

// 3. The model
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
  s.addText("The model: colour the square of the radio graph", { placeholder: "title" });
  iconRows(s, MX, 1.55, 6.2, [
    ["G: link if distance ≤ 500 m", "networkx graph; squared distances, inclusive boundary"],
    ["H = G²: join nodes ≤ 2 hops apart", "1-hop and 2-hop conflicts in one conflict graph"],
    ["Slot = colour", "any proper colouring of H is a collision-free schedule"],
    ["Minimise colours = χ(G²), NP-hard", "lower bound ω(G²): a clique of H needs distinct slots"],
  ], 1.12);
  s.addImage({ path: FIG("grid_topology.png"), x: 7.25, y: 1.3, w: 5.45, h: 4.92 });
  txt(s, "Sample grid: 42 links (300 m and 424 m), each node hears up to 8 others", { x: 7.25, y: 6.25, w: 5.45, h: 0.35, fontSize: 12, color: K.muted });
  s.addNotes("Reduction: distance-2 colouring of G equals ordinary colouring of the square graph, so all classical colouring " +
    "algorithms apply. The clique lower bound is what lets me prove optimality later.");
}

// 4. Finding
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
  s.addText("The sample output is infeasible: 9 slots is minimal", { placeholder: "title" });
  card(s, MX, 1.5, 5.8, 2.6, "FBE9E5");
  stat(s, MX + 0.35, 1.7, 5.2, "21", "two-hop conflicts in the PDF's 5-slot sample assignment, checked against its own 4×4 grid input", K.coral, 60);
  card(s, 6.95, 1.5, 5.8, 2.6, K.tint);
  stat(s, 7.3, 1.7, 5.2, `${D.grid_slots}`, "slots: provably the minimum. Any 3×3 block of nodes is pairwise within 2 hops, a 9-clique of G²", K.teal, 60);
  txt(s, [
    { text: "Example: the sample gives Node_01 and Node_03 the same slot, yet both hear Node_02 (hidden terminal).", options: { bullet: true, breakLine: true } },
    { text: "The colouring 3·(i mod 3) + (j mod 3) reaches 9, and this tool finds a 9-slot schedule in 1.4 ms.", options: { bullet: true, breakLine: true } },
    { text: "I follow the sample's format exactly (--sample-format is byte-for-byte), not its numbers.", options: { bullet: true } },
  ], { x: MX, y: 4.5, w: 12.1, h: 2.0, fontSize: 17, paraSpaceAfter: 10, valign: "top" });
  s.addNotes("This is the first thing a careful reader notices: the PDF's sample output is a format template. " +
    "Verified by an automated test and by the independent reviewer's ILP. Copying 5 slots would fail the collision criterion.");
}

pres.addSection({ title: "Part 1: the Brain" });
// 5. Pipeline
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 1: the Brain" });
  s.addText("Heuristics first, then a proof", { placeholder: "title" });
  const steps = [
    ["Lower bound", "ω(G²) by exact max clique (Bron-Kerbosch)"],
    ["Portfolio", "DSATUR, RLF, largest-first, smallest-last, BFS, sweep, 64 random orders"],
    ["Iterated greedy", "recolour by classes; can never use more slots"],
    ["TabuCol", "local search: try K−1, K−2, …"],
    ["Exact B&B", "DSATUR branch-and-bound proves the optimum"],
  ];
  const bw = 2.25, gap = 0.22, y0 = 1.6;
  steps.forEach(([h, b], i) => {
    const x = MX + i * (bw + gap);
    flowBox(s, x, y0, bw, 1.95, h, b, i === 4 ? "E2F1EF" : K.tint);
    numberBadge(s, x + bw - 0.55, y0 + 0.12, i + 1);
    if (i < steps.length - 1) arrow(s, x + bw + 0.02, y0 + 0.97, x + bw + gap - 0.02, y0 + 0.97, K.dark);
  });
  card(s, MX, 3.9, 12.1, 0.95, "FDF3E3");
  txt(s, "Every step runs only while K exceeds the lower bound: on the sample grid DSATUR hits 9 = ω and the pipeline stops after the portfolio (1.4 ms).",
      { x: MX + 0.25, y: 3.95, w: 11.6, h: 0.85, fontSize: 16, color: K.ink, valign: "middle" });
  txt(s, [
    { text: "Independent verifier", options: { bold: true, color: K.dark } },
    { text: ": a separate implementation (no networkx) recomputes links from the raw coordinates and checks every same-slot pair of the printed matrix. Exit code 0 only if it passes.", options: { color: K.ink } },
  ], { x: MX, y: 5.2, w: 12.1, h: 1.0, fontSize: 16, valign: "top" });
  s.addNotes("Why a portfolio: no single colouring heuristic wins everywhere (the benchmark shows the winner changes). " +
    "Why the exact step: heuristics cannot tell you they are optimal; at N = 16 the proof costs milliseconds. " +
    "Exact optimum cross-checked against a scipy/HiGHS ILP on 120 random instances.");
}

// 6. Output
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 1: the Brain" });
  s.addText("Output: the required report, verified", { placeholder: "title" });
  const L = D.grid_report_lines;
  const m = L.findIndex((l) => l.startsWith("STRUCTURAL"));
  const pick = [...L.slice(0, 13), "  ...", ...L.slice(m, m + 6), "  ...", ...L.slice(-3, -1)];
  card(s, MX, 1.3, 12.1, 3.95, "F4F6F6");
  txt(s, pick.join(String.fromCharCode(10)), { x: MX + 0.2, y: 1.4, w: 11.7, h: 3.8, fontFace: "Consolas", fontSize: 10, color: K.ink, valign: "top" });
  const call = [["Sample layout", "same sections and labels; --sample-format is byte-exact"],
                ["Proof printed", "lower bound and optimality status in the header"],
                ["Verified, not claimed", "independent check; exit code 0 / 1 / 2 / 3"],
                ["Robust input", "JSON string, @file, --file, stdin; PowerShell quote repair"]];
  call.forEach(([h, b], i) => {
    const x = MX + i * 3.08;
    numberBadge(s, x, 5.5, i + 1);
    txt(s, h, { x: x + 0.55, y: 5.45, w: 2.4, h: 0.4, fontSize: 15, bold: true, color: K.ink });
    txt(s, b, { x: x + 0.55, y: 5.85, w: 2.4, h: 0.8, fontSize: 13, color: K.muted, valign: "top" });
  });
  s.addNotes("Run live: python tdma_scheduler.py --file inputs/grid_4x4.json. Options: --verbose, --max-reuse, --simulate 100, --json-out.");
}

// 7. Spatial reuse
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 1: the Brain" });
  s.addText("Spatial reuse: 16 radios in 9 slots", { placeholder: "title" });
  s.addImage({ path: FIG("grid_4x4_slots.png"), x: MX, y: 1.25, w: 5.6, h: 5.6 });
  stat(s, 6.7, 1.5, 6.0, "1.78×", "throughput of one-node-per-slot TDMA: 9.33 vs 5.25 successful receptions per slot (slot-level simulator)", K.teal, 54);
  txt(s, [
    { text: "Corners share slot 0; edge nodes 900 m apart share slots 1, 2, 3 and 6.", options: { bullet: true, breakLine: true } },
    { text: "No receiver lies inside two coverage discs of the same slot.", options: { bullet: true, breakLine: true } },
    { text: "--max-reuse adds extra non-conflicting slots in the same frame (random_16: 16 → 26 transmissions per frame).", options: { bullet: true } },
  ], { x: 6.7, y: 3.45, w: 6.0, h: 2.6, fontSize: 16, paraSpaceAfter: 10, valign: "top" });
  s.addNotes("Each panel is one slot: filled nodes transmit, the wash is their 500 m coverage. " +
    "The inner four nodes each need their own slot because every one of them is within 2 hops of almost everyone.");
}

// 8. Benchmark (native chart)
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 1: the Brain" });
  s.addText(`${D.n_proven} of ${D.n_instances} networks solved optimally, with proof`, { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "Mean extra slots vs optimum (N = 50-200)", labels: D.method_labels.slice().reverse(), values: D.excess_large.slice().reverse() }], {
    x: MX, y: 1.3, w: 7.6, h: 5.4, barDir: "bar", chartColors: [K.grey],
    showTitle: true, title: "Mean extra slots over the proven optimum, N = 50-200 (110 networks)", titleFontSize: 13, titleColor: K.ink, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: K.ink, dataLabelFormatCode: "0.00", dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: K.ink, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt", valAxisHidden: true,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, barGapWidthPct: 60,
  });
  stat(s, 8.6, 1.45, 4.2, `${D.n_proven}/${D.n_instances}`, "networks (N = 13-200) solved optimally with a proof", K.teal, 44);
  stat(s, 8.6, 3.15, 4.2, `${D.ring_gap_instances} of ${D.n_ring}`, "rings where the optimum exceeds the clique bound: only the exact search can prove them", K.amber, 40);
  stat(s, 8.6, 4.85, 4.2, `≤ ${Math.ceil(D.max_time_ms_n200)} ms`, `at N = 200 (mean ${D.mean_time_ms_n16} ms at N = 16)`, K.dark, 40);
  s.addNotes("Every single heuristic misses the optimum somewhere; networkx independent-set misses on all 20 networks at N = 200. " +
    "Honest note: on random unit-disk graphs the best of all seven networkx strategies together is usually optimal too; " +
    "the pipeline's value is that it reaches the optimum every time and proves it.");
}

// 9. Throughput (native chart)
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 1: the Brain" });
  s.addText("Why the 2-hop rule matters", { placeholder: "title" });
  const sets = ["N16-1000m", "N16-1600m", "N50-2000m", "N200-4000m"];
  const labels = ["16 nodes, 1 km²", "16 nodes, 1.6 km²", "50 nodes, 2 km²", "200 nodes, 4 km²"];
  s.addChart(pres.charts.BAR, [
    { name: "This tool (distance-2, optimal)", labels, values: sets.map((k) => D.sim[k].sim_opt_deliv_per_slot) },
    { name: "Round-robin TDMA (no reuse)", labels, values: sets.map((k) => D.sim[k].sim_rr_deliv_per_slot) },
    { name: "Distance-1 colouring (hidden terminals)", labels, values: sets.map((k) => D.sim[k].sim_d1_deliv_per_slot) },
  ], {
    x: MX, y: 1.3, w: 8.0, h: 5.4, barDir: "col", barGrouping: "clustered", chartColors: [K.teal, K.grey, K.coral],
    showTitle: true, title: "Successful receptions per slot (slot-level simulator, saturated broadcast)", titleFontSize: 13, titleColor: K.ink, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelColor: K.ink, dataLabelFormatCode: "0.0", dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: K.ink, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt", valAxisLabelColor: K.muted, valAxisLabelFontSize: 10,
    valAxisLabelFontFace: "+mn-lt", valGridLine: { color: K.rule, size: 0.5 }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: "+mn-lt", legendColor: K.ink, barGapWidthPct: 70,
  });
  stat(s, 9.0, 1.45, 3.8, "0", "receptions lost by this tool's schedules on 638 benchmark networks", K.teal, 54);
  stat(s, 9.0, 3.35, 3.8, `${Math.round(100 * D.sim["N16-1000m"].sim_d1_lost_frac)}-${Math.round(100 * D.sim["N200-4000m"].sim_d1_lost_frac)} %`,
       "of receptions lost by a distance-1 colouring (hidden terminals)", K.coral, 40);
  stat(s, 9.0, 5.1, 3.8, "×10.7", "throughput vs round-robin at 200 nodes (95.2 vs 8.9 per slot)", K.dark, 36);
  s.addNotes("Round-robin is collision-free but wastes the channel; a 1-hop-only colouring uses fewer slots but loses half its packets " +
    "to hidden terminals. Distance-2 colouring gets both: no losses and spatial reuse.");
}

// 10. Trust
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 1: the Brain" });
  s.addText("Trust: verified independently, three ways", { placeholder: "title" });
  const cards = [
    ["91", "automated tests", "G² vs networkx (500 graphs) · verifier vs brute force (1 500) · exact B&B vs ILP (120) · printed report re-parsed and re-verified · identical output under 3 hash seeds"],
    ["0", "collisions found by an independent reviewer", "fresh AI reviewer, no access to my reasoning: 320 fuzzed CLI runs with its own checker and ILP. Found 8 input/output robustness defects; all 8 fixed with regression tests"],
    [`${D.e3_predicted} vs ${D.emane.E3_distance1.on_mean} %`, "simulator vs EMANE", "two independent models predict and measure the same hidden-terminal losses on a deliberately wrong schedule"],
  ];
  cards.forEach(([v, h, b], i) => {
    const x = MX + i * 4.1;
    card(s, x, 1.45, 3.8, 4.9);
    txt(s, v, { x: x + 0.3, y: 1.7, w: 3.2, h: 0.9, fontFace: "Cambria", fontSize: i === 2 ? 34 : 48, bold: true, color: i === 2 ? K.amber : K.teal });
    txt(s, h, { x: x + 0.3, y: 2.65, w: 3.2, h: 0.75, fontSize: 17, bold: true, color: K.dark, valign: "top" });
    txt(s, b, { x: x + 0.3, y: 3.45, w: 3.2, h: 2.7, fontSize: 14, color: K.ink, valign: "top" });
  });
  s.addNotes("The verification is layered so that no single bug can produce a false 'conflict-free'. " +
    "The reviewer's defects were all at the input/output boundary (encoding, overflow, exit codes, a sub-micrometre tolerance); none affected collisions.");
}

pres.addSection({ title: "Part 2: EMANE" });
// 11. Section divider
{
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: "Part 2: EMANE" });
  s.addText("Part 2: the EMANE engine", { placeholder: "title" });
  s.addText("Does a real TDMA emulator carry and drop packets exactly as the Brain planned?", { placeholder: "body" });
  s.addNotes("EMANE 1.5.3 on one Linux machine (WSL2 Ubuntu 24.04), 16 emulated radios.");
}

// 12. Architecture
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 2: EMANE" });
  s.addText("From matrix to EMANE in one bridge", { placeholder: "title" });
  flowBox(s, MX, 1.6, 2.55, 2.2, "Brain JSON", "--json-out: nodes, NEM ids, Slot × Node matrix, 500 m links");
  arrow(s, MX + 2.6, 2.7, MX + 3.0, 2.7, K.dark);
  flowBox(s, 3.65, 1.6, 2.7, 2.2, "schedule_to_emane.py", "validated against EMANE's own XSD; round-trip checked", "E2F1EF");
  arrow(s, 6.4, 2.7, 6.8, 2.7, K.dark);
  const outs = [["schedule.xml", "full TDMA schedule (XML route)"], ["TDMAScheduleEvent", "ProtoBuf, one event per NEM"],
                ["pathloss 90 / 200 dB", "EMANE's channel = the 500 m graph"], ["16 × platform XML", "virtual transport → TDMA MAC → PHY"]];
  outs.forEach(([h, b], i) => {
    card(s, 6.85, 1.45 + i * 0.66, 2.9, 0.58);
    txt(s, [{ text: h, options: { bold: true, color: K.dark, breakLine: true } }, { text: b, options: { color: K.muted, fontSize: 11 } }],
        { x: 6.97, y: 1.47 + i * 0.66, w: 2.7, h: 0.55, fontSize: 13, valign: "middle" });
  });
  arrow(s, 9.8, 2.7, 10.2, 2.7, K.dark);
  flowBox(s, 10.25, 1.6, 2.5, 2.2, "EMANE 1.5.3", "16 NEMs, each in its own unprivileged network namespace", K.dark, K.white);
  s.addText("16 NEMs, each in its own unprivileged network namespace", { x: 10.4, y: 2.2, w: 2.2, h: 1.4, isTextBox: true, fontFace: "Calibri", fontSize: 13, color: K.white, margin: 0, valign: "top" });
  iconRows(s, MX, 4.35, 12.1, [
    ["Rootless install", "no Docker, no sudo: the official .debs are extracted into a user sysroot (install_rootless.sh); a Dockerfile is provided but not built here"],
    ["Testbed", "hub bridge for OTA and event multicast; Poisson UDP broadcast probes; statistics read from every NEM's control port"],
  ], 1.0);
  s.addNotes("Both requested formats are implemented and tested: the XML route (what emaneevent-tdmaschedule does) and the ProtoBuf route " +
    "(TDMAScheduleEvent built directly). Precomputed pathloss makes EMANE's connectivity identical to the Brain's 500 m graph.");
}

// 13. TDMA profile
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 2: EMANE" });
  s.addText("TDMA profile: 1 ms slots, 9-slot frame", { placeholder: "title" });
  const st = [["1000 µs", "slot (100 µs guard ≫ 1.7 µs propagation over 500 m)"], ["9 ms", "frame = 9 slots, 1 frame per multiframe"],
              ["2.4 GHz", "carrier · 10 MHz bandwidth · 30 dBm"], ["1350 B", "per slot at 12 Mbit/s (12·10⁶ × 900 µs / 8)"]];
  st.forEach(([v, l], i) => {
    const x = MX + i * 3.08;
    card(s, x, 1.45, 2.85, 1.9);
    txt(s, v, { x: x + 0.2, y: 1.6, w: 2.5, h: 0.75, fontFace: "Cambria", fontSize: 32, bold: true, color: i === 0 ? K.amber : K.teal });
    txt(s, l, { x: x + 0.2, y: 2.38, w: 2.5, h: 0.9, fontSize: 13, color: K.ink, valign: "top" });
  });
  const xml = ["<emane-tdma-schedule>", "  <structure frames=\"1\" slots=\"9\" slotoverhead=\"100\"", "             slotduration=\"1000\" bandwidth=\"10M\"/>",
               "  <multiframe frequency=\"2.4G\" power=\"30\" class=\"0\" datarate=\"12M\">", "    <frame index=\"0\">",
               "      <slot index=\"0\" nodes=\"1,4,13,16\"/>", "      <slot index=\"1\" nodes=\"2,14\"/>", "      ...",
               "      <slot index=\"8\" nodes=\"11\"/>", "    </frame>", "  </multiframe>", "</emane-tdma-schedule>"];
  card(s, MX, 3.65, 7.1, 3.05, "F4F6F6");
  txt(s, xml.join("\n"), { x: MX + 0.2, y: 3.75, w: 6.8, h: 2.9, fontFace: "Consolas", fontSize: 11, color: K.ink, valign: "top" });
  txt(s, [
    { text: "Defined slot = TX for the listed NEMs; every other slot defaults to RX (half-duplex TDMA)", options: { bullet: true, breakLine: true } },
    { text: "Link budget: 30 − 90 = −60 dBm vs −100 dBm noise → SNR 40 dB, always decoded", options: { bullet: true, breakLine: true } },
    { text: "Two equal signals: SINR ≈ 0 dB, below the 12 Mbit/s curve's 3 dB floor → collision", options: { bullet: true } },
  ], { x: 8.05, y: 3.75, w: 4.7, h: 2.95, fontSize: 15, paraSpaceAfter: 10, valign: "top" });
  s.addNotes("The schedule XML is generated from the matrix: one slot element per row. The PCR curve for 12 Mbit/s gives 0 % reception " +
    "at SINR <= 3 dB and 100 % at >= 9 dB, so overlap is fatal and a clean link is perfect.");
}

// 14. Results table
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 2: EMANE" });
  s.addText("EMANE carries and drops packets as planned", { placeholder: "title" });
  const E = D.emane;
  const hdr = ["Experiment", "Slots", "Delivery on 500 m links", "Non-links", "Frames heard in sender's slot", "Collision drops"];
  const row = (cells, bold) => cells.map((c, i) => ({ text: String(c), options: { bold: bold || i === 0, fontSize: 12, color: K.ink, fill: { color: bold ? K.tint : K.white } } }));
  const attr = (e) => (e.attr_mean === null ? "-" : `${e.attr_mean} %`);
  s.addTable([
    row(hdr, true),
    row(["E1  Brain schedule (XML route)", 9, `${E.E1_optimized.on_mean} %`, `${E.E1_optimized.off_max} %`, attr(E.E1_optimized), "0"]),
    row(["E1b  same, ProtoBuf route", 9, `${E.E1b_protobuf.on_mean} %`, `${E.E1b_protobuf.off_max} %`, attr(E.E1b_protobuf), "0"]),
    row(["E2  Node_06's slot removed", 9, `others ${E.E2_silenced.on_active_mean} %; Node_06 0 %`, `${E.E2_silenced.off_max} %`, `${attr(E.E2_silenced)}; Node_06 sent ${E.E2_silenced.silenced_air_tx} frames`, `0 (${E.E2_silenced.queue_overflow} queue drops)`]),
    row(["E3  wrong (distance-1) schedule", 4, `${E.E3_distance1.on_mean} %`, `${E.E3_distance1.off_max} %`, attr(E.E3_distance1), `${(E.E3_distance1.sinr_bytes / 1000).toFixed(0)} kB (SINR)`]),
    row([`E4  E1 at ${E.E4_highload.rate} pkt/s per node`, 9, `${E.E4_highload.on_mean} %`, `${E.E4_highload.off_max} %`, attr(E.E4_highload), `${(E.E4_highload.sinr_bytes / 1000).toFixed(0)} kB`]),
  ], { x: MX, y: 1.35, w: 12.1, colW: [3.2, 0.7, 2.9, 1.1, 2.6, 1.6], border: { type: "solid", pt: 0.75, color: K.rule }, rowH: 0.48, valign: "middle" });
  iconRows(s, MX, 4.85, 12.1, [
    ["Permitted where planned", "every scheduled link delivers; no frame ever crosses a non-link; latency = half a frame + one slot, as TDMA theory predicts"],
    ["Dropped where the schedule says", "a node without a TX slot puts 0 frames on the air (its queue overflows); a schedule that breaks the 2-hop rule collides"],
  ], 0.95, [K.teal, K.coral]);
  s.addNotes(`All 16 NEMs accepted every schedule (0 rejects); traffic starts only after that is confirmed. E1 residual loss ` +
    `(${(100 - E.E1_optimized.on_mean).toFixed(2)} %) is host timing: EMANE missed ${E.E1_optimized.tx_missed} of ${E.E1_optimized.tx_valid} TX slots because ` +
    `realtime priority needs root. Mean latency ${E.E1_optimized.latency} ms.`);
}

// 15. Receiver-side evidence
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 2: EMANE" });
  s.addText("Each sender is heard only in its planned slot", { placeholder: "title" });
  s.addImage({ path: FIG("emane_slot_enforcement.png"), x: MX, y: 1.3, w: 9.0, h: 2.86 });
  s.addImage({ path: FIG("emane_slot_attribution.png"), x: 9.85, y: 1.3, w: 2.9, h: 2.54 });
  const E1 = D.emane.E1_optimized;
  const st = [[`${E1.attr_mean} %`, `of each sender's over-the-air frames were received by its neighbours in exactly its planned slot (${E1.attr_links} links, min ${E1.attr_min} %)`],
              [`${E1.stray_valid}`, "frames received in any slot where the receiver has no scheduled neighbour"],
              [`${D.emane.E2_silenced.silenced_air_tx}`, "frames transmitted by Node_06 once its slot was removed (E2)"]];
  st.forEach(([v, l], i) => {
    const x = MX + i * 4.1;
    card(s, x, 4.45, 3.8, 2.2);
    txt(s, v, { x: x + 0.25, y: 4.55, w: 3.3, h: 0.8, fontFace: "Cambria", fontSize: 36, bold: true, color: i === 0 ? K.teal : K.dark });
    txt(s, l, { x: x + 0.25, y: 5.35, w: 3.3, h: 1.25, fontSize: 13, color: K.ink, valign: "top" });
  });
  s.addNotes("This evidence uses physical events at both ends: frames the sender put on the air (EMANE PHY) and frames the " +
    "receiver got in each slot (EMANE RxSlotStatusTable). It does not rely on EMANE's installed-schedule tables, which " +
    "an independent reviewer correctly pointed out would only compare the schedule with itself.");
}

// 16. Agreement and repeatability
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 2: EMANE" });
  s.addText("Predicted = measured, and repeatable", { placeholder: "title" });
  s.addImage({ path: FIG("emane_e3_predicted_vs_measured.png"), x: MX, y: 1.3, w: 5.2, h: 4.86 });
  txt(s, `E3 (wrong schedule): my slot-level simulator vs EMANE, per link (${D.e3_predicted} % vs ${D.emane.E3_distance1.on_mean} % overall)`,
      { x: MX, y: 6.2, w: 5.2, h: 0.5, fontSize: 12, color: K.muted, valign: "top" });
  const R = D.replication || {};
  const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
  const ci = (a) => { const m = mean(a); const sd = Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / (a.length - 1)); return 2.776 * sd / Math.sqrt(a.length); };
  const rows = [["Schedule", "Delivery on links, 5 traffic seeds", "Mean ± 95 % CI", "Expected"]];
  if (R.E1) rows.push(["E1 Brain (9 slots)", R.E1.map((v) => v.toFixed(2)).join(", "), `${mean(R.E1).toFixed(2)} ± ${ci(R.E1).toFixed(2)} %`, "100 %"]);
  if (R.E3) rows.push(["E3 distance-1 (4 slots)", R.E3.map((v) => v.toFixed(1)).join(", "), `${mean(R.E3).toFixed(1)} ± ${ci(R.E3).toFixed(1)} %`, `${D.e3_predicted} % (simulator)`]);
  s.addTable(rows.map((r, i) => r.map((c, j) => ({ text: c, options: { fontSize: 12, bold: i === 0 || j === 0, color: K.ink, fill: { color: i === 0 ? K.tint : K.white } } }))),
             { x: 6.3, y: 1.45, w: 6.45, colW: [1.7, 2.2, 1.4, 1.15], border: { type: "solid", pt: 0.75, color: K.rule }, rowH: 0.6, valign: "middle" });
  txt(s, [
    { text: "Two independent implementations agree: ", options: { bold: true, color: K.dark } },
    { text: "links with two hidden interferers deliver about 60 %, links with one about 85 %, links with none 100 %, in both the simulator and EMANE's PHY/MAC.", options: { color: K.ink } },
  ], { x: 6.3, y: 3.7, w: 6.45, h: 1.2, fontSize: 15, valign: "top" });
  txt(s, [
    { text: "Latency follows TDMA theory: ", options: { bold: true, color: K.dark } },
    { text: `half a frame + one slot. Measured ${D.emane.E1_optimized.latency} ms (9-slot frame) and ${D.emane.E3_distance1.latency} ms (4-slot frame).`, options: { color: K.ink } },
  ], { x: 6.3, y: 5.0, w: 6.45, h: 1.0, fontSize: 15, valign: "top" });
  s.addNotes("Replication answers the 'single run' objection: five different Poisson traffic seeds per schedule, mean and 95 % " +
    "confidence interval (Student t, 4 degrees of freedom).");
}

// 17. Stress tests
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Part 2: EMANE" });
  s.addText("Stress tests: 10× load, and a physical channel", { placeholder: "title" });
  const E4 = D.emane.E4_highload, E5 = D.emane.E5_freespace;
  card(s, MX, 1.4, 5.9, 2.4);
  txt(s, [{ text: `E4: ${E4.rate} packets/s per node`, options: { bold: true, color: K.dark, breakLine: true } },
          { text: `${E4.on_mean} % delivered on links. Several packets are aggregated into one 1 ms slot (1350 B), so the 9-slot schedule carries 10× the load; the remaining loss is slot-timing jitter on the rootless host (0 collisions, 0 queue drops).`, options: { color: K.ink } }],
      { x: MX + 0.25, y: 1.55, w: 5.4, h: 2.1, fontSize: 15, valign: "top" });
  card(s, 6.85, 1.4, 5.9, 2.4, "FDF3E3");
  txt(s, [{ text: "E5: free-space path loss for every pair", options: { bold: true, color: K.dark, breakLine: true } },
          { text: `No 500 m cut-off (power set so the 100 % decode edge is about 500 m). Links ${E5.on_mean} %, and ${E5.off_max} % reaches some non-neighbours: physics has no hard edge.`, options: { color: K.ink } }],
      { x: 7.1, y: 1.55, w: 5.4, h: 2.1, fontSize: 15, valign: "top" });
  s.addImage({ path: FIG("emane_delivery_matrices.png"), x: MX, y: 4.05, w: 12.1, h: 2.75 });
  s.addNotes("E5 deliberately breaks the task's unit-disk assumption. Free space has a long tail: co-slot transmitters 900 m apart " +
    "are only about 6.5 dB weaker than a 424 m link, below the 9 dB the 12 Mbit/s curve needs. The remedy stays inside the Brain: " +
    "plan with an interference radius (--range) larger than the decode range, add power margin, or use a terrain path-loss model.");
}

pres.addSection({ title: "Close" });
// 18. Limitations
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Close" });
  s.addText("Limitations, stated plainly", { placeholder: "title" });
  iconRows(s, MX, 1.55, 12.1, [
    ["Interference model = unit disk (500 m), as the task defines", "E5 quantifies the gap: with free-space propagation the interference range exceeds 2 hops; plan with a larger --range"],
    ["EMANE ran rootless on WSL2 without realtime priority", `${(100 * D.emane.E1_optimized.tx_missed / D.emane.E1_optimized.tx_valid).toFixed(2)} % of TX slots missed (host timing); a real-root run can enable -r (VMN_EMANE_REALTIME=1)`],
    ["Dockerfile provided but not built", "Docker is not installed on the development machine; the native rootless path was executed"],
    ["Broadcast traffic, static topology", "node-based broadcast scheduling as specified; unicast/ARP and mobility not exercised"],
    ["NP-hard at scale", "if the exact search hits its limit, the tool reports 'optimum in [LB, K]'; never happened up to N = 200"],
  ], 0.98, [K.amber, K.amber, K.amber, K.amber, K.amber]);
  s.addNotes("Every limitation is also in the documentation PDF with its evidence.");
}

// 19. Close
{
  const s = pres.addSlide({ masterName: "DARK_TITLE", sectionTitle: "Close" });
  s.addText("Summary", { placeholder: "title" });
  s.addText("Correct by construction, optimal with proof, enforced in EMANE", { placeholder: "body" });
  const items = [["Correct", "distance-2 colouring of the 500 m graph; independently verified, 0 collisions"],
                 ["Optimal", `9 slots for the sample grid, proven; ${D.n_proven}/${D.n_instances} benchmark networks optimal with proof`],
                 ["Enforced", `EMANE: each sender heard only in its planned slot; ${D.emane.E1_optimized.on_mean} % on links, 0 % off-links`]];
  items.forEach(([h, b], i) => {
    const x = MX + i * 4.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 3.75, w: 3.8, h: 1.8, rectRadius: 0.08, fill: { color: "133B46" }, line: { color: "133B46", width: 0 } });
    txt(s, h, { x: x + 0.3, y: 3.9, w: 3.2, h: 0.5, fontFace: "Cambria", fontSize: 24, bold: true, color: K.amber });
    txt(s, b, { x: x + 0.3, y: 4.45, w: 3.2, h: 1.0, fontSize: 14, color: K.white, valign: "top" });
  });
  txt(s, "Demo:  python tdma_scheduler.py --file inputs/grid_4x4.json   ·   bash emane/runner/run_experiments.sh 20 40",
      { x: MX, y: 6.0, w: 12.1, h: 0.4, fontFace: "Consolas", fontSize: 13, color: K.tealLight });
  txt(s, "Questions welcome", { x: MX, y: 6.5, w: 6, h: 0.4, fontSize: 16, bold: true, color: K.white });
  s.addNotes("Close with the three words: correct, optimal, enforced. Then demo the CLI and show emane/results/summary.md.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  if (process.env.APPLY_THEME_JS) {
    const { applyTheme } = require(process.env.APPLY_THEME_JS);
    await applyTheme(OUT, THEME);
  }
  console.log("wrote", OUT);
})();
