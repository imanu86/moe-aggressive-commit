"""DOUBLE-LOOP — accuracy-drop con predittore HIDDEN (l'ultima porta).
Estende accuracy_drop.py: aggiunge il metodo 'hidden' = probe lineare W_L su h_{L-1} (hidden del layer
precedente, come Fate) che predice gli expert del layer L. Confronto: full / oracle / hidden / markov / static / random.
Se hidden regge il drop (ppl vicino a full) dove markov crolla -> drop-invece-di-fetch diventa possibile col +hidden.

Uso: python accuracy_drop_v2.py --model Qwen/Qwen3-30B-A3B --calib /workspace/general_it.jsonl --eval /workspace/raft_eval.jsonl
"""
import argparse, json, time, numpy as np, torch, torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

GL = {'mode': 'off', 'C': 128, 'method': 'full', 'Cmk': None, 'freqrank': None, 'prev': None,
      'E': 128, 'topk': 8, 'routes': None, 'rng': None,
      'Wh': None, 'bh': None, 'h_prev': None, 'hstore': None}

def gate_out(out):
    if isinstance(out, (tuple, list)): return out[0], out[1], out[2]
    return out, None, None

def make_layer_hook(Lidx):
    """Bufferizza l'hidden output del decoder layer Lidx -> serve al gate del layer Lidx+1."""
    def hook(mod, inp, out):
        h = out[0] if isinstance(out, (tuple, list)) else out
        h = h.reshape(-1, h.shape[-1])
        if GL['mode'] == 'collect_h':
            GL['hstore'].setdefault(Lidx, []).append(h.detach().to(torch.float16).cpu())
        GL['h_prev'] = (Lidx, h.detach())     # (layer, hidden) per il prossimo gate
        return out
    return hook

def make_gate_hook(Lidx):
    def hook(mod, inp, out):
        logits, weights, indices = gate_out(out)
        T, E = logits.shape
        if GL['mode'] == 'collect':
            GL['routes'].setdefault(Lidx, []).append(indices.detach().to(torch.int16).cpu())
            return out
        if GL['method'] != 'full' and GL['C'] < E and weights is not None:
            resident = compute_resident(Lidx, T, E, logits)
            resmark = torch.zeros(T, E, dtype=torch.bool, device=logits.device)
            resmark.scatter_(1, resident, True)
            keep = torch.gather(resmark, 1, indices)
            w = weights * keep; w = w / (w.sum(-1, keepdim=True) + 1e-9)
            GL['prev'] = indices.detach()
            return (logits, w.to(weights.dtype), indices)
        if weights is not None: GL['prev'] = indices.detach()
        return out
    return hook

def compute_resident(Lidx, T, E, logits):
    m = GL['method']; C = GL['C']
    if m == 'oracle':
        return logits.topk(C, dim=-1).indices
    if m == 'static':
        return GL['freqrank'][Lidx][:C].to(logits.device).unsqueeze(0).expand(T, C).contiguous()
    if m == 'random':
        return torch.stack([torch.randperm(E, device=logits.device, generator=GL['rng'])[:C] for _ in range(T)])
    if m == 'hidden':
        hp = GL['h_prev']
        if Lidx == 0 or hp is None or hp[0] != Lidx - 1 or GL['Wh'][Lidx-1] is None:
            return logits.topk(C, dim=-1).indices
        score = hp[1] @ GL['Wh'][Lidx-1] + GL['bh'][Lidx-1]      # [T, E]
        return score.topk(C, dim=-1).indices
    # markov
    if Lidx == 0 or GL['prev'] is None:
        return logits.topk(C, dim=-1).indices
    return GL['Cmk'][Lidx-1][GL['prev']].sum(1).topk(C, dim=-1).indices

def get_text(ex):
    if isinstance(ex, dict):
        if 'text' in ex: return ex['text']
        if 'messages' in ex: return "\n".join(str(m.get('content', '')) for m in ex['messages'])
    return str(ex)
def load_prompts(p, lim): return [json.loads(l) if l.strip().startswith('{') else l for l in open(p, encoding='utf-8') if l.strip()][:lim]

def perplexity(model, tok, prompts, maxtok):
    nll = 0.0; ntok = 0
    with torch.no_grad():
        for ex in prompts:
            enc = tok(get_text(ex), return_tensors='pt', truncation=True, max_length=maxtok).to('cuda')
            if enc['input_ids'].shape[1] < 2: continue
            out = model(**enc, labels=enc['input_ids']); n = enc['input_ids'].shape[1]-1
            nll += out.loss.item()*n; ntok += n
    return float(np.exp(nll/max(ntok, 1))), ntok

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--calib', required=True); ap.add_argument('--eval', required=True)
    ap.add_argument('--out', default='/workspace/accuracy_drop_v2.json'); ap.add_argument('--maxtok', type=int, default=384)
    ap.add_argument('--calib_lim', type=int, default=100); ap.add_argument('--eval_lim', type=int, default=120)
    ap.add_argument('--caps', default='4,6,8,12,16,24,32,48')
    a = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(a.model); log(f"load {a.model}")
    model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map={'': 0}); model.eval()
    E = int(model.config.num_experts); topk = int(model.config.num_experts_per_tok); NL = int(model.config.num_hidden_layers)
    GL.update(E=E, topk=topk, rng=torch.Generator(device='cuda').manual_seed(0))
    ghooks = [model.model.layers[i].mlp.gate.register_forward_hook(make_gate_hook(i)) for i in range(NL)]
    lhooks = [model.model.layers[i].register_forward_hook(make_layer_hook(i)) for i in range(NL)]
    caps = [int(x) for x in a.caps.split(',')]
    calib = load_prompts(a.calib, a.calib_lim); ev = load_prompts(a.eval, a.eval_lim)
    # === collect routes (markov+freq) ===
    GL['mode'] = 'collect'; GL['routes'] = {}
    with torch.no_grad():
        for ex in calib:
            enc = tok(get_text(ex), return_tensors='pt', truncation=True, max_length=a.maxtok).to('cuda'); model(**enc)
    log(f"collect routes ok ({len(calib)} prompts)")
    Cmk = [torch.zeros(E, E) for _ in range(NL)]; freq = [torch.zeros(E) for _ in range(NL)]
    Rall = {l: torch.cat(GL['routes'][l]).long() for l in range(NL)}
    for l in range(NL):
        R = Rall[l]
        for c in range(topk): freq[l].index_add_(0, R[:, c], torch.ones(R.shape[0]))
        if l < NL-1:
            Rn = Rall[l+1]
            for c1 in range(topk):
                for c2 in range(topk): Cmk[l].index_put_((R[:, c1], Rn[:, c2]), torch.ones(R.shape[0]), accumulate=True)
    GL['Cmk'] = [c.to('cuda') for c in Cmk]; GL['freqrank'] = [torch.argsort(-freq[l]) for l in range(NL)]
    # === collect hidden (per allenare le probe) ===
    GL['mode'] = 'collect_h'; GL['hstore'] = {}
    with torch.no_grad():
        for ex in calib:
            enc = tok(get_text(ex), return_tensors='pt', truncation=True, max_length=a.maxtok).to('cuda'); model(**enc)
    log("collect hidden ok -> train probe per-layer")
    Wh = [None]*NL; bh = [None]*NL
    for L in range(NL-1):
        H = torch.cat(GL['hstore'][L]).float().to('cuda')        # [T, H]
        Y = torch.zeros(H.shape[0], E, device='cuda'); Y.scatter_(1, Rall[L+1].to('cuda'), 1.0)
        W = torch.zeros(H.shape[1], E, device='cuda', requires_grad=True); b = torch.zeros(E, device='cuda', requires_grad=True)
        opt = torch.optim.Adam([W, b], lr=1e-2)
        for _ in range(120):
            opt.zero_grad(); loss = F.binary_cross_entropy_with_logits(H@W+b, Y); loss.backward(); opt.step()
        Wh[L] = W.detach(); bh[L] = b.detach(); del H, Y
        if L % 16 == 0: torch.cuda.empty_cache()
    GL['Wh'] = Wh; GL['bh'] = bh; GL['routes'] = None; GL['hstore'] = None; torch.cuda.empty_cache()
    # === eval perplexity ===
    GL['mode'] = 'eval'; res = {}
    GL['method'] = 'full'; GL['C'] = E; GL['prev'] = None
    ppl_full, nt = perplexity(model, tok, ev, a.maxtok); res['full'] = ppl_full
    log(f"=== FULL ppl {ppl_full:.4f} (ntok {nt}) ===")
    for method in ['hidden', 'oracle', 'markov', 'static', 'random']:
        res[method] = {}
        for C in caps:
            GL['method'] = method; GL['C'] = C; GL['prev'] = None
            p, _ = perplexity(model, tok, ev, a.maxtok); res[method][C] = p
            log(f"  {method:7s} C={C:3d} ({100*C/E:.0f}%)  ppl {p:.4f}  (x full {p/ppl_full:.3f})")
    for h in ghooks+lhooks: h.remove()
    json.dump({'model': a.model, 'E': E, 'topk': topk, 'NL': NL, 'caps': caps, 'ppl_full': ppl_full, 'results': res},
              open(a.out, 'w'), indent=1)
    log(f"saved {a.out}"); open('/workspace/ACCDROP2_DONE', 'w').close()

if __name__ == '__main__':
    main()
