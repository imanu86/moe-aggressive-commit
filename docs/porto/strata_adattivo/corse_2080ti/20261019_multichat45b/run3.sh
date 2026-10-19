#!/bin/bash
# Terzo giro sotto UN bench.lock: parita' dei logit del primo token (controllo ripetuto, fused, gg0) con l'exe di ecaad907.
H="$(cd "$(dirname "$0")" && pwd)"
K="$(cd "$H/../20261004_routed_keep" && pwd -W)"
EXE="$K\build-multichat45b-ecaad907\strata.exe"
cd "$H"
export PYTHONIOENCODING=utf-8
python -u mc45b_det.py --tag ctl3 --exe "$EXE" > ctl3.run.log 2>&1
python -u mc45b_det.py --tag ctl4 --exe "$EXE" > ctl4.run.log 2>&1
python -u mc45b_det.py --tag fused3 --exe "$EXE" --env "STRATA_PF_FUSED=1 STRATA_PF_FUSED_SM75=1 STRATA_PF_FUSED_NATIVE_SM75=1" > fused3.run.log 2>&1
python -u mc45b_det.py --tag gg03 --exe "$EXE" --env "STRATA_PREFILL_GROUP_GATHER=0" > gg03.run.log 2>&1
echo serie3 finita
