#!/bin/bash
# Second CPU series after det_cpu.sh: base nopark+fused vs nopark+fused+HOT=3:2000, 3 interleaved pairs.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
until grep -q "VERDETTO\|build failed" $D/det_cpu.log 2>/dev/null; do sleep 30; done
grep -q "build failed" $D/det_cpu.log && exit 1
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
NF="--env STRATA_POOL_NOPARK=1 --env STRATA_POOL_FUSED=1"
for r in 1 2 3; do
  bash $D/det_force.sh DET-cpuh-nf$r build-cpu-1 --env "$W" --add-opt=--pipeline-windows=2 $NF
  bash $D/det_force.sh DET-cpuh-hot$r build-cpu-1 --env "$W" --add-opt=--pipeline-windows=2 $NF --env STRATA_POOL_HOT=3:2000
done
cd $K && python $D/det_verdict.py DET-cpuh-nf1,DET-cpuh-nf2,DET-cpuh-nf3 DET-cpuh-hot1,DET-cpuh-hot2,DET-cpuh-hot3
grep -a "CPU pool lab" DET-cpuh-hot1/engine.log | head -2
