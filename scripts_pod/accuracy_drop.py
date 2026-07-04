"""DOUBLE-LOOP MARKOV — misura dell'accuracy-drop (idea utente): quanto perdi in perplexity se, invece di
FETCHARE gli expert che il router vuole ma non sono residenti, li DROPPI (azzeri), tenendo solo i C predetti.

Predittore = seconda matrice di Markov (transizione expert layer L-1 -> L). Confronto:
  full    : nessun drop (riferimento)
  markov  : residenti = top-C predetti dalla matrice di Markov dal layer precedente (per-token)
  oracle  : residenti = top-C per logit del router stesso (limite superiore per-token)
  static  : residenti = top-C per FREQUENZA globale del layer (pruning statico, per confronto)
  random  : residenti = C a caso (pavimento)
Metrica: perplexity forward-only su held-out, sweep C. La curva ppl-vs-C = costo-accuratezza del drop
= valutazione per-IMPATTO del predittore (non la recall nuda).

Uso: python accuracy_drop.py --model Qwen/Qwen3-30B-A3B --calib /workspace/general_it.jsonl --eval /workspace/raft_eval.jsonl
"""
import argparse, json, time, numpy as np, torch, torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

GL = {'mode': 'off', 'C': 128, 'method': 'full', 'Cmk': None, 'freqrank': None, 'prev': None,
      'E': 128, 'topk': 8, 'routes': None, 'rng': None}

def unpack_gate(out):
    """Ritorna (logits, weights, indices, is_tuple). Gate Qwen3Moe 5.x = tuple(logits,weights,indices)."""
    if isinstance(out, (tuple, list)):
        return out[0], out[1], out[2], True
    return out, None, None, False   # solo logits (fallback: nessun drop applicabile qui)

def make_hook(Lidx):
    def hook(mod, inp, out):
        logits, weights, indices, is_tup = unpack_gate(out)
        T, E = logits.shape
        if GL['mode'] == 'collect':
            idx = indices if is_tup else logits.topk(GL['topk'], -1).indices
            GL['routes'].setdefault(Lidx, []).append(idx.detach().to(torch.int16).cpu())
            return out
        # eval mode
        if GL['method'] != 'full' and GL['C'] < E and is_tup:
            resident = compute_resident(Lidx, T, E, logits)          # [T, C]
            resmark = torch.zeros(T, E, dtype=torch.bool, device=logits.device)
            resmark.scatter_(1, resident, True)
            keep = torch.gather(resmark, 1, indices)                 # [T, topk] bool
            w = weights * keep
            w = w / (w.sum(-1, keepdim=True) + 1e-9)                  # renormalizza (norm_topk_prob)
            GL['prev'] = indices.detach()                            # routing reale (per markov next layer)
            return (logits, w.to(weights.dtype), indices)
        if is_tup: GL['prev'] = indices.detach()
        return out
    return hook

def compute_resident(Lidx, T, E, logits):
    m = GL['method']; C = GL['C']; dev = logits.device
    if m == 'oracle':
        return logits.topk(C, dim=-1).indices
    if m == 'static':
        return GL['freqrank'][Lidx][:C].to(dev).unsqueeze(0).expand(T, C).contiguous()
    if m == 'random':
        return torch.stack([torch.randperm(E, device=dev, generator=GL['rng'])[:C] for _ in range(T)])
    # markov
    if Lidx == 0 or GL['prev'] is None:
        return logits.topk(C, dim=-1).indices
    score = GL['Cmk'][Lidx-1][GL['prev']].sum(1)                     # [T, E]
    return score.topk(C, dim=-1).indices

def get_text(ex):
    if isinstance(ex, dict):
        if 'text' in ex: return ex['text']
        if 'messages' in ex: return "\n".join(str(m.get('content', '')) for m in ex['messages'])
    return str(ex)

def load_prompts(path, lim):
    return [json.loads(l) if l.strip().startswith('{') else l for l in open(path, encoding='utf-8') if l.strip()][:lim]

def perplexity(model, tok, prompts, maxtok):
    nll = 0.0; ntok = 0
    with torch.no_grad():
        for ex in prompts:
            enc = tok(get_text(ex), return_tensors='pt', truncation=True, max_length=maxtok).to('cuda')
            if enc['input_ids'].shape[1] < 2: continue
            out = model(**enc, labels=enc['input_ids'])
            n = enc['input_ids'].shape[1] - 1
            nll += out.loss.item() * n; ntok += n
    return float(np.exp(nll / max(ntok, 1))), ntok

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--calib', required=True); ap.add_argument('--eval', required=True)
    ap.add_argument('--out', default='/root/accuracy_drop.json'); ap.add_argument('--maxtok', type=int, default=384)
    ap.add_argument('--calib_lim', type=int, default=120); ap.add_argument('--eval_lim', type=int, default=120)
    ap.add_argument('--caps', default='4,6,8,12,16,24,32,48')
    a = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(a.model); log(f"load {a.model}")
    model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map={'': 0}); model.eval()
    E = int(model.config.num_experts); topk = int(model.config.num_experts_per_tok); NL = int(model.config.num_hidden_layers)
    GL.update(E=E, topk=topk, rng=torch.Generator(device='cuda').manual_seed(0))
    hooks = [model.model.layers[i].mlp.gate.register_forward_hook(make_hook(i)) for i in range(NL)]
    caps = [int(x) for x in a.caps.split(',')]
    # verifica struttura gate
    GL['mode'] = 'collect'; GL['routes'] = {}
    calib = load_prompts(a.calib, a.calib_lim); ev = load_prompts(a.eval, a.eval_lim)
    with torch.no_grad():
        enc = tok(get_text(calib[0]), return_tensors='pt', truncation=True, max_length=32).to('cuda'); model(**enc)
    log(f"gate collect ok: layer 0 route shape {GL['routes'][0][0].shape} (tuple-gate={'si' if GL['routes'][0] else 'no'})")
    # === FASE 1: collect routes su calib -> Markov + freq ===
    log(f"FASE1 collect su {len(calib)} calib prompts")
    with torch.no_grad():
        for j, ex in enumerate(calib):
            enc = tok(get_text(ex), return_tensors='pt', truncation=True, max_length=a.maxtok).to('cuda'); model(**enc)
            if (j+1) % 40 == 0: log(f"  collect {j+1}/{len(calib)}")
    Cmk = [torch.zeros(E, E) for _ in range(NL)]; freq = [torch.zeros(E) for _ in range(NL)]
    for l in range(NL):
        R = torch.cat(GL['routes'][l]).long()                        # [Ttot, topk]
        for c in range(topk): freq[l].index_add_(0, R[:, c], torch.ones(R.shape[0]))
        if l < NL-1:
            Rn = torch.cat(GL['routes'][l+1]).long()
            for c1 in range(topk):
                for c2 in range(topk):
                    Cmk[l].index_put_((R[:, c1], Rn[:, c2]), torch.ones(R.shape[0]), accumulate=True)
    GL['Cmk'] = [c.to('cuda') for c in Cmk]
    GL['freqrank'] = [torch.argsort(-freq[l]) for l in range(NL)]
    GL['routes'] = None; torch.cuda.empty_cache()
    # === FASE 2: perplexity per metodo x C ===
    GL['mode'] = 'eval'; res = {}
    GL['method'] = 'full'; GL['C'] = E; GL['prev'] = None
    ppl_full, nt = perplexity(model, tok, ev, a.maxtok); res['full'] = ppl_full
    log(f"=== FULL ppl {ppl_full:.4f} (ntok {nt}) ===")
    for method in ['markov', 'oracle', 'static', 'random']:
        res[method] = {}
        for C in caps:
            GL['method'] = method; GL['C'] = C; GL['prev'] = None
            p, _ = perplexity(model, tok, ev, a.maxtok); res[method][C] = p
            log(f"  {method:7s} C={C:3d} ({100*C/E:.0f}%)  ppl {p:.4f}  (x full {p/ppl_full:.3f})")
    for h in hooks: h.remove()
    json.dump({'model': a.model, 'E': E, 'topk': topk, 'NL': NL, 'caps': caps, 'ppl_full': ppl_full,
               'eval': a.eval, 'calib': a.calib, 'results': res}, open(a.out, 'w'), indent=1)
    log(f"saved {a.out}"); open('/workspace/ACCDROP_DONE', 'w').close()

if __name__ == '__main__':
    main()
