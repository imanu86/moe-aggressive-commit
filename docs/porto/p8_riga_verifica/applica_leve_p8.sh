#!/bin/sh
# P8 - applica le quattro leve all'albero di lavoro, in ordine, e rigenera la patch
# cumulativa contro lo snapshot P0.
#
#   sh applica_leve_p8.sh                 # applica all'albero di lavoro
#   sh applica_leve_p8.sh --prova <dir>   # applica a una COPIA in <dir> e si ferma
#
# La prova NON puo' essere un `--dry-run` incatenato: p8_B_interruttore.patch e
# p8_D1.patch hanno per contesto righe introdotte da p8_B.patch, che in dry-run non
# esistono ancora. Si prova su una copia vera, non a vuoto.
#
# `--binary` e' obbligatorio: i sorgenti hanno fine riga CRLF e senza quel flag
# `patch` rifiuta con "different line endings" (e `git apply` per lo stesso motivo).
set -e

ALBERO="D:/ds4_work/p8_work/source"
BASE="D:/ds4_work/p0_snapshot_20260914/source"
PATCHDIR="C:/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/p8_riga_verifica"
LEVE="A B B_interruttore C D1"

PROVA=""
if [ "$1" = "--prova" ]; then
    PROVA="$2"
    rm -rf "$PROVA"
    mkdir -p "$PROVA"
    cp -r "$ALBERO/ggml" "$ALBERO/src" "$PROVA/"
    ALBERO="$PROVA"
    echo "prova su una copia: $PROVA"
fi

cd "$ALBERO"
for p in $LEVE; do
    printf '%-18s ' "p8_$p.patch"
    patch -p1 --binary < "$PATCHDIR/p8_$p.patch"
done

if [ -n "$PROVA" ]; then
    echo "prova finita: l'albero di lavoro non e' stato toccato"
    exit 0
fi

# Patch cumulativa: un solo diff contro la base pulita, sui tre file toccati.
# I nomi `a/...` e `b/...` vengono dalla forma delle cartelle, NON da un sed sulle prime
# due righe: sed su Windows riscrive lo standard output in modo testuale e toglie i CR
# alle righe di contesto, e la patch che ne esce viene poi rifiutata da `patch --binary`
# con "different line endings". Il diff deve uscire e restare intatto.
TMP=$(mktemp -d)
FILES="ggml/src/ggml-backend.cpp ggml/src/ggml-cuda/getrows.cu src/models/qwen4exp.cpp"
for f in $FILES; do
    mkdir -p "$TMP/a/$(dirname "$f")" "$TMP/b/$(dirname "$f")"
    cp "$BASE/$f" "$TMP/a/$f"
    cp "$ALBERO/$f" "$TMP/b/$f"
done
: > "$PATCHDIR/p8_cumulativa.patch"
( cd "$TMP" && for f in $FILES; do diff -u "a/$f" "b/$f" || true; done ) \
    >> "$PATCHDIR/p8_cumulativa.patch"
rm -rf "$TMP"
echo "patch cumulativa: $PATCHDIR/p8_cumulativa.patch"
wc -l "$PATCHDIR/p8_cumulativa.patch"
