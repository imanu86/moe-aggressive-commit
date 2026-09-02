#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""(B.5) Quanto vale l'OPZIONE (ii): K deciso dall'HOST per STRATO, senza
cambio di forma. Un K per strato deve valere per TUTTE le righe del gruppo,
quindi k_strato <= min(non_residenti) sulle righe, altrimenti la riga con meno
miss riprende a calcolare residenti.

Due varianti:
  (ii-a) ORACOLO: k_strato = min(2, min_righe(non_res)) dello STESSO passo
  (ii-b) RITARDO: k_strato dal conteggio del passo PRECEDENTE dello stesso
         strato (quello realmente disponibile all'host)
"""
import collections, sys
from leggi_cestrc import leggi

K = 2


def gruppi_da(righe):
    g, i = [], 0
    while i < len(righe):
        n = righe[i].n_tok
        g.append(righe[i:i + n])
        i += n
    return g


def main(path):
    meta, righe = leggi(path)
    g = gruppi_da(righe)
    tot = sum(K * len(x) for x in g)

    # R1 per riga (il tetto)
    spr_riga = sum(max(0, K - sum(1 for s in r.stati if s == 0))
                   for grp in g for r in grp)

    # ii-a oracolo per strato
    risp_a = 0
    # ii-b con ritardo di un passo sullo stesso strato
    prec = {}
    risp_b = 0
    danno_b = 0
    for grp in g:
        mins = min(sum(1 for s in r.stati if s == 0) for r in grp)
        k_a = min(K, mins)
        risp_a += (K - k_a) * len(grp)
        strato = grp[0].strato
        k_b = min(K, prec.get(strato, K))
        prec[strato] = mins
        risp_b += (K - k_b) * len(grp)
        # se k_b > mins di ADESSO, la riga torna a calcolare residenti
        for r in grp:
            nm = sum(1 for s in r.stati if s == 0)
            danno_b += max(0, min(k_b, K) - nm)

    print("### %s" % path)
    print("  esperti-riga alla CPU oggi                    : %d" % tot)
    print("  R1  per RIGA (tetto)          risparmio        : %d = %.2f%%"
          % (spr_riga, 100.0 * spr_riga / tot))
    print("  ii-a K per STRATO, ORACOLO    risparmio        : %d = %.2f%%"
          % (risp_a, 100.0 * risp_a / tot))
    print("  ii-b K per STRATO, RITARDO 1  risparmio        : %d = %.2f%%"
          % (risp_b, 100.0 * risp_b / tot))
    print("      di cui ANCORA sprecato (residenti presi)   : %d = %.2f%%"
          % (danno_b, 100.0 * danno_b / tot))
    print("  => l'opzione (ii) cattura %.1f%% del tetto (oracolo) / %.1f%% (reale)"
          % (100.0 * risp_a / spr_riga, 100.0 * risp_b / spr_riga))
    # quante volte K cambierebbe fra passi consecutivi dello stesso strato
    prec = {}
    cambi = tot_passi = 0
    for grp in g:
        mins = min(sum(1 for s in r.stati if s == 0) for r in grp)
        k = min(K, mins)
        s = grp[0].strato
        if s in prec:
            tot_passi += 1
            if prec[s] != k:
                cambi += 1
        prec[s] = k
    print("  OSCILLAZIONE di K fra passi consecutivi dello stesso strato: %d / %d = %.1f%%"
          % (cambi, tot_passi, 100.0 * cambi / tot_passi))
    print("      (ogni cambio = forme nuove = RICATTURA del CUDA graph)")


if __name__ == "__main__":
    for f in sys.argv[1:]:
        main(f)
        print()
