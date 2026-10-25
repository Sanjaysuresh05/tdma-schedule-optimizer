"""Slot-level TDMA simulator (unit-disk / protocol interference model).

Every transmission is a broadcast heard by all 1-hop neighbours.  In a slot
with transmitter set T, receiver r gets the packet of neighbour t in T iff

* r itself is not transmitting in that slot (half-duplex radio), and
* t is the *only* member of T within range of r (otherwise collision).

Traffic: each node has a FIFO queue.  ``load`` is the probability that a new
packet arrives at a node at the start of each frame (``load=None`` means
saturated: a node always has a packet for each of its slots).  A packet is
sent once in the node's next owned slot (no retransmission); per receiver it
is either delivered, lost to a collision or lost to half-duplex.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import networkx as nx


@dataclass
class SimResult:
    label: str
    frame_slots: int
    frames: int
    transmissions: int = 0
    attempts: int = 0          # (transmission, neighbour) pairs
    delivered: int = 0
    lost_collision: int = 0    # >= 2 transmitting neighbours at the receiver (incl. hidden terminals)
    lost_half_duplex: int = 0  # receiver was transmitting itself
    links_total: int = 0       # directed links t->r in G
    links_served: int = 0      # directed links with >= 1 delivery during the run
    delay_slots_sum: int = 0   # queueing delay of sent packets (slots from arrival to tx)
    sent_packets: int = 0
    per_link_delivered: dict = field(default_factory=dict)
    per_node_tx: dict = field(default_factory=dict)

    @property
    def delivery_ratio(self) -> float:
        return self.delivered / self.attempts if self.attempts else 1.0

    @property
    def collisions(self) -> int:
        return self.lost_collision + self.lost_half_duplex

    @property
    def deliveries_per_slot(self) -> float:
        slots = self.frames * self.frame_slots
        return self.delivered / slots if slots else 0.0

    @property
    def mean_delay_slots(self) -> float:
        return self.delay_slots_sum / self.sent_packets if self.sent_packets else 0.0

    @property
    def link_coverage(self) -> float:
        return self.links_served / self.links_total if self.links_total else 1.0


def simulate(G: nx.Graph, transmitters: list[list[str]], frames: int = 100,
             load: float | None = None, seed: int = 0, label: str = "") -> SimResult:
    """Simulate ``frames`` repetitions of a frame whose slot s is owned by ``transmitters[s]``."""
    rng = random.Random(seed)
    K = len(transmitters)
    res = SimResult(label=label, frame_slots=K, frames=frames)
    nbrs = {v: set(G[v]) for v in G}
    res.links_total = 2 * G.number_of_edges()
    served: set[tuple[str, str]] = set()
    queue: dict[str, list[int]] = {v: [] for v in G}   # arrival slot index of queued packets
    tx_sets = [set(T) for T in transmitters]

    for f in range(frames):
        base = f * K
        if load is not None:
            for v in G:
                if rng.random() < load:
                    queue[v].append(base)
        for s, owners in enumerate(tx_sets):
            now = base + s
            if load is None:
                T = owners
            else:
                T = {v for v in owners if queue[v]}
            for t in T:
                res.transmissions += 1
                res.per_node_tx[t] = res.per_node_tx.get(t, 0) + 1
                if load is not None:
                    res.delay_slots_sum += now - queue[t].pop(0)
                    res.sent_packets += 1
                for r in nbrs[t]:
                    res.attempts += 1
                    if r in T:
                        res.lost_half_duplex += 1
                    elif len(nbrs[r] & T) >= 2:
                        res.lost_collision += 1
                    else:
                        res.delivered += 1
                        served.add((t, r))
                        res.per_link_delivered[(t, r)] = res.per_link_delivered.get((t, r), 0) + 1
    res.links_served = len(served)
    return res


def schedule_from_colouring(names: list[str], colour: dict[str, int]) -> list[list[str]]:
    k = max(colour.values()) + 1 if colour else 0
    return [[n for n in names if colour[n] == s] for s in range(k)]


def baseline_schedules(G: nx.Graph, names: list[str]) -> dict[str, list[list[str]]]:
    """Reference schedules for comparison.

    * round-robin: one node per slot (classic TDMA, no spatial reuse, K = N);
    * distance-1 colouring: DSATUR on G itself, i.e. only direct neighbours are
      separated (hidden terminals NOT handled).
    """
    from .coloring import dsatur  # integer-indexed: deterministic across processes

    rr = [[n] for n in names]
    idx = {n: i for i, n in enumerate(names)}
    col = dsatur([{idx[u] for u in G[n]} for n in names])
    d1 = {n: col[idx[n]] for n in names}
    return {
        "Round-robin TDMA (no reuse)": rr,
        "Distance-1 colouring (no hidden-terminal rule)": schedule_from_colouring(names, d1),
    }
