#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""(C) Quanto SPESSO l'id -1 entra nel cammino CPU (ggml-cpu.c:1632).

Conta, per riga, quante delle k_cpu colonne CPU porterebbero -1 con la leva
accesa: sono esattamente le colonne DECLINATE = max(0, k_cpu - non_residenti).
Riporta il regime della traccia (473 slot) e quello di produzione, letto sugli
strati della traccia che gia' girano al tasso di colpi di produzione.
"""
import collections, sys
from leggi_cestrc import leggi

K = 2
# ancore del banco B0/SOTA (LEDGER_25 par.17): 1200 token
PARTIZIONI_BANCO = 29025      # righe x strati per corsa
CPU_ESP_RIGA     = 58050      # = 2 x partizioni
COLPI_PRODUZIONE = 0.672      # par.58-59, 623 slot


def blocco(righe, etichetta):
    n = len(righe)
    isto = collections.Counter(max(0, K - sum(1 for s in r.stati if s == 0))
                               for r in righe)
    colpi = sum(1 for r in righe for s in r.stati if s != 0) / (n * 6)
    decl = sum(k * v for k, v in isto.items())
    righe_con = sum(v for k, v in isto.items() if k > 0)
    print("  %s" % etichetta)
    print("    righe %d   colpi %.4f" % (n, colpi))
    for k in range(K + 1):
        v = isto.get(k, 0)
        print("      %d colonne CPU con -1 : %7d righe = %6.2f%%" % (k, v, 100.0 * v / n))
    print("    righe con ALMENO un -1     : %7d = %6.2f%%" % (righe_con, 100.0 * righe_con / n))
    print("    colonne -1 totali          : %7d = %6.2f%% dei %d esperti-riga CPU"
          % (decl, 100.0 * decl / (n * K), n * K))
    # scala al banco
    f_righe_con = righe_con / n
    f_decl = decl / (n * K)
    print("    SCALA AL BANCO (%d partizioni, %d esperti-riga CPU per corsa da 1200 token):"
          % (PARTIZIONI_BANCO, CPU_ESP_RIGA))
    print("      righe che portano almeno un -1 : %8.0f" % (f_righe_con * PARTIZIONI_BANCO))
    print("      ingressi -1 in ggml-cpu.c:1632 : %8.0f per corsa" % (f_decl * CPU_ESP_RIGA))
    print("      (la stessa maschera vale per le TRE mul_mat_id del ramo CPU:")
    print("       up, gate, down => %8.0f salti per corsa)" % (3 * f_decl * CPU_ESP_RIGA))
    return f_decl, f_righe_con


def main(path):
    meta, righe = leggi(path)
    print("### %s (slot %d)" % (path, meta["slot"]))
    blocco(righe, "[1] REGIME DELLA TRACCIA (473 slot)")
    print("")
    # strati al tasso di colpi di produzione
    per_strato = collections.defaultdict(list)
    for r in righe:
        per_strato[r.strato].append(r)
    sel = []
    strati_sel = []
    for s, rr in per_strato.items():
        h = sum(1 for r in rr for x in r.stati if x != 0) / (len(rr) * 6)
        if abs(h - COLPI_PRODUZIONE) < 0.02:
            sel.extend(rr)
            strati_sel.append((s, round(h, 4)))
    print("[2] REGIME DI PRODUZIONE, letto sugli strati gia' a colpi %.3f +-0,02"
          % COLPI_PRODUZIONE)
    print("    strati usati: %s" % sorted(strati_sel))
    blocco(sel, "")


if __name__ == "__main__":
    for f in sys.argv[1:]:
        main(f)
        print()
