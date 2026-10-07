#!/bin/bash
# Fable B1: split commit async (STRATA_SPLIT_COMMIT_ASYNC=1) vs off, B/A/B/A, inverted layout. Waits for round R.
export PATH=/usr/bin:/mingw64/bin:$PATH
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
while [ ! -f $K/R-base2/result.json ] || tasklist //FI "IMAGENAME eq strata.exe" | grep -q strata; do sleep 30; done
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
I="--build build-cas --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
bash "$L/long_ab_run.sh" "S-cas1|$I --env STRATA_SPLIT_COMMIT_ASYNC=1" "S-ref1|$I" "S-cas2|$I --env STRATA_SPLIT_COMMIT_ASYNC=1" "S-ref2|$I"
