#!/bin/bash
# Serie 1: profilo + B-A-B sulla VRAM dello stadio 0.  Ogni braccio prende bench.lock per la sola corsa (bench_lock.py).
export PATH=/usr/bin:/mingw64/bin:$PATH
H="$(cd "$(dirname "$0")" && pwd)"
BL="$H/st0_lock.py"
cd "$H"
run() { n=$1; shift; echo "=== $n $(date +%H:%M:%S)"; python -u "$BL" "DET-ST0-$n" -- python -u -B st0_run.py --name "DET-ST0-$n" "$@" > "runlog_$n.txt" 2>&1; echo "$n rc=$? $(date +%H:%M:%S)"; }
run P1 --env STRATA_PREFILL_TIMING=1 --env STRATA_VERIFY_PROFILE=1
for arm in "A1:0" "B2a:2048" "A2:0" "B4a:4096" "A3:0" "B2b:2048" "A4:0" "B4b:4096" "A5:0"; do
  n=${arm%%:*}; x=${arm##*:}
  [ -f "$H/STOP_SERIE" ] && { echo "STOP"; break; }
  run "$n" --extra-mib "$x"
done
