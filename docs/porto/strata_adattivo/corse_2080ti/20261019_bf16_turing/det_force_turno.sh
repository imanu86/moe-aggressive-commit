#!/bin/bash
# Forced-text check (P3, 6/10 sera): the same config twice with STRATA_FORCE_IDS = the L01/L02 ids of S-ref1, Daily
# elastic config (user-turn layout, no disk prefix), one binary for def and pw.
#   bash det_force.sh NAME BUILD [extra run_long args...]     NAME must start with DET-
export PATH=/usr/bin:/mingw64/bin:$PATH
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
F='C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids'
KW='C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep'
cd "$K" || exit 1
n=$1; b=$2; shift 2
case "$n" in DET-*) ;; *) echo "name must start with DET-"; exit 2;; esac
I="--build $b --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
timeout 3000 python -u run_long_turno.py --name "$n" $I --env "STRATA_FORCE_IDS=$F\force_L01.txt;$F\force_L02.txt" \
  --env "STRATA_FORCE_TRACE=$KW\\$n\force_trace.txt" "$@" > "$n.runlog" 2>&1
echo "$n rc=$?"
grep -a "strata force\|strata work\|serve: prompt [0-9]\|decode timing" "$n/engine.log" | cut -c1-260
