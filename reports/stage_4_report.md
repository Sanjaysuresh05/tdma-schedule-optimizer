# Stage 4 Report: EMANE engine (Part 2): install, TDMA profiles, bridge, enforcement experiments

## What I did
* **Installed EMANE 1.5.3** on one Linux machine (WSL2 Ubuntu 24.04.2, kernel 6.18) **without root or Docker**.
  * `emane/install_rootless.sh` downloads the official Adjacent Link Ubuntu 24.04 bundle and **verifies its SHA-256** (`a60a2fd1…f53638`; the script refuses to install on a mismatch).
  * It extracts the needed `.deb`s with `dpkg-deb -x` into `~/vmn-emane/sysroot` and fetches missing runtime dependencies from the Ubuntu archive.
  * It touches nothing outside that prefix. It is idempotent: I re-ran it and verified the result.
* **Wrote the integration bridge** `emane/bridge/schedule_to_emane.py`. It converts the Brain's schedule JSON into:
  * the EMANE TDMA **schedule XML**, validated against EMANE's own `tdmaschedule.xsd` and round-trip checked;
  * per-node platform/NEM/MAC/PHY/transport XML, using EMANE's official TDMA template;
  * a pathloss matrix. The default reproduces the 500 m graph; options give free space on links only, or free space for every pair.
* **Two publishing routes** in `emane/bridge/publish_events.py`:
  * through EMANE's own XML parser (`--route xml`, the same as `emaneevent-tdmaschedule`);
  * by building `TDMAScheduleEvent` ProtoBuf messages directly (`--route protobuf`).
  * It also publishes the pathloss events.
* **Built a rootless 16-node testbed** in `emane/runner/`:
  * one unprivileged user + network + mount + **PID** namespace, so no EMANE daemon can outlive a run;
  * a hub bridge carrying OTA and event multicast;
  * 16 node network namespaces, with IPv6 disabled so that only probe traffic uses the radio;
  * one EMANE platform per node, with a TAP radio interface.
* **Traffic only starts once every NEM reports the full schedule accepted** (`collect.py --require-schedule`). The probes are Poisson UDP broadcasts with exact one-way latency and a per-run seed. Per-node start skew is recorded (≤ 1.1 ms), and every traffic process's exit status is checked.
* **Ran 6 experiments plus 10 replications** (`emane/runner/run_experiments.sh 20 40`, 20 s each) and analysed them with `emane/analysis/analyze.py`. Output: `emane/results/summary.md` and 5 figures.
* **Wrote a Dockerfile** for the "one consolidated container" option. It is clearly labelled **not built here**, because Docker is not installed.
* **Wrote 5 bridge unit tests** that run without EMANE (`tests/test_stage4_bridge.py`).
* **Commissioned an independent reviewer** (a fresh Opus subagent) for this stage. It recomputed every number from the raw files and found one real flaw in my evidence, which is described and fixed below.

## Why this method
| Decision | Options compared | Choice and reason |
|---|---|---|
| Where to run EMANE | Docker (not installed); system-wide `dpkg -i` (needs a sudo password, not available); **rootless sysroot + user namespaces** | Rootless works within the real constraints and changes nothing on the host. A real-root run, or the Dockerfile, skips the user namespace and can enable realtime scheduling (`VMN_EMANE_REALTIME=1`). |
| How EMANE learns the 500 m graph | Location events + free space (fuzzy edge); **precomputed pathloss from the same graph** | Precomputed. Links at 90 dB, so rx = 30 − 90 = −60 dBm, 40 dB above the −100 dBm noise floor. Non-links at 200 dB, which makes them invisible. EMANE's connectivity then **equals the task's model by construction**. This is an input, not a result. Experiment E5 deliberately removes this assumption. |
| XML or ProtoBuf | Either reading of R15 | **Both** (E1 vs E1b), with identical behaviour. |
| Traffic | ping (unicast, ARP-dependent); iperf (not installed); **own UDP broadcast probe** | Broadcast is the Part 1 scheduling model. Sequence numbers and timestamps give exact per-link delivery and latency. |
| Evidence of enforcement | EMANE's `TxSlotStatusTable`; **receiver-side slot receptions versus sender-side air transmissions** | `TxSlotStatusTable` counts TX *opportunities* of the installed schedule, so it only confirms that the schedule was installed. The real evidence uses physical events at both ends; see below. |

### Correction made after the independent review
My first analysis cited "each NEM transmits only in its planned slot", taken from EMANE's `TxSlotStatusTable`. The reviewer showed that this table lists **TX opportunities**, not transmissions. For example, NEM 1 has 2 982 "valid" entries against only 708 physical transmissions, and the counts already exist before any traffic. So that check only compared the schedule with itself.

I replaced it with a **non-circular, receiver-side test**. For every directed link t → r where t is the only neighbour of r scheduled in t's slot:

ratio = (frames r received in that slot, from EMANE `RxSlotStatusTable` at r) / (frames t put on the air, from EMANE PHY `BroadcastPacketAcceptTable0` at t)

I also count frames received in any slot where r has *no* scheduled neighbour; these must be zero. The reviewer's other findings were fixed as well:
* traffic is gated on schedule acceptance;
* IPv6 is disabled, which removed 8–9 stray frames per node;
* each process's exit status is checked, and start skew is recorded;
* a PID namespace ensures cleanup;
* the bundle checksum is verified;
* 5-seed replication was added, with a high-load run (E4) and a physical-channel run (E5).

I also removed two claims that were wrong:
* "fspl would show capture". On this grid the interferers differ by at most 3 dB, which is below the curve's 0 % point, so there is no capture.
* "add -r with root". That can work only outside a user namespace; it is now implemented that way for real-root and Docker runs. It is untested here.

## How it works

**Intuition.** EMANE's TDMA model gives every NEM a per-slot role: TX, RX or idle. A NEM sends queued packets only at the start of its own TX slots and listens in RX slots. The emulated PHY decides whether a frame survives using the SINR and the packet-completion-rate (PCR) curve. Load the Brain's matrix as the schedule, and EMANE carries a frame only in its scheduled slot. Two schedule-violating transmitters overlapping at a receiver destroy each other's frames.

**EMANE mapping** (EMANE docs and the 1.5.3 XSD):
* `<structure frames="1" slots="K" slotduration="1000" slotoverhead="100" bandwidth="10M"/>` defines **1 ms slots** and a frame of K slots, i.e. K ms. The 100 µs guard leaves 900 µs; at 12 Mbit/s that is **1350 bytes per slot**.
* `<multiframe frequency="2.4G" power="30" class="0" datarate="12M">` sets the carrier, tx power and slot data rate. 12M exists in the TDMA PCR curve, which gives 0 % reception at SINR ≤ 3 dB and 100 % at ≥ 9 dB.
* Matrix row s becomes `<slot index="s" nodes="i,j,…"/>`. A defined slot defaults to **TX** for the listed NEMs. Every other slot defaults to **RX** under the full-schedule rule, which gives half-duplex TDMA.
* A silenced node (E2) is listed as `<slot index="0:K-1" nodes="6"><rx/></slot>`. It stays referenced, but it never transmits.

**Testbed.** The hub namespace holds `br0` (10.99.0.254/24, IGMP snooping off). Node namespace N holds:
* `backchan0` (10.99.0.N), carrying EMANE OTA 224.1.2.8:45702 and the event channel :45703;
* `emane0` (10.100.0.N/24), the TAP created by the virtual transport.

Pathloss and schedule events are published from the hub. The runner then polls every control port until `scheduleAcceptFull = 1` with no rejects, waits one more second (activation happens at the next multiframe boundary), and starts traffic 3 s later at a common epoch time.

**Worked numerical example** (E1 and E2, values from `emane/results/`):
* *Link budget.* rx = 30 dBm − 90 dB = −60 dBm. Noise = −174 dBm/Hz + 10·log₁₀(10⁷) + 4 dB = −100 dBm, so SNR = 40 dB, giving 100 % on the 12 Mbit/s curve. Two equal-power overlapping frames give SINR ≈ 0 dB, below the 3 dB floor, so both are lost.
* *Slot attribution.* Node_02's neighbours are 01, 03, 05, 06 and 07. Only Node_01 among them owns slot 0, so every frame Node_02 receives in slot 0 must come from Node_01, and that count can be compared with the frames Node_01's PHY transmitted. Over all 84 directed links the receiver-side count is **99.89 %** of the sender's air transmissions on average, and at least 99.70 % on every link. There were **0** frames in slots with no scheduled neighbour.
* *Access latency.* A Poisson packet waits for the sender's slot: uniform over the 9 ms frame (mean 4.5 ms), plus about one slot. Theory gives about 5.5 ms. **Measured: 5.73 ms mean.** The p99 is 10.15 ms, close to frame + slot = 10 ms.
* *E2 queue arithmetic.* Node_06 (no TX slot) enqueued its 787 probes. The queue depth is 255, so 787 − 255 = **532 overflow drops**, which is exactly EMANE's `QueueStatusTable`. Its PHY transmitted **0** frames.

## Results and evidence (final run; full tables in `emane/results/summary.md`)

| Experiment | Slots | Load (pkt/s/node) | Delivery on 500 m links (mean / min) | Non-links (max) | Frames heard in sender's slot / sent (mean, min) | Stray valid receptions | Collision (SINR) drops |
|---|---|---|---|---|---|---|---|
| **E1** Brain schedule (XML route) | 9 | 40 | **99.88 % / 99.38 %** | **0.00 %** | **99.89 %, 99.70 %** (84 links) | **0** | **0** |
| **E1b** same, ProtoBuf route | 9 | 40 | 99.93 % / 99.51 % | 0.00 % | 99.93 %, 99.69 % | 0 | 0 |
| **E2** Node_06's slot removed | 9 | 40 | others 99.99 % / 99.76 %; **Node_06: 0.0 %, 0 PHY frames** | 0.00 % | 99.98 %, 99.71 % (76 links) | 0 | 0 (532 queue overflows) |
| **E3** distance-1 (wrong) schedule | 4 | 40 | **84.36 % / 58.21 %** | 0.00 % | 99.58 %, 99.22 % (20 unshared links) | 0 | **532 226 B** (+4 788 RX-lock errors) |
| **E4** E1 at 10× load | 9 | 400 | 96.63 % / 93.42 % | 0.00 % | 96.78 %, 93.99 % | 0 | 0 (0 queue overflows) |
| **E5** E1 over free space, every pair | 9 | 40 | **83.42 % / 41.55 %** | **98.83 %** | n/a (channel ≠ planned graph) | n/a | **4 910 450 B** |

**Replication** (traffic seeds 1–5, same schedules):
* E1: 99.87, 99.98, 99.87, 99.93, 99.90 % → **99.91 % ± 0.06 (95 % CI)**.
* E3: 84.75, 84.77, 84.73, 84.97, 84.70 % → **84.78 % ± 0.13**, against **83.9 %** predicted by my slot-level simulator.

**Interpretation**
* **Permitted where planned.** Every scheduled link delivers. Each sender's frames are received by its neighbours in its planned slot (99.89 %). No frame ever arrives in a slot where the receiver has no scheduled neighbour, and nothing crosses a non-link.
* **Dropped where the schedule says.** A node without a TX slot puts **0 frames** on the air, and its queue overflows (E2). A schedule that violates the 2-hop rule collides at the common neighbours: 532 kB of SINR drops, exactly at the hidden-terminal receivers the verifier names (E3).
* **Independent models agree.** For E3, the per-link points fall on the diagonal of simulator vs EMANE (`docs/figures/emane_e3_predicted_vs_measured.png`): about 60 % with two hidden interferers, about 85 % with one, 100 % with none. EMANE runs about 0.9 pp above the simulator, reproducibly (CI ± 0.13). The likely cause is EMANE's packet aggregation: two queued probes leave in one transmission, so there are fewer collision opportunities. The simulator sends one packet per slot. This is a modelling difference I identified but did not test separately.
* **Residual E1 loss (0.12 %) is host timing, not scheduling.**
  * EMANE missed 76 of 47 703 TX slots (0.16 %); 57 TX opportunities fired more than 1.75 slots late; avgTimedEventLatency was 108–117 µs, comparable to the 100 µs guard.
  * Every log contains "Unable to set Real Time Priority": a rootless run inside a user namespace cannot have CAP_SYS_NICE.
  * There were 0 SINR drops and 0 RX-during-TX errors.
* **E4 (10× load).** Aggregation carries about 3.6 packets per frame in one 1 ms slot, with 0 queue overflows and 0 collisions. The 3.4 % loss is MAC "Slot Error" (2.4 MB) from longer frames crossing slot boundaries under the same host timing jitter. It is a fidelity limit of this host, not of the schedule.
* **E5 (physical channel).** With free-space loss for every pair (3 dBm, so the 100 % decode edge is about 500 m), the channel has **no hard edge**:
  * 600 m pairs are still received about 98 % of the time;
  * co-slot transmitters 900 m apart are only about 6.5 dB weaker than a 424 m link, below the 9 dB the 12 Mbit/s curve needs.
  * The 500 m distance-2 schedule therefore collides (4.9 MB SINR drops, 83.4 % delivery).
  * This quantifies the limit of the task's unit-disk assumption. The remedy stays in the Brain: plan with an interference radius (`--range`) that covers the real interference range, use power control, or use a lower data rate with a lower SINR threshold.
  * By my link-budget calculation, for this 900 m grid in free space at 12 Mbit/s even the best-separated pair (two opposite corners, 1 273 m apart) gives SINR ≈ 4.7 dB at a shared neighbour. So no two nodes can share a slot cleanly, and spatial reuse would need a steeper path-loss environment.

## Assumptions and limitations
* E1–E4 use a **unit-disk channel by construction** (90/200 dB). That validates schedule *enforcement*. E5 shows what happens without it.
* **No realtime priority** (rootless): 0.13–0.47 % of TX slots are missed per run. A real-root or Docker run can pass `-r` (`VMN_EMANE_REALTIME=1`); this is untested here.
* Only broadcast traffic is used (the scheduling model). Unicast/ARP is enabled but not exercised.
* The **Dockerfile was not built or run.** It follows the official instructions, verifies the checksum and uses the same runner.
* WSL2 is a VM; bare-metal Linux with realtime priority would show fewer missed slots.

## Final deliverable
* Top-level files in `emane/`: `README.md`, `install_rootless.sh`, `make_scenarios.py`.
* Bridge: `emane/bridge/{schedule_to_emane.py,publish_events.py}`.
* Runner: `emane/runner/{run_experiments.sh,inner.sh,traffic.py,collect.py}`.
* Analysis: `emane/analysis/analyze.py`.
* Schema, inputs and Docker: `emane/schema/tdmaschedule.xsd`, `emane/scenarios/inputs/*.json`, `emane/docker/Dockerfile`.
* Results: `emane/results/{E1_optimized,E1b_protobuf,E2_silenced,E3_distance1,E4_highload,E5_freespace}/` and `emane/results/replication/*` (raw scenario and results), plus `emane/results/summary.{md,json}`.
* Figures and tests: `docs/figures/emane_*.png`, `tests/test_stage4_bridge.py`.
