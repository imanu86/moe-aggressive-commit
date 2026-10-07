#!/bin/bash
# 3 runs of the serial default with STRATA_FORCE_IDS + STRATA_FORCE_WINDOWS (reference: DET-p3f-def1's trace)
D=C:/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
for r in 1 2 3; do bash $D/det_force.sh DET-p3r-def$r build-p3-9 --env "STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"; done
