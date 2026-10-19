#!/bin/bash
# Sotto UN bench.lock (lancio: python bench_fast.py MC45B-all -- bash run_all.sh): build, copia, serie di verifica.
H="$(cd "$(dirname "$0")" && pwd)"
WT='C:\Users\imanu\source\repos\Strata-wt\multichat45'
cd "$H"
export PYTHONIOENCODING=utf-8
python -u build_lock_held.py "$WT" > build.log 2>&1 || { echo "build fallita"; tail -40 build.log; exit 1; }
tail -5 build.log
EXE=$(python -u finish_build.py "$WT") || exit 1
echo "exe $EXE"
bash coda_mc45b.sh "$EXE"
