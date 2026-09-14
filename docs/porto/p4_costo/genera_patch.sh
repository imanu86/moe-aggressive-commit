#!/usr/bin/env bash
# P4 - diff INCREMENTALE rispetto allo stato patchato di P3.
#
# La copia di riferimento e' quella salvata PRIMA delle modifiche di P4, nello
# scratchpad della sessione. I sorgenti hanno terminatori CRLF: `diff` e `patch`
# vanno usati in modo binario, come per la patch di P3 (`patch -p1 --binary`).
#
#   bash genera_patch.sh <cartella_riferimento_p3> <cartella_sorgenti_p4> <uscita.patch>
set -u

RIF="${1:?cartella con i file allo stato P3}"
NEW="${2:?albero dei sorgenti di P4}"
OUT="${3:?file .patch da scrivere}"

FILES="
src/llama-moecpu.h
src/llama-moecpu.cpp
src/llama-graph.cpp
src/moe_cpu_executor.h
src/moe_cpu_executor.cpp
ggml/src/ggml-cuda/moe-demand.cuh
"

: > "$OUT"
for f in $FILES; do
    # -d (--minimal): senza, il diff rende un inserimento come «cancella 62
    # righe e riscrivile identiche», e la patch diventa illeggibile.
    diff -u -d --label "a/$f" --label "b/$f" "$RIF/$f" "$NEW/$f" >> "$OUT"
done
echo "scritte $(wc -l < "$OUT") righe in $OUT"
grep -c '^+++' "$OUT" | sed 's/^/file toccati: /'
