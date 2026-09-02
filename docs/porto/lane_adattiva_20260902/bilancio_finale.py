#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""(A) bilancio finale: le tre regole a confronto sulla STESSA traccia.

  R0  oggi              K=2 fisso per riga
  R1  lane adattiva     K = min(2, non residenti della riga)
  R2  K=1               (il braccio GIA' MISURATO, r54_k1: -2,05%)
  R3  q* di FreeToken   sui soli miss unici dello strato

Il discriminante e' il numero di COPIE NUOVE che ogni regola crea: e' il
canale per cui K=1 e' morto ("i byte MIGRANO sullo stesso bus", par.10).
"""
import collections, sys
from leggi_cestrc import leggi

K = 2

# --- ANCORE B0/SOTA (LEDGER_25 par.17 tabella + par.18 scomposizione) -------
PARETE_S      = 94.56     # s, decode 1200 token
TS_B0         = 12.69     # t/s
CALCOLO_S     = 19.43     # s, `calcolo` della lane
N_LAVORI      = 12642     # worker
CALC_MS_LAV   = 1.537     # ms/lavoro (par.17 B0)
PARTIZIONI    = 29025     # (riga x strato)
CPU_ESP_RIGA  = 58050     # = 2 x partizioni
# banda alternativa (par.58-59, 2/9, 623 slot): 15179 lavori x 1,87 ms / 97 s
CALCOLO_S_ALT = 15179 * 1.87 / 1000.0
PARETE_S_ALT  = 97.0
# costi unitari (llama-graph.cpp:1819-1820)
MS_CPU_ESP    = 0.242
MS_GPU_RES    = 0.060
MS_GPU_COPIA  = 0.271


def perm_sota(stati, ne0):
    p = []
    for fase in range(4):
        for i in range(ne0):
            if stati[i] == fase:
                p.append(i)
    return p


def gruppi_da(righe):
    g, i = [], 0
    while i < len(righe):
        n = righe[i].n_tok
        g.append(righe[i:i + n])
        i += n
    return g


def copie(gruppi, k_di_riga):
    """Chiavi UNICHE per gruppo che finiscono in copia (miss in lane GPU),
    dato un k per riga."""
    tot_copie = 0
    tot_cpu_righe = 0
    tot_cpu_unici = 0
    for g in gruppi:
        cop, cpu = set(), set()
        for r in g:
            st = r.stati
            pm = perm_sota(st, r.n_esp)
            k = k_di_riga(r, st)
            for j in pm[:k]:
                cpu.add(r.ids[j])
                tot_cpu_righe += 1
            for j in pm[k:]:
                if st[j] == 0:
                    cop.add((r.strato, r.ids[j]))
        tot_copie += len(cop)
        tot_cpu_unici += len(cpu)
    return tot_copie, tot_cpu_righe, tot_cpu_unici


def main(path):
    meta, righe = leggi(path)
    g = gruppi_da(righe)
    print("### %s  (slot %d, %d righe, %d gruppi)" % (path, meta["slot"], len(righe), len(g)))
    print("")

    regole = [
        ("R0 oggi   K=2 fisso", lambda r, st: K),
        ("R1 adattiva K=min(2,nonres)", lambda r, st: min(K, sum(1 for s in st if s == 0))),
        ("R2 K=1", lambda r, st: 1),
        ("R3 K=0 (tutto GPU)", lambda r, st: 0),
    ]
    base = None
    print("  regola                        | copie uniche | esp-riga CPU | esp unici CPU | copie NUOVE")
    print("  " + "-" * 96)
    for nome, f in regole:
        c, er, eu = copie(g, f)
        if base is None:
            base = c
        print("  %-29s | %12d | %12d | %13d | %+11d" % (nome, c, er, eu, c - base))
    print("")
    print("  LETTURA: la lane adattiva crea copie NUOVE = 0 PER COSTRUZIONE (toglie")
    print("  alla CPU solo esperti gia' RESIDENTI, che la GPU serve senza trasporto).")
    print("  K=1 e K=0 invece spostano MISS sulla GPU: ogni miss spostato e' una copia")
    print("  PCIe in piu' -- il canale per cui r54_k1 ha reso -2,05%% (par.10).")
    print("")

    # ---- bilancio in tempo, ancora B0 ------------------------------------
    c0, er0, eu0 = copie(g, regole[0][1])
    c1, er1, eu1 = copie(g, regole[1][1])
    f_righe = 1.0 - er1 / er0
    f_unici = 1.0 - eu1 / eu0
    print("  frazione di lane tolta: esperti-riga %.2f%%  /  esperti unici %.2f%%"
          % (100 * f_righe, 100 * f_unici))
    print("")
    for etichetta, parete, calcolo in (
            ("B0/SOTA par.17-18 (473-623 slot, 31/8)", PARETE_S, CALCOLO_S),
            ("wsolo par.58-59  (623 slot, 2/9)      ", PARETE_S_ALT, CALCOLO_S_ALT)):
        quota = calcolo / parete
        print("  [%s]  calcolo = %.2f s / %.2f s = %.2f%% della parete"
              % (etichetta, calcolo, parete, 100 * quota))
        for nome_f, fr in (("esperti-riga", f_righe), ("esperti unici", f_unici)):
            risp = fr * calcolo
            gain = risp / (parete - risp)
            print("      con frazione %-14s %.2f%%: risparmio %.2f s -> t/s %+.2f%%  (%.2f -> %.2f)"
                  % (nome_f, 100 * fr, risp, 100 * gain, TS_B0, TS_B0 * (1 + gain)))
        # correzione GPU: gli esperti spostati costano MS_GPU_RES invece di 0
        agg = er0 - er1
        gpu_ms = agg * MS_GPU_RES
        # scala: la traccia ha er0 esperti-riga, il banco CPU_ESP_RIGA
        scala = CPU_ESP_RIGA / er0
        gpu_s = gpu_ms * scala / 1000.0
        risp = f_righe * calcolo
        gain_c = (risp - gpu_s) / (parete - risp + gpu_s)
        print("      correzione GPU (se NON c'e' slack): +%.2f s -> t/s %+.2f%%"
              % (gpu_s, 100 * gain_c))
        print("")

    # ---- q* di FreeToken, con sensibilita' su BH -------------------------
    print("  q* di FreeToken: q/(m-q) = BP/(BH-BP)  =>  q = m * BP/BH  (q = alla GPU)")
    print("  m = miss UNICI per (strato, passo). Oggi la CPU ne assorbe:")
    tot_m = 0
    tot_cpu_miss = 0
    for grp in g:
        miss = set()
        cpu = set()
        for r in grp:
            st = r.stati
            pm = perm_sota(st, r.n_esp)
            for j in range(r.n_esp):
                if st[j] == 0:
                    miss.add((r.strato, r.ids[j]))
            for j in pm[:K]:
                if st[j] == 0:
                    cpu.add((r.strato, r.ids[j]))
        tot_m += len(miss)
        tot_cpu_miss += len(cpu)
    print("      m medio = %.3f ;  alla CPU oggi = %.3f  =>  quota CPU OGGI = %.1f%%"
          % (tot_m / len(g), tot_cpu_miss / len(g), 100.0 * tot_cpu_miss / tot_m))
    print("")
    print("      BP (PCIe) | BH (host) | q*/m (GPU) | quota CPU q* | verso")
    BP = 23.0
    for BH, nota in ((30.0, "ipotesi del mandato"),
                     (33.2, "terna misurata, par.18"),
                     (23.4, "gate+up IQ2_XXS, 86,8% del tempo lane"),
                     (12.8, "B2 continuo misurato, par.17")):
        if BH <= BP:
            print("      %9.1f | %9.1f | %10s | %12s | %s  [BH<=BP: l'ottimo e' q=m, cioe' K=0]"
                  % (BP, BH, "1,000", "0,0%", nota))
            continue
        qm = BP / BH
        print("      %9.1f | %9.1f | %10.3f | %11.1f%% | %s  [oggi la CPU ne ha %.1f%% => %s]"
              % (BP, BH, qm, 100 * (1 - qm), nota, 100.0 * tot_cpu_miss / tot_m,
                 "TOGLIERE alla CPU" if (1 - qm) < tot_cpu_miss / tot_m else "DARE alla CPU"))
    print("")


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print("=" * 100)
        main(f)
