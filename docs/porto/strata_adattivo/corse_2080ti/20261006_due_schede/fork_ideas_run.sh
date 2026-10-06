#!/bin/bash
# Monitor on the 3060: the 3060 first (CUDA_VISIBLE_DEVICES=1,0, layers 0-15, the display), the 2080 Ti last (layers
# 16-47, head, MTP; 2 GiB reserve: 1 GiB was not enough for its prompt path).  Ideas from the forks (research 6/10).
export PATH=/usr/bin:/mingw64/bin:$PATH
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
I="--build build-x7586e --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --add-opt=--vram-reserve-later-mib=2048"
bash "$L/long_ab_run.sh" \
  "F-inv|$I" \
  "F-spin|$I --env STRATA_POOL_SPIN_US=100" \
  "F-async|$I --env STRATA_POOL_SPIN_US=100 --add-opt=--adapt-async=1" \
  "F-pw2|$I --env STRATA_POOL_SPIN_US=100 --add-opt=--pipeline-windows=2 --env STRATA_PIPELINE_THETA=0.35"
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
for n in F-inv F-spin F-async F-pw2; do echo "== $n"; grep -aE "too little|expert cache [0-9]+ slots|CUDA1 runs|elastic: on|strata pipeline:" "$K/$n/engine.log" | cut -c1-200 | head -5; grep -a "strata decode timing" "$K/$n/engine.log" | head -1 | cut -c1-230; done
