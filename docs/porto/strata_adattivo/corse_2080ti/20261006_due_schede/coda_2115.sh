#!/bin/bash
# 11/10 sera, OktoCGControl ACCESO, DSH chiuso: (1) nuova base + catena fusa contro il Daily; (2) memoria +250 (profilo 2
# di Afterburner) contro profilo 1, cambiando profilo con le attivita' pianificate prima di ogni braccio.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
CF=/c/Users/imanu/source/repos/Strata-wt/chainfuse/build-sm7586
S=$K/build-chainfuse-50c04dc0
mkdir -p $S && cp $CF/strata.exe $S/ && printf '{\n "status": "completed",\n "executable_sha256": "%s",\n "note": "lab/chainfuse 50c04dc0 (Fable): STRATA_CHAIN_FUSE2=1 (mask 62 di default), attenzione opt-in STRATA_CHAIN_FUSE2_ATTN"\n}\n' "$(sha256sum $S/strata.exe | cut -d' ' -f1)" > $S/build.json
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
P="--add-opt=--pipeline-windows=2 --add-opt=--vram-reserve-later-mib=384 --add-opt=--host-core=last"
E="--env STRATA_VRAM_FREE=device --env STRATA_ROUTE_TAIL_SKIP=0 --env STRATA_MMVQ_IL=0 --env STRATA_B6_MMVQ_ROWS=1 --env STRATA_ATTN_DAILY=1 --env STRATA_CHAIN_FUSE2=1 --env STRATA_MTP_SHARED_BRANCH=0"
prof() { schtasks //Run //TN "AB profilo $1" >/dev/null 2>&1; sleep 8; nvidia-smi --query-gpu=index,clocks.max.mem --format=csv,noheader | tr '\n' ' '; echo "(profilo $1)"; }

prof 1
echo "== nuova base + catena fusa contro Daily, OCGC acceso $(date +%H:%M)"
for arm in b1 a b2; do
  case $arm in
    b*) bash $D/det_force.sh DET-ocgc-new-$arm build-chainfuse-50c04dc0 --env "$W" $P $E >/dev/null 2>&1;;
    a) bash $D/det_force.sh DET-ocgc-new-$arm build-main-be4cf1c --env "$W" $P >/dev/null 2>&1;;
  esac
done
(cd $K && python $D/bab_verdict.py DET-ocgc-new-a DET-ocgc-new-b1 DET-ocgc-new-b2)
for a in a b1 b2; do grep -ah "expert cache [0-9]* slots\|NVML" $K/DET-ocgc-new-$a/engine.log | head -2 | cut -c1-150; done

echo "== memoria +250 (profilo 2) contro profilo 1, nuova base $(date +%H:%M)"
for arm in b1 a b2; do
  case $arm in b*) prof 2;; a) prof 1;; esac
  bash $D/det_force.sh DET-ocgc-mem250-$arm build-chainfuse-50c04dc0 --env "$W" $P $E >/dev/null 2>&1
done
prof 1
(cd $K && python $D/bab_verdict.py DET-ocgc-mem250-a DET-ocgc-mem250-b1 DET-ocgc-mem250-b2)
