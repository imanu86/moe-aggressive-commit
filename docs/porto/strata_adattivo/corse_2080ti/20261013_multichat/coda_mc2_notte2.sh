#!/bin/bash
# Notte 13/10, seconda coda (dopo coda_mc2_notte.sh): diagnosi del costo fisso di lettura, cache, contesti lunghi,
# kv-resident, quota decode/prefill. Build lab/struct-a 075ce875, config del Daily in sola lettura.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261013_multichat
L=$D/../20261006_due_schede/bench_lock.py
CC="--conversation-cache-mib 20480 --conversation-cache-slots 8"
CC16="--conversation-cache-mib 28672 --conversation-cache-slots 16"
G2="--batch 4 --batch-groups 2"
cd $D
until grep -q "fine coda" $D/coda_mc2_notte.log 2>/dev/null; do sleep 30; done
run() {
  local tag=$1 extra=$2 scen=$3 env=$4
  echo "== mc2 $tag $(date +%H:%M)"
  timeout 5400 python -u $L DET-mc2-$tag -- python -u mc2.py --tag $tag --extra "$extra" --scen "$scen" --env "$env" \
    > $D/mc2_$tag.out 2>&1
  grep -aE "aggregati|engine up|Traceback|Error" $D/mc2_$tag.out | tail -16
}
# 1) da dove viene il ~1 s fisso di ogni lettura (Daily, prefisso in cache, code da 128 a 8k)
run pftime "" "pf:S" "STRATA_PREFILL_TIMING=1 STRATA_SPLIT_TIMING=1"
# 2) cache: 16 conversazioni parcheggiate, gruppi in pipeline; aiuto della scheda ferma nei prompt corti
run b4g2-cc16 "$G2 $CC16" "solo:S,same:4:S,diff:4:S,diff:8:S,cold:4:S,agents:4:P,agents:8:P" ""
run b4g2-cc16-help "$G2 $CC16" "pf:S,agents:4:P,agents:8:P" "STRATA_PREFILL_HELP=1"
# 3) quota del decode accanto a un prompt (default 0.5)
run b4g2-share2 "$G2 $CC16" "cold:4:S,agents:8:P" "STRATA_BATCH_DECODE_SHARE=2.0"
# 4) contesti lunghi 64k: Daily contro gruppi in pipeline
run daily-G "$CC16" "solo:G,same:4:G,diff:2:G,diff:4:G,agents:4:G" ""
run b4g2-G "$G2 $CC16" "solo:G,same:4:G,diff:2:G,diff:4:G,agents:4:G" ""
# 5) kv-resident piu' corto: VRAM agli esperti con gli slot
run b4g2-kv16 "$G2 $CC16 --kv-resident 16384" "solo:S,same:4:S,diff:4:S" ""
echo "== fine coda2 $(date +%H:%M)"
