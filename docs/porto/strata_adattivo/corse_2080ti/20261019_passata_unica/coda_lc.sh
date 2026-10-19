#!/bin/bash
# Passata unica, passo 1: B-A-B sullo STESSO exe (build-passata-<sha>), 4 lettori (2-4k nuovi su R0..R3 in cache) + 2 scrittori.
#   B = config batch attuale + STRATA_PIPED_CONCURRENT=1
#   A = B + STRATA_PACK_PREFILL=3 STRATA_PACK_CONCURRENT=1
# Ogni braccio prende bench.lock (bench_lock.py). Uso: bash coda_lc.sh <cartella build>  (es. build-passata-4ee62d09)
H="$(cd "$(dirname "$0")" && pwd)"
L="$H/../20261006_due_schede/bench_lock.py"
K="$(cd "$H/../20261004_routed_keep" && pwd -W)"
EXE="$K/${1:?build dir}/strata.exe"
G="--batch 4 --batch-groups 2 --conversation-cache-mib 20480 --conversation-cache-slots 16 --vram-reserve-mib 1905 --vram-reserve-later-mib 700"
cd "$H"
arm() { # tag env
  python -u "$L" "LC-$1" -- python -u -X utf8 letture_concorrenti.py --tag "$1" --exe "$EXE" --extra "$G" --env "$2" > "lc_$1.run.log" 2>&1
}
arm b1 "STRATA_PIPED_CONCURRENT=1"
arm a1 "STRATA_PIPED_CONCURRENT=1 STRATA_PACK_PREFILL=3 STRATA_PACK_CONCURRENT=1"
arm b2 "STRATA_PIPED_CONCURRENT=1"
