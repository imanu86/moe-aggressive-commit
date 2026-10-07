#!/bin/bash
# Owner 7/10: one A per bench, B A B where possible. HAGS on, P2 on, base main be4cf1c lineage.
#   cpua: A=off1 and B=on1 already run -> one more B (on2) => A B B
#   mtp : B (host switches, no profiler) A B on build-mtp-1
#   iq2 : B (STRATA_COLD_IQ2) A B on build-iq2-1
export PATH=/usr/bin:/mingw64/bin:$PATH
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
P="--add-opt=--pipeline-windows=2"
until [ -f $K/DET-cpua-on1/result.json ]; do sleep 15; done
bash $D/det_force.sh DET-cpua-on2 build-cpu-2 --env "$W" $P --env STRATA_POOL_ASYNC=1 >/dev/null 2>&1
echo "== cpua"; python $D/bab_verdict.py DET-cpua-off1 DET-cpua-on1 DET-cpua-on2
MT="--env STRATA_MTPC_F1=1 --env STRATA_MTPC_EARLY=1 --env STRATA_MTPC_FLUSH=1 --env STRATA_MTPC_POLL=1 --env STRATA_MTPC_CATCHUP=1 --env STRATA_MTPC_PLE=1 --env STRATA_MTPC_LAZY=1"
bash $D/det_force.sh DET-mtp-b1 build-mtp-1 --env "$W" $P $MT >/dev/null 2>&1
bash $D/det_force.sh DET-mtp-a build-mtp-1 --env "$W" $P >/dev/null 2>&1
bash $D/det_force.sh DET-mtp-b2 build-mtp-1 --env "$W" $P $MT >/dev/null 2>&1
echo "== mtp"; python $D/bab_verdict.py DET-mtp-a DET-mtp-b1 DET-mtp-b2
IQ="STRATA_COLD_IQ2=D:\ds4_work\strata\Strata-data\gguf\Qwen3.8-Flash-Next-GSQ-RCO-IQ2_XS-00001-of-00002.gguf"
bash $D/det_force.sh DET-iq2-b1 build-iq2-1 --env "$W" $P --env "$IQ" >/dev/null 2>&1
bash $D/det_force.sh DET-iq2-a build-iq2-1 --env "$W" $P >/dev/null 2>&1
bash $D/det_force.sh DET-iq2-b2 build-iq2-1 --env "$W" $P --env "$IQ" >/dev/null 2>&1
echo "== iq2"; python $D/bab_verdict.py DET-iq2-a DET-iq2-b1 DET-iq2-b2
