"""Ridondanza cross-expert su DeepSeek-V2-Lite leggendo i PESI dai safetensors (NO model load -> niente
version-hell del codice remoto). 64 routed + 2 shared. Confronto con Qwen (off ~0.004, eff pieno, 0% shared)."""
import json, numpy as np, time
from collections import defaultdict
from huggingface_hub import snapshot_download
from safetensors import safe_open
def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
log("download safetensors DeepSeek-V2-Lite")
path=snapshot_download("deepseek-ai/DeepSeek-V2-Lite", allow_patterns=["*.safetensors","*.json"])
idx=json.load(open(f"{path}/model.safetensors.index.json"))['weight_map']
sample=[k for k in idx if 'experts' in k and 'gate_proj' in k][:4]
log(f"sample expert keys: {sample}")
def load_gate(keys):
    byshard=defaultdict(list)
    for tag,k in keys:
        if k in idx: byshard[idx[k]].append((tag,k))
    out={}
    for shard,items in byshard.items():
        with safe_open(f"{path}/{shard}", framework='pt') as f:
            for tag,k in items: out[tag]=f.get_tensor(k).float().numpy()
    return out
NEXP=64
for L in [6,13,24]:
    rk=[(e,f"model.layers.{L}.mlp.experts.{e}.gate_proj.weight") for e in range(NEXP)]
    d=load_gate(rk)
    if not d: log(f"L{L}: nessuna chiave expert, skip"); continue
    W=np.stack([d[e] for e in sorted(d)]); E,I,H=W.shape
    V=W.reshape(E,-1); Vn=V/(np.linalg.norm(V,axis=1,keepdims=True)+1e-8); S=Vn@Vn.T; off=S[~np.eye(E,bool)]
    ev=np.clip(np.linalg.eigvalsh(S),0,None)[::-1]; p=ev/ev.sum(); eff=float(np.exp(-(p*np.log(p+1e-12)).sum()))
    N=W.reshape(E*I,H); Nc=N-N.mean(0); cov=Nc.T@Nc/Nc.shape[0]; evn=np.clip(np.linalg.eigvalsh(cov),0,None)[::-1]; cc=np.cumsum(evn)/evn.sum()
    d90=int(np.searchsorted(cc,0.9))+1
    rng=np.random.default_rng(0); Nn=N/(np.linalg.norm(N,axis=1,keepdims=True)+1e-8)
    samp=rng.choice(E*I,min(400,E*I),replace=False)
    best=np.array([float((lambda s: (lambda sims: (sims.__setitem__(slice((s//I)*I,(s//I+1)*I),-1), sims.max())[1])(Nn@Nn[s]))(s)) for s in samp])
    shstr=""
    shd=load_gate([('sh',f"model.layers.{L}.mlp.shared_experts.gate_proj.weight")])
    if shd:
        Nsh=shd['sh'].reshape(-1,H); Nshn=Nsh/(np.linalg.norm(Nsh,axis=1,keepdims=True)+1e-8)
        bs=np.array([float((Nn[s]@Nshn.T).max()) for s in samp[:200]])
        shstr=f"| routed->SHARED NN media {bs.mean():.3f} frac>0.8 {(bs>0.8).mean():.2f} (shared neurons {Nsh.shape[0]})"
    log(f"L{L}: routed E={E} I={I} H={H} | expert-cos off {off.mean():.3f} max {off.max():.3f} | eff_rank {eff:.1f}/{E} | neuron-dims90 {d90}/{H} | x-expert neuron NN media {best.mean():.3f} frac>0.8 {(best>0.8).mean():.2f} {shstr}")
log("DS-Lite redundancy done")
