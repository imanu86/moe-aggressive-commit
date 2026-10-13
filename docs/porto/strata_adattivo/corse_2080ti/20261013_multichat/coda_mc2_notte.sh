#!/bin/bash
# Notte 13/10: prove di configurazione multi-chat sulla build di lab/struct-a 075ce875 (= exe della 0.1.43 Daily),
# config del Daily in sola lettura (mc2.py la copia), ogni braccio sotto il proprio bench.lock.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261013_multichat
L=$D/../20261006_due_schede/bench_lock.py
CC="--conversation-cache-mib 20480 --conversation-cache-slots 8"
SC_S="solo:S,pf:S,same:2:S,same:4:S,same:8:S,diff:2:S,diff:4:S,diff:8:S,cold:4:S,agents:4:P,agents:8:P"
cd $D
run() {
  local tag=$1 extra=$2 scen=$3 env=$4
  echo "== mc2 $tag $(date +%H:%M)"
  timeout 5400 python -u $L DET-mc2-$tag -- python -u mc2.py --tag $tag --extra "$extra" --scen "$scen" --env "$env" \
    > $D/mc2_$tag.out 2>&1
  grep -aE "aggregati|engine up|Traceback|Error" $D/mc2_$tag.out | tail -16
}
run daily "" "$SC_S" ""
run b4mtp "--batch 4 --batch-mtp --batch-groups 1 $CC" "$SC_S" ""
run b4g2 "--batch 4 --batch-groups 2 $CC" "$SC_S" ""
run b8mtp "--batch 8 --batch-mtp --batch-groups 1 --max-context 147456 $CC" "$SC_S" ""
run b8g2 "--batch 8 --batch-groups 2 --max-context 147456 $CC" "$SC_S" ""
run b4mtp-prof "--batch 4 --batch-mtp --batch-groups 1 $CC" "solo:S,same:4:S" "STRATA_VERIFY_PROFILE=1"
echo "== fine coda $(date +%H:%M)"
