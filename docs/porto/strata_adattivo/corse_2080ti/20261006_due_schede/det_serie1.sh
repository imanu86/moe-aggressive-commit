#!/bin/bash
# Deterministic series 1 (coordinator, 6/10 notte). Forced ids + forced windows (ref trace DET-p3f-def1).
#   Q1: B6 kernel STRATA_B6_MMVQ_ROWS=1 vs off, serial default, 3 interleaved pairs.
#   Q2: pipeline 2 + STRATA_PIPELINE_ELASTIC=1 vs serial default, 3 interleaved pairs.
# Decision rule written BEFORE the data: pass if all 3 paired differences have the same sign on L01 AND L02
# and the mean paired gain on the summed decode time (L01+L02) is > 2.7% (2x the standard error of a 3-pair mean
# from the calibration DET-p3r-def1..3: SD 0.62 s on 37.75 s).
export PATH=/usr/bin:/mingw64/bin:$PATH
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
python $D/build_lock.py C:/Users/imanu/source/repos/Strata-wt/p3 > $D/build_p3_10.log 2>&1 || { echo "build failed"; tail -20 $D/build_p3_10.log; exit 1; }
mkdir -p $K/build-p3-10 && cp /c/Users/imanu/source/repos/Strata-wt/p3/build-sm7586/strata.exe $K/build-p3-10/
H=$(sha256sum $K/build-p3-10/strata.exe | cut -d' ' -f1)
printf '{\n "status": "completed",\n "executable_sha256": "%s",\n "note": "lab/p3-pipeline 542dd41: P3 + forcing + B6 mmvq rows (cherry-pick 065566a)"\n}\n' $H > $K/build-p3-10/build.json
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
B6="--env STRATA_B6_MMVQ_ROWS=1"
PW="--add-opt=--pipeline-windows=2 --env STRATA_PIPELINE_ELASTIC=1"
for r in 1 2 3; do
  bash $D/det_force.sh DET-q1-off$r build-p3-10 --env "$W"
  bash $D/det_force.sh DET-q1-on$r build-p3-10 --env "$W" $B6
done
for r in 1 2 3; do
  bash $D/det_force.sh DET-q2-pw$r build-p3-10 --env "$W" $PW
  bash $D/det_force.sh DET-q2-def$r build-p3-10 --env "$W"
done
