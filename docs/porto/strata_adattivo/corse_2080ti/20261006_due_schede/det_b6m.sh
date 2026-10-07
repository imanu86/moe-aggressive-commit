#!/bin/bash
# B6 MMVQ rows on the new base (main a0ebf74, pipeline + elastic), 3 interleaved pairs, forced ids + windows.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
for r in 1 2 3; do
  bash $D/det_force.sh DET-b6m-off$r build-main-a0ebf74 --env "$W" --add-opt=--pipeline-windows=2
  bash $D/det_force.sh DET-b6m-on$r build-main-a0ebf74 --env "$W" --add-opt=--pipeline-windows=2 --env STRATA_B6_MMVQ_ROWS=1
done
cd $K && python $D/det_verdict.py DET-b6m-off1,DET-b6m-off2,DET-b6m-off3 DET-b6m-on1,DET-b6m-on2,DET-b6m-on3
