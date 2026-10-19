#!/bin/bash
# Terzo giro (da lanciare solo dopo "pausa tolta").  Perche': la prima corsa a 8 agenti con --batch 4 e riserva 1393 MiB e' finita con
# 0 MiB di VRAM liberi sulla 3060 (WDDM pagina), il motore si e' fermato per 240 s e il server l'ha riavviato a meta': scartata.
# Qui le config con batch hanno una riserva piu' larga (3060 / 2080 Ti); la chat singola ha la stessa.
H="$(cd "$(dirname "$0")" && pwd)"
L="$H/../20261006_due_schede/bench_lock.py"
M="$H/../20261018_multichat45/mc2.py"
K="$(cd "$H/../20261004_routed_keep" && pwd -W)"
MC45="$K/build-multichat45-e42d8af8/strata.exe"
G="--conversation-cache-mib 20480 --conversation-cache-slots 16"
R4="--vram-reserve-mib 1905 --vram-reserve-later-mib 700"
R8="--vram-reserve-mib 3400 --vram-reserve-later-mib 1100"
cd "$H"
run8() { # tag extra
  python -u "$L" "R8-$1" -- python -u replay_trace.py --tag "q1-$1-8ag" --t0 3600 --span 1200 --dup 2 --extra "$2" --env "STRATA_PIPED_CONCURRENT=1" > "q1-$1-8ag.run.log" 2>&1
}
run8 b4 "--batch 4 --batch-groups 2 $G $R4"
run8 b8g2 "--batch 8 --batch-groups 2 $G $R8"
run8 b8g4 "--batch 8 --batch-groups 4 $G $R8"
solo() { # tag extra env
  python -u "$L" "SOLO-$1" -- python -u -X utf8 "$M" --tag "q4-$1" --exe "$MC45" --extra "$2" --env "$3" --scen "solo:S,solo:S" --port 8103 > "q4-$1.run.log" 2>&1
}
solo bp-1 "--batch 4 --batch-groups 2 $G $R4" "STRATA_BATCH_PIPELINE=1"
solo daily-2 "" ""
solo bp-2 "--batch 4 --batch-groups 2 $G $R4" "STRATA_BATCH_PIPELINE=1"
# Q5: nucleo RAM piu' grande sulla 2080 Ti (5500 del Daily -> 6900), chat singola
solo core6900-1 "" "STRATA_RAM_CORE_SLOTS_DEV1=6900"
solo core6900-2 "" "STRATA_RAM_CORE_SLOTS_DEV1=6900"
