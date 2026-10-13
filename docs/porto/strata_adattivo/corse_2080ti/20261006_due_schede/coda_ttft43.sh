#!/bin/bash
# 13/10 notte: banco TTFT di lab/ttft43 (ttft_bench.py), una corsa per braccio, ognuna sotto bench.lock (bench_lock.py).
#   bash coda_ttft43.sh <build dir in 20261004_routed_keep> [bracci]     bracci di default: fA fB0 fBL A B C
# fA/fB0/fBL: cache fissa (--expert-cache 1500, senza --elastic, --adapt-every 0) per il testo: Daily, ttft43 coi default
# (scrittura su thread + PLE in anticipo), ttft43 con tutte le leve.  A/B/C: config del Daily per i tempi: Daily, ttft43
# con le leve (un file per prefisso, conversazioni su disco, tokenizzazione #1852), C = B + STRATA_PREFILL_HELP=1.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
PY=/d/ds4_work/strata/Strata/.venv/Scripts/python.exe
DA=/d/ds4_work/strata/Strata/build-0143-daily
B=$K/$1
ARMS=${2:-"fA fB0 fBL A B C"}
FIX=(--set-opt=--expert-cache=1500 --drop-opt=--elastic "--args=--adapt-every 0")
LEV="STRATA_PREFIX_DISK_MULTI=24 STRATA_CONV_DISK=10"
run() {
  local tag=$1; shift
  echo "== $tag $(date +%H:%M)"
  python $D/bench_lock.py DET-ttft-$tag -- $PY -B $D/ttft_bench.py --tag $tag "$@" > $D/ttft_$tag.runlog 2>&1
  echo "$tag rc=$? $(date +%H:%M)"
  tail -14 $D/ttft_$tag.runlog
}
for arm in $ARMS; do
  case $arm in
    fA)  run fA --exe $DA/strata.exe --serve $DA/source/serve "${FIX[@]}" ;;
    fB0) run fB0 --exe $B/strata.exe --serve $B/source/serve "${FIX[@]}" --compare fA ;;
    fBL) run fBL --exe $B/strata.exe --serve $B/source/serve "${FIX[@]}" --env "$LEV" --server-env STRATA_PROMPT_ENCODER=1 --compare fA ;;
    A)   run A --exe $DA/strata.exe --serve $DA/source/serve ;;
    B)   run B --exe $B/strata.exe --serve $B/source/serve --env "$LEV" --server-env STRATA_PROMPT_ENCODER=1 --compare A ;;
    C)   run C --exe $B/strata.exe --serve $B/source/serve --env "$LEV STRATA_PREFILL_HELP=1" --server-env STRATA_PROMPT_ENCODER=1 --compare B ;;
  esac
done
echo "== fine ttft43 $(date +%H:%M)"
