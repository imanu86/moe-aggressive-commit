#!/bin/bash
# Layer split with the pipeline on (6/10 notte): the stages now overlap, so the slower stage sets the pace.
# Measured per layer: 3060 ~0.6 ms, 2080 Ti ~0.45 ms -> K=16 gives 9.6 vs 14.4 ms; K=19 ~11.4 vs 13.0.
# Hypothesis: K=19 cuts >= 1 ms per window. Base main be4cf1c (pipeline + elastic + B6), forced ids + windows.
# det_force.sh adds --layer-split=16; the arm's own --add-opt=--layer-split=19 comes later on the command line.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
for r in 1 2 3; do
  bash $D/det_force.sh DET-k16-$r build-main-be4cf1c --env "$W" --add-opt=--pipeline-windows=2
  bash $D/det_force.sh DET-k19-$r build-main-be4cf1c --env "$W" --add-opt=--pipeline-windows=2 --add-opt=--layer-split=19
done
cd $K && python $D/det_verdict.py DET-k16-1,DET-k16-2,DET-k16-3 DET-k19-1,DET-k19-2,DET-k19-3
grep -a "CUDA1 runs\|expert cache [0-9]* slots" DET-k19-1/engine.log | cut -c1-160
