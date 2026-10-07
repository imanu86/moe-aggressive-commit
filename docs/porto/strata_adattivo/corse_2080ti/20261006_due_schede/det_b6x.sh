#!/bin/bash
# B6 pipeline items on main be4cf1c (+ lab/b6-draft bc30da7: ${B6BUILD:-build-b6-6}), forced ids + forced windows.
#   bash det_b6x.sh TAG PAIRS "ENV ARGS FOR ON"     arms DET-b6x-TAGoff<r> / DET-b6x-TAGon<r>, r = PAIRS
# then: python det_verdict.py (when 3 pairs)
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
tag=$1; pairs=$2; on=$3
for r in $pairs; do
  bash $D/det_force.sh DET-b6x-${tag}off$r ${B6BUILD:-build-b6-6} --env "$W" --add-opt=--pipeline-windows=2
  bash $D/det_force.sh DET-b6x-${tag}on$r ${B6BUILD:-build-b6-6} --env "$W" --add-opt=--pipeline-windows=2 $on
done
