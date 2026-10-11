#!/bin/bash
# Notte 11-12/10: dopo la coda dei B-A-B, multi-chat sulla base v0.1.42 (upsync 133e3a69): batch-groups auto di upstream,
# cache adattiva nelle finestre batch, batch-mtp sullo split; OktoCGControl acceso.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
Q="C:/Users/imanu/AppData/Local/Temp/claude/C--Users-imanu-source-repos-MultiPhoneControls/ed7f0b6e-3526-46a2-98fc-c7ce7a44ef30/tasks/bmk29cbhf.output"
until grep -q "fine coda" "$Q" 2>/dev/null; do sleep 60; done
EXE="$(cygpath -w $K/build-upsync-133e3a69/strata.exe)"
SERVE='C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-upsync-133e3a69\source\serve'
ENV="STRATA_VRAM_FREE=device STRATA_ROUTE_TAIL_SKIP=0 STRATA_MMVQ_IL=0 STRATA_B6_MMVQ_ROWS=1 STRATA_ATTN_DAILY=1 STRATA_DECODE_TIMING=1"
COMMON="--conversation-cache-mib 16384 --conversation-cache-slots 4 --host-core last --vram-reserve-later-mib 384"
cd $D
run() {
  local tag=$1 extra=$2 env=$3
  echo "== mc $tag $(date +%H:%M)"
  timeout 3600 python -u bench_lock.py DET-mc-$tag -- python -u multi_chat_mc.py --tag $tag --exe "$EXE" --serve "$SERVE" \
    --extra "$extra $COMMON" --env "$ENV $env" --scen serial,same2,same3,diff2 2>&1 | grep -E "aggregati|err\": \"[^n]|Traceback" | tail -8
  grep -ah "batch groups\|batch-groups\|strata batch:\|strata batch MTP\|batch pipeline" $D/mc_$tag/engine.log 2>/dev/null | tail -4 | cut -c1-260
}
run g42-auto "--batch 3" ""
run g42-auto-mtp "--batch 3 --batch-mtp" ""
run g42-g1-mtp "--batch 3 --batch-mtp --batch-groups 1" ""
echo "== fine mc $(date +%H:%M)"
