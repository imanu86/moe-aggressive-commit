#!/bin/bash
# Notte 13/10, terza coda: la chat singola, Daily contro gruppi in pipeline (6 richieste ciascuno, contesti 8k in cache).
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261013_multichat
L=$D/../20261006_due_schede/bench_lock.py
cd $D
until grep -q "fine coda2" $D/coda_mc2_notte2.log 2>/dev/null; do sleep 30; done
run() {
  local tag=$1 extra=$2 scen=$3 env=$4
  echo "== mc2 $tag $(date +%H:%M)"
  timeout 3600 python -u $L DET-mc2-$tag -- python -u mc2.py --tag $tag --extra "$extra" --scen "$scen" --env "$env" \
    > $D/mc2_$tag.out 2>&1
  grep -aE "aggregati|engine up|Traceback|Error" $D/mc2_$tag.out | tail -16
}
run single-daily "" "solo:S,solo:S,solo:S,solo:S" ""
run single-b4g2 "--batch 4 --batch-groups 2 --conversation-cache-mib 28672 --conversation-cache-slots 16" "solo:S,solo:S,solo:S,solo:S" ""
run single-daily-b "" "solo:S,solo:S,solo:S,solo:S" ""
echo "== fine coda3 $(date +%H:%M)"
