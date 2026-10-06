#!/bin/bash
# Pure upstream 0.1.40 under the same fixed-placement teacher forcing: the merge must match it byte for byte
# (any difference against TFX-enc then comes from upstream's own 0.1.39 -> 0.1.40 changes, not from the merge).
export PATH=/usr/bin:/mingw64/bin:$PATH
H=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261005_handoff/script
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
bash "$H/tf_fixed.sh" "TFX-up0140|--build build-up0140"
cd "$D" || exit 1
for t in code explain; do
  for ref in TFX-up0140 TFX-enc; do
    a=TFX-m040-$t/logpos.tsv; b=$ref-$t/logpos.tsv
    if [ ! -f "$b" ]; then echo "$t: $ref senza logpos" | tee -a tf_fixed_m040.txt; continue; fi
    if cmp -s "$a" "$b"; then echo "$t: TFX-m040 identico bit per bit a $ref"; else echo "$t: TFX-m040 DIVERSO da $ref"; fi | tee -a tf_fixed_m040.txt
  done
  cmp -s TFX-up0140-$t/logpos.tsv TFX-enc-$t/logpos.tsv && echo "$t: upstream 0.1.40 = TFX-enc" || echo "$t: upstream 0.1.40 diverso da TFX-enc"
done | tee -a tf_fixed_m040.txt
