#!/bin/bash
# 19/10: microbanco delle letture hyper-connection sulla 2080 Ti (pesi freddi a rotazione), percorso staged di oggi contro
# STRATA_GR_DOWN75 (righe a blocco 2/4/8) e STRATA_GR_UP75=1/2. Hash delle uscite: deve restare quello di "base".
# Lanciato sotto bench_lock.py (bench.lock O_EXCL).
B=/c/Users/imanu/source/repos/Strata-wt/bf16-turing/build-sm7586/fused_gr_bench.exe
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 STRATA_HC_SPLIT=2
nvidia-smi --query-gpu=index,name,clocks.sm,temperature.gpu --format=csv,noheader
for v in base d75_4 d75_2 d75_8 up1 up2 d75_4up2 base2; do
  unset STRATA_GR_DOWN75 STRATA_GR_UP75
  case $v in d75_4) export STRATA_GR_DOWN75=4;; d75_2) export STRATA_GR_DOWN75=2;; d75_8) export STRATA_GR_DOWN75=8;;
    up1) export STRATA_GR_UP75=1;; up2) export STRATA_GR_UP75=2;; d75_4up2) export STRATA_GR_DOWN75=4 STRATA_GR_UP75=2;; esac
  echo "== $v $(bash $(dirname "$0")/jump_stato.sh)"
  "$B" 300 1 4 24 | grep -E "^T [0-9] apply|COLD.*fast 0|differing"
done
