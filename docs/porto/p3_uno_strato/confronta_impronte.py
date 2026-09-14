#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3 - confronto delle impronte del testo fra una corsa e il blocco di riferimento.

L'impronta e' l'ORACOLO: due corse identiche in greedy, con MTP spento e -np 1,
danno lo stesso testo byte per byte (regola di metodo del 13/9). Se la patch e'
neutra a funzione spenta, le impronte devono coincidere caso per caso.

    python confronta_impronte.py <cartella_corsa> [<cartella_riferimento>]

Uscita 0 se tutte le chiavi in comune coincidono, 1 altrimenti.
"""
import json
import sys
from pathlib import Path

RIF = r"D:\ds4_work\banco_p0_run\20260914_072049_P0_sper_ibrido_assente_r1"


def leggi(cartella):
    out = {}
    p = Path(cartella) / "results.jsonl"
    with open(p, encoding="utf-8") as f:
        for riga in f:
            riga = riga.strip()
            if not riga:
                continue
            r = json.loads(riga)
            if not r.get("valido", True):
                continue
            et = r.get("etichetta")
            if et is None:
                continue
            out[et] = r.get("impronta_testo_sha256")
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    corsa = leggi(sys.argv[1])
    rif = leggi(sys.argv[2] if len(sys.argv) > 2 else RIF)
    comuni = [k for k in corsa if k in rif]
    diverse = [k for k in comuni if corsa[k] != rif[k]]
    print("chiavi nella corsa: %d, nel riferimento: %d, in comune: %d"
          % (len(corsa), len(rif), len(comuni)))
    for k in sorted(comuni):
        stato = "UGUALE" if corsa[k] == rif[k] else "DIVERSA"
        print("  %-8s %-22s corsa %s  riferimento %s"
              % (stato, k, (corsa[k] or "-")[:16], (rif[k] or "-")[:16]))
    solo = [k for k in corsa if k not in rif]
    if solo:
        print("solo nella corsa (nessun confronto possibile): %s" % ", ".join(sorted(solo)))
    print("DIVERSE: %d su %d" % (len(diverse), len(comuni)))
    return 1 if diverse else 0


if __name__ == "__main__":
    sys.exit(main())
