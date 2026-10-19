#!/bin/bash
# 19/10: leve BF16 su Turing (branch lab/bf16-turing), banco DET a 131k.
#  parte 1 (decode, bitwise): B-A-B con finestre forzate, A = env del Daily, B = A + STRATA_GR_DOWN75 + STRATA_GR_UP75=2.
#  parte 2 (prompt + accettazione, solo FORCE_IDS): off / BF16_TC / BF16_TC+TC_DRAFT=0 / HC16 / off2.
#  Regola: scartare un braccio con stage di L01 > 0,6 ms o PLE bloccato in decode > ~300 ms.
#  Uso: bash coda_bf16.sh <build> <env decode B, es. "--env STRATA_GR_DOWN75=4 --env STRATA_GR_UP75=2"> [solo1|solo2]
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
P="--add-opt=--pipeline-windows=2 --add-opt=--vram-reserve-later-mib=384 --add-opt=--host-core=last --set-opt=--ple-gguf=D:\ds4_work\strata\Strata-data\gguf\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"
A="--env STRATA_VRAM_FREE=device --env STRATA_ROUTE_TAIL_SKIP=0 --env STRATA_ATTN_DAILY=1 --env STRATA_B6_MMVQ_ROWS=1 --env STRATA_MTP_SHARED_BRANCH=0 --env STRATA_SIDE_MIXER=2 --env STRATA_RAM_CORE=1 --env STRATA_RAM_CORE_SLOTS_DEV1=5500 --env STRATA_EXPDEC=1 --env STRATA_QSA_ROWS=1 --env STRATA_SA_BET=1 --env STRATA_SA_CHAIN=1 --env STRATA_P2_FLUSH_NOSWITCH=1 --env STRATA_MMVQ_IL=0"
B=$1; BENV=$2; ONLY=$3
J=$(dirname "$0")/jump_stato.sh
run() { echo "$1 $(date +%H:%M) $(bash $J)"; bash $D/det_force.sh "$@" >/dev/null 2>&1; echo "$1 fine $(bash $J)"; }
show() { grep -aEh "decode timing|PLE primary|prompt [0-9]+ tokens|strata work|strata hc:" $K/$1/engine.log 2>/dev/null | cut -c1-240; }
if [ "$ONLY" != solo2 ]; then
  echo "== decode $(date +%H:%M)"
  run DET-x25-dec-warm $B --env "$W" $P $A
  for arm in b1 a b2; do
    case $arm in a) run DET-x25-dec-$arm $B --env "$W" $P $A;; *) run DET-x25-dec-$arm $B --env "$W" $P $A $BENV;; esac
    echo "braccio $arm $(date +%H:%M)"; show DET-x25-dec-$arm
  done
  (cd $K && python $D/bab_verdict.py DET-x25-dec-a DET-x25-dec-b1 DET-x25-dec-b2)
fi
if [ "$ONLY" != solo1 ]; then
  echo "== prompt e accettazione $(date +%H:%M)"
  run DET-x25-pf-warm $B $P $A
  for arm in off tc tcd hc16 off2; do
    case $arm in off|off2) e="";; tc) e="--env STRATA_BF16_TC=1";; tcd) e="--env STRATA_BF16_TC=1 --env STRATA_BF16_TC_DRAFT=0";; hc16) e="--env STRATA_HC16_SM75=1";; esac
    run DET-x25-pf-$arm $B $P $A $e
    echo "== $arm $(date +%H:%M)"; show DET-x25-pf-$arm
  done
fi
echo "== fine $(date +%H:%M)"
