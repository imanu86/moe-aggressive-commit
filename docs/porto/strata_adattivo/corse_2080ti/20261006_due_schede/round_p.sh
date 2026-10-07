#!/bin/bash
# Pruning A/B again (P-miss1/P-base1/P-miss2 failed: overlapping chains). Waits until no chain and no engine run.
export PATH=/usr/bin:/mingw64/bin:$PATH
while tasklist //FI "IMAGENAME eq strata.exe" | grep -qi strata || tasklist //FI "PID eq 12360" | grep -qi bash; do sleep 20; done
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
I="--build build-stage --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
M="--env STRATA_ROUTED_MISS_W=0.08 --env STRATA_ROUTED_KEEP_SKIP=1"
bash "$L/long_ab_run.sh" "P-miss3|$I $M" "P-base3|$I" "P-miss4|$I $M"
