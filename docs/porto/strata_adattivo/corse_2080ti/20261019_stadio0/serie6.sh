#!/bin/bash
# Serie 6: famiglia --expert-cache esplicito (punti intermedi) e profilo del prefill in salute (tempo per stadio).
export PATH=/usr/bin:/mingw64/bin:$PATH
H="$(cd "$(dirname "$0")" && pwd)"
BL="$H/st0_lock.py"
cd "$H"
until grep -q "S5P2b rc\|STOP5" serie5.log; do sleep 5; done
run() { n=$1; shift; echo "=== $n $(date +%H:%M:%S)"; python -u "$BL" "DET-ST0-$n" -- python -u -B st0_run.py --name "DET-ST0-$n" --gpu-engine --short-n 5 --decodes 3 "$@" > "runlog_$n.txt" 2>&1; echo "$n rc=$? $(date +%H:%M:%S)"; }
chk() { [ -f "$H/STOP_SERIE6" ] && { echo "STOP6"; exit 0; }; }
chk; run S6T1 --set-opt=--expert-cache=2000 --env STRATA_PREFILL_TIMING=1 --short-n 2 --decodes 0
chk; run S6E1 --set-opt=--expert-cache=1500
chk; run S6E2 --set-opt=--expert-cache=1750
chk; run S6H3c --set-opt=--expert-cache=2000
