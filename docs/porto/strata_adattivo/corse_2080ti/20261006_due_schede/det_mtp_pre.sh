#!/bin/bash
# MTP chain front (lab/mtp-chain): pre-screen of build-mtp-1, forced windows.
#   p1: profile only (STRATA_MTPC_PROF=2: chain GPU times, step segments, fresh-path host stamps, PLE gather)
#   p2: profile + host switches (F1 EARLY FLUSH POLL CATCHUP PLE LAZY)
#   p3: p2 + LOPRIO (forced chains on the lowest-priority stream)
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
ON="--env STRATA_MTPC_F1=1 --env STRATA_MTPC_EARLY=1 --env STRATA_MTPC_FLUSH=1 --env STRATA_MTPC_POLL=1 --env STRATA_MTPC_CATCHUP=1 --env STRATA_MTPC_PLE=1 --env STRATA_MTPC_LAZY=1"
bash $D/det_force.sh DET-mtp-p1 build-mtp-1 --env "$W" --add-opt=--pipeline-windows=2 --env STRATA_MTPC_PROF=2
bash $D/det_force.sh DET-mtp-p2 build-mtp-1 --env "$W" --add-opt=--pipeline-windows=2 --env STRATA_MTPC_PROF=1 $ON
bash $D/det_force.sh DET-mtp-p3 build-mtp-1 --env "$W" --add-opt=--pipeline-windows=2 --env STRATA_MTPC_PROF=1 $ON --env STRATA_MTPC_LOPRIO=1
