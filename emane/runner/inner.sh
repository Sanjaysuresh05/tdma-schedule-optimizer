#!/bin/bash
# One EMANE experiment inside a private (user +) network + mount + PID namespace.
# Started by run_experiments.sh via:
#   unshare [--user --map-root-user] --net --mount --pid --fork --mount-proc \
#           bash inner.sh SCENARIO RESULTS DURATION RATE ROUTE SEED
#
# Topology built here (all disappears when the namespace exits; the PID namespace
# guarantees that no EMANE daemon outlives the experiment):
#
#   hub netns:  br0 (10.99.0.254/24)  <- event publisher (pathloss + TDMA schedule)
#                 |  vethN  (one per node)
#   nodeN netns: backchan0 10.99.0.N/24  (EMANE OTA + event multicast 224.1.2.8)
#                emane0    10.100.0.N/24 (EMANE virtual transport TAP = the "radio")
#                emane platform (NEM N: virtual transport -> TDMA MAC -> emulator PHY)
#                traffic.py (UDP broadcast probes over emane0)
set -euo pipefail

SCEN=$1; RES=$2; DUR=${3:-20}; RATE=${4:-40}; ROUTE=${5:-xml}; SEED=${6:-0}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE="$HERE/../bridge"
NODES=$(python3 -c "import json,sys; print(' '.join(str(n['nem_id']) for n in json.load(open(sys.argv[1]))))" "$SCEN/nodes.json")
# Realtime scheduling needs CAP_SYS_NICE in the initial user namespace, i.e. a real-root run.
RT_FLAG=""; [ "${VMN_EMANE_REALTIME:-0}" = "1" ] && RT_FLAG="-r"
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$RES/run.log"; }

cleanup() {
  for p in "$RES"/emane-*.pid; do [ -f "$p" ] && kill "$(cat "$p")" 2>/dev/null || true; done
  sleep 1
  for p in "$RES"/emane-*.pid; do [ -f "$p" ] && kill -9 "$(cat "$p")" 2>/dev/null || true; done
}
trap cleanup EXIT

# --- private /run so that `ip netns` works without touching the real system
mount -t tmpfs tmpfs /run
mkdir -p /run/netns

# --- hub: bridge for the back-channel (OTA + event multicast)
ip link set lo up
ip link add br0 type bridge
ip link set br0 type bridge mcast_snooping 0   # flood multicast: no IGMP querier here
ip addr add 10.99.0.254/24 dev br0
ip link set br0 up
ip route add 224.0.0.0/4 dev br0

for n in $NODES; do
  ip netns add "node$n"
  ip link add "veth$n" type veth peer name backchan0 netns "node$n"
  ip link set "veth$n" master br0 up
  # IPv6 off in the node: otherwise router/neighbour-discovery frames ride the radio too
  ip netns exec "node$n" sh -c "sysctl -qw net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1; \
                                ip link set lo up; ip addr add 10.99.0.$n/24 dev backchan0; \
                                ip link set backchan0 up; ip route add 224.0.0.0/4 dev backchan0"
done
log "namespaces up: $(echo $NODES | wc -w) nodes (seed $SEED, realtime ${RT_FLAG:-off})"

# --- start one EMANE platform per node
for n in $NODES; do
  ip netns exec "node$n" emane "$SCEN/platform-$(printf %02d "$n").xml" -d -l 2 $RT_FLAG \
      -f "$RES/emane-$n.log" --pidfile "$RES/emane-$n.pid" --uuidfile "$RES/emane-$n.uuid"
done

# --- wait for every control port
HOSTS=""
for n in $NODES; do HOSTS="$HOSTS 10.99.0.$n"; done
python3 - "$HOSTS" <<'EOF'
import socket, sys, time
hosts = sys.argv[1].split()
deadline = time.time() + 30
pending = set(hosts)
while pending and time.time() < deadline:
    for h in list(pending):
        try:
            socket.create_connection((h, 47000), timeout=0.5).close()
            pending.discard(h)
        except OSError:
            pass
    time.sleep(0.2)
if pending:
    sys.exit(f"control port not reachable on {sorted(pending)}")
EOF
log "all EMANE control ports up"
for n in $NODES; do ip netns exec "node$n" ip -br addr show emane0 >> "$RES/interfaces.txt"; done

# --- publish channel model (pathloss) and the TDMA schedule from the hub
python3 "$BRIDGE/publish_events.py" "$SCEN" -i br0 --route "$ROUTE" \
        --dump "$RES/schedule_events_hex.json" | tee -a "$RES/run.log"

# --- gate: traffic starts only once every NEM reports the full schedule accepted
ok=0
for attempt in $(seq 1 20); do
  sleep 0.5
  if python3 "$HERE/collect.py" --hosts $HOSTS --out "$RES/stats_before_traffic.json" --require-schedule \
       >> "$RES/run.log" 2>&1; then ok=1; break; fi
done
[ "$ok" = 1 ] || { log "ERROR: schedule not accepted by all NEMs"; exit 3; }
sleep 1   # the schedule takes effect at the next multiframe boundary (K ms)
log "schedule accepted by all NEMs (attempt $attempt)"

# --- traffic: Poisson UDP broadcast probes from every node
START=$(python3 -c "import time; print(time.time() + 3.0)")
log "traffic: $RATE pkt/s per node for ${DUR}s"
PIDS=""
for n in $NODES; do
  ip netns exec "node$n" python3 "$HERE/traffic.py" --nem "$n" --rate "$RATE" --duration "$DUR" \
      --start-at "$START" --seed "$SEED" --out "$RES/traffic-$n.json" &
  PIDS="$PIDS $!"
done
fail=0
for p in $PIDS; do wait "$p" || fail=1; done
[ "$fail" = 0 ] || { log "ERROR: a traffic generator failed"; exit 4; }
log "traffic done"

python3 "$HERE/collect.py" --hosts $HOSTS --out "$RES/stats.json" | tee -a "$RES/run.log"
cp "$SCEN/scenario.json" "$SCEN/nodes.json" "$SCEN/schedule.xml" "$RES/"
log "experiment complete"
