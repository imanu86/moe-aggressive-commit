#!/bin/bash
# Coda di lab/batch-dyn (19/10): (a) banco comunita' + test di passaggio, (b) replay dei 3 agenti.  Ogni corsa prende e
# rilascia bench.lock da se'.  Uso: bash coda_dyn.sh <dir della build>
H="$(cd "$(dirname "$0")" && pwd)"
B="$1"
cd "$H"
G2="--batch 4 --batch-groups 2 --conversation-cache-mib 28672 --conversation-cache-slots 16"
python -u run_dyn.py a-dyn 'D:\ds4_work\strata\Strata\strata-0145-daily.json' "$B/strata.exe" \
  --env STRATA_BATCH_DYNAMIC=1 --env STRATA_BATCH_IDLE_S=30 --args "--vram-reserve-mib 1393" --community --switch 2 > a-dyn.run.log 2>&1
python -u run_replay_dyn.py b-dyn -- --tag dyn-g2cc --exe "$B/strata.exe" --t0 3600 --span 1200 --extra "$G2" \
  --env "STRATA_PIPED_CONCURRENT=1 STRATA_BATCH_DYNAMIC=1 STRATA_BATCH_IDLE_S=30" > b-dyn.run.log 2>&1
