#!/bin/bash
# The faster hyper-connection read (STRATA_HC_DOWN_W4=1 STRATA_HC_UP_FAST=1, bit-identical by gr_parity / gr_multi_parity):
# identity on the 2080 Ti (teacher forcing vs TFX-m040), then 131k on the inverted layout B/A/B/A.  Waits for the queue.
export PATH=/usr/bin:/mingw64/bin:$PATH
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
while [ ! -f $K/X-exact2/result.json ] || tasklist //FI "IMAGENAME eq strata.exe" | grep -q strata; do sleep 30; done
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
E="--env STRATA_HC_DOWN_W4=1 --env STRATA_HC_UP_FAST=1"
bash "$L/tfx_pr_run.sh" hcfast build-hc $E
I="--build build-hc --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
bash "$L/long_ab_run.sh" "Y-hc1|$I $E" "Y-ref1|$I" "Y-hc2|$I $E" "Y-ref2|$I"
