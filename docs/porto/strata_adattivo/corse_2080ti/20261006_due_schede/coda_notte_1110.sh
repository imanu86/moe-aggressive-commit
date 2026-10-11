#!/bin/bash
# Notte 11-12/10, OktoCGControl acceso, profilo Afterburner 1. Un B-A-B per leva sulla build lab/chainfuse 50c04dc0
# (= upsync + critpath2 spente + fusioni opt-in). Base comune: NVML, IL spento, B6, attenzione del Daily, tail skip spento.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
B=build-chainfuse-50c04dc0
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
P="--add-opt=--pipeline-windows=2 --add-opt=--vram-reserve-later-mib=384 --add-opt=--host-core=last"
BASE="--env STRATA_VRAM_FREE=device --env STRATA_ROUTE_TAIL_SKIP=0 --env STRATA_ATTN_DAILY=1"
KER="--env STRATA_MMVQ_IL=0 --env STRATA_B6_MMVQ_ROWS=1"
schtasks //Run //TN "AB profilo 1" >/dev/null 2>&1

# bab NOME "opzioni A" "opzioni B"
bab() {
  local n=$1 oa=$2 ob=$3
  for arm in b1 a b2; do
    local o=$oa; case $arm in b*) o=$ob;; esac
    bash $D/det_force.sh DET-n-$n-$arm $B --env "$W" $P $BASE $o >/dev/null 2>&1
  done
  echo "== $n $(date +%H:%M)"
  (cd $K && python $D/bab_verdict.py DET-n-$n-a DET-n-$n-b1 DET-n-$n-b2)
}

bab fuse2 "$KER" "$KER --env STRATA_CHAIN_FUSE2=1"
bab sharedbr "$KER" "$KER --env STRATA_MTP_SHARED_BRANCH=0"
bab il "$KER" "--env STRATA_MMVQ_IL=1 --env STRATA_B6_MMVQ_ROWS=0"
bab plecache "$KER" "$KER --set-opt=--ple-row-cache=67108864"
bab plec "$KER" "$KER --set-opt=--ple-gguf=C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"
bab resident "$KER" "$KER --env STRATA_ROUTE_RESIDENT=1"
echo "== fine coda $(date +%H:%M)"
