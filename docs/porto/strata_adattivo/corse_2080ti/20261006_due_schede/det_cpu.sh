#!/bin/bash
# CPU-expert pool variants (lab/cpu-experts cf2daf0 = main be4cf1c + pool nopark/fused/hot), coordinator 7/10 notte.
# 3 interleaved pairs: off vs STRATA_POOL_NOPARK=1 STRATA_POOL_FUSED=1. Forced ids + windows, pipeline 2.
export PATH=/usr/bin:/mingw64/bin:$PATH
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
python $D/build_lock.py C:/Users/imanu/source/repos/Strata-wt/cpu > $D/build_cpu_1.log 2>&1 || { echo "build failed"; tail -30 $D/build_cpu_1.log; exit 1; }
mkdir -p $K/build-cpu-1 && cp /c/Users/imanu/source/repos/Strata-wt/cpu/build-sm7586/strata.exe $K/build-cpu-1/
H=$(sha256sum $K/build-cpu-1/strata.exe | cut -d' ' -f1)
printf '{\n "status": "completed",\n "executable_sha256": "%s",\n "note": "lab/cpu-experts cf2daf0: main be4cf1c + pool nopark/fused/hot opt-in"\n}\n' $H > $K/build-cpu-1/build.json
echo "build ok $(date +%H:%M)"
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
for r in 1 2 3; do
  bash $D/det_force.sh DET-cpu-off$r build-cpu-1 --env "$W" --add-opt=--pipeline-windows=2
  bash $D/det_force.sh DET-cpu-on$r build-cpu-1 --env "$W" --add-opt=--pipeline-windows=2 --env STRATA_POOL_NOPARK=1 --env STRATA_POOL_FUSED=1
done
cd $K && python $D/det_verdict.py DET-cpu-off1,DET-cpu-off2,DET-cpu-off3 DET-cpu-on1,DET-cpu-on2,DET-cpu-on3
for n in DET-cpu-off1 DET-cpu-on1; do grep -a "decode timing" $n/engine.log | sed -E 's/.*(CPU [0-9.]+)\].*/\1/' | tr '\n' ' '; echo " $n"; done
