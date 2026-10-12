#!/bin/bash
# 12/10 pomeriggio (owner: un'ora di PC libero, OktoCGControl acceso in background).
# 1) B-A-B speed4 (build-speed4-311b6fda): B = NODECUT senza QFUSE_HC + top-k QSA a 8 CTA + testa MINB 6.
# 2) B-A-B testa MTP: A = rt_it48k, B = rt_it48k_ft1 (pod, 1 epoca off-policy); solo FORCE_IDS (le finestre cambiano
#    con la bozza), poi un braccio C = ft1 con --spec-min-p 0.4.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
B=build-speed4-311b6fda
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
P="--add-opt=--pipeline-windows=2 --add-opt=--vram-reserve-later-mib=384 --add-opt=--host-core=last --set-opt=--ple-gguf=C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"
BASE="--env STRATA_VRAM_FREE=device --env STRATA_ROUTE_TAIL_SKIP=0 --env STRATA_ATTN_DAILY=1 --env STRATA_MMVQ_IL=0 --env STRATA_B6_MMVQ_ROWS=1 --env STRATA_MTP_SHARED_BRANCH=0 --env STRATA_SIDE_MIXER=2 --env STRATA_RAM_CORE=1 --env STRATA_RAM_CORE_SLOTS_DEV1=5500 --env STRATA_EXPDEC=1 --env STRATA_QSA_ROWS=1"
LEV="--env STRATA_NODECUT=1 --env STRATA_QFUSE_HC=0 --env STRATA_TOPK_GRID=1 --env STRATA_B6_HEAD_MINB=6"
MTP0="--set-opt=--mtp=D:\ds4_work\strata\Strata-data\mtp\rt_it48k"
MTP1="--set-opt=--mtp=D:\ds4_work\strata\Strata-data\mtp\rt_it48k_ft1"

echo "== 1) speed4 $(date +%H:%M)"
bash $D/det_force.sh DET-x14-s4-warm $B --env "$W" $P $BASE >/dev/null 2>&1; echo "riscaldamento $(date +%H:%M)"
for arm in b1 a b2; do
  o=""; case $arm in b*) o="$LEV";; esac
  bash $D/det_force.sh DET-x14-s4-$arm $B --env "$W" $P $BASE $o >/dev/null 2>&1
  echo "braccio $arm $(date +%H:%M)"
done
(cd $K && python $D/bab_verdict.py DET-x14-s4-a DET-x14-s4-b1 DET-x14-s4-b2)
grep -aEh "strata decode timing|strata nodecut|topk" $K/DET-x14-s4-*/engine.log 2>/dev/null | tail -8 | cut -c1-220

echo "== 2) testa MTP $(date +%H:%M)"
for arm in b1 a b2; do
  m="$MTP1"; case $arm in a) m="$MTP0";; esac
  bash $D/det_force.sh DET-x14-mtp-$arm $B $P $BASE $m >/dev/null 2>&1
  echo "braccio $arm $(date +%H:%M)"
done
bash $D/det_force.sh DET-x14-mtp-c04 $B $P $BASE $MTP1 --set-opt=--spec-min-p=0.4 >/dev/null 2>&1; echo "braccio c (0.4) $(date +%H:%M)"
(cd $K && python $D/bab_verdict.py DET-x14-mtp-a DET-x14-mtp-b1 DET-x14-mtp-b2; python $D/bab_verdict.py DET-x14-mtp-a DET-x14-mtp-c04 DET-x14-mtp-c04)
grep -aEh "strata decode timing|accepted|draft" $K/DET-x14-mtp-*/engine.log 2>/dev/null | grep -a "decode timing\|acceptance\|accepted" | tail -10 | cut -c1-220
echo "== fine coda pomeriggio $(date +%H:%M)"
