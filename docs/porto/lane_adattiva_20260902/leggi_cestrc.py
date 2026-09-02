#!/usr/bin/env python3
"""Lettore indipendente del formato traccia route del fork (magic CESTRC2).

Scritto da zero: NON importa analyze_route_trace.py. La deduzione del layout
e' verificata dai controlli in `verifica()` (id in 0..255, n_esperti==6,
somma pesi ~1, ordine progressivo, gruppi di righe coerenti).

Layout dedotto (little endian):
  HEADER 36 B : 8s magic ("CESTRC2\0") + 7 x uint32
                [version, record_size, n_record, totale, capacita, slot, esperti]
  RECORD 64 B : <I h B B B B H 6h 6B 6B 4x 6f>
                ordine(u32) strato(i16) riga(u8) n_tok(u8) k_cpu(u8)
                n_esperti(u8) riservato(u16)
                ids(6xi16) stati(6xu8) fork(6xu8) pad(4) pesi(6xf32)
"""
import struct, sys, collections
from pathlib import Path

HEADER = struct.Struct("<8s7I")
RECORD = struct.Struct("<IhBBBBH6h6B6B4x6f")
assert HEADER.size == 36 and RECORD.size == 64


class Riga:
    __slots__ = ("ordine", "strato", "riga", "n_tok", "k_cpu", "n_esp",
                 "ids", "stati", "fork", "pesi")

    def __init__(self, v):
        (self.ordine, self.strato, self.riga, self.n_tok, self.k_cpu,
         self.n_esp, _ris) = v[:7]
        n = self.n_esp
        self.ids = tuple(v[7:13])[:n]
        self.stati = tuple(v[13:19])[:n]
        self.fork = tuple(v[19:25])[:n]
        self.pesi = tuple(v[25:31])[:n]


def leggi(path):
    raw = Path(path).read_bytes()
    magic, ver, rsz, n, tot, cap, slot, esperti = HEADER.unpack_from(raw)
    if magic.rstrip(b"\0") != b"CESTRC2":
        raise ValueError("magic inatteso: %r" % magic)
    if rsz != RECORD.size:
        raise ValueError("record_size %d != %d dedotto" % (rsz, RECORD.size))
    atteso = HEADER.size + n * rsz
    if len(raw) != atteso:
        raise ValueError("taglia %d != %d attesa" % (len(raw), atteso))
    meta = dict(version=ver, record_size=rsz, n_record=n, totale=tot,
                capacita=cap, slot=slot, esperti=esperti)
    righe = [Riga(RECORD.unpack_from(raw, HEADER.size + i * rsz)) for i in range(n)]
    return meta, righe


def verifica(meta, righe, out=sys.stdout):
    p = lambda *a: print(*a, file=out)
    p("META:", meta)
    p("record letti:", len(righe))
    # 1) id in 0..n_esperti-1
    ids = [e for r in righe for e in r.ids]
    p("id: min=%d max=%d  (atteso 0..%d)" % (min(ids), max(ids), meta["esperti"] - 1))
    fuori = sum(1 for e in ids if e < 0 or e >= meta["esperti"])
    p("id fuori intervallo:", fuori)
    # 2) strati
    strati = sorted({r.strato for r in righe})
    p("strati distinti: %d  min=%d max=%d" % (len(strati), strati[0], strati[-1]))
    p("  elenco:", strati)
    # 3) n_esperti
    p("n_esperti:", collections.Counter(r.n_esp for r in righe))
    # 4) k_cpu / n_tok
    p("k_cpu:", collections.Counter(r.k_cpu for r in righe))
    p("n_tok:", collections.Counter(r.n_tok for r in righe))
    # 5) somma pesi (prova che 6f sono i pesi del router, normalizzati)
    import statistics
    somme = [sum(w for w in r.pesi if w >= 0.0) for r in righe[:5000]]
    p("somma pesi (primi 5000): media=%.6f min=%.6f max=%.6f"
      % (statistics.fmean(somme), min(somme), max(somme)))
    # 6) ordine progressivo
    ok = all(righe[i].ordine == i for i in range(len(righe)))
    p("campo `ordine` == indice del record per tutti:", ok)
    # 7) gruppi (riga 0..n_tok-1 consecutivi, stesso strato)
    rotti, gruppi, i = 0, 0, 0
    while i < len(righe):
        n = righe[i].n_tok
        g = righe[i:i + n]
        if len(g) != n or any(x.strato != g[0].strato for x in g) or \
           [x.riga for x in g] != list(range(n)):
            rotti += 1
            i += 1
        else:
            gruppi += 1
            i += n
    p("gruppi (strato,taglia) coerenti: %d  rotti: %d" % (gruppi, rotti))
    # 8) istogrammi stati e fork -> prova che 6B/6B sono classe e destinazione
    p("istogramma STATI (classe residenza al momento della partizione):",
      dict(sorted(collections.Counter(s for r in righe for s in r.stati).items())))
    p("istogramma FORK  (maschera di corsia):",
      dict(sorted(collections.Counter(f for r in righe for f in r.fork).items())))
    # fork per posizione
    for pos in range(6):
        c = collections.Counter(r.fork[pos] for r in righe if r.n_esp > pos)
        p("  fork[pos=%d]: %s" % (pos, dict(sorted(c.items()))))
    return strati


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print("=" * 78)
        print(f)
        print("=" * 78)
        m, r = leggi(f)
        verifica(m, r)
        print()
