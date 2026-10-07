#!/bin/bash
# Deterministic series 2 (6/10 notte, AFTER reboot with HAGS OFF; P2 untouched; OktoCGControl open, Jump not connected).
# Same build (build-p3-10), same forced ids + forced windows as the HAGS-on calibration DET-p3r-def1..3.
#   HAGS effect: the serial-default arms here (h0-def*, h0-off*) against DET-p3r-def1..3 (HAGS on).
#   Q1: B6 kernel on/off, 3 interleaved pairs.  Q2: pipeline+elastic vs default, 3 interleaved pairs.
# Decision rule (written before the data): same sign in all 3 pairs on L01 and L02, mean gain on L01+L02 decode
# time > 2.7%.
export PATH=/usr/bin:/mingw64/bin:$PATH
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
B6="--env STRATA_B6_MMVQ_ROWS=1"
PW="--add-opt=--pipeline-windows=2 --env STRATA_PIPELINE_ELASTIC=1"
for r in 1 2 3; do
  bash $D/det_force.sh DET-h0-off$r build-p3-10 --env "$W"
  bash $D/det_force.sh DET-h0-b6on$r build-p3-10 --env "$W" $B6
done
for r in 1 2 3; do
  bash $D/det_force.sh DET-h0-pw$r build-p3-10 --env "$W" $PW
  bash $D/det_force.sh DET-h0-def$r build-p3-10 --env "$W"
done
