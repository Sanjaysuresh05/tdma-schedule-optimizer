#!/usr/bin/env python3
"""Publish a scenario's events onto the EMANE event channel (runs on the EMANE host).

* Pathloss: one ``PathlossEvent`` per target NEM with an entry for every other
  NEM (same pattern as EMANE's ``emaneevent-pathloss``).
* TDMA schedule, two equivalent routes (R15: "XML or ProtoBuf"):
    --route xml       parse schedule.xml with EMANE's own ``TDMASchedule`` class
                      (exactly what ``emaneevent-tdmaschedule`` does), then publish;
    --route protobuf  build ``TDMAScheduleEvent`` ProtoBuf messages directly from
                      nodes.json (no XML involved) and publish them.
  Each NEM receives only its own schedule (one event per NEM), as EMANE requires.

Requires EMANE's Python package (python3-emane) on PYTHONPATH.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from emane.events import EventService, PathlossEvent, TDMAScheduleEvent, TDMASchedule


def publish_pathloss(service: EventService, scenario: Path) -> int:
    table = json.loads((scenario / "pathloss.json").read_text())
    for target, row in table.items():
        ev = PathlossEvent()
        for other, pl in row.items():
            ev.append(int(other), forward=float(pl))
        service.publish(int(target), ev)
    return len(table)


def schedule_events_from_xml(scenario: Path) -> dict[int, TDMAScheduleEvent]:
    """Mirror of emaneevent-tdmaschedule (EMANE 1.5.3) using EMANE's XML parser."""
    schedule = TDMASchedule(str(scenario / "schedule.xml"))
    info, structure, frame_defaults = schedule.info(), schedule.structure(), schedule.defaultsFrame()
    events = {}
    for nem in info:
        ev = TDMAScheduleEvent(**schedule.defaults())
        for frame_index in info[nem]:
            for slot_index, args in info[nem][frame_index].items():
                kwargs = dict(args)
                for key, value in frame_defaults[frame_index].items():
                    kwargs["frame." + key] = value
                ev.append(frame_index, slot_index, **kwargs)
        if structure is not None:
            ev.structure(**structure)
        events[nem] = ev
    return events


def schedule_events_from_json(scenario: Path) -> dict[int, TDMAScheduleEvent]:
    """Build the ProtoBuf events directly from the Brain's per-node TX slots."""
    meta = json.loads((scenario / "scenario.json").read_text())
    nodes = json.loads((scenario / "nodes.json").read_text())
    k, frames = meta["num_slots"], meta["frames_per_multiframe"]
    events = {}
    for n in nodes:
        ev = TDMAScheduleEvent(frequency=meta["frequency_hz"], datarate=meta["datarate_bps"],
                               service=0, power=float(meta["tx_power_dbm"]))
        for f in range(frames):
            for s in range(k):
                if s in n["tx_slots"]:
                    ev.append(f, s, type="tx")
                else:
                    ev.append(f, s, type="rx", frequency=meta["frequency_hz"])
        ev.structure(slots=k, frames=frames, slotduration=meta["slot_duration_us"],
                     slotoverhead=meta["slot_overhead_us"], bandwidth=meta["bandwidth_hz"])
        events[n["nem_id"]] = ev
    return events


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("scenario", type=Path)
    p.add_argument("-i", "--device", default="br0", help="event channel multicast device")
    p.add_argument("-g", "--group", default="224.1.2.8")
    p.add_argument("-p", "--port", type=int, default=45703)
    p.add_argument("--route", choices=["xml", "protobuf"], default="xml")
    p.add_argument("--what", choices=["all", "pathloss", "schedule"], default="all")
    p.add_argument("--dump", type=Path, help="also write the serialized events (hex) to this JSON file")
    a = p.parse_args()

    service = EventService((a.group, a.port, a.device))
    if a.what in ("all", "pathloss"):
        n = publish_pathloss(service, a.scenario)
        print(f"published {n} pathloss events")
    if a.what in ("all", "schedule"):
        events = (schedule_events_from_xml if a.route == "xml" else schedule_events_from_json)(a.scenario)
        for nem, ev in sorted(events.items()):
            service.publish(nem, ev)
        print(f"published {len(events)} TDMAScheduleEvent(s) via the {a.route} route")
        if a.dump:
            a.dump.write_text(json.dumps({str(k): v.serialize().hex() for k, v in events.items()},
                                         indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
