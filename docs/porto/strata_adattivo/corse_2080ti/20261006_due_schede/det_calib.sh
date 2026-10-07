#!/bin/bash
# Calibration: the same binary 3 times. Is the text identical? How much do ms/window and t/s move?
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
for i in 1 2 3; do bash $D/det_bench.sh DET-cal$i build-pfx; done
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
for c in L01 L02; do for i in 2 3; do cmp -s $K/DET-cal1/$c.txt $K/DET-cal$i/$c.txt && echo "$c cal1=cal$i IDENTICO" || echo "$c cal1~cal$i DIVERSO"; done; done
