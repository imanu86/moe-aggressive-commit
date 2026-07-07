"""Genera mask runtime keep-K (reap-saliency + controllo random) dalla salienza
gia' calcolata in reap_mask_coding_k91.json.

Formato output (DS4_REAP_MASK_FILE, patch 0011): righe "<layer> <expert>" = esperto
POTATO (bias -1e9). Per keep-K scrivo i (n_expert - K) esperti FUORI dai top-K per
salienza, per ogni layer MoE.

Uso: python make_keepK_mask.py <k91.json> <outdir> 8 12 16 20 23 28 32
Produce, per ogni K: reap_keepK_<K>.runtime.txt e random_keepK_<K>_seed0.runtime.txt
"""
import json
import random
import sys

def main():
    src = sys.argv[1]
    outdir = sys.argv[2].rstrip("/")
    ks = [int(x) for x in sys.argv[3:]] or [8, 12, 16, 20, 23, 28, 32]
    d = json.load(open(src))
    sal = d["saliency"]           # {layer: {expert: score}}
    n_expert = d["n_expert"]
    layers = sorted(int(l) for l in sal)
    # ranking per layer: esperti ordinati per salienza desc, tie-break su indice
    ranked = {}
    for l in layers:
        s = sal[str(l)]
        order = sorted(range(n_expert), key=lambda e: (-float(s.get(str(e), 0.0)), e))
        ranked[l] = order
    for K in ks:
        # REAP: potati = tutti tranne i top-K per salienza
        pr = f"{outdir}/reap_keepK_{K}.runtime.txt"
        with open(pr, "w", newline="\n") as f:
            n = 0
            for l in layers:
                keep = set(ranked[l][:K])
                for e in range(n_expert):
                    if e not in keep:
                        f.write(f"{l} {e}\n"); n += 1
        # RANDOM: keep-K a caso (seed fisso), stessa cardinalita'
        rng = random.Random(1000 + K)
        prr = f"{outdir}/random_keepK_{K}_seed0.runtime.txt"
        with open(prr, "w", newline="\n") as f:
            nr = 0
            for l in layers:
                keep = set(rng.sample(range(n_expert), K))
                for e in range(n_expert):
                    if e not in keep:
                        f.write(f"{l} {e}\n"); nr += 1
        exp = len(layers) * (n_expert - K)
        assert n == exp == nr, f"K{K}: reap {n} random {nr} atteso {exp}"
        print(f"K={K:2d}: keep {K}/{n_expert} su {len(layers)} layer -> {n} righe potate/mask "
              f"[reap_keepK_{K}.runtime.txt, random_keepK_{K}_seed0.runtime.txt]")

if __name__ == "__main__":
    main()
