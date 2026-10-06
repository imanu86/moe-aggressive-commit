#!/bin/bash
# Upstream's "exact" switches (on by default on gfx1151 only): STRATA_QFUSE, STRATA_MMVF_ROWS, STRATA_TSUM.
# 1) fixed-placement teacher forcing on the 2080 Ti (single card) against TFX-m040: must be byte-identical;
# 2) 131k on the inverted two-card layout with STRATA_POOL_SPIN_US=100, against H-spin2 / G-spin.
# Waits for the queued pipeline sweep.
export PATH=/usr/bin:/mingw64/bin:$PATH
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
while [ ! -f $K/P-th50/result.json ] || tasklist //FI "IMAGENAME eq strata.exe" | grep -q strata; do sleep 30; done
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
E="--env STRATA_QFUSE=1 --env STRATA_MMVF_ROWS=1 --env STRATA_TSUM=1"
bash "$L/tfx_pr_run.sh" exact build-dbg $E
I="--build build-dbg --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
bash "$L/long_ab_run.sh" "X-exact|$I $E" "X-exact2|$I $E"
