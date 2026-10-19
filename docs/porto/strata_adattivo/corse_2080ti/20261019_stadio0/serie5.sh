#!/bin/bash
# Serie 5: --expert-cache esplicito (cache piu' grande della 3060 in salute: ~2 GB liberi), punti alti degli slot, traccia di instradamento, visione, variante senza --batch.
export PATH=/usr/bin:/mingw64/bin:$PATH
H="$(cd "$(dirname "$0")" && pwd)"
BL="$H/st0_lock.py"
cd "$H"
run() { n=$1; shift; echo "=== $n $(date +%H:%M:%S)"; python -u "$BL" "DET-ST0-$n" -- python -u -B st0_run.py --name "DET-ST0-$n" --gpu-engine --short-n 5 --decodes 3 "$@" > "runlog_$n.txt" 2>&1; echo "$n rc=$? $(date +%H:%M:%S)"; }
chk() { [ -f "$H/STOP_SERIE5" ] && { echo "STOP5"; exit 0; }; }
chk; run S5X1  --set-opt=--expert-cache=2500
chk; run S5X2  --set-opt=--expert-cache=2900
chk; run S5H3b --set-opt=--expert-cache=2000
chk; run S5R1  --set-opt=--expert-cache=2000 --routing --short-n 0
chk; echo "=== S5V1 $(date +%H:%M:%S)"; python -u "$BL" DET-ST0-S5V1 -- python -u -B st0_vision.py DET-ST0-S5V1 > runlog_S5V1.txt 2>&1; echo "S5V1 rc=$? $(date +%H:%M:%S)"
chk; run S5P2a --drop-opt=--batch --drop-opt=--batch-groups --env STRATA_PIPELINE_DEBUG=1
chk; run S5P2b --drop-opt=--batch --drop-opt=--batch-groups --env STRATA_PIPELINE_DEBUG=1 --extra-mib 1024
