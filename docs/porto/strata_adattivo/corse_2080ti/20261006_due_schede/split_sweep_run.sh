#!/bin/bash
# Two cards (2080 Ti CUDA0 + 3060 CUDA1 on Oculink): 131k L01/L02 on the Daily config.  Split runs first (the 2080 Ti
# runs layers [0, K), the 3060 [K, 48) with the MTP drafter and the head; fixed caches: the elastic one is single-GPU),
# then the single-card baseline (elastic) after the reboot.
export PATH=/usr/bin:/mingw64/bin:$PATH
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
SPLIT="--add-opt=--trim-stage-weights"
bash "$L/long_ab_run.sh" \
  "S32|--build build-x7586 --add-opt=--layer-split=32 $SPLIT" \
  "S28|--build build-x7586 --add-opt=--layer-split=28 $SPLIT" \
  "S36|--build build-x7586 --add-opt=--layer-split=36 $SPLIT" \
  "S0-base|--build build-x7586"
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
for n in S32 S28 S36 S0-base; do
  echo "== $n"
  grep -aE "layer split|stage [0-9]|expert cache [0-9]+ slots|elastic: on|elastic cache|per-stage|stage GPU" "$D/$n/engine.log" | cut -c1-220 | head -12
done
