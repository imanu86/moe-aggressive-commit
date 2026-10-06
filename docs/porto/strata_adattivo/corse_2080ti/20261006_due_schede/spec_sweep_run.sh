#!/bin/bash
# Draft length now that the experts are mostly in VRAM (verify cheaper).  Inverted layout (3060 first with the
# display and the elastic cache, 2080 Ti last), STRATA_POOL_SPIN_US=100 as the new base.  Waits for the running sweep.
export PATH=/usr/bin:/mingw64/bin:$PATH
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
while [ ! -f $K/G-pw2/result.json ] || tasklist //FI "IMAGENAME eq strata.exe" | grep -q strata; do sleep 30; done
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
I="--build build-dbg --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
bash "$L/long_ab_run.sh" \
  "H-spin2|$I" \
  "H-s3|$I --set-opt=--spec=3" \
  "H-s5|$I --set-opt=--spec=5" \
  "H-s6|$I --set-opt=--spec=6" \
  "H-s8|$I --set-opt=--spec=8" \
  "H-mp65|$I --set-opt=--spec-min-p=0.65"
