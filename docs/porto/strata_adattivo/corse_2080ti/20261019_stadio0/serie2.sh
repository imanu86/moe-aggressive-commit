#!/bin/bash
# Serie 2 (Daily 0.1.45 com'e', --batch 4: cache fissa sullo stadio 0): B-A-B sulla riserva di VRAM della 3060.  Ogni braccio prende bench.lock per la sola corsa.
export PATH=/usr/bin:/mingw64/bin:$PATH
H="$(cd "$(dirname "$0")" && pwd)"
BL="$H/st0_lock.py"
cd "$H"
run() { n=$1; shift; echo "=== $n $(date +%H:%M:%S)"; python -u "$BL" "DET-ST0-$n" -- python -u -B st0_run.py --name "DET-ST0-$n" --gpu-engine --short-n 5 --decodes 3 "$@" > "runlog_$n.txt" 2>&1; echo "$n rc=$? $(date +%H:%M:%S)"; }
for arm in "S2A1:0" "S2B1a:1024" "S2A2:0" "S2B2a:2048" "S2A3:0" "S2B3a:3072" "S2A4:0" "S2B1b:1024" "S2A5:0" "S2B2b:2048" "S2A6:0"; do
  n=${arm%%:*}; x=${arm##*:}
  [ -f "$H/STOP_SERIE" ] && { echo "STOP"; break; }
  run "$n" --extra-mib "$x"
done
