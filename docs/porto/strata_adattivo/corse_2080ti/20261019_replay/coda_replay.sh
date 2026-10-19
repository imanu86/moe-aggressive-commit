#!/bin/bash
# Ripetizioni della finestra 3600-4800 s: config 2 poi config 1 (ognuna prende bench.lock via bench_lock.py)
H="$(cd "$(dirname "$0")" && pwd)"
L="$H/../20261006_due_schede/bench_lock.py"
cd "$H"
G2="--batch 4 --batch-groups 2 --conversation-cache-mib 28672 --conversation-cache-slots 16"
python -u "$L" REPLAY-c2b -- python -u replay_trace.py --tag c2b-g2cc --t0 3600 --span 1200 --extra "$G2" --env "STRATA_PIPED_CONCURRENT=1" > c2b-g2cc.run.log 2>&1
python -u "$L" REPLAY-c1b -- python -u replay_trace.py --tag c1b-daily --t0 3600 --span 1200 > c1b-daily.run.log 2>&1
