"""Adaptive-K via COPERTURA di massa-gate (idea SPEX/utente). Invece di fissare K,
fissa una copertura COV% della massa-gate osservata e lascia che K_layer sia la
conseguenza: per ogni layer, rank esperti per massa cumulata, tieni finche' la
cumulata copre COV% della massa totale del layer.

K diventa un OUTPUT (auto-scala con la larghezza del task), non un input.

Output: file DS4_REAP_MASK_FILE (righe "<layer> <expert>" = POTATO) + stampa K-auto
medio/min/max. Uso: python build_coverage_mask.py <route.csv> <out_mask.txt> <COV%> [n_expert]
"""
import csv
import sys
from collections import defaultdict

route = sys.argv[1]
out = sys.argv[2]
COV = float(sys.argv[3]) / 100.0
n_expert = int(sys.argv[4]) if len(sys.argv) > 4 else 256

mass = defaultdict(lambda: defaultdict(float))
count = defaultdict(lambda: defaultdict(int))
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
            if len(r) >= 15:
                try:
                    mass[layer][e] += float(r[9 + s]); have_weights = True
                except (ValueError, IndexError):
                    pass

score = mass if have_weights else count
layers = sorted(score)
if not layers:
    raise SystemExit(f"ERRORE: nessun routing letto da {route}")
ks = []
with open(out, "w", newline="\n") as f:
    for l in layers:
        ranked = sorted(score[l], key=lambda e: -score[l][e])
        tot = sum(score[l][e] for e in ranked)
        keep = set()
        acc = 0.0
        for e in ranked:
            if tot > 0 and acc / tot >= COV and keep:
                break
            keep.add(e); acc += score[l][e]
        ks.append(len(keep))
        for e in range(n_expert):
            if e not in keep:
                f.write(f"{l} {e}\n")

avg = sum(ks) / len(ks)
print(f"coverage {COV*100:.0f}% (rank {'massa' if have_weights else 'freq'}): "
      f"K-auto medio {avg:.1f}/layer (min {min(ks)} max {max(ks)}) su {len(layers)} layer")
