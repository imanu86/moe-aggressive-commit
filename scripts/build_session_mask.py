"""Costruisce una session-mask keep-K dalla traccia di routing dei primi W token
(fase di osservazione wide). Rank per MASSA-GATE cumulata (somma dei pesi w0..w5
dell'esperto sul layer, sui token osservati), keep top-K per layer.

Output: file DS4_REAP_MASK_FILE (righe "<layer> <expert>" = POTATO).
Uso: python build_session_mask.py <route.csv> <out_mask.txt> <K> [n_expert=256]
Se un layer non e' stato osservato abbastanza (meno di K esperti distinti visti),
tiene tutti quelli visti (mask piu' larga li'). Stampa la copertura media.
"""
import csv
import sys
from collections import defaultdict

route = sys.argv[1]
out = sys.argv[2]
K = int(sys.argv[3])
n_expert = int(sys.argv[4]) if len(sys.argv) > 4 else 256

mass = defaultdict(lambda: defaultdict(float))  # layer -> expert -> massa
seen = defaultdict(set)
with open(route) as f:
    rd = csv.reader(f)
    next(rd, None)
    for r in rd:
        if len(r) < 15:
            continue
        try:
            layer, n = int(r[1]), int(r[2])
        except ValueError:
            continue
        for s in range(min(n, 6)):
            try:
                e = int(r[3 + s]); w = float(r[9 + s])
            except (ValueError, IndexError):
                continue
            if e < 0:
                continue
            mass[layer][e] += w
            seen[layer].add(e)

layers = sorted(mass)
covered = []
with open(out, "w", newline="\n") as f:
    for l in layers:
        ranked = sorted(mass[l], key=lambda e: -mass[l][e])
        keep = set(ranked[:K])
        covered.append(len(keep))
        for e in range(n_expert):
            if e not in keep:
                f.write(f"{l} {e}\n")

avg = sum(covered) / len(covered) if covered else 0
full = sum(1 for c in covered if c >= K)
print(f"session-mask keep-{K}: {len(layers)} layer, keep medio {avg:.1f}/{K} "
      f"({full}/{len(layers)} layer pieni). esperti distinti visti/layer: "
      f"min {min(len(v) for v in seen.values())} max {max(len(v) for v in seen.values())}")
