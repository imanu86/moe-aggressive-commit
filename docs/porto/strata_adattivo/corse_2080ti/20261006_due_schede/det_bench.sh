#!/bin/bash
# Deterministic bench (6/10 sera): fixed expert placement so greedy decode repeats the same text run to run
# (same windows, same accepted drafts, same experts). Prefix as system + disk prefix file (restore ~3 s).
#   bash det_bench.sh NAME BUILD [extra run_long args...]     NAME must start with DET-
export PATH=/usr/bin:/mingw64/bin:$PATH
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$K" || exit 1
n=$1; b=$2; shift 2
FIX="--drop-opt=--elastic --set-opt=--expert-cache=3500 --set-opt=--adapt-every=0 --set-opt=--pcie-frac=0.36"
P="--prefix-as-system --add-opt=--prompt-cache-file=D:/ds4_work/strata/lab_prefix/det_${b}.bin"
I="--build $b --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
timeout 1800 python -u run_long.py --name "$n" $I $FIX $P "$@" > "$n.runlog" 2>&1
echo "$n rc=$?"
grep -a "prefix disk cache: \(saved\|restored\)\|serve: prompt [0-9]\|decode timing\|decode stage" "$n/engine.log" | cut -c1-230
