#!/bin/bash
# Draft length: --spec-min-p (Daily 0.5) lower = longer drafts, more rows per window. Waits for round X (PID in arg 1).
export PATH=/usr/bin:/mingw64/bin:$PATH
while tasklist //FI "PID eq $1" | grep -qi bash || tasklist //FI "IMAGENAME eq strata.exe" | grep -qi strata; do sleep 20; done
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
I="--build build-stage --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
bash "$L/long_ab_run.sh" \
  "M-mp30|$I --set-opt=--spec-min-p=0.3" \
  "M-mp20s5|$I --set-opt=--spec-min-p=0.2 --set-opt=--spec=5" \
  "M-ref|$I" \
  "M-mp30b|$I --set-opt=--spec-min-p=0.3" \
  "M-mp20s5b|$I --set-opt=--spec-min-p=0.2 --set-opt=--spec=5"
