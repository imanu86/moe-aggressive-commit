"""Dump trace di routing per DeepSeek-V2-Lite (arch DeepSeekMoE: layer 0 dense, 64 routed + 2 shared, 6 attivi).
Robusto al version-hell: prova a caricare NATIVO (deepseek_v2 in transformers 5.x?) poi remote+shim;
auto-rileva la struttura del gate; hooka solo i layer MoE. Output: traces_ds2lite_<tag>.npz {experts[T,Lmoe,k],doclens,...}.
Uso: python dump_traces_ds.py --model deepseek-ai/DeepSeek-V2-Lite --out /workspace --jobs domain:raft_eval.jsonl:150 ..."""
import argparse, json, time, numpy as np, torch
# --- shim per codice remoto DeepSeek-V2 (2024) su transformers 5.x ---
import transformers.utils.import_utils as _iu, transformers.utils as _u
for _n, _v in [('is_torch_fx_available', lambda *a, **k: False)]:
    for _mod in (_iu, _u):
        if not hasattr(_mod, _n): setattr(_mod, _n, _v)
from transformers import AutoModelForCausalLM, AutoTokenizer
def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def load_model(M):
    last = None
    for tr in (False, True):
        try:
            m = AutoModelForCausalLM.from_pretrained(M, dtype=torch.bfloat16, device_map={'': 0}, trust_remote_code=tr)
            log(f"loaded OK (trust_remote_code={tr})"); return m
        except Exception as e:
            last = e; log(f"load trust={tr} FAIL: {str(e)[:180]}")
    raise last

BUF = {}
def extract_ids(out, topk, E):
    cands = list(out) if isinstance(out, (tuple, list)) else [out]
    for x in cands:                       # 1) topk_idx intero [*, topk]
        if torch.is_tensor(x) and x.shape[-1] == topk and x.dtype in (torch.int64, torch.int32, torch.long):
            return x
    for x in cands:                       # 2) logits [*, E] -> topk
        if torch.is_tensor(x) and x.dim() >= 2 and x.shape[-1] == E:
            return x.reshape(-1, E).topk(topk, dim=-1).indices
    return None
def make_hook(li, topk, E):
    def hook(mod, inp, out):
        ids = extract_ids(out, topk, E)
        if ids is not None: BUF[li] = ids.reshape(-1, topk).to(torch.int16).cpu()
    return hook
def get_text(ex):
    if isinstance(ex, dict):
        if 'text' in ex: return ex['text']
        if 'messages' in ex: return "\n".join(str(m.get('content', '')) for m in ex['messages'])
    return str(ex)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--out', default='/workspace')
    ap.add_argument('--maxtok', type=int, default=384); ap.add_argument('--jobs', nargs='+', required=True)
    a = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(a.model, trust_remote_code=True)
    model = load_model(a.model); model.eval(); cfg = model.config
    NL = int(cfg.num_hidden_layers); topk = int(getattr(cfg, 'num_experts_per_tok', 6))
    E = int(getattr(cfg, 'n_routed_experts', getattr(cfg, 'num_experts', 64)))
    hooks = []
    for i in range(NL):
        mlp = model.model.layers[i].mlp
        if hasattr(mlp, 'gate'): hooks.append((i, mlp.gate.register_forward_hook(make_hook(i, topk, E))))
    log(f"hooked {len(hooks)} gate (E={E} topk={topk} NL={NL})")
    # detect: forward piccolo
    enc = tok("The quick brown fox jumps over the lazy dog. " * 5, return_tensors='pt', truncation=True, max_length=48).to('cuda')
    BUF.clear()
    with torch.no_grad(): model(**enc)
    got = sorted(BUF.keys())
    if not got: log("!! nessun gate ha prodotto ID — struttura non riconosciuta, ABORT"); return
    log(f"detect OK: {len(got)} layer MoE attivi (primo {got[0]}), sample shape {BUF[got[0]].shape}, dtype {BUF[got[0]].dtype}")
    for job in a.jobs:
        tag, f, lim = job.split(':'); lim = int(lim)
        rows = [json.loads(l) if l.strip().startswith('{') else l for l in open(f, encoding='utf-8') if l.strip()][:lim]
        all_e = []; doclens = []; t0 = time.time()
        with torch.no_grad():
            for j, ex in enumerate(rows):
                enc = tok(get_text(ex), return_tensors='pt', truncation=True, max_length=a.maxtok).to('cuda')
                BUF.clear(); model(**enc)
                ls = sorted(BUF.keys())
                arr = torch.stack([BUF[i] for i in ls], 0).permute(1, 0, 2).numpy().astype(np.int16)  # [n, Lmoe, k]
                all_e.append(arr); doclens.append(arr.shape[0])
                if (j+1) % 40 == 0: log(f"  {tag} {j+1}/{len(rows)} tok {sum(doclens)} ({(time.time()-t0)/(j+1):.2f}s/p)")
        Earr = np.concatenate(all_e, 0)
        np.savez_compressed(f"{a.out}/traces_ds2lite_{tag}.npz", experts=Earr, doclens=np.array(doclens),
                            n_experts=E, topk=topk, n_layers=Earr.shape[1])
        log(f"=== {tag} {Earr.shape} -> traces_ds2lite_{tag}.npz ==="); open(f"/workspace/TRDS_{tag}_DONE", 'w').close()
    for _, h in hooks: h.remove()
    open("/workspace/DS2_DONE", 'w').close(); log("ALL DS2-Lite traces done")

if __name__ == '__main__':
    main()
