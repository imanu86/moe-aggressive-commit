#!/bin/bash
# Serie di verifica di lab/multichat45b sotto UN solo bench.lock (lancio:  bench_lock.py DET-mc45b -- bash coda_mc45b.sh <exe>)
H="$(cd "$(dirname "$0")" && pwd)"
EXE="$1"
cd "$H"
export PYTHONIOENCODING=utf-8
G2="--batch 4 --batch-groups 2 --conversation-cache-mib 28672 --conversation-cache-slots 16"
# 1) chat singola con --batch 4 --batch-groups 2, senza e con STRATA_PW_WITH_BATCH=1 (C P C P, ognuno due corse solo:S)
python -u mc2.py --tag pw-ctrl1 --exe "$EXE" --extra "$G2" --scen solo:S,solo:S > pw-ctrl1.run.log 2>&1
python -u mc2.py --tag pw-on1 --exe "$EXE" --extra "$G2" --env "STRATA_PW_WITH_BATCH=1" --scen solo:S,solo:S > pw-on1.run.log 2>&1
python -u mc2.py --tag pw-ctrl2 --exe "$EXE" --extra "$G2" --scen solo:S,solo:S > pw-ctrl2.run.log 2>&1
python -u mc2.py --tag pw-on2 --exe "$EXE" --extra "$G2" --env "STRATA_PW_WITH_BATCH=1" --scen solo:S,solo:S > pw-on2.run.log 2>&1
# 2) parita' e TTFT a cache fissa (--expert-cache 1500, senza --elastic, --adapt-every 0)
python -u mc45b_det.py --tag ctl0 --exe "$EXE" > ctl0.run.log 2>&1
python -u mc45b_det.py --tag fused --exe "$EXE" --env "STRATA_PF_FUSED=1 STRATA_PF_FUSED_SM75=1 STRATA_PF_FUSED_NATIVE_SM75=1" > fused.run.log 2>&1
python -u mc45b_det.py --tag diretto --exe "$EXE" --env "STRATA_PF_DIRETTO=1" > diretto.run.log 2>&1
python -u mc45b_det.py --tag gg0 --exe "$EXE" --env "STRATA_PREFILL_GROUP_GATHER=0" > gg0.run.log 2>&1
python -u mc45b_det.py --tag ctl1 --exe "$EXE" > ctl1.run.log 2>&1
echo serie finita
