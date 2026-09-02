#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""(A) estrapolazione dello SPRECO al regime di produzione (623 slot, colpi
67,2% per LEDGER_25 par.58-59), usando la variazione INTERNA alla traccia:
ogni strato ha un tasso di colpi diverso, e la coppia (colpi, spreco) da' la
curva empirica -- che porta dentro la CLUSTERIZZAZIONE vera della residenza,
cosa che ne' la binomiale ne' una LRU giocattolo sanno riprodurre.
"""
import collections, sys, math
from leggi_cestrc import leggi

K = 2


def perm_sota(stati, ne0):
    p = []
    for fase in range(4):
        for i in range(ne0):
            if stati[i] == fase:
                p.append(i)
    return p


def punti(righe, chiave):
    """chiave(riga)->gruppo. Ritorna [(colpi, spreco, n_righe)] per gruppo."""
    agg = collections.defaultdict(lambda: [0, 0, 0])   # res, spreco, righe
    for r in righe:
        g = agg[chiave(r)]
        g[0] += sum(1 for s in r.stati if s != 0)
        g[1] += max(0, K - sum(1 for s in r.stati if s == 0))
        g[2] += 1
    return [(res / (n * 6), spr / (n * K), n) for res, spr, n in agg.values() if n > 0]


def binomiale(h):
    return (2 * h ** 6 + 6 * h ** 5 * (1 - h)) / 2.0


def regressione(pts):
    """minimi quadrati pesati sul LOGIT dello spreco contro i colpi."""
    sw = sx = sy = sxx = sxy = 0.0
    for h, s, n in pts:
        if s <= 0.0 or s >= 1.0:
            continue
        y = math.log(s / (1 - s))
        w = float(n)
        sw += w; sx += w * h; sy += w * y; sxx += w * h * h; sxy += w * h * y
    b = (sw * sxy - sx * sy) / (sw * sxx - sx * sx)
    a = (sy - b * sx) / sw
    return a, b


def main(path):
    meta, righe = leggi(path)
    print("### %s  (slot %d)" % (path, meta["slot"]))
    h_glob = sum(1 for r in righe for s in r.stati if s != 0) / (len(righe) * 6)
    s_glob = sum(max(0, K - sum(1 for s in r.stati if s == 0)) for r in righe) / (len(righe) * K)
    print("globale: colpi %.4f  spreco %.4f   (binomiale iid darebbe %.4f)"
          % (h_glob, s_glob, binomiale(h_glob)))
    print("  => la residenza e' CLUSTERIZZATA: spreco reale / binomiale = %.2fx"
          % (s_glob / binomiale(h_glob)))
    print("")

    # punti per STRATO
    pts = punti(righe, lambda r: r.strato)
    pts = [p for p in pts if 0.0 < p[1] < 1.0]
    a, b = regressione(pts)
    print("regressione logit(spreco) = %.4f + %.4f * colpi   (%d strati)" % (a, b, len(pts)))
    print("")
    print("  colpi | spreco previsto | osservato (strati vicini)")
    for h in (0.40, 0.50, 0.5663, 0.60, 0.65, 0.672, 0.70):
        y = a + b * h
        s = 1 / (1 + math.exp(-y))
        vicini = [p[1] for p in pts if abs(p[0] - h) < 0.02]
        oss = ("%.4f (n=%d)" % (sum(vicini) / len(vicini), len(vicini))) if vicini else "-"
        marca = "   <== PRODUZIONE 623 slot" if abs(h - 0.672) < 1e-6 else ""
        print("  %.4f |     %.4f      | %s%s" % (h, s, oss, marca))
    print("")
    # tabella per strato, ordinata per colpi
    print("dettaglio per strato (colpi, spreco):")
    tab = sorted(zip([p[0] for p in pts], [p[1] for p in pts]))
    for i in range(0, len(tab), 1):
        h, s = tab[i]
        print("   %.4f  %.4f" % (h, s), end="\n" if i % 3 == 2 else "")
    print("")
    return a, b, h_glob, s_glob


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print("=" * 78)
        main(f)
        print()
