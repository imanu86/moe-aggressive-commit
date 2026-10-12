#!/bin/bash
# 12/10: B-A-B dei kernel esperti di Fable (lab/expertdec ff8614a6), braccio B = STRATA_EXPDEC=1.
# Base = config di Strata 0.1.42 Daily (candidate 5dea5258 + SHARED_BRANCH=0 + SIDE_MIXER=2 + nucleo RAM).
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
P="--add-opt=--pipeline-windows=2 --add-opt=--vram-reserve-later-mib=384 --add-opt=--host-core=last --set-opt=--ple-gguf=C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"
BASE="--env STRATA_VRAM_FREE=device --env STRATA_ROUTE_TAIL_SKIP=0 --env STRATA_ATTN_DAILY=1 --env STRATA_MMVQ_IL=0 --env STRATA_B6_MMVQ_ROWS=1 --env STRATA_MTP_SHARED_BRANCH=0 --env STRATA_SIDE_MIXER=2 --env STRATA_RAM_CORE=1 --env STRATA_RAM_CORE_SLOTS_DEV1=5500"
B=build-expertdec-52a74f6a
for arm in b1 a b2; do
  o=""; case $arm in b*) o="--env STRATA_EXPDEC=1";; esac
  bash $D/det_force.sh DET-x3-expdec-$arm $B --env "$W" $P $BASE $o >/dev/null 2>&1
  echo "braccio $arm $(date +%H:%M)"
done
echo "== expdec ($B) $(date +%H:%M)"
(cd $K && python $D/bab_verdict.py DET-x3-expdec-a DET-x3-expdec-b1 DET-x3-expdec-b2)
grep -ah "strata decode timing" $K/DET-x3-expdec-*/*.log 2>/dev/null | tail -6 | cut -c1-240
echo "== fine expdec $(date +%H:%M)"
