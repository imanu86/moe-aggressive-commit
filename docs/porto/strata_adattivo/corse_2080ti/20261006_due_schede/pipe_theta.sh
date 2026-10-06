#!/bin/bash
# Pipeline (--pipeline-windows 2) on the inverted layout with STRATA_POOL_SPIN_US=100: a repeat, and the speculation
# gate theta (only read with STRATA_PIPELINE_DEBUG=1).  Waits for the draft-length sweep.
export PATH=/usr/bin:/mingw64/bin:$PATH
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
while [ ! -f $K/H-mp65/result.json ] || tasklist //FI "IMAGENAME eq strata.exe" | grep -q strata; do sleep 30; done
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
P="--build build-dbg --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100 --add-opt=--pipeline-windows=2"
bash "$L/long_ab_run.sh" \
  "P-pw2b|$P" \
  "P-th35|$P --env STRATA_PIPELINE_DEBUG=1 --env STRATA_PIPELINE_THETA=0.35" \
  "P-th50|$P --env STRATA_PIPELINE_DEBUG=1 --env STRATA_PIPELINE_THETA=0.50"
for n in P-pw2b P-th35 P-th50; do grep -a "strata pipeline:" $K/$n/engine.log | head -1 | cut -c1-200; done
