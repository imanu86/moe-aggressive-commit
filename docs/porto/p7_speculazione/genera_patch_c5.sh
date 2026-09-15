#!/bin/sh
# P7 cella 5 - patch incrementale rispetto allo stato "dopo cella 4".
#
# Il riferimento e' `D:\ds4_work\p3_work\tmp\ref_c4\source`, ricostruito dallo
# snapshot immutabile `D:\ds4_work\p0_snapshot_20260914\source` applicando in
# ordine, con `patch -p1 --binary`:
#   1. docs/porto/p3_uno_strato/p3_uno_strato.patch
#   2. docs/porto/p4_costo/p4_costo.patch
#   3. docs/porto/p4_estensione/p4_estensione.patch
#   4. docs/porto/p7_speculazione/p7_cella4.patch
#
# `-d` per usare percorsi relativi (`a/src/...`), `--binary` in applicazione:
# i sorgenti hanno terminatori CRLF e senza quel flag `patch` rifiuta gli hunk
# dei `.cuh` con «different line endings».
set -e

REF="/d/ds4_work/p3_work/tmp/ref_c4/source"
CUR="/d/ds4_work/p3_work/source"
OUT="/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/p7_speculazione/p7_cella5.patch"

FILES="ggml/src/ggml-cuda/fork-moe-kernels.cuh
ggml/src/ggml-cuda/moe-demand.cuh
src/llama-graph.cpp
src/llama-moecpu.cpp
src/llama-moecpu.h
src/moe_cpu_executor.cpp
src/moe_cpu_executor.h"

: > "$OUT"
for f in $FILES; do
    diff -u "$REF/$f" "$CUR/$f" \
        --label "a/$f" --label "b/$f" >> "$OUT" || true
done

echo "scritta $OUT"
wc -l "$OUT"
