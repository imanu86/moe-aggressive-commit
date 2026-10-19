#!/bin/bash
# Aggregato in decode con 2, 3 e 4 conversazioni insieme (prompt corti, 384 token, 2 ripetizioni): (c1) lab/batch-dyn nel modo
# agenti (gruppi in pipeline senza bozze), (c2) la config del coordinatore: --batch 2 --batch-mtp + STRATA_PIPED_MTP=1 (#2985,
# uno slot per gruppo, build multichat45 e42d8af8), senza passaggio a caldo.  Ogni corsa prende il turno da se'.
H="$(cd "$(dirname "$0")" && pwd)"
B="$1"
K="$H/../20261004_routed_keep"
cd "$H"
python -u run_dyn.py c-dyn 'D:\ds4_work\strata\Strata\strata-0145-daily.json' "$B/strata.exe" \
  --env STRATA_BATCH_DYNAMIC=1 --env STRATA_BATCH_IDLE_S=30 --args "--vram-reserve-mib 1393" --conc 2,3,4 --switch 1 > c-dyn.run.log 2>&1
python -u run_dyn.py c-pmtp 'D:\ds4_work\strata\Strata\strata-0145-daily.json' "$K/build-multichat45-e42d8af8/strata.exe" \
  --env STRATA_PIPED_MTP=1 --args "--batch 2 --batch-groups 2 --batch-mtp" --conc 2,3,4 > c-pmtp.run.log 2>&1
# (b) di nuovo, con la RAM pinned restituita all'uscita (c4af6851)
G2="--batch 4 --batch-groups 2 --conversation-cache-mib 28672 --conversation-cache-slots 16"
python -u run_replay_dyn.py b-dyn2 -- --tag dyn2-g2cc --exe "$B/strata.exe" --t0 3600 --span 1200 --extra "$G2" \
  --env "STRATA_PIPED_CONCURRENT=1 STRATA_BATCH_DYNAMIC=1 STRATA_BATCH_IDLE_S=30" > b-dyn2.run.log 2>&1
