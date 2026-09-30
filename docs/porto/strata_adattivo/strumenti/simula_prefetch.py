"""Simulazione del prefetch degli esperti da una traccia di instradamento di Strata (--dump-routing), 30/9/2026.

Record: int32 strato, int32 k, k int32 id, k float32 pesi (i pesi a 0 nelle finestre di verifica). Le finestre si
separano quando lo strato torna indietro (48 → 0). Per ogni strato una cache di C slot; confronto a pari slot:
  statica      i C esperti piu' usati dello strato (su tutta la traccia: un profilo «perfetto»);
  nucleo+coda  i (C - T) piu' usati fissi + una coda di T slot che accoglie a fine finestra i mancanti appena usati
               (via di uscita: il meno recente della coda) = prefetch per recenza nelle nostre due zone.
Stampa: colpi (per uso esperto-riga), mancanti per finestra, quanti dei mancanti erano stati instradati nelle 1/2/4/8
finestre prima, e i MB da copiare per finestra per la coda (1,69 MiB per esperto) contro il bilancio del PCIe 3.0.
Uso:  python simula_prefetch.py TRACCIA [--slot 140] [--coda 0.25]
"""
import sys
from collections import OrderedDict, defaultdict

import numpy as np

BLOB_MIB = 1.69
L = 48


def leggi(path):
    raw = np.fromfile(path, dtype=np.int32)
    i, fin = 0, []
    while i + 2 <= len(raw):
        layer, k = int(raw[i]), int(raw[i + 1])
        if k <= 0 or k > 64 or layer < 0 or layer >= L or i + 2 + 2 * k > len(raw):
            break
        fin.append((layer, raw[i + 2:i + 2 + k]))
        i += 2 + 2 * k   # gli id, poi k float32 (stessa larghezza)
    return fin


def finestre(rec):
    out, cur, prev = [], defaultdict(list), -1
    for layer, ids in rec:
        if layer < prev and cur:
            out.append(cur)
            cur = defaultdict(list)
        cur[layer].append(ids)
        prev = layer
    if cur:
        out.append(cur)
    return out


def main():
    path = sys.argv[1]
    slot = int(sys.argv[sys.argv.index("--slot") + 1]) if "--slot" in sys.argv else 140
    fcoda = float(sys.argv[sys.argv.index("--coda") + 1]) if "--coda" in sys.argv else 0.25
    rec = leggi(path)
    fin = finestre(rec)
    print("record %d, finestre %d, righe per finestra %.2f" % (len(rec), len(fin),
                                                                  len(rec) / max(1, len(fin)) / L))
    conta = np.zeros((L, 512), dtype=np.int64)
    for layer, ids in rec:
        np.add.at(conta[layer], ids, 1)
    top = [set(np.argsort(-conta[l])[:slot].tolist()) for l in range(L)]
    t = max(1, int(round(slot * fcoda)))
    nucleo = [set(np.argsort(-conta[l])[:slot - t].tolist()) for l in range(L)]
    coda = [OrderedDict() for _ in range(L)]
    usi = colpi_s = colpi_n = 0
    manc_s = manc_n = 0
    visti = [[set() for _ in range(L)] for _ in range(8)]   # instradati nelle 8 finestre precedenti
    prevedibili = {1: 0, 2: 0, 4: 0, 8: 0}
    copie = 0
    for w, f in enumerate(fin):
        nuovi = [set() for _ in range(L)]
        for l, righe in f.items():
            for ids in righe:
                for e in ids.tolist():
                    usi += 1
                    nuovi[l].add(e)
                    if e in top[l]:
                        colpi_s += 1
                    else:
                        manc_s += 1
                        for m in (1, 2, 4, 8):
                            if any(e in visti[j][l] for j in range(min(m, 8))):
                                prevedibili[m] += 1
                    if e in nucleo[l] or e in coda[l]:
                        colpi_n += 1
                        if e in coda[l]:
                            coda[l].move_to_end(e)
                    else:
                        manc_n += 1
        # a fine finestra la coda accoglie i mancanti usati (prefetch per recenza)
        for l in range(L):
            for e in nuovi[l]:
                if e not in nucleo[l] and e not in coda[l]:
                    coda[l][e] = True
                    copie += 1
                    if len(coda[l]) > t:
                        coda[l].popitem(last=False)
        visti = [nuovi] + visti[:-1]
    nf = max(1, len(fin))
    print("slot per strato %d (%d in tutto), coda %d per strato" % (slot, slot * L, t))
    print("statica:     colpi %.1f%%, mancanti per finestra %.1f" % (100.0 * colpi_s / usi, manc_s / nf))
    print("nucleo+coda: colpi %.1f%%, mancanti per finestra %.1f, copie per finestra %.1f (%.0f MiB; PCIe 3.0 a "
          "13 GB/s in 45 ms = ~560 MiB)" % (100.0 * colpi_n / usi, manc_n / nf, copie / nf, copie / nf * BLOB_MIB))
    print("mancanti della statica gia' instradati nelle ultime 1/2/4/8 finestre: " +
          " / ".join("%.0f%%" % (100.0 * prevedibili[m] / max(1, manc_s)) for m in (1, 2, 4, 8)))


if __name__ == "__main__":
    main()
