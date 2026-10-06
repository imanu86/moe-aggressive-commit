#!/bin/bash
# Monitor on the 3060: the 3060 as CUDA0 (CUDA_VISIBLE_DEVICES=1,0) = stage 0 with the elastic cache and the display,
# the 2080 Ti a later stage with the head, the MTP drafter and a small reserve (no display on it).  131k L01/L02.
export PATH=/usr/bin:/mingw64/bin:$PATH
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
I="--build build-x7586e --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--trim-stage-weights --add-opt=--vram-reserve-later-mib=1024"
bash "$L/long_ab_run.sh" "M-inv16r|$I --add-opt=--layer-split=16" "M-inv12r|$I --add-opt=--layer-split=12"
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
for n in M-inv16r M-inv12r; do echo "== $n"; grep -aE "layer split: CUDA[01] runs|expert cache [0-9]+ slots|elastic: on|elastic cache|VRAM free with everything" "$K/$n/engine.log" | cut -c1-200 | head -6; grep -a "strata decode timing" "$K/$n/engine.log" | head -1 | cut -c1-260; done
