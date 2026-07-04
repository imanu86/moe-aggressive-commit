"""REAP/fine-tune union-reduction sim (OFFLINE, gratis, su hidden_scores con gli score del router).
Domanda: quanto un REAP sul dominio (prune expert a bassa saliency + re-route ai superstiti) riduce
l'UNION degli expert, e a quale COSTO di disruption del routing (proxy di qualita' PRE-healing)?
Metriche per keep-ratio rho:
  - reroute_rate: frazione di scelte top-k originali che cadono su expert PRUNATI (vanno ri-assegnate)
  - mass_retained: frazione di massa-gate (softmax) che resta sui superstiti (alta = poca disruption)
  - miss@C (static hot-cache): frazione di scelte non nei C expert piu' caldi/layer, base vs prunato+reroute
  - footprint V4 a 2-bit e se entra in VRAM12 / nei 44GB
REAP reale aggiunge HEALING (fine-tune) che recupera i reroute -> reroute_rate = LIMITE SUPERIORE del danno.
Uso: python reap_union_sim.py
"""
import numpy as np, glob, os

V4_E, V4_L = 256, 43
EXPERT_2BIT_MB = 3*2048*2048*2.3/8/1e6   # expert reale 12.6M param (hidden-exp 2048), 2.3 bpw dwarf -> MB
VRAM_GB, BUDGET_GB = 12.0, 44.0

def softmax(x):
    x = x - x.max(-1, keepdims=True)
    e = np.exp(x); return e/(e.sum(-1, keepdims=True)+1e-9)

def analyze(path, topk=8, caps=(4,8,16)):
    z = np.load(path)
    sc = z['scores'].astype(np.float32)          # [T, L, E]
    T, L, E = sc.shape
    probs = softmax(sc)                            # gate prob per expert
    sal = probs.sum(0)                             # [L, E] saliency = massa-gate totale per expert (REAP-style)
    orig_top = np.argpartition(sc, -topk, axis=-1)[..., -topk:]   # [T, L, topk] scelte originali
    out = {'T': T, 'L': L, 'E': E, 'rows': {}}
    # cache statica "hot" per il miss-proxy (i C expert a saliency piu' alta per layer)
    order = np.argsort(-sal, axis=1)               # [L, E] ranking per layer
    for rho in (1.0, 0.5, 0.375, 0.25, 0.125):
        K = max(1, int(round(rho*E)))
        keep = np.zeros((L, E), bool)
        for l in range(L):
            keep[l, order[l, :K]] = True
        # reroute: quante scelte originali sono su expert prunati
        kept_of_orig = keep[np.arange(L)[None, :, None], orig_top]   # [T,L,topk] bool
        reroute_rate = float((~kept_of_orig).mean())
        # massa-gate trattenuta dai superstiti
        mass_ret = float((probs * keep[None]).sum(-1).mean())
        # miss statico @C con re-routing: dopo prune, ricalcola top-k sui superstiti, poi miss vs hot-cache di taglia C (tra i superstiti)
        sc_masked = np.where(keep[None], sc, -1e30)
        new_top = np.argpartition(sc_masked, -topk, axis=-1)[..., -topk:]    # [T,L,topk]
        miss = {}
        for C in caps:
            Cc = min(C, K)
            hot = np.zeros((L, E), bool)
            for l in range(L):
                surv = order[l][keep[l, order[l]]]      # superstiti in ordine di saliency
                hot[l, surv[:Cc]] = True
            inhot = hot[np.arange(L)[None, :, None], new_top]
            miss[C] = float((~inhot).mean())
        # footprint V4 a 2-bit con questa frazione di union (rho * union-dominio)
        # union-dominio base (99%cov) ~ 0.64*E su Qwen -> qui usiamo rho come frazione di modello mantenuta
        v4_kept_per_layer = rho * V4_E
        fp_gb = v4_kept_per_layer * V4_L * EXPERT_2BIT_MB / 1000.0
        out['rows'][rho] = dict(K=K, reroute=reroute_rate, mass_ret=mass_ret, miss=miss,
                                v4_fp_gb=fp_gb, fits_vram=fp_gb < VRAM_GB, fits44=fp_gb < BUDGET_GB)
    return out

files = {}
for f in sorted(glob.glob('D:/models/spex/hidden_scores_q30_*.npz')):
    tag = os.path.basename(f).replace('hidden_scores_q30_','').replace('.npz','')
    files[tag] = f

print(f"expert V4 2-bit = {EXPERT_2BIT_MB:.2f} MB ; union V4 completa 2-bit = {V4_E*V4_L*EXPERT_2BIT_MB/1000:.1f} GB ; VRAM {VRAM_GB} / budget {BUDGET_GB} GB")
print("REAP = prune per saliency + reroute ai superstiti. reroute_rate = LIMITE SUP. del danno (healing lo recupera).\n")
for tag in ['dom','gen']:
    if tag not in files: continue
    r = analyze(files[tag])
    print(f"================ q30 {tag}  (T={r['T']} L={r['L']} E={r['E']}) ================")
    print(f"{'keep':>6} {'K':>4} {'reroute':>8} {'mass_ret':>9} {'miss@4':>7} {'miss@8':>7} {'miss@16':>8} {'V4_2bit_GB':>11} {'VRAM12':>7} {'44GB':>5}")
    for rho, d in r['rows'].items():
        print(f"{rho:>6.3f} {d['K']:>4} {d['reroute']*100:>7.1f}% {d['mass_ret']*100:>8.1f}% "
              f"{d['miss'][4]*100:>6.1f}% {d['miss'][8]*100:>6.1f}% {d['miss'][16]*100:>7.1f}% "
              f"{d['v4_fp_gb']:>11.1f} {('YES' if d['fits_vram'] else 'no'):>7} {('YES' if d['fits44'] else 'no'):>5}")
    print()
print("Nota: keep=1.0 e' il modello intero (baseline). reroute a keep basso = quanti token perdono il loro expert")
print("      preferito (li recupera l'healing/fine-tune). mass_ret alto = poca disruption. V4_2bit_GB = footprint")
print("      union a 2-bit se il modello dominio mantiene solo rho*256 expert/layer.")
