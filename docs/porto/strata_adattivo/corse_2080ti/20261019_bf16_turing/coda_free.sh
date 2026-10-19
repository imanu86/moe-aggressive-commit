#!/bin/bash
# 19/10: qualità del testo libero (niente FORCE_IDS) a 131k: off contro BF16_TC=1 e HC16_SM75=1, stessa config di coda_bf16.sh.
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
D=$K/../20261006_due_schede
J=$(dirname "$0")/jump_stato.sh
export STRATA_TURNO_LOCK=CODA-bf16-free
P="--add-opt=--pipeline-windows=2 --add-opt=--vram-reserve-later-mib=384 --add-opt=--host-core=last --set-opt=--ple-gguf=D:\ds4_work\strata\Strata-data\gguf\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"
A="--env STRATA_VRAM_FREE=device --env STRATA_ROUTE_TAIL_SKIP=0 --env STRATA_ATTN_DAILY=1 --env STRATA_B6_MMVQ_ROWS=1 --env STRATA_MTP_SHARED_BRANCH=0 --env STRATA_SIDE_MIXER=2 --env STRATA_RAM_CORE=1 --env STRATA_RAM_CORE_SLOTS_DEV1=5500 --env STRATA_EXPDEC=1 --env STRATA_QSA_ROWS=1 --env STRATA_SA_BET=1 --env STRATA_SA_CHAIN=1 --env STRATA_P2_FLUSH_NOSWITCH=1 --env STRATA_MMVQ_IL=0"
I="--build $1 --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
cd $K
for arm in off tc hc16; do
  case $arm in off) e="";; tc) e="--env STRATA_BF16_TC=1";; hc16) e="--env STRATA_HC16_SM75=1";; esac
  echo "DET-x25-free-$arm $(date +%H:%M) $(bash $J)"
  timeout 3000 python -u run_long_turno.py --name DET-x25-free-$arm $I $P $A $e > DET-x25-free-$arm.runlog 2>&1
  grep -aE "strata serve: prompt|strata work" DET-x25-free-$arm/engine.log | cut -c1-220
done
python $D/monitor_giri.py DET-x25-free-off DET-x25-free-tc DET-x25-free-hc16 2>&1 | tail -4
