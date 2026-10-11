#!/bin/bash
# Notte 11-12/10, terza coda: dopo il multi-chat, leve a costo zero (env) e port (#1437 sm_75 IL, #1889 SIDE_MIXER),
# poi la taglia della finestra di Fable (STRATA_DW). Base con PLE da NVMe (C:) e SHARED_BRANCH=0 (promossi stanotte).
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
Q="C:/Users/imanu/AppData/Local/Temp/claude/C--Users-imanu-source-repos-MultiPhoneControls/ed7f0b6e-3526-46a2-98fc-c7ce7a44ef30/tasks/bnpx2trsm.output"
until grep -q "fine mc" "$Q" 2>/dev/null; do sleep 60; done
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
P="--add-opt=--pipeline-windows=2 --add-opt=--vram-reserve-later-mib=384 --add-opt=--host-core=last --set-opt=--ple-gguf=C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"
BASE="--env STRATA_VRAM_FREE=device --env STRATA_ROUTE_TAIL_SKIP=0 --env STRATA_ATTN_DAILY=1 --env STRATA_MMVQ_IL=0 --env STRATA_B6_MMVQ_ROWS=1 --env STRATA_MTP_SHARED_BRANCH=0"
bab() {
  local n=$1 b=$2 ob=$3
  for arm in b1 a b2; do
    local o=""; case $arm in b*) o=$ob;; esac
    bash $D/det_force.sh DET-n3-$n-$arm $b --env "$W" $P $BASE $o >/dev/null 2>&1
  done
  echo "== $n ($b) $(date +%H:%M)"
  (cd $K && python $D/bab_verdict.py DET-n3-$n-a DET-n3-$n-b1 DET-n3-$n-b2)
}
bab lookahead0 build-chainfuse-50c04dc0 "--env STRATA_LOOKAHEAD=0"
bab lfuse build-chainfuse-50c04dc0 "--env STRATA_LFUSE=1"
P1=$(ls -d $K/build-ports1-* 2>/dev/null | head -1)
if [ -n "$P1" ]; then
  bab il75 $(basename $P1) "--env STRATA_MMVQ_IL=1"
  bab sidemixer2 $(basename $P1) "--env STRATA_SIDE_MIXER=2"
fi
DW=$(ls -d $K/build-draftwin-* 2>/dev/null | head -1)
if [ -n "$DW" ]; then
  # la leva cambia le righe: senza FORCE_WINDOWS (solo FORCE_IDS, gia' nel det_force)
  W=""
  for arm in b1 a b2; do
    o=""; case $arm in b*) o="--env STRATA_DW=1";; esac
    bash $D/det_force.sh DET-n3-dw-$arm $(basename $DW) $P $BASE $o >/dev/null 2>&1
  done
  echo "== draftwin ($(basename $DW)) $(date +%H:%M)"
  (cd $K && python $D/bab_verdict.py DET-n3-dw-a DET-n3-dw-b1 DET-n3-dw-b2)
fi
echo "== fine coda 3 $(date +%H:%M)"
