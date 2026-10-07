#!/bin/bash
# B6 hc read (STRATA_B6_HC) on main be4cf1c (pipeline + elastic + MMVQ rows default), 3 interleaved pairs, forced
# ids + forced windows; the same exe (build-b6-5) in both arms, only the switch differs.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
for r in 1 2 3; do
  bash $D/det_force.sh DET-b6h-off$r build-b6-5 --env "$W" --add-opt=--pipeline-windows=2
  bash $D/det_force.sh DET-b6h-on$r build-b6-5 --env "$W" --add-opt=--pipeline-windows=2 --env STRATA_B6_HC=1
done
cd $K && python $D/det_verdict.py DET-b6h-off1,DET-b6h-off2,DET-b6h-off3 DET-b6h-on1,DET-b6h-on2,DET-b6h-on3
