"""Stage 3: CLI behaviour, report format, JSON export, simulator."""

import io
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tdma_brain.cli import main
from tdma_brain.optimizer import optimize
from tdma_brain.simulator import baseline_schedules, simulate
from tdma_brain.topology import Topology
from tdma_brain.verify import matrix_from_slots, verify_matrix

ROOT = Path(__file__).resolve().parents[1]
GRID_JSON = (ROOT / "inputs" / "grid_4x4.json").read_text()
GRID = {k: tuple(v) for k, v in json.loads(GRID_JSON).items()}


def run(argv, capsys, stdin=None, monkeypatch=None):
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    code = main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def parse_report(text):
    """Re-read mapping and matrix from the printed report (end-to-end check)."""
    mapping = {m.group(1): int(m.group(2)) for m in re.finditer(r"^ (\S+): Slot (\d+)", text, re.M)}
    block = text.split("STRUCTURAL TDMA SCHEDULE MATRIX")[1]
    rows = [list(map(int, re.findall(r"\|\s*([01])\s*(?=\||$)", line)))
            for line in block.splitlines() if re.match(r"^Slot \d\d", line)]
    return mapping, rows


# ------------------------------------------------------------- CLI / report
def test_grid_report_matches_sample_layout(capsys):
    code, out, _ = run([GRID_JSON], capsys)
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == "=" * 64 and lines[1] == " TDMA TOPOLOGY OPTIMIZATION REPORT " and lines[2] == "=" * 64
    assert "Total Nodes Processed : 16" in lines
    assert "Configured Radio Range : 500.0 meters" in lines
    assert "Optimized Frame Length : 9 unique timeslots (Lower is better)" in lines
    assert "NODE -> SLOT ASSIGNMENTS:" in lines
    assert " Node_01: Slot 0" in lines
    assert "STRUCTURAL TDMA SCHEDULE MATRIX (Slot x Node Boolean Matrix):" in lines
    assert any(l.startswith("Slot \\ Node | 01 | 02 |") and l.endswith("| 16") for l in lines)
    assert lines[-2] == "Execution finalized cleanly. Schedule verified conflict-free."
    assert all(ord(ch) < 128 for ch in out)  # pure ASCII


def test_printed_report_is_itself_conflict_free(capsys):
    """Parse the *printed text* back and verify it independently."""
    for f in sorted((ROOT / "inputs").glob("*.json")):
        coords = {k: tuple(v) for k, v in json.loads(f.read_text()).items()}
        code, out, _ = run(["--file", str(f)], capsys)
        assert code == 0, f
        mapping, rows = parse_report(out)
        order = sorted(coords, key=lambda n: int(n.split("_")[1]))
        assert len(mapping) == 16 and len(rows) == max(mapping.values()) + 1
        assert verify_matrix(coords, 500.0, order, rows, mapping).ok, f


def test_input_forms_agree(capsys, monkeypatch, tmp_path):
    p = tmp_path / "in.json"
    p.write_text(GRID_JSON)
    spaced = json.dumps(json.loads(GRID_JSON))          # '{"Node_01": [0.0, 0.0], ...}'
    outs = [
        run([GRID_JSON], capsys)[1],
        run(["--file", str(p)], capsys)[1],
        run(["@" + str(p)], capsys)[1],
        run(["-"], capsys, stdin=GRID_JSON, monkeypatch=monkeypatch)[1],
        run([GRID_JSON.replace('"', "")], capsys)[1],        # PowerShell-stripped quotes
        run(spaced.replace('"', "").split(" "), capsys)[1],  # ...and split at the spaces
    ]
    strip = lambda s: re.sub(r"\d+\.\d+ ms", "", s)  # timing varies
    assert all(strip(o) == strip(outs[0]) for o in outs)


@pytest.mark.parametrize("argv, fragment", [
    (['{"A":[0,0],"A":[1,1]}'], "duplicate"),
    (['not json'], "invalid JSON"),
    (["--file", "does/not/exist.json"], "cannot read"),
    (['{"A":[0,0]}', "--range", "-5"], "--range"),
    (['{"A":[0,0]}', "--range", "nan"], "--range"),
    (['{"A":[0,0]}', "--simulate", "-1"], "--simulate"),
])
def test_invalid_input_exit_code_1(argv, fragment, capsys):
    code, out, err = run(argv, capsys)
    assert code == 1 and fragment in err and out == ""


def test_json_export_round_trip(capsys, tmp_path):
    o = tmp_path / "sched.json"
    code, _, _ = run([GRID_JSON, "--json-out", str(o)], capsys)
    assert code == 0
    d = json.loads(o.read_text())
    assert d["schema"] == "vmn-tdma-schedule/1" and d["num_slots"] == 9 and d["proven_optimal"]
    assert [n["nem_id"] for n in d["nodes"]] == list(range(1, 17))
    assert verify_matrix(GRID, 500.0, d["node_order"], d["matrix"], d["slot_of"]).ok
    assert len(d["links"]) == 42 and d["verification"]["ok"]


def test_max_reuse_and_simulation_sections(capsys):
    code, out, _ = run(["--file", str(ROOT / "inputs" / "random_16.json"), "--max-reuse",
                        "--simulate", "50", "--verbose"], capsys)
    assert code == 0
    assert "MAX-REUSE SCHEDULE MATRIX" in out and "Max-reuse verification" in out
    assert "HEURISTIC PORTFOLIO" in out and "SPATIAL REUSE" in out
    sim_lines = [l for l in out.splitlines() if l.startswith(" Optimized")]
    assert sim_lines and all(re.search(r"\s0\.0\s+100\.0%\s+100\.0%$", l) for l in sim_lines)


def test_range_option_changes_topology(capsys):
    _, out_big, _ = run([GRID_JSON, "--range", "5000"], capsys)
    assert "Optimized Frame Length : 16 unique timeslots" in out_big   # everyone hears everyone
    _, out_small, _ = run([GRID_JSON, "--range", "100"], capsys)
    assert "Optimized Frame Length : 1 unique timeslots" in out_small  # nobody hears anyone


def test_script_entry_point_runs_as_subprocess():
    r = subprocess.run([sys.executable, str(ROOT / "tdma_scheduler.py"), "--file",
                        str(ROOT / "inputs" / "grid_4x4.json")], capture_output=True, text=True)
    assert r.returncode == 0 and "9 unique timeslots" in r.stdout
    r = subprocess.run([sys.executable, "-m", "tdma_brain", "{bad"], capture_output=True,
                       text=True, cwd=ROOT)
    assert r.returncode == 1 and "error:" in r.stderr


# ------------------------------------------------------------- simulator
def random_coords(rng, n, side):
    return {f"Node_{i + 1:02d}": (rng.uniform(0, side), rng.uniform(0, side)) for i in range(n)}


def test_optimized_schedules_never_collide_and_serve_every_link():
    rng = random.Random(30)
    d1_collided = 0
    for _ in range(300):
        topo = Topology(random_coords(rng, 16, rng.choice([700, 1000, 1500, 2200])), 500.0)
        s = optimize(topo)
        r = simulate(topo.G, s.transmitters(), frames=5)
        assert r.collisions == 0 and r.delivery_ratio == 1.0 and r.link_coverage == 1.0
        r2 = simulate(topo.G, optimize(topo, max_reuse=True).transmitters(include_extra=True), frames=5)
        assert r2.collisions == 0 and r2.delivered >= r.delivered
        base = baseline_schedules(topo.G, topo.names)
        rr = simulate(topo.G, base["Round-robin TDMA (no reuse)"], frames=5)
        assert rr.collisions == 0 and rr.frame_slots == 16 >= s.num_slots
        d1 = simulate(topo.G, base["Distance-1 colouring (no hidden-terminal rule)"], frames=5)
        d1_collided += d1.lost_collision > 0
    assert d1_collided > 100   # hidden terminals are common: distance-1 colouring is not enough


def test_simulator_losses_iff_verifier_conflicts():
    rng = random.Random(31)
    for _ in range(1000):
        coords = random_coords(rng, rng.randint(2, 16), rng.choice([600, 1200, 2000]))
        topo = Topology(coords, 500.0)
        k = rng.randint(1, len(coords))
        slots_of = {n: {rng.randrange(k)} for n in topo.names}
        tx = [[n for n in topo.names if s in slots_of[n]] for s in range(k)]
        sim = simulate(topo.G, tx, frames=1)
        ok = verify_matrix(coords, 500.0, topo.names, matrix_from_slots(topo.names, slots_of, k)).conflict_free
        assert (sim.collisions == 0) == ok


def test_bernoulli_load_delay_reflects_frame_length():
    topo = Topology(GRID, 500.0)
    s = optimize(topo)
    opt = simulate(topo.G, s.transmitters(), frames=4000, load=0.3, seed=1)
    rr = simulate(topo.G, [[n] for n in topo.names], frames=4000, load=0.3, seed=1)
    assert opt.collisions == 0 and rr.collisions == 0
    assert opt.sent_packets > 0 and rr.sent_packets > 0
    assert opt.mean_delay_slots < rr.mean_delay_slots   # shorter frame -> lower access delay
