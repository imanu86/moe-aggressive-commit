"""SPEX +hidden predictor (F4, il delta di robustezza): predici gli esperti del layer L+1 dall'HIDDEN
a fine layer L (input a L+1, disponibile PRIMA del gate di L+1). Confronta col Markov (solo expert-ID).
Se +hidden >> Markov -> il predittore condizionale batte davvero -> giustifica SPEX dinamico.
Uso: python hidden_predict.py --model Qwen/Qwen3-30B-A3B --prompts /workspace/general_it.jsonl --tag q30_gen
"""
import argparse, json, time
import numpy as np, torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
HID = {}; EXP = {}

def get_text(ex, tok):
    if isinstance(ex, dict):
        if 'text' in ex: return ex['text']
        if 'messages' in ex: return "\n".join(str(m.get('content', '')) for m in ex['messages'])
    return str(ex)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--tag', required=True)
    ap.add_argument('--prompts', default='/workspace/raft_eval.jsonl'); ap.add_argument('--out', default='/root')
    ap.add_argument('--limit', type=int, default=120); ap.add_argument('--maxtok', type=int, default=320)
    a = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(a.model); log(f"load {a.model}")
    model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map={'': 0}); model.eval()
    NL = int(model.config.num_hidden_layers); E = int(model.config.num_experts); topk = int(model.config.num_experts_per_tok)
    hooks = []
    def mk_gate(li):
        def h(mod, inp, out):
            lg = out[0] if isinstance(out, (tuple, list)) else out
            EXP[li] = torch.topk(lg.reshape(-1, lg.shape[-1]), topk, dim=-1).indices.to(torch.int16).cpu()
        return h
    def mk_layer(li):
        def h(mod, inp, out):
            hs = out[0] if isinstance(out, (tuple, list)) else out
            HID[li] = hs.reshape(-1, hs.shape[-1]).to(torch.float16).cpu()
        return h
    for i in range(NL):
        hooks.append(model.model.layers[i].mlp.gate.register_forward_hook(mk_gate(i)))
        hooks.append(model.model.layers[i].register_forward_hook(mk_layer(i)))
    rows = [json.loads(l) if l.strip().startswith('{') else l for l in open(a.prompts, encoding='utf-8') if l.strip()][:a.limit]
    Hd = {i: [] for i in range(NL)}; Ex = {i: [] for i in range(NL)}
    with torch.no_grad():
        for j, ex in enumerate(rows):
            enc = tok(get_text(ex, tok), return_tensors='pt', truncation=True, max_length=a.maxtok).to('cuda')
            HID.clear(); EXP.clear(); model(**enc)
            for i in range(NL):
                if i in HID: Hd[i].append(HID[i])
                if i in EXP: Ex[i].append(EXP[i])
            if (j + 1) % 40 == 0: log(f"  fwd {j+1}/{len(rows)}")
    for h in hooks: h.remove()
    Hd = {i: torch.cat(Hd[i]).float() for i in range(NL)}
    Ex = {i: torch.cat(Ex[i]).long() for i in range(NL)}
    T = Hd[0].shape[0]; split = T // 2; dev = 'cuda'
    budgets = [topk, 2 * topk, 4 * topk]
    hid_rec = {B: [] for B in budgets}; mk_rec = {B: [] for B in budgets}
    log(f"T={T} NL={NL} E={E} k={topk} -> train predittori per layer")
    for L in range(NL - 1):
        X = Hd[L].to(dev)
        Yh = torch.zeros(T, E, device=dev); Yh.scatter_(1, Ex[L + 1].to(dev), 1.0)
        Xtr, Ytr = X[:split], Yh[:split]
        W = torch.zeros(X.shape[1], E, device=dev, requires_grad=True)
        b = torch.zeros(E, device=dev, requires_grad=True)
        opt = torch.optim.Adam([W, b], lr=1e-2)
        for _ in range(150):
            opt.zero_grad(); loss = F.binary_cross_entropy_with_logits(Xtr @ W + b, Ytr); loss.backward(); opt.step()
        with torch.no_grad():
            hsc = X[split:] @ W + b
        Yte = Ex[L + 1][split:].to(dev)
        C = torch.zeros(E, E, device=dev)
        Al, Al1 = Ex[L][:split].to(dev), Ex[L + 1][:split].to(dev)
        for c1 in range(topk):
            for c2 in range(topk):
                C.index_put_((Al[:, c1], Al1[:, c2]), torch.ones(split, device=dev), accumulate=True)
        msc = C[Ex[L][split:].to(dev)].sum(1)
        for B in budgets:
            for scores, store in [(hsc, hid_rec), (msc, mk_rec)]:
                topB = scores.topk(B, dim=1).indices
                mask = torch.zeros_like(scores, dtype=torch.bool); mask.scatter_(1, topB, True)
                store[B].append(mask.gather(1, Yte).float().mean().item())
        del X, Yh, W, b, opt, C; torch.cuda.empty_cache()
        if L % 12 == 0: log(f"  L{L}: hidden@2k {np.mean(hid_rec[2*topk]):.3f} markov@2k {np.mean(mk_rec[2*topk]):.3f}")
    res = {'tag': a.tag, 'T': T, 'E': E, 'k': topk, 'NL': NL, 'prompts': a.prompts,
           'hidden': {str(B): float(np.mean(hid_rec[B])) for B in budgets},
           'markov': {str(B): float(np.mean(mk_rec[B])) for B in budgets}}
    json.dump(res, open(f"{a.out}/hidden_predict_{a.tag}.json", 'w'), indent=1)
    log(f"=== [{a.tag}] recall@budget HIDDEN {res['hidden']} | MARKOV {res['markov']} ===")
    open(f"/root/HIDDEN_{a.tag}_DONE", 'w').close()

if __name__ == '__main__':
    main()
