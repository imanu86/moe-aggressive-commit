#!/bin/bash
# Monitor moved to the 3060 (the 2080 Ti has no display).  131k L01/L02, Daily config.
#  M-same: the old layout (2080 Ti stage 0 with layers 0-31, fixed caches) - the move alone, against C-ref 57.1/51.1
#  M-inv16: 3060 as CUDA0 (CUDA_VISIBLE_DEVICES=1,0) = stage 0 with layers 0-15 and the elastic cache (the display card),
#           2080 Ti stage 1 with layers 16-47, the head and the MTP drafter, fixed cache
#  M-inv12: the same with 12 layers on the 3060
export PATH=/usr/bin:/mingw64/bin:$PATH
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
T="--add-opt=--trim-stage-weights"
bash "$L/long_ab_run.sh" \
  "M-same|--build build-x7586 --add-opt=--layer-split=32 $T" \
  "M-inv16|--build build-x7586e --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 $T" \
  "M-inv12|--build build-x7586e --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=12 $T"
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
for n in M-same M-inv16 M-inv12; do echo "== $n"; grep -aE "layer split: CUDA[01] runs|expert cache [0-9]+ slots|elastic: on|elastic cache" "$K/$n/engine.log" | cut -c1-200 | head -5; grep -a "strata decode timing" "$K/$n/engine.log" | head -1 | cut -c1-260; done
