"""Ridondanza cross-expert su DeepSeek-V4-Flash (256 routed + 1 shared, arch custom, FP8 block-quant).
Chiavi: layers.{L}.ffn.experts.{e}.w1.weight (+ .w1.scale). Dequant block-fp8 (weight*scale). w1 = gate SwiGLU."""
import json, re, time, numpy as np, torch
from collections import defaultdict
from huggingface_hub import hf_hub_download
from safetensors import safe_open
def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
REPO = "deepseek-ai/DeepSeek-V4-Flash"
idx = json.load(open(hf_hub_download(REPO, "model.safetensors.index.json")))['weight_map']
by = defaultdict(set)
for k in idx:
    m = re.match(r'layers\.(\d+)\.ffn\.experts\.(\d+)\.w1\.weight$', k)
    if m: by[int(m.group(1))].add(int(m.group(2)))
moe = sorted(by); nexp = max((len(v) for v in by.values()), default=0)
log(f"MoE layers {moe[:2]}..{moe[-1]} (n={len(moe)}) n_routed={nexp}")
has_scale = 'layers.%d.ffn.experts.0.w1.scale' % moe[0] in idx
log(f"block-fp8 scale: {has_scale}")
def load(keys):
    bs = defaultdict(list)
    for tag, k in keys:
        if k in idx: bs[idx[k]].append((tag, k))
    out = {}
    for sh, items in bs.items():
        sp = hf_hub_download(REPO, sh)
        with safe_open(sp, framework='pt') as f:
            for tag, k in items: out[tag] = f.get_tensor(k)
    return out
def deq(w, s):
    w = w.float()
    if s is None: return w.numpy()
    s = s.float(); R, C = w.shape; br = -(-R // s.shape[0]); bc = -(-C // s.shape[1])
    se = s.repeat_interleave(br, 0).repeat_interleave(bc, 1)[:R, :C]
    return (w * se).numpy()
def gate(L, e):
    wk = f"layers.{L}.ffn.experts.{e}.w1.weight"; d = load([('w', wk)] + ([('s', wk[:-6]+'scale')] if has_scale else []))
    return deq(d['w'], d.get('s'))
def sgate(L):
    wk = f"layers.{L}.ffn.shared_experts.w1.weight"; d = load([('w', wk)] + ([('s', wk[:-6]+'scale')] if has_scale else []))
    return deq(d['w'], d.get('s')) if 'w' in d else None
for L in [moe[len(moe)//3], moe[2*len(moe)//3]]:
    t0 = time.time(); W = np.stack([gate(L, e) for e in range(nexp)]); E, I, H = W.shape
    V = W.reshape(E, -1); Vn = V/(np.linalg.norm(V, 1 if False else None, axis=1, keepdims=True)+1e-8)
    S = Vn@Vn.T; off = S[~np.eye(E, dtype=bool)]
    ev = np.clip(np.linalg.eigvalsh(S), 0, None)[::-1]; p = ev/ev.sum(); eff = float(np.exp(-(p*np.log(p+1e-12)).sum()))
    N = W.reshape(E*I, H); Nc = N-N.mean(0); cov = Nc.T@Nc/Nc.shape[0]; evn = np.clip(np.linalg.eigvalsh(cov), 0, None)[::-1]; cc = np.cumsum(evn)/evn.sum()
    d90 = int(np.searchsorted(cc, 0.9))+1
    rng = np.random.default_rng(0); Nn = N/(np.linalg.norm(N, axis=1, keepdims=True)+1e-8); samp = rng.choice(E*I, min(400, E*I), replace=False)
    best = np.array([float((lambda sm: (sm.__setitem__(slice((s//I)*I, (s//I+1)*I), -1), sm.max())[1])(Nn@Nn[s])) for s in samp])
    Wsh = sgate(L); shstr = ""
    if Wsh is not None:
        Nsh = Wsh.reshape(-1, H); Nshn = Nsh/(np.linalg.norm(Nsh, axis=1, keepdims=True)+1e-8)
        bs = np.array([float((Nn[s]@Nshn.T).max()) for s in samp[:200]]); shstr = f"| routed->SHARED NN {bs.mean():.3f} >0.8 {(bs>0.8).mean():.2f} (n {Nsh.shape[0]})"
    log(f"L{L}: E={E} I={I} H={H} | expert-cos off {off.mean():.4f} max {off.max():.3f} | eff_rank {eff:.1f}/{E} | neuron-dims90 {d90}/{H} | x-expert NN {best.mean():.3f} >0.8 {(best>0.8).mean():.2f} {shstr} [{time.time()-t0:.0f}s]")
log("V4-Flash redundancy done")
