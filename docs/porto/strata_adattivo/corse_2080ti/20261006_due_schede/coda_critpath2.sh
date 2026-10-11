#!/bin/bash
# 11/10: B-A-B per leva di lab/critpath2 (8b4fd975) sul banco forzato a 131k. A = stessa build senza la leva.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
B=build-critpath2-8b4fd975
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
P="--add-opt=--pipeline-windows=2 --add-opt=--vram-reserve-later-mib=384 --add-opt=--host-core=last"
E="--env STRATA_VRAM_FREE=device --env STRATA_ROUTE_TAIL_SKIP=0 --env STRATA_MMVQ_IL=0 --env STRATA_B6_MMVQ_ROWS=1 --env STRATA_ATTN_DAILY=1"
for lev in L1FIRST S1FIRST CHAIN_PRE RESPLAN; do
  for arm in b1 a b2; do
    X=""
    case $arm in b*) X="--env STRATA_CP_$lev=1";; esac
    bash $D/det_force.sh DET-cp2-$lev-$arm $B --env "$W" $P $E $X >/dev/null 2>&1
  done
  echo "== $lev $(date +%H:%M)"
  (cd $K && python $D/bab_verdict.py DET-cp2-$lev-a DET-cp2-$lev-b1 DET-cp2-$lev-b2)
  grep -ah "strata critpath:" $K/DET-cp2-$lev-b1/engine.log | tail -1 | cut -c1-240
  for a in a b1; do grep -ah "target picks replaced" $K/DET-cp2-$lev-$a/engine.log | grep -o "replaced on verified rows [0-9]*" | tr '\n' ' '; echo " ($a)"; done
done
