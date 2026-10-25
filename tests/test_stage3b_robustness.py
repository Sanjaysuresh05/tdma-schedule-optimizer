"""Regression tests for the defects found by the independent review of Part 1.

Each test names the defect it guards (review report, items 1-8 + observations).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tdma_brain.cli import main
from tdma_brain.optimizer import optimize
from tdma_brain.topology import Topology, natural_key
from tdma_brain.verify import verify_matrix

ROOT = Path(__file__).resolve().parents[1]
GRID_JSON = (ROOT / "inputs" / "grid_4x4.json").read_text().strip()


def cli(*args, **kw):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    return subprocess.run([sys.executable, str(ROOT / "tdma_scheduler.py"), *args],
                          capture_output=True, env=env, **kw)


def run(argv, capsys):
    code = main(argv)
    out, err = capsys.readouterr()
    return code, out, err


# 1. non-ASCII names with redirected stdout must not crash (Windows cp1252 pipes)
def test_non_ascii_names_with_redirected_output():
    r = cli('{"节点_01":[0,0],"节点_02":[300,0]}')
    assert r.returncode == 0, r.stderr
    assert b"Schedule verified conflict-free" in r.stdout


# 2. verifier must not overflow; absurd coordinates are rejected cleanly
def test_huge_coordinates(capsys):
    code, out, err = run(['{"A":[0,0],"B":[1e155,0]}'], capsys)
    assert code == 1 and "exceeds" in err and out == ""
    res = verify_matrix({"A": (0.0, 0.0), "B": (1e200, 0.0)}, 500.0, ["A", "B"], [[1, 1]])
    assert res.conflict_free  # no OverflowError, and not linked


# 3. numbers that cannot become floats -> clean error, never a traceback
@pytest.mark.parametrize("text", [
    '{"A":[1' + "0" * 400 + ',0]}',          # int too large for float
    '{"A":[' + "9" * 5000 + ',0]}',          # > 4300 digits
    '{"A":' + "[" * 100000 + "]" * 100000 + '}',  # nesting too deep
], ids=["int-too-large-for-float", "int-over-4300-digits", "nesting-too-deep"])
def test_unconvertible_numbers_are_input_errors(text, capsys):
    code, out, err = run([text], capsys)
    assert code == 1 and err.startswith("error:") and out == ""


# 4. node-name sort key must accept any Unicode digits / very long digit runs
@pytest.mark.parametrize("names", [["Node_1²", "Node_2"], ["²", "٣"],
                                   ["N" + "7" * 5000, "N8"]],
                         ids=["superscript-digit", "unicode-digits-only", "5000-digit-run"])
def test_exotic_names_sort_and_schedule(names):
    sorted(names, key=natural_key)
    coords = {n: (300.0 * i, 0.0) for i, n in enumerate(names)}
    s = optimize(Topology(coords, 500.0))
    assert verify_matrix(coords, 500.0, s.names, s.matrix(), s.slot_of).ok


# 5. non-UTF-8 input file -> clean error
def test_non_utf8_file(tmp_path, capsys):
    p = tmp_path / "latin1.json"
    p.write_bytes('{"N\xe9_01":[0,0]}'.encode("latin-1"))
    code, out, err = run(["--file", str(p)], capsys)
    assert code == 1 and "not UTF-8" in err


# 6. exit codes match the documentation
def test_exit_codes(tmp_path, capsys):
    assert cli("-r", "abc", GRID_JSON).returncode == 1          # usage error -> 1, not 2
    blocker = tmp_path / "file.txt"
    blocker.write_text("x")
    code, out, err = run([GRID_JSON, "-o", str(blocker / "sched.json")], capsys)
    assert code == 3 and "cannot write" in err                   # output not written -> 3
    code, _, err = run([GRID_JSON, "--time-limit", "nan"], capsys)
    assert code == 1 and "--time-limit" in err


# 7. range tolerance only absorbs float rounding (sub-nanometre), not micrometres
def test_range_tolerance_is_rounding_only():
    coords = {"A": (0.0, 0.0), "B": (500.0000001, 0.0), "C": (1000.0000002, 0.0)}
    t = Topology(coords, 500.0)
    assert t.G.number_of_edges() == 0 and optimize(t).num_slots == 1
    diag = 500.0 / 2 ** 0.5
    assert Topology({"A": (0.0, 0.0), "B": (diag, diag)}, 500.0).G.number_of_edges() == 1


# 8. names that could forge report lines or look identical are rejected
@pytest.mark.parametrize("text, fragment", [
    ('{"A\\nNode_99: Slot 7":[0,0]}', "control"),
    ('{"Node_01 ":[0,0]}', "whitespace"),
    ('{"\\u200bNode":[0,0]}', "control"),
])
def test_name_sanitising(text, fragment, capsys):
    code, out, err = run([text], capsys)
    assert code == 1 and fragment in err


def test_singular_note(capsys):
    _, _, err = run(['{"Solo":[0,0]}'], capsys)
    assert "1 node given" in err


# sample-format option reproduces the PDF layout exactly
def test_sample_format_matches_pdf_layout(capsys):
    code, out, _ = run([GRID_JSON, "--sample-format"], capsys)
    lines = out.splitlines()
    assert code == 0
    assert lines[:6] == ["=" * 64, " TDMA TOPOLOGY OPTIMIZATION REPORT ", "=" * 64,
                         "Total Nodes Processed : 16", "Configured Radio Range : 500.0 meters",
                         "Optimized Frame Length : 9 unique timeslots (Lower is better)"]
    assert lines[6] == "-" * 65 and lines[7] == "NODE -> SLOT ASSIGNMENTS:"
    i = lines.index("STRUCTURAL TDMA SCHEDULE MATRIX (Slot x Node Boolean Matrix):")
    assert lines[i + 1] == "Slot \\ Node | " + " | ".join(f"{k:02d}" for k in range(1, 17))
    assert lines[i + 2] == "-" * 89                                  # as in the sample
    assert lines[i + 3].startswith("Slot 00 | 1 | 0 | ")
    assert lines[-2:] == ["Execution finalized cleanly. Schedule verified conflict-free.", "=" * 63]
    assert not any(l.startswith(("Theoretical", "Independent")) for l in lines)


def test_tabucol_respects_deadline():
    import random
    import time
    from tdma_brain import coloring as C
    rng = random.Random(0)
    coords = {f"N{i}": (rng.uniform(0, 4000), rng.uniform(0, 4000)) for i in range(300)}
    topo = Topology(coords, 500.0)
    idx = {v: i for i, v in enumerate(topo.names)}
    adj = [{idx[u] for u in topo.H[v]} for v in topo.names]
    t0 = time.perf_counter()
    out = C.tabucol(adj, 1, [0] * len(adj), rng, max_iters=10 ** 9, deadline=t0 + 0.3)
    assert out is None and time.perf_counter() - t0 < 2.0


# observation: results must not depend on Python's per-process string hash seed
@pytest.mark.parametrize("name", ["ring_16", "random_16", "clustered_16"])
def test_output_identical_across_hash_seeds(name):
    import re
    outs = []
    for seed in ("1", "2", "3"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run([sys.executable, str(ROOT / "tdma_scheduler.py"), "--file",
                            str(ROOT / "inputs" / f"{name}.json"), "--verbose", "--max-reuse",
                            "--simulate", "5"], capture_output=True, text=True, env=env)
        assert r.returncode == 0
        outs.append(re.sub(r"\d+\.\d+ ms", "", r.stdout))
    assert outs[0] == outs[1] == outs[2]
