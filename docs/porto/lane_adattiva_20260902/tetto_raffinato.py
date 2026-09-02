#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""(A) raffinamento: modello di costo UNICO-ESPERTO vs ESPERTO-RIGA, e
estrapolazione a 623 slot con una LRU chiusa sul ciclo (installa solo i miss
della lane GPU, come kern_fj_copia).
"""
import collections, sys
from leggi_cestrc import leggi

K = 2


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


def modello_costo(gruppi, statifn, out=sys.stdout):
    """statifn(riga) -> tupla di classi. Ritorna le due frazioni di risparmio."""
    p = lambda *a: print(*a, file=out)
    righe_oggi = righe_ad = 0
    unici_oggi = unici_ad = 0
    gpu_agg_righe = 0          # esperti-riga aggiunti alla lane GPU (residenti)
    gpu_agg_unici = 0
    lavori_senza_cpu = 0
    for g in gruppi:
        cpu_oggi, cpu_ad, agg = set(), set(), set()
        for r in g:
            st = statifn(r)
            pm = perm_sota(st, r.n_esp)
            testa = pm[:K]
            righe_oggi += K
            for j in testa:
                cpu_oggi.add(r.ids[j])
                if st[j] == 0:
                    cpu_ad.add(r.ids[j])
                    righe_ad += 1
                else:
                    agg.add(r.ids[j])
                    gpu_agg_righe += 1
        unici_oggi += len(cpu_oggi)
        unici_ad += len(cpu_ad)
        # un esperto e' AGGIUNTO alla GPU solo se nessuna riga lo tiene in CPU
        gpu_agg_unici += len(agg - cpu_ad)
        if not cpu_ad:
            lavori_senza_cpu += 1
    f_righe = 1.0 - righe_ad / righe_oggi
    f_unici = 1.0 - unici_ad / unici_oggi
    p("    esperti-RIGA alla CPU  : oggi %d -> adattivo %d   risparmio %.2f%%"
      % (righe_oggi, righe_ad, 100.0 * f_righe))
    p("    esperti UNICI alla CPU : oggi %d -> adattivo %d   risparmio %.2f%%"
      % (unici_oggi, unici_ad, 100.0 * f_unici))
    p("    unici per lavoro       : oggi %.3f -> adattivo %.3f"
      % (unici_oggi / len(gruppi), unici_ad / len(gruppi)))
    p("    lavori con lane CPU VUOTA (K=0 di fatto): %d / %d = %.2f%%"
      % (lavori_senza_cpu, len(gruppi), 100.0 * lavori_senza_cpu / len(gruppi)))
    p("    carico AGGIUNTO alla lane GPU: %d esperti-riga, %d esperti unici"
      % (gpu_agg_righe, gpu_agg_unici))
    p("      (tutti RESIDENTI per costruzione => ZERO byte PCIe in piu')")
    return f_righe, f_unici, gpu_agg_righe, gpu_agg_unici, len(gruppi)


class LRU:
    """Cache globale a `n_slot` slot su chiavi (strato, esperto).
    Installa SOLO i miss serviti dalla lane GPU (kern_fj_copia). I miss presi
    dalla CPU non entrano mai in VRAM."""

    def __init__(self, n_slot):
        self.n = n_slot
        self.d = collections.OrderedDict()   # chiave -> None, ordine = recency

    def dentro(self, k):
        return k in self.d

    def tocca(self, k):
        if k in self.d:
            self.d.move_to_end(k)

    def installa(self, k):
        if k in self.d:
            self.d.move_to_end(k)
            return
        if len(self.d) >= self.n:
            self.d.popitem(last=False)
        self.d[k] = None


def simula(gruppi, n_slot):
    """Ritorna, per ogni riga, la tupla di classi simulate (0 miss / 3 res)."""
    c = LRU(n_slot)
    fuori = []
    for g in gruppi:
        stati_g = []
        for r in g:
            st = tuple(0 if not c.dentro((r.strato, r.ids[j])) else 3
                       for j in range(r.n_esp))
            stati_g.append(st)
        # decisione e aggiornamento cache DOPO aver classificato tutto il gruppo
        for r, st in zip(g, stati_g):
            pm = perm_sota(st, r.n_esp)
            for j in pm[:K]:
                pass                     # lane CPU: nessuna installazione
            for j in pm[K:]:
                k = (r.strato, r.ids[j])
                if st[j] == 0:
                    c.installa(k)        # miss lane GPU -> copia + installa
                else:
                    c.tocca(k)
        fuori.append(stati_g)
    return fuori


def main(path):
    meta, righe = leggi(path)
    g = gruppi_da(righe)
    print("### %s   (slot registrati: %d)" % (path, meta["slot"]))
    print("")
    print("[1] STATI REGISTRATI dalla traccia (cache vera a %d slot)" % meta["slot"])
    reali = {id(r): r.stati for r in righe}
    fr, fu, agr, agu, nl = modello_costo(g, lambda r: reali[id(r)])
    colpi = sum(1 for r in righe for s in r.stati if s != 0) / (len(righe) * 6)
    print("    colpi cache misurati sulla traccia: %.2f%%" % (100.0 * colpi))

    for n_slot in (473, 623):
        print("")
        print("[2] LRU SIMULATA a %d slot (installa solo i miss della lane GPU)" % n_slot)
        sim = simula(g, n_slot)
        mappa = {}
        for grp, sg in zip(g, sim):
            for r, st in zip(grp, sg):
                mappa[id(r)] = st
        colpi_s = sum(1 for st in mappa.values() for s in st if s != 0) / (len(righe) * 6)
        print("    colpi simulati: %.2f%%" % (100.0 * colpi_s))
        isto = collections.Counter(sum(1 for s in st if s == 0) for st in mappa.values())
        print("    non residenti/riga: %s" % dict(sorted(isto.items())))
        r0, r1 = isto.get(0, 0), isto.get(1, 0)
        print("    righe con 0 non res: %.2f%%   con 1: %.2f%%"
              % (100.0 * r0 / len(righe), 100.0 * r1 / len(righe)))
        modello_costo(g, lambda r: mappa[id(r)])
    return


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print("=" * 78)
        main(f)
        print()
