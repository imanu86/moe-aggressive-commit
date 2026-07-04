"""HOT/COLD partition + FOOTPRINT-UNION sotto vari schemi di precisione, dai trace reali.
Per q30/q235/ds2lite domain+general: per ogni layer HOT = expert che coprono il 90% degli slot,
COLD = il resto-ma-toccati (touched meno hot). Media sui layer -> hot_frac, cold_frac (frazione di E).
Poi traduce alla geometria V4 (256 exp/layer, 43 layer) e calcola il FOOTPRINT-UNION in GB sotto
4 schemi di precisione, usando 99%-coverage per la union completa e 90% per l'hot-set (bracket).
Input: traces_*.npz con experts[T,L,k] (+ n_experts). Nessun pod/GPU."""
import numpy as np, glob, os, re

# ---- geometria V4 ----
V4_E, V4_L = 256, 43
BUDGET_GB = 44.0  # VRAM 12 + RAM 32

# per-expert footprint (MB) per schema di precisione, dati dal brief
MB = {
    'S1_fp4':        {'hot': 12.58, 'cold': 12.58},   # fp4 uniforme
    'S2_dwarf2':     {'hot': 7.23,  'cold': 7.23},    # dwarf 2-bit uniforme
    'S3_hot2_cold1p58': {'hot': 7.23, 'cold': 5.03 - (7.23 - 7.23)},  # placeholder, override sotto
    'S4_hot2_cold1': {'hot': 7.23,  'cold': 3.15},
}
# NB: i valori 12.58/7.23/5.03/3.15 nel brief sono il footprint per-expert COMBINATO
# (o meglio la size media per lo schema). Interpretazione robusta: sono i valori
# per-expert dello schema. Definisco esplicitamente hot-MB e cold-MB per schema:
#   S1 fp4 uniforme:            hot=cold=12.58
#   S2 dwarf 2-bit uniforme:    hot=cold=7.23
#   S3 temp-mix:               hot=7.23 (2-bit),  cold=5.03  (1.58-bit)
#   S4 temp-mix:               hot=7.23 (2-bit),  cold=3.15  (1-bit)
SCHEMES = {
    'S1': {'hot': 12.58, 'cold': 12.58},
    'S2': {'hot': 7.23,  'cold': 7.23},
    'S3': {'hot': 7.23,  'cold': 5.03},
    'S4': {'hot': 7.23,  'cold': 3.15},
}

def load_experts(path):
    z = np.load(path)
    e = z['experts']
    E = int(z['n_experts']) if 'n_experts' in z else int(e.max()) + 1
    return e.astype(np.int64), E

def hotcold(e, E, hot_p=0.90, union_p=0.99):
    """per ogni layer: HOT=#exp per coprire hot_p degli slot; UNION=#exp per union_p;
    COLD=UNION-HOT (resto-ma-toccati entro la union-bracket). Media sui layer, frazione di E."""
    T, L, k = e.shape
    hot_f, cold_f, union_f, touched_f = [], [], [], []
    for l in range(L):
        ids = e[:, l, :].ravel()
        cnt = np.bincount(ids, minlength=E).astype(np.float64)
        tot = cnt.sum()
        if tot == 0:
            continue
        s = np.sort(cnt)[::-1]
        cum = np.cumsum(s) / tot
        n_hot   = int(np.searchsorted(cum, hot_p)) + 1
        n_union = int(np.searchsorted(cum, union_p)) + 1
        n_touch = int((cnt > 0).sum())
        n_hot   = min(n_hot, n_touch)
        n_union = min(n_union, n_touch)
        n_cold  = max(n_union - n_hot, 0)   # cold = resto-ma-toccati DENTRO la union bracket
        hot_f.append(n_hot / E)
        cold_f.append(n_cold / E)
        union_f.append(n_union / E)
        touched_f.append(n_touch / E)
    return (float(np.mean(hot_f)), float(np.mean(cold_f)),
            float(np.mean(union_f)), float(np.mean(touched_f)))

def v4_counts(hot_frac, cold_frac):
    """frazioni -> #expert per layer nella geometria V4."""
    hot_v4  = hot_frac  * V4_E
    cold_v4 = cold_frac * V4_E
    return hot_v4, cold_v4

def footprint_gb(hot_v4, cold_v4, scheme):
    mb = hot_v4 * V4_L * scheme['hot'] + cold_v4 * V4_L * scheme['cold']
    return mb / 1000.0

files = sorted(glob.glob('D:/models/spex/traces_*.npz'))
groups = {}
for f in files:
    b = os.path.basename(f)
    m = re.match(r'traces_(q30|q235|ds2lite)_(domain|general)\.npz', b)
    if not m:
        continue
    groups.setdefault(m.group(1), {})[m.group(2)] = f

print(f"V4 geometry: {V4_E} exp/layer x {V4_L} layer = {V4_E*V4_L} expert totali")
print(f"budget = {BUDGET_GB} GB (VRAM12+RAM32)\n")
print("HOT = exp/layer che coprono il 90% degli slot ; UNION = 99% ; COLD = union-hot (resto-ma-toccati)\n")

# raccogli hot_frac/cold_frac per model+wl e la union-DOMINIO per il footprint
rows = []
per_model = {}
hdr = f"{'model':8} {'wl':8} {'E':>4} | {'hot_frac':>9} {'cold_frac':>9} {'union_frac':>10} {'touch_frac':>10}"
print(hdr); print('-'*len(hdr))
for model in ['q30', 'q235', 'ds2lite']:
    wls = groups.get(model, {})
    per_model[model] = {}
    for wl in ['domain', 'general']:
        if wl not in wls:
            continue
        e, E = load_experts(wls[wl])
        hf, cf, uf, tf = hotcold(e, E)
        per_model[model][wl] = dict(hf=hf, cf=cf, uf=uf, tf=tf, E=E)
        print(f"{model:8} {wl:8} {E:>4} | {hf:>9.3f} {cf:>9.3f} {uf:>10.3f} {tf:>10.3f}")

# media hot_frac/cold_frac su tutti i model x wl (come richiesto: media sui layer -> qui media anche sui trace)
all_hf = [v['hf'] for m in per_model.values() for v in m.values()]
all_cf = [v['cf'] for m in per_model.values() for v in m.values()]
HOT_FRAC = float(np.mean(all_hf))
COLD_FRAC = float(np.mean(all_cf))
print(f"\nMEDIA (tutti model x wl):  hot_frac={HOT_FRAC:.3f}  cold_frac={COLD_FRAC:.3f}")

# regime "large-MoE" (q30+q235, E=128, vicino a V4 E=256): ds2lite E=64 topk6 tocca ~100% e
# gonfia le frazioni, non e' rappresentativo. Riportiamo anche questa media.
big = ['q30', 'q235']
big_hf = float(np.mean([per_model[m][w]['hf'] for m in big for w in per_model[m]]))
big_cf = float(np.mean([per_model[m][w]['cf'] for m in big for w in per_model[m]]))
print(f"MEDIA large-MoE (q30+q235, E=128): hot_frac={big_hf:.3f} cold_frac={big_cf:.3f}")

# --- FOOTPRINT-UNION per la union-DOMINIO (regime large-MoE q30+q235) ---
# usiamo la union-dominio: hot(90%)+cold(fino a 99%) del workload DOMAIN, mediati sui model large-MoE
dom_hf = float(np.mean([per_model[m]['domain']['hf'] for m in big if 'domain' in per_model[m]]))
dom_cf = float(np.mean([per_model[m]['domain']['cf'] for m in big if 'domain' in per_model[m]]))
print(f"union-DOMINIO (media model):  hot_frac={dom_hf:.3f}  cold_frac={dom_cf:.3f}")
hot_v4, cold_v4 = v4_counts(dom_hf, dom_cf)
print(f"  -> V4: hot={hot_v4:.1f} exp/layer, cold={cold_v4:.1f} exp/layer, "
      f"union={hot_v4+cold_v4:.1f}/{V4_E} exp/layer\n")

print(f"{'scheme':30} {'hot_MB':>7} {'cold_MB':>8} | {'union_GB':>9} {'fits44':>7} {'GB_left':>8}")
print('-'*80)
out_numbers = {'hot_frac': round(HOT_FRAC,4), 'cold_frac': round(COLD_FRAC,4),
               'hot_frac_bigMoE': round(big_hf,4), 'cold_frac_bigMoE': round(big_cf,4),
               'dom_hot_frac': round(dom_hf,4), 'dom_cold_frac': round(dom_cf,4)}
names = {'S1':'S1 fp4 uniforme',
         'S2':'S2 dwarf 2-bit uniforme',
         'S3':'S3 temp-mix hot2b/cold1.58b',
         'S4':'S4 temp-mix hot2b/cold1b'}
table_lines = []
for key in ['S1','S2','S3','S4']:
    sc = SCHEMES[key]
    gb = footprint_gb(hot_v4, cold_v4, sc)
    fits = gb < BUDGET_GB
    left = BUDGET_GB - gb
    print(f"{names[key]:30} {sc['hot']:>7.2f} {sc['cold']:>8.2f} | {gb:>9.2f} {str(fits):>7} {left:>8.2f}")
    table_lines.append((names[key], sc['hot'], sc['cold'], gb, fits, left))
    out_numbers[f'union_gb_{key}'] = round(gb, 2)
    out_numbers[f'fits44_{key}'] = bool(fits)
    out_numbers[f'gb_left_{key}'] = round(left, 2)

import json
print("\nNUMBERS=" + json.dumps(out_numbers))
