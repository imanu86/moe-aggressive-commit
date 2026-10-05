#!/bin/bash
# 0.1.39-r2 shipping exe: fixed-placement identity with --pool-tasks 96, then one 131k L01/L02 in the r2 configuration
H=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261005_handoff/script
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
bash "$H/tf_fixed.sh" "TFX-r2ship|--build build-r2ship --set-opt=--pool-tasks=96"
cd "$D" || exit 1
for t in code explain; do
  cmp -s TFX-r2ship-$t/logpos.tsv TFX-enc-$t/logpos.tsv && echo "$t: TFX-r2ship identico bit per bit a TFX-enc" || echo "$t: TFX-r2ship DIVERSO da TFX-enc"
done | tee tf_fixed_r2ship.txt
timeout 3000 python -u run_long.py --name L-r2ship --build build-r2ship --env STRATA_ARENA_PIN_GIB=64 --env STRATA_ELASTIC_CORE_ADAPT=1 --set-opt=--pcie-mode=dma --set-opt=--pool-tasks=96 > L-r2ship.runlog 2>&1
echo "L-r2ship rc=$?"
grep -a "serve: prompt [0-9]" L-r2ship/engine.log | cut -c1-200
