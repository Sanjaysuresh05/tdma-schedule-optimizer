# Stage 4 Report: EMANE engine (Part 2): install, TDMA profiles, bridge, enforcement experiments

## What I did
* **Installed EMANE 1.5.3** on one Linux machine (WSL2 Ubuntu 24.04.2, kernel 6.18) **without root or Docker**.
  * `emane/install_rootless.sh` downloads the official Adjacent Link Ubuntu 24.04 bundle (sha256 `a60a2fd1…f53638`).
  * It extracts the needed `.deb`s with `dpkg-deb -x` into `~/vmn-emane/sysroot` and fetches the missing runtime dependencies from the Ubuntu archive.
  * It touches nothing outside that prefix, and it is idempotent (re-run and verified).
* **Wrote the integration bridge** `emane/bridge/schedule_to_emane.py`. It converts the Brain's schedule JSON into:
  * EMANE TDMA **schedule XML**, validated against EMANE's own `tdmaschedule.xsd` and round-trip checked;
  * per-node platform/NEM/MAC/PHY/transport XML (EMANE's official TDMA template);
  * a precomputed **pathloss** matrix that reproduces the 500 m graph.
* **ProtoBuf route.** `emane/bridge/publish_events.py` publishes the schedule either via EMANE's own XML parser (`--route xml`, the same as `emaneevent-tdmaschedule`) or by building `TDMAScheduleEvent` ProtoBuf messages directly (`--route protobuf`). It also publishes the pathloss events.
* **Built a rootless 16-node testbed** (`emane/runner/`):
  * one unprivileged user + network + mount namespace;
  * a hub bridge carrying the OTA and event multicast;
  * 16 node network namespaces, each running one EMANE platform with a TAP radio interface;
  * Poisson UDP broadcast probes with exact one-way latency (shared kernel clock);
  * statistics pulled from every NEM's control port with EMANE's `ControlPortClient`.
* **Ran 4 experiments** (`emane/runner/run_experiments.sh 20 40`, 20 s each, 40 packets/s per node) and analysed them with `emane/analysis/analyze.py`. Output is in `emane/results/summary.md` and 3 figures.
* **Wrote a Dockerfile** for the "one consolidated container" option. It is clearly labelled **not built here**, because Docker is not installed on this machine.
* **Wrote 5 bridge unit tests** that run without EMANE (`tests/test_stage4_bridge.py`).

## Why this method
| Decision | Options compared | Choice and reason |
|---|---|---|
| Where to run EMANE | Docker container (not installed); system-wide `dpkg -i` (needs sudo password, not available); **rootless sysroot + user namespaces** | Rootless works within the real constraints. I proved in Phase 0 that unprivileged user/net namespaces with bridge and TUN work in this WSL2. Nothing on the user's system is modified. The Dockerfile covers the container option for graders. |
| How EMANE learns the 500 m graph | Location events + free-space propagation (the link edge depends on tuned power/sensitivity, so it is fuzzy); **precomputed pathloss from the same graph** | Precomputed. Linked pairs at 90 dB, so rx = 30 − 90 = −60 dBm, 40 dB above the −100 dBm noise floor. Unlinked pairs at 200 dB, so rx = −170 dBm, invisible. EMANE's connectivity is then *exactly* the Brain's model, which is what "strictly based on the schedule" requires. `--pathloss-model fspl` is available for distance-dependent loss. |
| XML or ProtoBuf | Either reading of R15 | **Both**, exercised as E1 (XML) and E1b (ProtoBuf), with identical results. |
| Traffic | ping (unicast, ARP-dependent); iperf (not installed); **own UDP broadcast probe** | Broadcast is the scheduling model of Part 1 (node-based, a transmission is heard by all neighbours). Sequence numbers and timestamps give exact per-link delivery and latency. No dependencies. |
| Evidence | Application counters only; **application counters + EMANE's own MAC statistics** | Both. EMANE's `TxSlotStatusTable` shows *which slot index* each NEM transmitted in. That is direct proof that the MAC follows the Brain's matrix, independent of whether traffic arrived. |

## How it works

**Intuition.** EMANE's TDMA model gives every NEM a per-slot role: TX, RX or idle. A NEM sends queued packets only at the start of its own TX slots and listens in RX slots. The emulated PHY decides whether a frame survives, using the SINR and the packet-completion-rate curve. If the Brain's matrix is loaded as the schedule, EMANE carries a packet only when the schedule allows it. If two schedule-violating transmitters overlap at a receiver, the PHY destroys the frames.

**EMANE mapping (from the EMANE docs and the 1.5.3 XSD).**
* `<structure frames="1" slots="K" slotduration="1000" slotoverhead="100" bandwidth="10M"/>` defines 1 ms slots and a frame of K slots, i.e. a K ms frame. 100 µs of guard per slot leaves 900 µs; at 12 Mbit/s that is **1350 bytes per slot**.
* `<multiframe frequency="2.4G" power="30" class="0" datarate="12M">` sets the carrier, tx power and slot data rate. 12M must exist in the TDMA PCR curve, which defines 1/2/5.5/11/6/9/12/18/24/36/48/54 Mbit/s.
* Row s of the matrix becomes `<slot index="s" nodes="i,j,…"/>`. A defined slot defaults to **TX** for the listed NEMs. Every slot a NEM is not listed in defaults to **RX** on the multiframe frequency (full-schedule rule). That gives exactly the half-duplex TDMA behaviour wanted.
* A "silenced" node (E2) is listed as `<slot index="0:K-1" nodes="6"><rx/></slot>`. It stays referenced, because EMANE only sends schedules to referenced NEMs, but it never transmits.
* EMANE activates a full schedule at the next multiframe boundary counted from the epoch. The runner waits 3 s after publishing, more than 300 multiframes.

**Testbed.** The hub namespace holds `br0` (10.99.0.254/24, IGMP snooping off so multicast floods). Node namespace N holds `backchan0` (10.99.0.N, the EMANE OTA channel 224.1.2.8:45702 and the event channel :45703) and `emane0` (10.100.0.N/24, the TAP created by EMANE's virtual transport). Pathloss and schedule events are published from the hub on `br0`. All of it is torn down automatically when the namespace exits, and leftover EMANE processes are killed by a trap.

**Worked numerical example (E1 and E2, values from `emane/results/`).**
* *Link budget.* rx = 30 dBm − 90 dB = −60 dBm. Noise floor = −174 dBm/Hz + 10·log₁₀(10⁷ Hz) + 4 dB (noise figure) = −100 dBm, so SNR = 40 dB. EMANE's 12 Mbit/s PCR curve (`tdmabasemodelpcr.xml`) gives 0 % reception at SINR ≤ 3 dB and 100 % at ≥ 9 dB. At 40 dB, every frame on a link survives. Two equal-power overlapping frames give SINR ≈ 0 dB, which is below the 3 dB floor, so both are lost. E3 shows this as SINR drops.
* *Access latency.* Poisson packets wait for the sender's slot, a uniform wait over the 9 ms frame (mean 4.5 ms), plus the slot transmission and processing. The predicted mean is about 4.5 + 1 ≈ 5.5 ms. **Measured: 5.71 ms mean**, with p99 = 10.16 ms ≤ frame + slot = 10 ms (+ processing jitter).
* *E2 queue arithmetic.* Node_06 (no TX slot) enqueued 795 packets: 787 probe packets plus 8 packets the kernel emitted on its TAP. Queue depth is 255, so 795 − 255 = **540 overflow drops**. That is exactly EMANE's `QueueStatusTable`. Zero of its packets reached any neighbour.

## Results and evidence (final run; full table in `emane/results/summary.md`)

| Experiment | Slots / frame | Delivery on the 84 directed links (mean / min) | Delivery on non-links (max) | Schedules accepted | TX only in planned slots | RX only in neighbours' slots | Mean latency | Collision (SINR) drops |
|---|---|---|---|---|---|---|---|---|
| E1 optimised (XML route) | 9 / 9 ms | **99.96 % / 99.62 %** | **0.00 %** | 16/16, 0 rejects | **16/16** | 16/16 | 5.71 ms | **0** |
| E1b same schedule (ProtoBuf route) | 9 / 9 ms | 99.94 % / 99.64 % | 0.00 % | 16/16 | 16/16 | 16/16 | 5.76 ms | 0 |
| E2 Node_06 TX slot removed | 9 / 9 ms | others 99.98 % / 99.76 %; **Node_06 → anyone 0.0 %** | 0.00 % | 16/16 | 16/16 (Node_06: none) | 16/16 | 5.69 ms | 0 (540 queue overflows at Node_06) |
| E3 distance-1 baseline | 4 / 4 ms | **84.50 % / 59.22 %** | 0.00 % | 16/16 | 16/16 | 16/16 | 3.22 ms | **545 752 bytes** (+4 927 RX-lock slot errors) |

* **The schedule is enforced.** In E1 the slot index of every NEM's TX activity (`TxSlotStatusTable`) equals the Brain's assignment, for example NEM 6 → slot 4 and NEMs 1/4/13/16 → slot 0. See figure `docs/figures/emane_slot_enforcement.png`, which places the planned matrix next to EMANE's observed matrix (identical).
* **Permitted vs dropped.** Packets are permitted on graph links (99.96 %) and dropped for non-neighbours (0 %, PHY "Rx Sensitivity" drops). Packets from a node without a TX slot are never sent (E2). Packets collide where the schedule violates the 2-hop rule (E3).
* **Independent model check.** For E3, the slot-level simulator (Stage 3), given the same offered load (0.16 packets per node per frame), predicted **83.9 %** delivery. EMANE measured **84.5 %**. Per link, the points sit on the diagonal (`docs/figures/emane_e3_predicted_vs_measured.png`): the links with two hidden-terminal interferers cluster at about 60 %, and those with one at about 85 %. Two independent implementations, my simulator and EMANE's PHY/MAC, agree.
* **The tiny E1 loss (0.04 %) is explained.** EMANE's `TxSlotErrorMissed` = 88 of 47 703 TX slots (0.18 %), and the MAC "Slot Error" drops are about 3 KB. EMANE logs "Unable to set Real Time Priority" because realtime scheduling needs root. EMANE's docs name missed slots as the symptom of a timing-limited host. The losses are not schedule-related: there are 0 SINR drops and 0 RX-during-TX errors.

## Assumptions and limitations
* **Channel = unit-disk by construction** (precomputed pathloss of 90/200 dB). This validates schedule *enforcement*, not RF propagation. With `--pathloss-model fspl`, capture effects between unequal interferers would appear.
* **No realtime priority** (rootless), so a measured 0.18 % of TX slots were missed. With root, add `-r` to the `emane` command to remove this.
* Only broadcast traffic was tested, because broadcast is the scheduling model. Unicast would need ARP over the virtual transport, which is enabled but not exercised.
* The **Dockerfile was not built or run** (no Docker on this machine). It follows the official install instructions and uses the same runner. The executed path is the native rootless one.
* WSL2 is a VM. Experiments on bare-metal Linux with realtime priority would show even fewer missed slots.

## Final deliverable
`emane/README.md`, `emane/install_rootless.sh`, `emane/bridge/schedule_to_emane.py`, `emane/bridge/publish_events.py`, `emane/runner/{run_experiments.sh,inner.sh,traffic.py,collect.py}`, `emane/analysis/analyze.py`, `emane/make_scenarios.py`, `emane/schema/tdmaschedule.xsd`, `emane/scenarios/inputs/{E1_optimized,E3_distance1,predictions}.json`, `emane/docker/Dockerfile`, `emane/results/{E1_optimized,E1b_protobuf,E2_silenced,E3_distance1}/` (raw scenario and results), `emane/results/summary.{md,json}`, `docs/figures/emane_*.png`, `tests/test_stage4_bridge.py`
