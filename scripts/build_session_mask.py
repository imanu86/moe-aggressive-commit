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

mass = defaultdict(lambda: defaultdict(float))   # layer -> expert -> massa-gate (se pesi)
count = defaultdict(lambda: defaultdict(int))    # layer -> expert -> frequenza
seen = defaultdict(set)
have_weights = False
with open(route) as f:
    rd = csv.reader(f)
    next(rd, None)
    for r in rd:
        if len(r) < 9:
            continue
        try:
            layer, n = int(r[1]), int(r[2])
        except ValueError:
            continue
        for s in range(min(n, 6)):
            try:
                e = int(r[3 + s])
            except (ValueError, IndexError):
                continue
            if e < 0:
                continue
            count[layer][e] += 1
            seen[layer].add(e)
            if len(r) >= 15:  # pesi presenti (w0..w5)
                try:
                    mass[layer][e] += float(r[9 + s]); have_weights = True
                except (ValueError, IndexError):
                    pass

score = mass if have_weights else count  # rank per massa-gate, altrimenti per frequenza
layers = sorted(seen)
if not layers:
    raise SystemExit(f"ERRORE: nessun routing letto da {route} (trace vuoto?)")
covered = []
with open(out, "w", newline="\n") as f:
    for l in layers:
        ranked = sorted(seen[l], key=lambda e: -score[l][e])
        keep = set(ranked[:K])
        covered.append(len(keep))
        for e in range(n_expert):
            if e not in keep:
                f.write(f"{l} {e}\n")

avg = sum(covered) / len(covered) if covered else 0
full = sum(1 for c in covered if c >= K)
distinct = [len(v) for v in seen.values()]
print(f"session-mask keep-{K} (rank per {'massa-gate' if have_weights else 'frequenza'}): "
      f"{len(layers)} layer, keep medio {avg:.1f}/{K} ({full}/{len(layers)} pieni). "
      f"esperti distinti visti/layer: min {min(distinct)} max {max(distinct)}")
