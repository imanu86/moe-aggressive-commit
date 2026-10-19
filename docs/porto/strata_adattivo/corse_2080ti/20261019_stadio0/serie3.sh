#!/bin/bash
# Serie 3: regime con la 3060 in salute (~1 GiB liberi): scansione degli slot dello stadio 0, traccia di instradamento, visione, variante senza --batch (pipeline).
export PATH=/usr/bin:/mingw64/bin:$PATH
H="$(cd "$(dirname "$0")" && pwd)"
BL="$H/st0_lock.py"
cd "$H"
until grep -q "S2B3a rc" serie2.log; do sleep 5; done
run() { n=$1; shift; echo "=== $n $(date +%H:%M:%S)"; python -u "$BL" "DET-ST0-$n" -- python -u -B st0_run.py --name "DET-ST0-$n" --gpu-engine --short-n 5 --decodes 3 "$@" > "runlog_$n.txt" 2>&1; echo "$n rc=$? $(date +%H:%M:%S)"; }
chk() { [ -f "$H/STOP_SERIE3" ] && { echo "STOP3"; exit 0; }; }
chk; run S3H1  --extra-mib 2048
chk; run S3H2  --set-opt=--expert-cache=1000
chk; run S3H3  --set-opt=--expert-cache=2000
chk; run S3H1b --extra-mib 2048
chk; run S3H4  --set-opt=--expert-cache=600
chk; run S3R1  --extra-mib 2048 --routing --short-n 0
chk; echo "=== S3V1 $(date +%H:%M:%S)"; python -u "$BL" DET-ST0-S3V1 -- python -u -B st0_vision.py DET-ST0-S3V1 > runlog_S3V1.txt 2>&1; echo "S3V1 rc=$? $(date +%H:%M:%S)"
chk; run S3P2a --drop-opt=--batch --drop-opt=--batch-groups --env STRATA_PIPELINE_DEBUG=1
chk; run S3H1c --extra-mib 2048
