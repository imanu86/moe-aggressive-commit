#!/bin/bash
# Upstream PRs on top of the 0.1.40 merge: fixed-placement teacher forcing against TFX-m040 (the merge alone).
#   bash tfx_pr.sh NAME BUILD [extra run_keep args...]
export PATH=/usr/bin:/mingw64/bin:$PATH
H=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261005_handoff/script
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
n=$1; b=$2; shift 2
bash "$H/tf_fixed.sh" "TFX-$n|--build $b $*"
cd "$D" || exit 1
for t in code explain; do
  if cmp -s "TFX-$n-$t/logpos.tsv" "TFX-m040-$t/logpos.tsv"; then r="identico bit per bit a TFX-m040"; else r="DIVERSO da TFX-m040"; fi
  echo "$t: TFX-$n $r" | tee -a tf_fixed_m040.txt
  python analyze_tf.py TFX-$n-$t TFX-m040-$t 2>&1 | tail -1 | tee -a tf_fixed_m040.txt
done
