"""Stage 4: the Brain -> EMANE integration bridge (runs without EMANE installed)."""

import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "emane" / "bridge"))

import schedule_to_emane as B  # noqa: E402
from tdma_brain.optimizer import optimize  # noqa: E402
from tdma_brain.report import to_json  # noqa: E402
from tdma_brain.topology import Topology  # noqa: E402
from tdma_brain.verify import verify_matrix  # noqa: E402

GRID = {k: tuple(v) for k, v in json.loads((ROOT / "inputs" / "grid_4x4.json").read_text()).items()}


def schedule_json(tmp_path, coords, max_reuse=False):
    topo = Topology(coords, 500.0)
    s = optimize(topo, max_reuse=max_reuse)
    ver = verify_matrix(coords, 500.0, s.names, s.matrix(), s.slot_of)
    p = tmp_path / "sched.json"
    p.write_text(json.dumps(to_json(topo, s, ver)))
    return p, s, topo


def test_compress_expand_round_trip():
    rng = random.Random(1)
    for _ in range(500):
        ids = sorted(rng.sample(range(0, 60), rng.randint(1, 20)))
        text = B.compress(ids)
        assert B.expand(text) == set(ids)
    assert B.compress([0, 1, 2, 5, 7, 8]) == "0:2,5,7:8"
    assert B.si_to_int("2.4G") == 2_400_000_000 and B.si_to_int("12M") == 12_000_000


def test_grid_scenario_is_valid_and_faithful(tmp_path):
    src, s, topo = schedule_json(tmp_path, GRID)
    out = tmp_path / "scen"
    assert B.main([str(src), "-o", str(out)]) == 0
    meta = json.loads((out / "scenario.json").read_text())
    assert meta["xsd_validation"] == "valid"              # EMANE's own tdmaschedule.xsd
    assert meta["num_slots"] == 9 and meta["slot_duration_us"] == 1000
    assert meta["bytes_per_slot"] == 12_000_000 * 900 // 8_000_000 == 1350
    st, tx = B.parse_schedule_xml(out / "schedule.xml")
    assert st["slots"] == "9" and st["slotduration"] == "1000" and st["frames"] == "1"
    nodes = json.loads((out / "nodes.json").read_text())
    for n in nodes:                                       # XML == Brain's matrix
        assert tx[n["nem_id"]][0] == {s.slot_of[n["name"]]}
        assert sorted(n["neighbours"]) == sorted(int(m[-2:]) for m in topo.G[n["name"]])
    for i in range(1, 17):
        assert (out / f"platform-{i:02d}.xml").exists()


def test_pathloss_reproduces_unit_disk_graph(tmp_path):
    src, s, topo = schedule_json(tmp_path, GRID)
    out = tmp_path / "scen"
    B.main([str(src), "-o", str(out)])
    pl = json.loads((out / "pathloss.json").read_text())
    rx_dbm = lambda a, b: 30.0 - pl[str(a)][str(b)]
    noise = -100.0
    for u in range(1, 17):
        for v in range(1, 17):
            if u == v:
                continue
            assert pl[str(u)][str(v)] == pl[str(v)][str(u)]          # symmetric channel
            linked = topo.G.has_edge(f"Node_{u:02d}", f"Node_{v:02d}")
            snr = rx_dbm(u, v) - noise
            assert (snr > 20) if linked else (snr < -60)             # decodable vs invisible


def test_silence_and_max_reuse_variants(tmp_path):
    src, s, _ = schedule_json(tmp_path, GRID)
    out = tmp_path / "silenced"
    B.main([str(src), "-o", str(out), "--silence", "Node_06"])
    _, tx = B.parse_schedule_xml(out / "schedule.xml")
    assert tx[6][0] == set() and len(tx) == 16                    # still referenced, never TX
    assert json.loads((out / "scenario.json").read_text())["xsd_validation"] == "valid"

    coords = {k: tuple(v) for k, v in json.loads((ROOT / "inputs" / "random_16.json").read_text()).items()}
    src2, s2, _ = schedule_json(tmp_path, coords, max_reuse=True)
    out2 = tmp_path / "reuse"
    B.main([str(src2), "-o", str(out2), "--use-max-reuse", "--frames", "3"])
    _, tx2 = B.parse_schedule_xml(out2 / "schedule.xml")
    owned = s2.slots_of(include_extra=True)
    for i, name in enumerate(s2.names, start=1):
        for f in range(3):
            assert tx2[i][f] == owned[name]


def test_bridge_rejects_bad_input(tmp_path):
    src, _, _ = schedule_json(tmp_path, GRID)
    d = json.loads(src.read_text())
    d["links"] = d["links"][1:]                                   # tampered links
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(d))
    with pytest.raises(SystemExit, match="disagree"):
        B.main([str(bad), "-o", str(tmp_path / "x")])
    with pytest.raises(SystemExit, match="unknown nodes"):
        B.main([str(src), "-o", str(tmp_path / "y"), "--silence", "Nope"])
    with pytest.raises(SystemExit, match="slot duration"):
        B.main([str(src), "-o", str(tmp_path / "z"), "--slot-overhead-us", "1000"])
