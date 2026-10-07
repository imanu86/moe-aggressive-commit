#!/bin/bash
# Fable plan step 2 + quick levers, inverted two-card layout, STRATA_POOL_SPIN_US=100, per-stage host timing.
export PATH=/usr/bin:/mingw64/bin:$PATH
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
I="--build build-stage --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
bash "$L/long_ab_run.sh" \
  "R-base|$I" \
  "R-devplan|$I --env STRATA_VERIFY_DEVICE_PLAN=1" \
  "R-res1024|$I --add-opt=--vram-reserve-later-mib=1024" \
  "R-miss08|$I --env STRATA_ROUTED_MISS_W=0.08 --env STRATA_ROUTED_KEEP_SKIP=1" \
  "R-base2|$I"
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
for n in R-base R-devplan R-res1024 R-miss08 R-base2; do echo "== $n"; grep -aE "decode stage|expert cache [0-9]+ slots|CUDA1 runs|hit rate" "$K/$n/engine.log" | cut -c1-200 | head -8; done
