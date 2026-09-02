#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""(A) TETTO della LANE ADATTIVA, dalle tracce route, senza build.

Ricostruisce la permutazione di `kern_partiziona`
(cache-esperti.cu:7205-7250, ramo `else` = SOTA con MASSA_CORSIE=0 e
CPU_LEGGERI=0: ordinamento STABILE per classe crescente) e conta quanti dei
k_cpu esperti presi dalla TESTA erano RESIDENTI (classe 2/3), cioe' lavoro
CPU sprecato.
"""
import collections, sys, io
from leggi_cestrc import leggi

# --- ingressi di costo, con provenienza -------------------------------------
CALCOLO_LANE_MS_PER_LAVORO = 1.87   # LEDGER_25_AGOSTO par.58-59 (623 slot)
K_CPU_NOMINALE             = 2      # LLAMA_OVERLAP_K=2
MS_PER_ESPERTO_RIGA        = CALCOLO_LANE_MS_PER_LAVORO / K_CPU_NOMINALE
DECODE_S                   = 97.0   # LEDGER_25_AGOSTO par.58-59
LAVORI                     = 15179  # LEDGER_25_AGOSTO par.58-59
MS_COPIA                   = 0.32   # 7,30 MiB @ 23 GB/s (ingresso del mandato)
BP_GBS                     = 23.0   # PCIe
BH_GBS                     = 30.0   # lane CPU unpack-bound


def perm_sota(stati, ne0):
    """Ordinamento stabile per classe crescente, classi 0..3 (fase_max=3
    nell'istanziazione <false>, quella di produzione)."""
    p = []
    for fase in range(0, 4):
        for i in range(ne0):
            if stati[i] == fase:
                p.append(i)
    return p


def analizza(path, out=sys.stdout):
    p = lambda *a: print(*a, file=out)
    meta, righe = leggi(path)
    p("### %s" % path)
    p("meta: slot=%d esperti=%d record=%d" % (meta["slot"], meta["esperti"], len(righe)))

    n_righe = len(righe)
    k = righe[0].k_cpu
    assert all(r.k_cpu == k for r in righe), "k_cpu non costante"
    ne0 = righe[0].n_esp

    isto_miss = collections.Counter()
    sprecati_tot = 0
    cpu_tot = 0
    fork_ok = fork_no = fork_na = 0
    sprecati_per_strato = collections.Counter()
    righe_per_strato = collections.Counter()

    i = 0
    gruppi = []
    while i < n_righe:
        n = righe[i].n_tok
        gruppi.append(righe[i:i + n])
        i += n

    for r in righe:
        n_miss = sum(1 for s in r.stati if s == 0)
        isto_miss[n_miss] += 1
        righe_per_strato[r.strato] += 1
        pm = perm_sota(r.stati, ne0)
        testa = pm[:k]
        spr = sum(1 for j in testa if r.stati[j] != 0)
        assert spr == max(0, k - n_miss), "incoerenza permutazione"
        sprecati_tot += spr
        sprecati_per_strato[r.strato] += spr
        cpu_tot += k
        if any(f != 255 for f in r.fork):
            attesi = set(testa)
            oss = {j for j in range(ne0) if r.fork[j] == 255}
            if oss and oss <= attesi:
                fork_ok += 1
            elif oss:
                fork_no += 1
            else:
                fork_na += 1
        else:
            fork_na += 1

    p("")
    p("(a) DISTRIBUZIONE dei NON RESIDENTI per riga (su %d esperti):" % ne0)
    p("    non_res | righe      |      %")
    for m in range(ne0 + 1):
        c = isto_miss.get(m, 0)
        p("    %7d | %10d | %6.2f%%" % (m, c, 100.0 * c / n_righe))
    r0 = isto_miss.get(0, 0)
    r1 = isto_miss.get(1, 0)
    p("    righe con 0 non residenti (CPU calcola 2 residenti): %d = %.2f%%"
      % (r0, 100.0 * r0 / n_righe))
    p("    righe con 1 non residente (CPU calcola 1 residente): %d = %.2f%%"
      % (r1, 100.0 * r1 / n_righe))
    p("    righe con >= k=%d non residenti (nessuno spreco):     %d = %.2f%%"
      % (k, n_righe - r0 - r1, 100.0 * (n_righe - r0 - r1) / n_righe))

    p("")
    p("(b) LAVORO CPU SPRECATO")
    p("    esperti dati alla CPU  : %d  (= %d righe x k_cpu %d)" % (cpu_tot, n_righe, k))
    p("    di cui RESIDENTI       : %d" % sprecati_tot)
    frazione = sprecati_tot / cpu_tot
    p("    frazione sprecata      : %.4f = %.2f%%" % (frazione, 100.0 * frazione))
    p("    controprova FORK (maschera MMVQ): coerenti=%d incoerenti=%d n/d=%d"
      % (fork_ok, fork_no, fork_na))

    p("")
    p("(b2) SPRECO per STRATO (5 peggiori / 5 migliori):")
    tab = sorted(((sprecati_per_strato[s] / (righe_per_strato[s] * k), s)
                  for s in righe_per_strato), reverse=True)
    for f, s in tab[:5]:
        p("     strato %2d : %6.2f%%  (%d righe)" % (s, 100.0 * f, righe_per_strato[s]))
    p("     ...")
    for f, s in tab[-5:]:
        p("     strato %2d : %6.2f%%  (%d righe)" % (s, 100.0 * f, righe_per_strato[s]))

    p("")
    p("(c) TEMPO RECUPERABILE  (la lane E' il cammino critico: join ~ 0)")
    p("    ms per esperto-riga sulla lane = %.3f  (= %.2f ms/lavoro / k=%d)"
      % (MS_PER_ESPERTO_RIGA, CALCOLO_LANE_MS_PER_LAVORO, K_CPU_NOMINALE))
    p("    REGOLA 1: K = min(k_cpu, non_residenti) -> si tolgono TUTTI gli sprecati")
    calcolo_tot_ms = cpu_tot * MS_PER_ESPERTO_RIGA
    risp_ms = sprecati_tot * MS_PER_ESPERTO_RIGA
    p("      calcolo lane nella traccia : %.0f ms (%d x %.3f)"
      % (calcolo_tot_ms, cpu_tot, MS_PER_ESPERTO_RIGA))
    p("      risparmio                  : %.0f ms = %.2f%% del calcolo lane"
      % (risp_ms, 100.0 * risp_ms / calcolo_tot_ms))
    calcolo_banco_ms = LAVORI * CALCOLO_LANE_MS_PER_LAVORO
    risp_banco_ms = calcolo_banco_ms * frazione
    p("      SCALA AL BANCO (par.58-59: %d lavori, %.0f s decode):" % (LAVORI, DECODE_S))
    p("        calcolo lane sul banco : %.0f ms su %.0f ms di parete = %.2f%%"
      % (calcolo_banco_ms, DECODE_S * 1000, 100.0 * calcolo_banco_ms / (DECODE_S * 1000)))
    p("        risparmio              : %.0f ms = %.3f%% della parete"
      % (risp_banco_ms, 100.0 * risp_banco_ms / (DECODE_S * 1000)))
    guad = risp_banco_ms / (DECODE_S * 1000 - risp_banco_ms)
    p("        guadagno t/s           : %+.3f%%   [risp / (parete - risp)]"
      % (100.0 * guad))

    return dict(meta=meta, n_righe=n_righe, k=k, ne0=ne0, isto_miss=isto_miss,
                sprecati=sprecati_tot, cpu_tot=cpu_tot, frazione=frazione,
                gruppi=gruppi, righe=righe, calcolo_banco_ms=calcolo_banco_ms)


def freetoken(res, out=sys.stdout):
    """q*/(m-q*) = BP/(BH-BP)  =>  q* = m * BP/BH."""
    p = lambda *a: print(*a, file=out)
    gruppi = res["gruppi"]
    k = res["k"]
    fq = BP_GBS / BH_GBS
    p("")
    p("(c-bis) REGOLA q* di FreeToken sui SOLI MISS")
    p("    q*/(m-q*) = BP/(BH-BP) = %.0f/(%.0f-%.0f) = %.4f  =>  q* = m * BP/BH = m * %.4f"
      % (BP_GBS, BH_GBS, BP_GBS, BP_GBS / (BH_GBS - BP_GBS), fq))

    tot_m = 0
    tot_righe_ft = 0.0
    tot_copie_ft = 0.0
    tot_copie_oggi = 0
    tot_cpu_oggi = 0
    isto_m = collections.Counter()
    for g in gruppi:
        dom = collections.Counter()
        for r in g:
            for j in range(r.n_esp):
                if r.stati[j] == 0:
                    dom[(r.strato, r.ids[j])] += 1
        m = len(dom)
        isto_m[m] += 1
        tot_m += m
        tot_cpu_oggi += k * len(g)
        # OGGI: la CPU assorbe (per riga) i miss in testa; le chiavi miss NON
        # coperte da nessuna riga CPU vanno in copia. Approssimazione onesta:
        # tutte le chiavi miss del gruppo generano una copia se la GPU le vede.
        # Contiamo le chiavi miss che restano alla lane GPU.
        coperte = set()
        for r in g:
            pm = perm_sota(r.stati, r.n_esp)
            for j in pm[:k]:
                if r.stati[j] == 0:
                    coperte.add((r.strato, r.ids[j]))
        # una chiave e' copiata se almeno una riga la domanda in lane GPU
        copiate = set()
        for r in g:
            pm = perm_sota(r.stati, r.n_esp)
            for j in pm[k:]:
                if r.stati[j] == 0:
                    copiate.add((r.strato, r.ids[j]))
        tot_copie_oggi += len(copiate)
        if m == 0:
            continue
        q = m * fq
        n_cpu_chiavi = m - q
        # la CPU prende le chiavi MENO domandate: minimizza gli esperti-riga
        ordinate = sorted(dom.values())
        presi, rimane = 0.0, n_cpu_chiavi
        for d in ordinate:
            if rimane <= 0:
                break
            quota = min(1.0, rimane)
            presi += quota * d
            rimane -= quota
        tot_righe_ft += presi
        tot_copie_ft += q
    n_g = len(gruppi)
    p("    gruppi (strato x passo forward)   : %d" % n_g)
    p("    miss UNICI per gruppo m           : media %.3f  isto %s"
      % (tot_m / n_g, dict(sorted(isto_m.items()))))
    p("")
    p("    esperti-RIGA alla CPU  OGGI       : %d" % tot_cpu_oggi)
    p("    esperti-RIGA alla CPU  con q*     : %.0f" % tot_righe_ft)
    d_righe = tot_righe_ft - tot_cpu_oggi
    p("    DELTA lane                        : %+.0f esperti-riga = %+.0f ms di calcolo"
      % (d_righe, d_righe * MS_PER_ESPERTO_RIGA))
    p("    copie  OGGI (chiavi miss in lane GPU): %d  = %.0f ms"
      % (tot_copie_oggi, tot_copie_oggi * MS_COPIA))
    p("    copie  con q*                     : %.0f  = %.0f ms"
      % (tot_copie_ft, tot_copie_ft * MS_COPIA))
    d_copie = tot_copie_ft - tot_copie_oggi
    p("    DELTA copie                       : %+.0f = %+.0f ms di trasporto"
      % (d_copie, d_copie * MS_COPIA))
    p("    BILANCIO q* (lane + trasporto)    : %+.0f ms sulla traccia"
      % (d_righe * MS_PER_ESPERTO_RIGA + d_copie * MS_COPIA))
    return dict(tot_m=tot_m, tot_righe_ft=tot_righe_ft, tot_cpu_oggi=tot_cpu_oggi,
                tot_copie_ft=tot_copie_ft, tot_copie_oggi=tot_copie_oggi, n_g=n_g)


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print("=" * 78)
        res = analizza(f)
        freetoken(res)
        print()
