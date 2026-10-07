#!/bin/bash
# CPU-expert async pool (lab/cpu-experts 5b7f463 = cf2daf0 + STRATA_POOL_ASYNC), agente CPU 7/10 notte.
# 1) micro-bench pool_layer_bench under the bench lock (CPU only, real blobs); 2) 3 interleaved pairs off vs
# STRATA_POOL_ASYNC=1, forced ids + windows, pipeline 2; 3) verdict.  The build is done before (build_cpu_2.log).
export PATH=/usr/bin:/mingw64/bin:$PATH
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
B=/c/Users/imanu/source/repos/Strata-wt/cpu/build-sm7586
mkdir -p $K/build-cpu-2 && cp $B/strata.exe $K/build-cpu-2/
H=$(sha256sum $K/build-cpu-2/strata.exe | cut -d' ' -f1)
printf '{\n "status": "completed",\n "executable_sha256": "%s",\n "note": "lab/cpu-experts 5b7f463: main be4cf1c + pool nopark/fused/hot + STRATA_POOL_ASYNC opt-in"\n}\n' $H > $K/build-cpu-2/build.json
echo "staged build-cpu-2 $H $(date +%H:%M)"
if [ "$1" != "--no-micro" ]; then
  STRATA_POOL_SPIN_US=100 python $D/bench_lock.py cpu-micro -- "$B/pool_layer_bench.exe" \
    'D:\ds4_work\strata\Strata-data\packs\iq3_xxs' 'C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf' \
    300 3 400 base,nf,async,asyncnh,asynchot3,allhot > $D/cpu_micro_async.txt 2>&1
  echo "micro rc=$? $(date +%H:%M)"
  cat $D/cpu_micro_async.txt
fi
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
for r in 1 2 3; do
  bash $D/det_force.sh DET-cpua-off$r build-cpu-2 --env "$W" --add-opt=--pipeline-windows=2
  bash $D/det_force.sh DET-cpua-on$r build-cpu-2 --env "$W" --add-opt=--pipeline-windows=2 --env STRATA_POOL_ASYNC=1
done
cd $K && python $D/det_verdict.py DET-cpua-off1,DET-cpua-off2,DET-cpua-off3 DET-cpua-on1,DET-cpua-on2,DET-cpua-on3
for n in DET-cpua-off1 DET-cpua-off2 DET-cpua-off3 DET-cpua-on1 DET-cpua-on2 DET-cpua-on3; do
  echo "== $n"; grep -a "decode timing\|decode stage\|decode async\|STRATA_POOL_ASYNC\|^ERR\|ERR " $n/engine.log | cut -c1-330
done
