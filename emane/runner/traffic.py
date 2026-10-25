#!/usr/bin/env python3
"""UDP broadcast probe for one emulated node (run inside the node's network namespace).

Sends Poisson-timed broadcast packets (src NEM, sequence number, send time) to
the radio subnet and counts every packet received from each other NEM.  All
namespaces share one kernel clock, so one-way latency is measured exactly.

Writes a JSON summary: packets sent, and per source: packets received, unique
sequence numbers, latency statistics (ms).
"""

from __future__ import annotations

import argparse
import json
import random
import select
import socket
import struct
import time

HDR = struct.Struct("!HIQ")  # src nem id, sequence, send time (ns, CLOCK_REALTIME)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--nem", type=int, required=True)
    p.add_argument("--rate", type=float, default=40.0, help="mean packets per second (Poisson)")
    p.add_argument("--duration", type=float, default=20.0, help="seconds of sending")
    p.add_argument("--start-at", type=float, default=0.0, help="epoch time to start sending")
    p.add_argument("--linger", type=float, default=2.0, help="seconds to keep receiving after sending")
    p.add_argument("--size", type=int, default=64, help="UDP payload bytes")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--bcast", default="10.100.0.255")
    p.add_argument("--seed", type=int, default=0, help="traffic seed (replications use different seeds)")
    p.add_argument("--out", required=True)
    a = p.parse_args()

    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind(("", a.port))
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    tx.bind((f"10.100.0.{a.nem}", 0))

    rng = random.Random(a.nem * 7919 + a.seed * 1_000_003)
    pad = b"\0" * max(0, a.size - HDR.size)
    while time.time() < a.start_at:
        time.sleep(0.001)
    t0 = time.time()
    t_end = t0 + a.duration
    next_tx = t0 + rng.expovariate(a.rate)
    seq = 0
    stats: dict[int, dict] = {}
    send_errors = 0

    while True:
        now = time.time()
        if now >= t_end + a.linger:
            break
        if now >= next_tx and now < t_end:
            try:
                tx.sendto(HDR.pack(a.nem, seq, time.time_ns()) + pad, (a.bcast, a.port))
                seq += 1
            except OSError:
                send_errors += 1
            next_tx += rng.expovariate(a.rate)
            continue
        timeout = max(0.0, min(next_tx if now < t_end else t_end + a.linger, t_end + a.linger) - now)
        r, _, _ = select.select([rx], [], [], timeout)
        if r:
            data, _ = rx.recvfrom(65535)
            t_rx = time.time_ns()
            if len(data) < HDR.size:
                continue
            src, s, t_tx = HDR.unpack_from(data)
            if src == a.nem:
                continue  # own broadcast looped back by the kernel
            st = stats.setdefault(src, {"received": 0, "seqs": set(), "lat": []})
            st["received"] += 1
            st["seqs"].add(s)
            st["lat"].append((t_rx - t_tx) / 1e6)

    out = {"nem": a.nem, "sent": seq, "send_errors": send_errors, "rate": a.rate, "seed": a.seed,
           "duration": a.duration, "size": a.size, "start_at": a.start_at, "started": t0,
           "start_skew_ms": (t0 - a.start_at) * 1000 if a.start_at else None, "from": {}}
    for src, st in sorted(stats.items()):
        lat = sorted(st["lat"])
        out["from"][str(src)] = {
            "received": st["received"], "unique": len(st["seqs"]),
            "lat_ms_mean": sum(lat) / len(lat), "lat_ms_p50": lat[len(lat) // 2],
            "lat_ms_p99": lat[min(len(lat) - 1, int(0.99 * len(lat)))], "lat_ms_max": lat[-1],
        }
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
