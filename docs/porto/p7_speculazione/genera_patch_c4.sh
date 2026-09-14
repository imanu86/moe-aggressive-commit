#!/bin/sh
# P7, cella 4 - patch INCREMENTALE rispetto allo stato dopo P4-estensione.
#
# Il lato sinistro e' la copia congelata `D:/ds4_work/p7_cella4_base`, presa dai
# file dell'albero di lavoro PRIMA di questa cella (14 settembre, 13:05, gli
# stessi byte che P4-estensione ha lasciato). Non viene mai modificata.
#
# `-d` e' obbligatorio: senza, `diff` rende un inserimento come «cancella N
# righe e riscrivile identiche» e la patch diventa illeggibile (difetto 4 di
# P4-costo).
#
# COME SI APPLICA (e la trappola). Il `patch` di Git Bash apre i file in modo
# TESTO e su due dei sette file rifiuta OGNI hunk con «different line endings»,
# pur non essendoci un solo CR ne' nella patch ne' nei sorgenti. Serve
# `--binary`:
#
#   cd <albero allo stato P4-estensione>
#   patch -p1 --binary < p7_cella4.patch
#
# Verificata cosi' su una copia di `D:/ds4_work/p7_cella4_base`: i sette file
# risultanti coincidono BYTE PER BYTE con l'albero di lavoro.
A="D:/ds4_work/p7_cella4_base"
B="D:/ds4_work/p3_work/source"
OUT="C:/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/p7_speculazione/p7_cella4.patch"
: > "$OUT"
FILES="
ggml/include/moe_cpu_job.h
ggml/src/ggml-cuda/fork-moe-kernels.cuh
ggml/src/ggml-cuda/moe-demand.cuh
src/llama-moecpu.h
src/llama-moecpu.cpp
src/moe_cpu_executor.h
src/moe_cpu_executor.cpp
src/llama-graph.cpp
src/llama-context.h
src/llama-context.cpp
"
for f in $FILES; do
  if [ -f "$A/$f" ]; then L="$A/$f"; else L="/dev/null"; fi
  diff -u -d --label "a/$f" "$L" --label "b/$f" "$B/$f" >> "$OUT"
done
wc -l "$OUT"
