#!/usr/bin/env python3
"""Legge la TRAIETTORIA di un run llama.cpp, non solo il totale.

Perche' esiste
--------------
Il 2/8 abbiamo catalogato ogni run col numero finale che llama.cpp stampa,
`eval time = ... N tokens per second`. Quel numero e' una MEDIA CUMULATIVA su
tutta la corsa, e su questa macchina la corsa non e' stazionaria: il modello
sta 16 GB sopra la RAM, quindi la page cache si scalda token dopo token.

    LLAMA_ngl99_ncmoe42   ~100 token 4,51 t/s   ~800 6,06   1500 6,86

La media finale quindi dipende da DUE cose che non c'entrano con la leva in
prova: quanto e' lunga la corsa, e quanto era calda la cache all'inizio. Il run
del reap era a 800 token contro i 1500 del riferimento, e confrontarne le medie
finali (4,66 contro 6,86) attribuiva alla leva un terzo di divario che era solo
lunghezza.

Cosa stampa
-----------
    finale      la media cumulativa: quello che il ledger ha sempre registrato
    a_N         la media cumulativa al token N -- confrontabile FRA run diversi
    finestre    mediana di tg_3s in finestre FISSE di token. Fisse, non "ultimo
                terzo": un terzo di 800 e un terzo di 1500 cadono in due punti
                diversi della salita, che e' lo stesso errore di lunghezza da cui
                nasce questo strumento.

La finestra 500-800 e' quella che ogni run della campagna raggiunge, quindi e'
il confronto buono di default.

Quanto e' piu' stabile: le due ripetizioni di ncmoe42 danno 6,86 e 6,75 sul
totale (1,6% di scarto) e 8,58 contro 8,59 in regime (0,1%). La "varianza fra
run ~1,6%" registrata il 2/8 era quasi tutta rumore di riscaldamento.

Uso:  python curva_run.py <log...>            (accetta glob e cartelle)
"""

import re
import statistics
import sys
from pathlib import Path

RE_DEC = re.compile(r"n_decoded\s*=\s*(\d+).*?tg\s*=\s*([\d.]+).*?tg_3s\s*=\s*([\d.]+)")
RE_EVAL = re.compile(r"eval time =\s*([\d.]+) ms /\s*(\d+) tokens.*?([\d.]+) tokens per second")

# I token a cui appaiare i confronti. 800 c'e' perche' e' la lunghezza del run
# del reap; 1500 perche' e' quella della campagna.
APPAIA = (100, 400, 800, 1200, 1500)

# Finestre fisse per la mediana di tg_3s. Non dipendono dalla lunghezza del run,
# quindi due corse di lunghezza diversa restano confrontabili.
FINESTRE = ((0, 200), (200, 500), (500, 800), (800, 1200), (1200, 1600))
RIFERIMENTO = (500, 800)   # la finestra che ogni run della campagna raggiunge


def leggi(percorso: Path):
    punti = []          # (n_decoded, tg_cumulativa, tg_3s)
    finale = None       # (ms_per_token, n_token, t_s) dalla riga 'eval time'
    prompt = None
    with percorso.open(encoding="utf-8", errors="replace") as f:
        for riga in f:
            m = RE_DEC.search(riga)
            if m:
                punti.append((int(m.group(1)), float(m.group(2)), float(m.group(3))))
                continue
            m = RE_EVAL.search(riga)
            if m:
                # la riga compare due volte: 'prompt eval time' e 'eval time'
                v = (float(m.group(1)), int(m.group(2)), float(m.group(3)))
                if "prompt eval" in riga:
                    prompt = v
                else:
                    finale = v
    return punti, finale, prompt


def a_token(punti, n):
    """Media cumulativa al token piu' vicino a n, se il run ci e' arrivato."""
    vicini = [p for p in punti if abs(p[0] - n) <= max(25, n * 0.03)]
    if not vicini:
        return None
    return min(vicini, key=lambda p: abs(p[0] - n))[1]


def analizza(percorso: Path):
    punti, finale, prompt = leggi(percorso)
    if not punti:
        print(f"{percorso.name}: nessun campione n_decoded")
        return

    print(f"\n{percorso.name}")
    if finale:
        print(f"  finale    {finale[2]:.2f} t/s  su {finale[1]} token"
              f"  ({finale[0] / finale[1]:.1f} ms/token)")
    if prompt:
        print(f"  prefill   {prompt[2]:.2f} t/s  su {prompt[1]} token")

    campi = []
    for n in APPAIA:
        v = a_token(punti, n)
        if v is not None:
            campi.append(f"a{n} {v:.2f}")
    if campi:
        print("  appaiato  " + "   ".join(campi))

    finestre, rif = [], None
    for lo, hi in FINESTRE:
        v = [p[2] for p in punti if lo <= p[0] < hi]
        if len(v) < 3:            # meno di 3 campioni: una mediana non significa nulla
            continue
        m = statistics.median(v)
        finestre.append(f"{lo}-{hi} {m:.2f}")
        if (lo, hi) == RIFERIMENTO:
            rif = m
    if finestre:
        print("  finestre  " + "   ".join(finestre))
    if rif is not None:
        print(f"  REGIME    {rif:.2f} t/s   <- mediana tg_3s in {RIFERIMENTO[0]}-{RIFERIMENTO[1]},"
              f" il confronto buono")
    else:
        print(f"  REGIME    non calcolabile: il run non copre {RIFERIMENTO[0]}-{RIFERIMENTO[1]}")


def espandi(argomenti):
    for a in argomenti:
        p = Path(a)
        if p.is_dir():
            yield from sorted(p.glob("*.server.log"))
        elif any(c in a for c in "*?["):
            yield from sorted(Path().glob(a))
        else:
            yield p


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for p in espandi(sys.argv[1:]):
        analizza(p)
