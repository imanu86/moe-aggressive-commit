#!/usr/bin/env bash
# P4, seconda cella - diff INCREMENTALE rispetto allo stato patchato di P4-costo.
#
# La copia di riferimento e' quella salvata PRIMA delle modifiche di questa
# cella (`D:\ds4_work\p4_estensione_base`). I sorgenti hanno terminatori CRLF:
# `diff` e `patch` vanno usati in modo binario, come per le patch di P3 e P4
# (`patch -p1 --binary`).
#
#   bash genera_patch.sh <cartella_riferimento_p4costo> <albero_sorgenti> <uscita.patch>
set -u

RIF="${1:?cartella con i file allo stato P4-costo}"
NEW="${2:?albero dei sorgenti di questa cella}"
OUT="${3:?file .patch da scrivere}"

FILES="
ggml/include/moe_cpu_job.h
ggml/src/ggml-cuda/moe-demand.cuh
src/llama-moecpu.h
src/llama-moecpu.cpp
src/moe_cpu_executor.h
src/moe_cpu_executor.cpp
"

: > "$OUT"
for f in $FILES; do
    # -d (--minimal): senza, il diff rende un inserimento come «cancella N righe
    # e riscrivile identiche» (difetto 4 di P4-costo).
    diff -u -d --label "a/$f" --label "b/$f" "$RIF/$f" "$NEW/$f" >> "$OUT"
done
echo "scritte $(wc -l < "$OUT") righe in $OUT"
grep -c '^+++' "$OUT" | sed 's/^/file toccati: /'
