#!/bin/bash
# Draft length on the new base (main be4cf1c: pipeline + elastic + B6 rows, a row is ~1 ms cheaper than before).
# Hypothesis: longer windows now pay: --spec 5 --spec-min-p 0.4 vs Daily --spec 4 --spec-min-p 0.5.
# FORCE_IDS only (same text); the windows are free on purpose: they ARE the lever. Drafter jitter ~0.5% of windows.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
for r in 1 2 3; do
  bash $D/det_force.sh DET-sp4-$r build-main-be4cf1c --add-opt=--pipeline-windows=2
  bash $D/det_force.sh DET-sp5-$r build-main-be4cf1c --add-opt=--pipeline-windows=2 --set-opt=--spec=5 --set-opt=--spec-min-p=0.4
done
cd $K && python $D/det_verdict.py DET-sp4-1,DET-sp4-2,DET-sp4-3 DET-sp5-1,DET-sp5-2,DET-sp5-3
for n in DET-sp4-1 DET-sp5-1; do grep -a "strata work" $n/engine.log | cut -c1-150; done
