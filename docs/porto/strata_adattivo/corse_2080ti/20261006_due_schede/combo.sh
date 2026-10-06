#!/bin/bash
# Two cards, split 32: what the GPUs taking turns costs.  131k L01/L02, fixed caches (build-x7586).
export PATH=/usr/bin:/mingw64/bin:$PATH
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
S="--build build-x7586 --add-opt=--layer-split=32 --add-opt=--trim-stage-weights"
bash "$L/long_ab_run.sh" \
  "C-pw2|$S --add-opt=--pipeline-windows=2" \
  "C-pw1|$S --add-opt=--pipeline-windows=1" \
  "C-prof|$S --env STRATA_VERIFY_PROFILE=1" \
  "C-spec6|$S --set-opt=--spec=6" \
  "C-ref|$S"
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
for n in C-pw2 C-pw1 C-prof C-spec6 C-ref; do echo "== $n"; grep -aE "pipelin|GPU stages|stage [0-9] \(ms|speculat|rolled" "$K/$n/engine.log" | cut -c1-260 | head -6; done
