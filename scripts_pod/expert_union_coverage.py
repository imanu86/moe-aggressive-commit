"""Copertura/union degli expert per DOMINIO vs GENERALE (no fine-tune): quanto si restringe il
'modello effettivo' quando l'input e' ristretto. Per ogni layer conta quanti expert servono a
coprire 90/95/99/100% degli slot di routing, media sui layer. Traduce in GB per la geometria V4-Flash.
Input: traces_*.npz con experts[T,L,k] (+ n_experts). Nessun pod/GPU."""
import numpy as np, glob, os, re

# geometria V4-Flash per la traduzione in GB (expert fp4)
V4_E, V4_L = 256, 43
V4_EXPERT_MB = 3 * 2048 * 4096 * 0.5 / 1e6   # w1+w2+w3 SwiGLU, hidden4096/moe2048, fp4=0.5B -> MB
BUDGET_GB = 44.0  # VRAM 12 + RAM 32

def load_experts(path):
    z = np.load(path)
    e = z['experts']            # [T, L, k] int
    E = int(z['n_experts']) if 'n_experts' in z else int(e.max())+1
    dl = z['doclens'].astype(np.int64) if 'doclens' in z else None
    return e.astype(np.int64), E, dl

def perdoc_coverage(e, E, dl):
    """media SUI DOCUMENTI (=un prompt/contesto ristretto): per doc, per layer, expert/layer per
    coprire 99% e quanti expert TOCCATI dentro il singolo doc. Modella l'input davvero ristretto."""
    if dl is None:
        return None
    T, L, k = e.shape
    off = np.concatenate([[0], np.cumsum(dl)])
    c99, touched, ntok = [], [], []
    for d in range(len(dl)):
        a, b = off[d], off[d+1]
        if b <= a:
            continue
        seg = e[a:b]                       # [len, L, k]
        ntok.append(b-a)
        per_l_99, per_l_t = [], []
        for l in range(L):
            ids = seg[:, l, :].ravel()
            cnt = np.bincount(ids, minlength=E).astype(np.float64)
            tot = cnt.sum()
            if tot == 0:
                continue
            s = np.sort(cnt)[::-1]; cum = np.cumsum(s)/tot
            per_l_99.append(int(np.searchsorted(cum, 0.99))+1)
            per_l_t.append(int((cnt > 0).sum()))
        c99.append(np.mean(per_l_99)); touched.append(np.mean(per_l_t))
    return {'c99': float(np.mean(c99)), 'touched': float(np.mean(touched)),
            'avg_doc_tok': float(np.mean(ntok)), 'ndoc': len(c99)}

def coverage(e, E):
    """ritorna, mediato sui layer: expert/layer per coprire 90/95/99/100% degli slot."""
    T, L, k = e.shape
    res = {p: [] for p in (90,95,99,100)}
    touched = []
    for l in range(L):
        ids = e[:, l, :].ravel()
        cnt = np.bincount(ids, minlength=E).astype(np.float64)
        tot = cnt.sum()
        if tot == 0:
            continue
        s = np.sort(cnt)[::-1]
        cum = np.cumsum(s) / tot
        touched.append(int((cnt > 0).sum()))
        for p in (90,95,99):
            res[p].append(int(np.searchsorted(cum, p/100.0)) + 1)
        res[100].append(int((cnt > 0).sum()))
    out = {p: float(np.mean(v)) for p, v in res.items() if v}
    out['touched'] = float(np.mean(touched))
    out['E'] = E
    out['ntok'] = int(T)
    return out

def gb_v4(experts_per_layer, E):
    """se in questo modello servono X exp/layer su E, scala alla geometria V4 (256 exp) e da' i GB."""
    frac = experts_per_layer / E
    exp_v4 = frac * V4_E
    gb = exp_v4 * V4_L * V4_EXPERT_MB / 1000.0
    return frac, exp_v4, gb

files = sorted(glob.glob('D:/models/spex/traces_*.npz')) + sorted(glob.glob('D:/models/spex/hidden_scores_*.npz'))
# raggruppa per modello
groups = {}
for f in files:
    b = os.path.basename(f)
    m = re.match(r'(?:traces|hidden_scores)_(q30|q235|ds2lite|olmoe)_(\w+?)\.npz', b)
    if not m:
        continue
    model, wl = m.group(1), m.group(2)
    wl = {'dom':'domain','gen':'general'}.get(wl, wl)
    groups.setdefault(model, {})[wl] = f

print(f"V4 expert fp4 = {V4_EXPERT_MB:.2f} MB ; 256*43 = {V4_E*V4_L} expert totali ; "
      f"tutti gli expert V4 in fp4 = {V4_E*V4_L*V4_EXPERT_MB/1000:.1f} GB ; budget VRAM+RAM = {BUDGET_GB} GB\n")

for model, wls in groups.items():
    print(f"================ {model} ================")
    print(f"{'workload':11} {'E':>4} {'tok':>6} | CORPUS(union){'99%':>6} {'touch':>6} | PER-DOC(prompt ristretto){'doc99':>7} {'docTch':>7} {'docTok':>7} | ->V4 doc99 {'GB':>6} {'fit44?':>5}")
    for wl in ['domain','general','code','reasoning','english','mmlu']:
        if wl not in wls:
            continue
        e, E, dl = load_experts(wls[wl])
        c = coverage(e, E)
        pd = perdoc_coverage(e, E, dl)
        if pd:
            frac_d, expv4_d, gb_d = gb_v4(pd['c99'], E)
            fit = 'YES' if gb_d < BUDGET_GB else 'no'
            print(f"{wl:11} {c['E']:>4} {c['ntok']:>6} | {c[99]:>17.1f} {c['touched']:>6.1f} | "
                  f"{pd['c99']:>28.1f} {pd['touched']:>7.1f} {pd['avg_doc_tok']:>7.0f} | "
                  f"{gb_d:>16.1f} {fit:>5}")
        else:
            print(f"{wl:11} {c['E']:>4} {c['ntok']:>6} | {c[99]:>17.1f} {c['touched']:>6.1f} | (no doclens)")
    print()
print("Nota: '99%' = expert/layer per coprire il 99% degli slot di routing (media sui layer).")
print("'->V4' = la stessa frazione applicata alla geometria V4-Flash (256 exp/layer, 43 layer, fp4).")
print("Se GB < 44 => l'intero working-set del dominio entra in VRAM+RAM => zero streaming SSD dopo warmup.")
