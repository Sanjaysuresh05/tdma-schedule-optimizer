#!/usr/bin/env python3
"""Integration bridge (Part 2): Brain schedule JSON -> EMANE TDMA scenario.

Input  : the JSON written by ``tdma_scheduler.py --json-out`` (schema
         ``vmn-tdma-schedule/1``): nodes (name, nem_id, x, y), the Slot x Node
         matrix and the 500 m links.
Output : a self-contained scenario directory

    schedule.xml          EMANE TDMA *full* schedule (structure + multiframe),
                          validated against EMANE's own tdmaschedule.xsd
    schedule_matrix.txt   the same schedule as a readable Slot x NEM table
    pathloss.json         NEM x NEM pathloss (dB) reproducing the 500 m unit-disk graph
    nodes.json            node name <-> NEM id <-> IP addresses <-> slots
    platform-NN.xml       one EMANE platform file per node
    tdma-nem.xml          NEM definition (virtual transport + TDMA MAC + emulator PHY)
    tdma-radiomodel.xml   TDMA radio model configuration
    transvirtual.xml      virtual transport configuration
    scenario.json         every parameter used, plus derived values (bytes/slot, frame time)

Pure standard library (lxml optional, used for XSD validation when present),
so it runs both on the Windows planning host and inside the Linux EMANE host.

Schedule mapping (EMANE semantics, see emane.io/tdma-radio-model):
* <structure frames=F slots=K slotduration=1000 slotoverhead=... bandwidth=...>
* one <slot index="s" nodes="..."/> per matrix row s (a defined slot defaults to
  TX for the listed NEMs); every slot a NEM does not transmit in defaults to RX
  on the multiframe frequency, exactly the half-duplex TDMA behaviour wanted;
* ``--silence NODE`` removes all TX slots of NODE and lists it with explicit
  <rx/> slots instead (experiment E2: EMANE must then drop that node's traffic).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCHEMA_ID = "vmn-tdma-schedule/1"
HERE = Path(__file__).resolve().parent
DEFAULT_XSD = HERE.parent / "schema" / "tdmaschedule.xsd"
RANGE_REL_TOL = 1e-12         # identical to the Brain's inclusive 500 m rule (rounding only)


# ----------------------------------------------------------------- helpers
def si_to_int(value: str) -> int:
    """'2.4G' -> 2400000000, '12M' -> 12000000, '1000' -> 1000 (EMANE SI notation)."""
    mult = {"G": 10 ** 9, "M": 10 ** 6, "K": 10 ** 3}.get(value[-1:].upper(), 1)
    number = value[:-1] if mult != 1 else value
    return int(round(float(number) * mult))


def compress(ids: list[int]) -> str:
    """[0,1,2,5,7,8] -> '0:2,5,7:8' (EMANE index/node list syntax, inclusive ranges)."""
    ids = sorted(set(ids))
    out, i = [], 0
    while i < len(ids):
        j = i
        while j + 1 < len(ids) and ids[j + 1] == ids[j] + 1:
            j += 1
        out.append(str(ids[i]) if i == j else f"{ids[i]}:{ids[j]}")
        i = j + 1
    return ",".join(out)


def expand(text: str) -> set[int]:
    """Inverse of compress (same semantics as emane.events.tdmaschedule.expandIndex)."""
    out: set[int] = set()
    for item in text.split(","):
        if ":" in item:
            a, b = item.split(":")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(item))
    return out


def fspl_db(distance_m: float, frequency_hz: float) -> float:
    """Free-space pathloss (Friis), distance floored at 1 m."""
    d = max(distance_m, 1.0)
    return 20 * math.log10(d) + 20 * math.log10(frequency_hz) - 147.55


def write_xml(path: Path, root: ET.Element, doctype: str | None = None) -> None:
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    head = '<?xml version="1.0" encoding="UTF-8"?>\n' + (doctype + "\n" if doctype else "")
    path.write_text(head + body + "\n", encoding="utf-8")


def param(parent: ET.Element, name: str, value: str) -> None:
    ET.SubElement(parent, "param", name=name, value=value)


# ----------------------------------------------------------------- core
def load_schedule(path: Path, use_max_reuse: bool) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA_ID:
        raise SystemExit(f"error: {path} is not a {SCHEMA_ID} file (run tdma_scheduler.py --json-out)")
    matrix = data["matrix_max_reuse"] if use_max_reuse and data.get("matrix_max_reuse") else data["matrix"]
    order = data["node_order"]
    nodes = {n["name"]: n for n in data["nodes"]}
    if len(matrix) != data["num_slots"] or any(len(r) != len(order) for r in matrix):
        raise SystemExit("error: matrix shape does not match num_slots x num_nodes")
    if len(order) > 250:
        raise SystemExit("error: the runner's 10.100.0.N/24 addressing supports at most 250 nodes")
    return {"data": data, "matrix": matrix, "order": order, "nodes": nodes}


def check_links(sched: dict) -> set[frozenset]:
    """Links from the Brain, cross-checked against the coordinates (fail loudly on mismatch)."""
    data, nodes = sched["data"], sched["nodes"]
    r = float(data["radio_range_m"])
    given = {frozenset((u, v)) for u, v, _ in data["links"]}
    names = sched["order"]
    recomputed = set()
    for i, u in enumerate(names):
        for v in names[i + 1:]:
            dx, dy = nodes[u]["x"] - nodes[v]["x"], nodes[u]["y"] - nodes[v]["y"]
            if dx * dx + dy * dy <= r * r * (1 + RANGE_REL_TOL):
                recomputed.add(frozenset((u, v)))
    if given != recomputed:
        raise SystemExit("error: links in the schedule JSON disagree with the coordinates")
    return given


def tx_slots_per_nem(sched: dict, silence: set[str]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for j, name in enumerate(sched["order"]):
        nem = sched["nodes"][name]["nem_id"]
        out[nem] = [] if name in silence else [s for s, row in enumerate(sched["matrix"]) if row[j]]
    return out


def build_schedule_xml(tx: dict[int, list[int]], k: int, a: argparse.Namespace) -> ET.Element:
    root = ET.Element("emane-tdma-schedule")
    ET.SubElement(root, "structure", frames=str(a.frames), slots=str(k),
                  slotoverhead=str(a.slot_overhead_us), slotduration=str(a.slot_duration_us),
                  bandwidth=a.bandwidth)
    mf = ET.SubElement(root, "multiframe", frequency=a.frequency, power=f"{a.power:g}",
                       **{"class": "0"}, datarate=a.datarate)
    frame = ET.SubElement(mf, "frame", index=compress(list(range(a.frames))))
    for s in range(k):
        nems = [nem for nem, slots in tx.items() if s in slots]
        if nems:
            ET.SubElement(frame, "slot", index=str(s), nodes=compress(nems))  # default type: tx
    silent = [nem for nem, slots in tx.items() if not slots]
    if silent:  # reference silenced NEMs explicitly as receive-only in every slot
        slot = ET.SubElement(frame, "slot", index=compress(list(range(k))), nodes=compress(silent))
        ET.SubElement(slot, "rx")
    return root


def parse_schedule_xml(path: Path) -> tuple[dict, dict[int, dict[int, set[int]]]]:
    """Independent re-reader: returns (structure, {nem: {frame: tx_slots}})."""
    root = ET.parse(path).getroot()
    st = root.find("structure").attrib
    tx: dict[int, dict[int, set[int]]] = {}
    for frame in root.find("multiframe").findall("frame"):
        for f in expand(frame.get("index")):
            for slot in frame.findall("slot"):
                kind = slot[0].tag if len(slot) else "tx"
                for nem in expand(slot.get("nodes")):
                    tx.setdefault(nem, {}).setdefault(f, set())
                    if kind == "tx":
                        tx[nem][f] |= expand(slot.get("index"))
    return st, tx


def validate_xsd(xml_path: Path, xsd_path: Path) -> str:
    try:
        from lxml import etree
    except ImportError:
        return "skipped (lxml not installed)"
    schema = etree.XMLSchema(etree.parse(str(xsd_path)))
    doc = etree.parse(str(xml_path))
    if not schema.validate(doc):
        raise SystemExit("error: schedule.xml fails tdmaschedule.xsd:\n" +
                         "\n".join(str(e) for e in schema.error_log))
    return "valid"


def build_configs(out: Path, sched: dict, a: argparse.Namespace) -> None:
    dtd = a.dtd_dir.rstrip("/")
    # NEM definition (official EMANE TDMA template, with the PHY tied to our parameters)
    nem = ET.Element("nem")
    ET.SubElement(nem, "transport", definition="transvirtual.xml")
    ET.SubElement(nem, "mac", definition="tdma-radiomodel.xml")
    phy = ET.SubElement(nem, "phy")
    for k, v in [("fixedantennagain", "0.0"), ("fixedantennagainenable", "on"),
                 ("bandwidth", a.bandwidth), ("noisemode", "all"),
                 ("propagationmodel", "precomputed"), ("systemnoisefigure", "4.0"),
                 ("subid", "7"), ("fading.model", "none")]:
        param(phy, k, v)
    write_xml(out / "tdma-nem.xml", nem, f'<!DOCTYPE nem SYSTEM "file://{dtd}/nem.dtd">')

    mac = ET.Element("mac", library="tdmaeventschedulerradiomodel")
    for k, v in [("enablepromiscuousmode", "off"), ("fragmentcheckthreshold", "2"),
                 ("fragmenttimeoutthreshold", "5"), ("neighbormetricdeletetime", "60.0"),
                 ("neighbormetricupdateinterval", "1.0"), ("queue.aggregationenable", "on"),
                 ("queue.aggregationslotthreshold", "90.0"), ("queue.depth", "255"),
                 ("queue.fragmentationenable", "on"), ("queue.strictdequeueenable", "off"),
                 ("pcrcurveuri", a.pcr_uri)]:
        param(mac, k, v)
    write_xml(out / "tdma-radiomodel.xml", mac, f'<!DOCTYPE mac SYSTEM "file://{dtd}/mac.dtd">')

    tv = ET.Element("transport", library="transvirtual")
    param(tv, "bitrate", "0")
    param(tv, "devicepath", "/dev/net/tun")
    write_xml(out / "transvirtual.xml", tv, f'<!DOCTYPE transport SYSTEM "file://{dtd}/transport.dtd">')

    for name in sched["order"]:
        n = sched["nodes"][name]["nem_id"]
        plat = ET.Element("platform")
        for k, v in [("otamanagerchannelenable", "on"), ("otamanagerdevice", "backchan0"),
                     ("otamanagergroup", "224.1.2.8:45702"), ("eventservicegroup", "224.1.2.8:45703"),
                     ("eventservicedevice", "backchan0"), ("controlportendpoint", "0.0.0.0:47000")]:
            param(plat, k, v)
        nem_el = ET.SubElement(plat, "nem", id=str(n), definition="tdma-nem.xml")
        tr = ET.SubElement(nem_el, "transport", definition="transvirtual.xml")
        param(tr, "device", "emane0")
        param(tr, "address", f"10.100.0.{n}")
        param(tr, "mask", "255.255.255.0")
        write_xml(out / f"platform-{n:02d}.xml", plat, f'<!DOCTYPE platform SYSTEM "file://{dtd}/platform.dtd">')


def build_pathloss(sched: dict, links: set[frozenset], a: argparse.Namespace) -> dict:
    nodes, order = sched["nodes"], sched["order"]
    f_hz = si_to_int(a.frequency)
    table = {}
    for u in order:
        row = {}
        for v in order:
            if u == v:
                continue
            d = math.dist((nodes[u]["x"], nodes[u]["y"]), (nodes[v]["x"], nodes[v]["y"]))
            if a.pathloss_model == "fspl-all":      # physical channel, no 500 m cut-off
                pl = fspl_db(d, f_hz)
            elif frozenset((u, v)) in links:
                pl = fspl_db(d, f_hz) if a.pathloss_model == "fspl" else a.link_pathloss
            else:
                pl = a.no_link_pathloss
            row[str(nodes[v]["nem_id"])] = round(pl, 2)
        table[str(nodes[u]["nem_id"])] = row
    return table


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("schedule_json", type=Path)
    p.add_argument("-o", "--out", type=Path, required=True, help="scenario output directory")
    p.add_argument("--slot-duration-us", type=int, default=1000, help="slot length (default 1000 us = 1 ms)")
    p.add_argument("--slot-overhead-us", type=int, default=100,
                   help="guard time per slot (default 100 us >> 1.7 us propagation over 500 m)")
    p.add_argument("--frames", type=int, default=1, help="frames per multiframe (default 1)")
    p.add_argument("--frequency", default="2.4G", help="carrier frequency (default 2.4G)")
    p.add_argument("--datarate", default="12M", help="slot data rate; must exist in the PCR curve (default 12M)")
    p.add_argument("--bandwidth", default="10M", help="transceiver bandwidth (default 10M)")
    p.add_argument("--power", type=float, default=30.0, help="transmit power dBm (default 30)")
    p.add_argument("--pathloss-model", choices=["constant", "fspl", "fspl-all"], default="constant",
                   help="constant: --link-pathloss on 500 m links, --no-link-pathloss otherwise (unit-disk "
                        "channel, default); fspl: free space on links only; fspl-all: free space for every "
                        "pair (physical channel without a 500 m cut-off)")
    p.add_argument("--link-pathloss", type=float, default=90.0, help="dB on linked pairs (default 90)")
    p.add_argument("--no-link-pathloss", type=float, default=200.0, help="dB on unlinked pairs (default 200)")
    p.add_argument("--dtd-dir", default="/usr/share/emane/dtd", help="where EMANE's DTDs live")
    p.add_argument("--pcr-uri", default="/usr/share/emane/xml/models/mac/tdmaeventscheduler/tdmabasemodelpcr.xml")
    p.add_argument("--silence", nargs="*", default=[], metavar="NODE",
                   help="remove every TX slot of these nodes (experiment E2)")
    p.add_argument("--use-max-reuse", action="store_true", help="use matrix_max_reuse if present")
    p.add_argument("--xsd", type=Path, default=DEFAULT_XSD)
    a = p.parse_args(argv)

    if a.slot_duration_us <= a.slot_overhead_us or a.frames < 1:
        raise SystemExit("error: need slot duration > overhead and frames >= 1")
    sched = load_schedule(a.schedule_json, a.use_max_reuse)
    unknown = set(a.silence) - set(sched["order"])
    if unknown:
        raise SystemExit(f"error: --silence names unknown nodes: {sorted(unknown)}")
    links = check_links(sched)
    k = len(sched["matrix"])
    tx = tx_slots_per_nem(sched, set(a.silence))

    out = a.out
    out.mkdir(parents=True, exist_ok=True)
    xml_root = build_schedule_xml(tx, k, a)
    write_xml(out / "schedule.xml", xml_root)
    xsd_status = validate_xsd(out / "schedule.xml", a.xsd)

    # round-trip check: re-read the XML and compare with the intended TX slots
    st, parsed = parse_schedule_xml(out / "schedule.xml")
    for nem, slots in tx.items():
        for f in range(a.frames):
            got = parsed.get(nem, {}).get(f)
            if got is None or got != set(slots):
                raise SystemExit(f"error: round-trip mismatch for NEM {nem} frame {f}")
    assert int(st["slots"]) == k

    build_configs(out, sched, a)
    pathloss = build_pathloss(sched, links, a)
    (out / "pathloss.json").write_text(json.dumps(pathloss, indent=1) + "\n", encoding="utf-8")

    nodes_info = [{"name": n, "nem_id": sched["nodes"][n]["nem_id"],
                   "radio_ip": f"10.100.0.{sched['nodes'][n]['nem_id']}",
                   "backchannel_ip": f"10.99.0.{sched['nodes'][n]['nem_id']}",
                   "x": sched["nodes"][n]["x"], "y": sched["nodes"][n]["y"],
                   "tx_slots": tx[sched["nodes"][n]["nem_id"]],
                   "neighbours": sorted(sched["nodes"][m]["nem_id"] for m in sched["order"]
                                        if frozenset((n, m)) in links)}
                  for n in sched["order"]]
    (out / "nodes.json").write_text(json.dumps(nodes_info, indent=1) + "\n", encoding="utf-8")

    lines = ["Slot \\ NEM | " + " | ".join(f"{i['nem_id']:02d}" for i in nodes_info)]
    for s in range(k):
        lines.append(f"Slot {s:02d}    | " + " | ".join(" 1" if s in i["tx_slots"] else " 0" for i in nodes_info))
    (out / "schedule_matrix.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    usable_us = a.slot_duration_us - a.slot_overhead_us
    meta = {
        "source": str(a.schedule_json), "num_nodes": len(sched["order"]), "num_slots": k,
        "frames_per_multiframe": a.frames, "slot_duration_us": a.slot_duration_us,
        "slot_overhead_us": a.slot_overhead_us, "frame_duration_ms": k * a.slot_duration_us / 1000,
        "multiframe_duration_ms": a.frames * k * a.slot_duration_us / 1000,
        "frequency_hz": si_to_int(a.frequency), "datarate_bps": si_to_int(a.datarate),
        "bandwidth_hz": si_to_int(a.bandwidth), "tx_power_dbm": a.power,
        "bytes_per_slot": si_to_int(a.datarate) * usable_us // 8_000_000,
        "pathloss_model": a.pathloss_model, "link_pathloss_db": a.link_pathloss,
        "no_link_pathloss_db": a.no_link_pathloss, "silenced": sorted(a.silence),
        "matrix": "max_reuse" if a.use_max_reuse and sched["data"].get("matrix_max_reuse") else "base",
        "links": len(links), "xsd_validation": xsd_status,
        "noise_floor_dbm": round(-174 + 10 * math.log10(si_to_int(a.bandwidth)) + 4.0, 1),
    }
    (out / "scenario.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(f"scenario written to {out}: {k} slots x {a.slot_duration_us} us, "
          f"{meta['bytes_per_slot']} B/slot, schedule.xml XSD {xsd_status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
