#!/bin/bash
# 13/10 notte: B-A-B delle tre leve strutturali (opus struct-a/b/c), ognuna sulla sua build, solo FORCE_IDS
# (le leve cambiano la composizione delle finestre: niente FORCE_WINDOWS), riscaldamento prima di ogni B-A-B.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
P="--add-opt=--pipeline-windows=2 --add-opt=--vram-reserve-later-mib=384 --add-opt=--host-core=last --set-opt=--ple-gguf=D:\ds4_work\strata\Strata-data\gguf\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"
BASE="--env STRATA_VRAM_FREE=device --env STRATA_ROUTE_TAIL_SKIP=0 --env STRATA_ATTN_DAILY=1 --env STRATA_MMVQ_IL=0 --env STRATA_B6_MMVQ_ROWS=1 --env STRATA_MTP_SHARED_BRANCH=0 --env STRATA_SIDE_MIXER=2 --env STRATA_RAM_CORE=1 --env STRATA_RAM_CORE_SLOTS_DEV1=5500 --env STRATA_EXPDEC=1 --env STRATA_QSA_ROWS=1 --env STRATA_NODECUT=1 --env STRATA_QFUSE_HC=0 --env STRATA_TOPK_GRID=1 --env STRATA_B6_HEAD_MINB=6"
bab() {
  local tag=$1 b=$2 lev=$3
  echo "== $tag ($b) $(date +%H:%M)"
  bash $D/det_force.sh DET-x21-$tag-warm $b $P $BASE >/dev/null 2>&1
  for arm in b1 a b2; do
    local o=""; case $arm in b*) o="$lev";; esac
    bash $D/det_force.sh DET-x21-$tag-$arm $b $P $BASE $o >/dev/null 2>&1
    echo "braccio $arm $(date +%H:%M)"
  done
  (cd $K && python $D/bab_verdict.py DET-x21-$tag-a DET-x21-$tag-b1 DET-x21-$tag-b2)
  grep -aEh "pipeline classes|struct-a:|PLE primary" $K/DET-x21-$tag-{a,b1,b2}/engine.log 2>/dev/null | cut -c1-200
}
bab sb build-structb-08165b90 "--env STRATA_SB_FRESH=2"
bab sa build-structa-075ce875 "--env STRATA_SA_BET=1 --env STRATA_SA_CHAIN=1"
bab sc build-structc-4f3cdee8 "--env STRATA_SC_SNAP_INLINE=1"
echo "== fine struct notte $(date +%H:%M)"
