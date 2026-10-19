#!/bin/bash
# Domande 1 e 4 del 19/10, secondo giro: il primo giro di BATCH_PIPELINE con la riserva del Daily (1393 MiB) lasciava 0 MiB di VRAM
# liberi sulla 3060 (WDDM pagina, lettura da 8K in 980 s): scartato.  Qui 8 agenti prima, poi la chat singola con riserva 1905 MiB.
H="$(cd "$(dirname "$0")" && pwd)"
L="$H/../20261006_due_schede/bench_lock.py"
M="$H/../20261018_multichat45/mc2.py"
K="$(cd "$H/../20261004_routed_keep" && pwd -W)"
MC45="$K/build-multichat45-e42d8af8/strata.exe"
G="--conversation-cache-mib 28672 --conversation-cache-slots 16"
cd "$H"
python -u "$L" "R8-b4" -- python -u replay_trace.py --tag q1-b4-8ag --t0 3600 --span 1200 --dup 2 --extra "--batch 4 --batch-groups 2 $G" --env "STRATA_PIPED_CONCURRENT=1" > q1-b4-8ag.run.log 2>&1
python -u "$L" "R8-b8g2" -- python -u replay_trace.py --tag q1-b8g2-8ag --t0 3600 --span 1200 --dup 2 --extra "--batch 8 --batch-groups 2 $G" --env "STRATA_PIPED_CONCURRENT=1" > q1-b8g2-8ag.run.log 2>&1
python -u "$L" "R8-b8g4" -- python -u replay_trace.py --tag q1-b8g4-8ag --t0 3600 --span 1200 --dup 2 --extra "--batch 8 --batch-groups 4 $G" --env "STRATA_PIPED_CONCURRENT=1" > q1-b8g4-8ag.run.log 2>&1
for i in 1 2; do
  python -u "$L" "SOLO-bp-$i" -- python -u -X utf8 "$M" --tag "q4-bp-$i" --exe "$MC45" --extra "--batch 4 --batch-groups 2 $G --vram-reserve-mib 1905" --env "STRATA_BATCH_PIPELINE=1" --scen "solo:S,solo:S" --port 8103 > "q4-bp-$i.run.log" 2>&1
  [ "$i" = 2 ] && break
  python -u "$L" "SOLO-daily-2" -- python -u -X utf8 "$M" --tag "q4-daily-2" --exe "$MC45" --extra "" --scen "solo:S,solo:S" --port 8103 > "q4-daily-2.run.log" 2>&1
done
