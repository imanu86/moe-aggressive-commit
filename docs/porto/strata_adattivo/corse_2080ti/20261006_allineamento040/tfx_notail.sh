#!/bin/bash
# Merge vs pure upstream 0.1.40 without --prompt-cache-tail: is the fork's divergence on `code` the tail checkpoint?
export PATH=/usr/bin:/mingw64/bin:$PATH
H=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261005_handoff/script
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
bash "$H/tf_fixed.sh" "TFX-m040nt|--build build-m040 --drop-opt=--prompt-cache-tail" "TFX-up0140nt|--build build-up0140 --drop-opt=--prompt-cache-tail"
cd "$D" || exit 1
for t in code explain; do
  for pair in "TFX-m040nt TFX-up0140nt" "TFX-m040nt TFX-m040" "TFX-up0140nt TFX-up0140" "TFX-up0140nt TFX-up0139"; do
    set -- $pair
    cmp -s "$1-$t/logpos.tsv" "$2-$t/logpos.tsv" && r=identico || r=DIVERSO
    echo "$t: $1 $r $2"
  done
done | tee -a tf_fixed_m040.txt
