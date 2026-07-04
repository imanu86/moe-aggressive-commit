"""Sondaggio ridondanza CROSS-EXPERT sui pesi del 30B mergiato (test dell'idea sub-expert dell'utente).
Misura: (1) similarita' coseno tra i 128 expert interi; (2) rango effettivo dello spazio-neuroni condiviso;
(3) duplicazione di neuroni TRA expert diversi (nearest-neighbor cross-expert)."""
import json, glob, numpy as np, torch, time
from collections import defaultdict
from safetensors import safe_open
def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
base='D:/models/qwen3-bonusx-merged'
idx=json.load(open(glob.glob(base+'/*index.json')[0]))['weight_map']
def load_layer_gate(L, E=128):
    byshard=defaultdict(list)
    for e in range(E):
        k=f'model.layers.{L}.mlp.experts.{e}.gate_proj.weight'; byshard[idx[k]].append((e,k))
    out={}
    for shard,items in byshard.items():
        with safe_open(f'{base}/{shard}', framework='pt') as f:
            for e,k in items: out[e]=f.get_tensor(k).float().numpy()   # [I=768, H=2048]
    return np.stack([out[e] for e in range(E)])   # [E, I, H]
for L in [3, 24, 44]:
    t0=time.time(); W=load_layer_gate(L); E,I,H=W.shape
    # (1) similarita' tra expert interi
    V=W.reshape(E,-1); Vn=V/ (np.linalg.norm(V,axis=1,keepdims=True)+1e-8)
    S=Vn@Vn.T; off=S[~np.eye(E,dtype=bool)]
    # rango effettivo tra expert (eigenvalues del Gram normalizzato)
    ev=np.linalg.eigvalsh(S); ev=np.clip(ev,0,None)[::-1]; p=ev/ev.sum(); eff_exp=np.exp(-(p*np.log(p+1e-12)).sum())
    # (2) spazio-neuroni: covarianza dei 128*768 neuroni in R^H
    N=W.reshape(E*I, H); Nc=N-N.mean(0)
    cov=Nc.T@Nc/Nc.shape[0]; evn=np.linalg.eigvalsh(cov)[::-1]; evn=np.clip(evn,0,None); c=np.cumsum(evn)/evn.sum()
    d90=int(np.searchsorted(c,0.90))+1; d99=int(np.searchsorted(c,0.99))+1
    # (3) duplicazione neuroni CROSS-expert: 400 neuroni campione, nearest in un expert DIVERSO
    rng=np.random.default_rng(0); Nn=N/(np.linalg.norm(N,axis=1,keepdims=True)+1e-8)
    samp=rng.choice(E*I,400,replace=False); best=[]
    for s in samp:
        my_e=s//I; sims=Nn@Nn[s]; sims[my_e*I:(my_e+1)*I]=-1  # escludi stesso expert
        best.append(sims.max())
    best=np.array(best)
    log(f"L{L}: expert-cos off-diag media {off.mean():.3f} max {off.max():.3f} | eff_rank_expert {eff_exp:.1f}/{E} "
        f"| neuron-dims 90%={d90}/{H} 99%={d99} | cross-expert neuron NN-cos: media {best.mean():.3f} frac>0.8 {(best>0.8).mean():.2f} frac>0.9 {(best>0.9).mean():.2f} [{time.time()-t0:.0f}s]")
