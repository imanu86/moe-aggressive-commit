"""SPEX (paper separato) — dump delle TRACE di routing: per ogni token, gli expert top-k attivi a OGNI layer.
Forward-only. Hook su ogni mlp.gate -> topk dai router logits. Generico su MoE con model.model.layers[i].mlp.gate.
Output: /root/traces_<tag>.npz  { experts:int16[T,L,k], doclens, n_experts, topk, n_layers }
Uso: python dump_traces.py --model allenai/OLMoE-1B-7B-0924 --prompts /workspace/general_en.jsonl --tag olmoe_general
"""
import argparse, json, time
import numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
BUF = {}  # layer_id -> [n_tok, k] int16 cpu (forward corrente)

def mk_hook(li, topk):
    def hook(mod, inp, out):
        logits = out[0] if isinstance(out, (tuple, list)) else out
        lg = logits.reshape(-1, logits.shape[-1])            # [n_tok, n_experts]
        BUF[li] = torch.topk(lg, topk, dim=-1).indices.to(torch.int16).cpu()
    return hook

def get_text(ex, tok):
    if isinstance(ex, dict):
        if 'text' in ex: return ex['text']
        if 'messages' in ex:  # niente chat_template (OLMoE non ce l'ha): concateno i contenuti
            return "\n".join(str(m.get('content', '')) for m in ex['messages'])
    return str(ex)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--tag', required=True)
    ap.add_argument('--prompts', required=True); ap.add_argument('--out', default='/root')
    ap.add_argument('--limit', type=int, default=300); ap.add_argument('--maxtok', type=int, default=512)
    ap.add_argument('--gptqmodel', action='store_true')  # per il 235B GPTQ-Int4
    a = ap.parse_args()
    log(f"load {a.model}")
    if a.gptqmodel:
        from gptqmodel import GPTQModel, BACKEND
        _gm = GPTQModel.load(a.model, backend=BACKEND.TORCH, device_map={'': 0}); model = _gm.model; tok = _gm.tokenizer; model.eval()
    else:
        tok = AutoTokenizer.from_pretrained(a.model)
        model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map={'': 0}); model.eval()
    cfg = model.config
    NL = int(cfg.num_hidden_layers)
    topk = int(getattr(cfg, 'num_experts_per_tok', 8))
    hooks = []
    for i in range(NL):
        mlp = model.model.layers[i].mlp
        if hasattr(mlp, 'gate'):
            hooks.append(mlp.gate.register_forward_hook(mk_hook(i, topk)))
    log(f"hook su {len(hooks)}/{NL} gate, topk={topk}, E={int(cfg.num_experts)}")
    rows = [json.loads(l) if l.strip().startswith('{') else l for l in open(a.prompts, encoding='utf-8') if l.strip()][:a.limit]
    all_e = []; doclens = []
    with torch.no_grad():
        for j, ex in enumerate(rows):
            enc = tok(get_text(ex, tok), return_tensors='pt', truncation=True, max_length=a.maxtok).to('cuda')
            BUF.clear(); model(**enc)
            ls = sorted(BUF.keys())
            arr = torch.stack([BUF[i] for i in ls], dim=0).permute(1, 0, 2).numpy().astype(np.int16)  # [n_tok,L,k]
            all_e.append(arr); doclens.append(arr.shape[0])
            if (j + 1) % 50 == 0: log(f"  {j+1}/{len(rows)}  tok cumul {sum(doclens)}")
    for h in hooks: h.remove()
    E = np.concatenate(all_e, axis=0)  # [T, L, k]
    np.savez_compressed(f"{a.out}/traces_{a.tag}.npz", experts=E, doclens=np.array(doclens),
                        n_experts=int(cfg.num_experts), topk=topk, n_layers=E.shape[1])
    log(f"=== [{a.tag}] traces {E.shape} (T,L,k) -> traces_{a.tag}.npz ===")
    open(f"/root/SPEX_{a.tag}_DONE", 'w').close()

if __name__ == '__main__':
    main()
