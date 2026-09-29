"""Riassume i campioni di CPU (100 = un core) di daily_rapido.py: il motore contro tutti gli altri processi."""
import json
import sys
from collections import defaultdict

MOTORE = {"llama-server.exe", "strata.exe"}
righe = [json.loads(r) for r in open(sys.argv[1], encoding="utf-8") if r.strip()]
tot = defaultdict(float)
altri_per_campione, motore_per_campione = [], []
for r in righe:
    a = sum(v for k, v in r["proc"].items() if k not in MOTORE and k != "System Idle Process")
    m = sum(v for k, v in r["proc"].items() if k in MOTORE)
    altri_per_campione.append(a)
    motore_per_campione.append(m)
    for k, v in r["proc"].items():
        if k != "System Idle Process":
            tot[k] += v
n = len(righe)
print("campioni: %d (%s - %s)" % (n, righe[0]["t"], righe[-1]["t"]))
print("motore: media %.2f core, max %.2f" % (sum(motore_per_campione) / n, max(motore_per_campione)))
print("altri:  media %.2f core, max %.2f, min %.2f" % (sum(altri_per_campione) / n, max(altri_per_campione),
                                                       min(altri_per_campione)))
print("per campione (altri):", " ".join("%s=%.1f" % (r["t"][3:], a) for r, a in zip(righe, altri_per_campione)))
print("medie per processo (core):")
for k, v in sorted(tot.items(), key=lambda x: -x[1])[:12]:
    print("  %-28s %.2f" % (k, v / n))
print("RAM disponibile GB: min %.1f, max %.1f" % (min(r["ram_disp_gb"] for r in righe), max(r["ram_disp_gb"] for r in righe)))
