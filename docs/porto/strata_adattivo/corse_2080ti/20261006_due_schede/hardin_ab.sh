#!/bin/bash
# Hardin22 / upstream patches (opt-in): identity with everything off, then 131k on the inverted layout one switch at a time.
export PATH=/usr/bin:/mingw64/bin:$PATH
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
while [ ! -f $K/Y-ref2/result.json ] || tasklist //FI "IMAGENAME eq strata.exe" | grep -q strata; do sleep 30; done
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
bash "$L/tfx_pr_run.sh" hardin_off build-hardin
I="--build build-hardin --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
bash "$L/long_ab_run.sh" \
  "Z-ca|$I --env STRATA_COMMIT_ASYNC=1" \
  "Z-xs|$I --env STRATA_XSTAGE=1" \
  "Z-plef|$I --env STRATA_PLE_FIRST=1" \
  "Z-chain|$I --env STRATA_MTP_CHAIN=1" \
  "Z-all|$I --env STRATA_COMMIT_ASYNC=1 --env STRATA_XSTAGE=1 --env STRATA_PLE_FIRST=1 --env STRATA_MTP_CHAIN=1" \
  "Z-simt|$I --env STRATA_SELECT_SIMT=1" \
  "Z-ref|$I"
