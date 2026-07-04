"""STEP F — concentrazione del routing FT-vs-base sui prompt BonusX reali (raft_eval).
Hook su ogni mlp.gate (router) -> committed_fraction@theta + N_eff per layer + massa per-expert
(candidati pruning = expert a massa bassa, proxy-frequenza di REAP). GPU A100.

Uso: python step_f.py --model Qwen/Qwen3-30B-A3B --tag base
     python step_f.py --model /workspace/qwen3-bonusx-merged --tag ft
"""
import argparse, json, time
import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--prompts', default='/workspace/raft_eval.jsonl')
    ap.add_argument('--tag', required=True); ap.add_argument('--gptqmodel', action='store_true')
    ap.add_argument('--out', default='/root')
    ap.add_argument('--limit', type=int, default=152)
    a = ap.parse_args()

    if a.gptqmodel:
        from gptqmodel import GPTQModel, BACKEND
        _gm = GPTQModel.load(a.model, backend=BACKEND.TORCH, device_map={'': 0}); model = _gm.model; tok = _gm.tokenizer; model.eval()
    else:
        tok = AutoTokenizer.from_pretrained(a.model)
        _kw = {} if ('GPTQ' in a.model or 'Int4' in a.model or 'AWQ' in a.model) else {'dtype': torch.bfloat16}
        model = AutoModelForCausalLM.from_pretrained(a.model, device_map={'': 0}, **_kw); model.eval()
    cfg = model.config
    E = int(cfg.num_experts); topk = int(cfg.num_experts_per_tok); NL = int(cfg.num_hidden_layers)
    log(f"E={E} topk={topk} layers={NL}")

    mass = [torch.zeros(E, device='cuda', dtype=torch.float64) for _ in range(NL)]
    ntok = [0] * NL

    def mk(li):
        def hook(mod, inp, out):
            logits = (out if isinstance(out, torch.Tensor) else out[0]).reshape(-1, E).float()
            probs = torch.softmax(logits, dim=-1)
            tv, ti = torch.topk(probs, topk, dim=-1)
            tv = tv / tv.sum(-1, keepdim=True).clamp_min(1e-9)   # norm_topk_prob
            m = torch.zeros_like(probs).scatter_(-1, ti, tv)
            mass[li] += m.sum(0).double()
            ntok[li] += m.shape[0]
        return hook
    hooks = [model.model.layers[i].mlp.gate.register_forward_hook(mk(i)) for i in range(NL)]

    rows = [json.loads(l) for l in open(a.prompts, encoding='utf-8')][:a.limit]
    log(f"{len(rows)} prompt, forward...")
    with torch.no_grad():
        for j, ex in enumerate(rows):
            enc = tok.apply_chat_template(ex['messages'][:2], add_generation_prompt=True,
                                          return_tensors='pt', return_dict=True).to('cuda')
            model(**enc)
            if (j + 1) % 25 == 0: log(f"  {j+1}/{len(rows)}")
    for h in hooks: h.remove()

    res = {'tag': a.tag, 'E': E, 'topk': topk, 'n_layers': NL, 'total_tokens': int(np.mean(ntok)), 'layers': {}}
    fr = {0.8: [], 0.9: [], 0.95: []}; neffs = []
    low = {}
    for i in range(NL):
        m = mass[i].cpu().numpy(); p = m / m.sum()
        ps = np.sort(p)[::-1]; cum = np.cumsum(ps)
        cf = {}
        for th in (0.8, 0.9, 0.95):
            k = int(np.searchsorted(cum, th) + 1); cf[str(th)] = k / E; fr[th].append(k / E)
        ent = float(-(p * np.log(p + 1e-12)).sum()); neff = float(np.exp(ent)); neffs.append(neff)
        res['layers'][i] = {'committed_fraction': cf, 'n_eff': neff}
        low[i] = np.argsort(m).tolist()   # TUTTI gli expert ordinati per massa ASCENDENTE (candidati pruning, qualsiasi K)
    res['mean_committed_fraction'] = {str(th): float(np.mean(fr[th])) for th in (0.8, 0.9, 0.95)}
    res['mean_n_eff'] = float(np.mean(neffs))
    res['experts_by_mass_asc'] = {str(k): v for k, v in low.items()}
    res['low_mass_experts_bottom50pct'] = {str(k): v[:int(E * 0.5)] for k, v in low.items()}  # backward-compat
    json.dump(res, open(f"{a.out}/stepf_{a.tag}.json", 'w'), indent=1)
    log(f"=== [{a.tag}] committed_fraction {res['mean_committed_fraction']}  N_eff {res['mean_n_eff']:.1f} ===")
    open(f"/root/STEPF_{a.tag}_DONE", 'w').close()

if __name__ == '__main__':
    main()
