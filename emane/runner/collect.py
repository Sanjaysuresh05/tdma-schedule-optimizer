#!/usr/bin/env python3
"""Collect EMANE statistics from every node's control port into one JSON file.

Per NEM: TDMA MAC scheduler counters, slot counters, Tx/Rx slot status tables,
schedule/structure tables, queue tables, broadcast accept/drop tables, PHY
counters.  Uses EMANE's own ControlPortClient (same API as emanesh).
"""

from __future__ import annotations

import argparse
import json
import sys

from emane.shell import ControlPortClient

MAC_TABLES = ["TxSlotStatusTable", "RxSlotStatusTable", "scheduler.ScheduleInfoTable",
              "scheduler.StructureInfoTable", "QueueStatusTable",
              "BroadcastByteAcceptTable0", "BroadcastByteDropTable0",
              "EventReceptionTable", "NeighborStatusTable"]
PHY_TABLES = ["BroadcastPacketDropTable0", "BroadcastPacketAcceptTable0"]


def value(v):
    """ControlPortClient returns (value, type) pairs; keep the plain value."""
    v = v[0] if isinstance(v, tuple) and len(v) == 2 and isinstance(v[1], int) else v
    return v.decode(errors="replace") if isinstance(v, bytes) else v


def rows(table_rows):
    return [[value(cell) for cell in row] for row in table_rows]


def collect(host: str, port: int) -> dict:
    client = ControlPortClient(host, port)
    try:
        out = {}
        for nem, layers in client.getManifest().items():
            entry = {}
            for build_id, layer, plugin in layers:
                if layer not in ("MAC", "PHY"):
                    continue
                stats = client.getStatistic(build_id)
                tables = client.getStatisticTable(build_id)
                # key tables first, then every other table the layer exposes
                wanted = (MAC_TABLES if layer == "MAC" else PHY_TABLES)
                wanted = wanted + sorted(set(tables) - set(wanted))
                entry[layer] = {
                    "plugin": plugin,
                    "stats": {k: value(v) for k, v in stats.items()},
                    "tables": {name: {"labels": list(tables[name][0]),
                                      "rows": rows(tables[name][1])}
                               for name in wanted if name in tables},
                }
            out[str(nem)] = entry
        return out
    finally:
        client.stop()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--hosts", nargs="+", required=True, help="control port host per node")
    p.add_argument("--port", type=int, default=47000)
    p.add_argument("--out", required=True)
    p.add_argument("--require-schedule", action="store_true",
                   help="exit 2 unless every NEM reports scheduler.scheduleAcceptFull >= 1 and no rejects")
    a = p.parse_args()
    result, errors = {}, {}
    for h in a.hosts:
        try:
            result.update(collect(h, a.port))
        except Exception as e:  # report but keep collecting the other nodes
            errors[h] = repr(e)
    with open(a.out, "w") as f:
        json.dump({"nems": result, "errors": errors}, f, indent=1)
    print(f"collected statistics from {len(result)} NEM(s); {len(errors)} error(s)")
    if errors:
        return 1
    if a.require_schedule:
        bad = [n for n, e in result.items()
               if e.get("MAC", {}).get("stats", {}).get("scheduler.scheduleAcceptFull", 0) < 1
               or any(v for k, v in e.get("MAC", {}).get("stats", {}).items() if k.startswith("scheduler.scheduleReject"))]
        if bad or len(result) != len(a.hosts):
            print(f"schedule not (yet) accepted by NEM(s): {sorted(bad, key=int)}")
            return 2
        print("schedule accepted by all NEMs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
