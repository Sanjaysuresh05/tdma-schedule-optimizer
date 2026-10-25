#!/bin/bash
# Run the Part 2 EMANE experiments on one Linux host (rootless by default).
#
#   emane/runner/run_experiments.sh [DURATION_S] [RATE_PPS] [EXPERIMENT ...]
#
#   E1_optimized   Brain schedule (4x4 grid, 9 slots), XML route
#   E1b_protobuf   same schedule, ProtoBuf route
#   E2_silenced    Node_06's TX slot removed
#   E3_distance1   distance-1 colouring (hidden terminals not handled)
#   E4_highload    E1 at 10x the offered load (exercises aggregation / slot capacity)
#   E5_freespace   E1 schedule over a physical free-space channel for ALL pairs
#                  (no 500 m cut-off; tx power set so the 100 % decode edge is ~500 m)
#   REPLICATION    E1 and E3 with traffic seeds 1..5 (statistical spread)
#
# Prerequisites: EMANE 1.5.3 either installed system-wide (official .debs) or
# extracted rootless (emane/install_rootless.sh); VMN_EMANE_ENV points to a script
# exporting PATH/LD_LIBRARY_PATH/PYTHONPATH/VMN_EMANE_SYSROOT ("" = system install).
# As real root the user namespace is skipped and VMN_EMANE_REALTIME=1 enables -r.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
ENV_FILE="${VMN_EMANE_ENV:-$HOME/vmn-emane/env.sh}"
[ -f "$ENV_FILE" ] && source "$ENV_FILE"
SYSROOT="${VMN_EMANE_SYSROOT:-}"
WORK="${VMN_EMANE_WORK:-$HOME/vmn-emane/work}"
DUR=${1:-20}
RATE=${2:-40}
shift $(( $# > 2 ? 2 : $# ))
WANT="${*:-E1_optimized E1b_protobuf E2_silenced E3_distance1 E4_highload E5_freespace REPLICATION}"

DTD="$SYSROOT/usr/share/emane/dtd"
PCR="$SYSROOT/usr/share/emane/xml/models/mac/tdmaeventscheduler/tdmabasemodelpcr.xml"
INPUTS="$REPO/emane/scenarios/inputs"
if [ "$(id -u)" = 0 ]; then NS=(unshare --net --mount --pid --fork --mount-proc)
else NS=(unshare --user --map-root-user --net --mount --pid --fork --mount-proc); fi

# run NAME GROUP JSON ROUTE RATE SEED [bridge args...]
run() {
  local name=$1 group=$2 json=$3 route=$4 rate=$5 seed=$6; shift 6
  case " $WANT " in *" $group "*) ;; *) return 0 ;; esac
  echo "=== $name (route=$route, rate=$rate, seed=$seed) ==="
  rm -rf "${WORK:?}/$name"; mkdir -p "$WORK/$name/results"
  python3 "$REPO/emane/bridge/schedule_to_emane.py" "$json" -o "$WORK/$name/scenario" \
          --dtd-dir "$DTD" --pcr-uri "$PCR" "$@"
  "${NS[@]}" bash "$HERE/inner.sh" "$WORK/$name/scenario" "$WORK/$name/results" "$DUR" "$rate" "$route" "$seed"
  local dest="$REPO/emane/results/$name"
  # a directory that some (Windows) process has as its cwd cannot be removed: empty it instead
  rm -rf "$dest" 2>/dev/null || find "$dest" -mindepth 1 -delete 2>/dev/null || true
  mkdir -p "$dest"
  cp -r "$WORK/$name/scenario" "$WORK/$name/results" "$dest/"
}

run E1_optimized E1_optimized "$INPUTS/E1_optimized.json" xml      "$RATE" 0
run E1b_protobuf E1b_protobuf "$INPUTS/E1_optimized.json" protobuf "$RATE" 0
run E2_silenced  E2_silenced  "$INPUTS/E1_optimized.json" xml      "$RATE" 0 --silence Node_06
run E3_distance1 E3_distance1 "$INPUTS/E3_distance1.json" xml      "$RATE" 0
run E4_highload  E4_highload  "$INPUTS/E1_optimized.json" xml      "$(( RATE * 10 ))" 0
run E5_freespace E5_freespace "$INPUTS/E1_optimized.json" xml      "$RATE" 0 \
    --pathloss-model fspl-all --power 3
for seed in 1 2 3 4 5; do
  run "replication/E1_seed$seed" REPLICATION "$INPUTS/E1_optimized.json" xml "$RATE" "$seed"
  run "replication/E3_seed$seed" REPLICATION "$INPUTS/E3_distance1.json" xml "$RATE" "$seed"
done
echo "results in $REPO/emane/results"
