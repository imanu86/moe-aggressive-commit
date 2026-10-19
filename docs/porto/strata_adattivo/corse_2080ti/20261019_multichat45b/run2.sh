#!/bin/bash
# Secondo giro sotto UN bench.lock: ricompila (scratch di PF_DIRETTO per scheda) e rifa' i bracci diretto e controllo.
H="$(cd "$(dirname "$0")" && pwd)"
WT='C:\Users\imanu\source\repos\Strata-wt\multichat45'
cd "$H"
export PYTHONIOENCODING=utf-8
python -u build_lock_held.py "$WT" > build2.log 2>&1 || { echo "build fallita"; tail -40 build2.log; exit 1; }
tail -4 build2.log
EXE=$(python -u finish_build.py "$WT" 2>/dev/null | tail -1) || exit 1
echo "exe $EXE"
python -u mc45b_det.py --tag ctl2 --exe "$EXE" > ctl2.run.log 2>&1
python -u mc45b_det.py --tag diretto2 --exe "$EXE" --env "STRATA_PF_DIRETTO=1" > diretto2.run.log 2>&1
echo serie2 finita
