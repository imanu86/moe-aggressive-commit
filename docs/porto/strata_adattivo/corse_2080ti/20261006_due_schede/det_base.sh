#!/bin/bash
# Base of all further A/B (6/10 notte): fork main a0ebf74, pipeline 2 + elastic (default with two cards), forced ids
# + forced windows. 3 runs. Usage: bash det_base.sh TAG   (arms DET-base-TAG1..3)
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
for r in 1 2 3; do bash $D/det_force.sh DET-base-$1$r build-main-a0ebf74 --env "$W" --add-opt=--pipeline-windows=2; done
