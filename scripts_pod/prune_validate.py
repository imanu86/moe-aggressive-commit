"""STEP F+ — validazione PRUNING: maschera i bottom-K% expert (per ranking in --maskfile)
via reroute nel gate, e misura la qualità. Due metriche:
  --metric field       (DEFAULT): generate greedy + accuracy per-campo BonusX (come prima).
  --metric perplexity  : FORWARD-ONLY (labels=input_ids), niente generate -> niente compile-storm
                         sul 235B, e serve per DOMINIO-vs-GENERALE (perplexity su corpus diversi).

Uso 30B base:   python prune_validate.py --model Qwen/Qwen3-30B-A3B --k 50 --tag prune50
Uso FT:         python prune_validate.py --model /workspace/qwen3-bonusx-merged --k 50 --maskfile /root/stepf_ft.json --tag ftprune50
Uso 235B:       TORCHDYNAMO_DISABLE=1 python prune_validate.py --model Qwen/Qwen3-235B-A22B-GPTQ-Int4 --gptqmodel --k 50 \
                    --maskfile /root/stepf_base235.json --metric perplexity --tag prune235_50
Uso dominio/gen: ... --metric perplexity --prompts /workspace/general_corpus.jsonl --tag gen_k50
     (k = % expert mascherati per layer; 0 = full/nessun mask)
"""
import argparse, json, re, time, math
from collections import Counter
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

NUM = ["cap_eur", "rollover_x", "cashback_pct", "stake_min_eur"]
CAT = ["technique", "variance", "validity"]

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
def num_eq(a, b):
    if a is None and b is None: return True
    if a is None or b is None: return False
    try: return abs(float(a) - float(b)) < 0.01
    except Exception: return False
def parse_json(t):
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception: return None

def load_text(ex, tok):
    """Ritorna il TESTO su cui calcolare la perplexity. Supporta jsonl chat ('messages'),
    jsonl con 'text', o riga di testo grezzo (corpus generale)."""
    if isinstance(ex, dict):
        if 'messages' in ex:
            return tok.apply_chat_template(ex['messages'], tokenize=False, enable_thinking=False)
        if 'text' in ex: return ex['text']
    return str(ex)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--tag', required=True); ap.add_argument('--gptqmodel', action='store_true')
    ap.add_argument('--k', type=int, default=50, help='%% expert mascherati per layer')
    ap.add_argument('--metric', default='field', choices=['field', 'perplexity'])
    ap.add_argument('--random', action='store_true', help='CONTROLLO: maschera K%% expert a CASO (invece dei freddi)')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--maskfile', default='/root/stepf_base.json')
    ap.add_argument('--maskkey', default='experts_by_mass_asc', help='chiave del ranking nel maskfile (es. experts_by_ean_asc)')
    ap.add_argument('--maxlen', type=int, default=4096)
    ap.add_argument('--prompts', default='/workspace/raft_eval.jsonl'); ap.add_argument('--out', default='/root')
    a = ap.parse_args()
    log(f"load {a.model}  (metric={a.metric})")
    if a.gptqmodel:
        from gptqmodel import GPTQModel, BACKEND
        _gm = GPTQModel.load(a.model, backend=BACKEND.TORCH, device_map={'': 0}); model = _gm.model; tok = _gm.tokenizer; model.eval()
    else:
        tok = AutoTokenizer.from_pretrained(a.model)
        kw = {} if ('GPTQ' in a.model or 'Int4' in a.model or 'AWQ' in a.model) else {'dtype': torch.bfloat16}
        model = AutoModelForCausalLM.from_pretrained(a.model, device_map={'': 0}, **kw); model.eval()
    cfg = model.config; E = int(cfg.num_experts); topk = int(cfg.num_experts_per_tok); NL = int(cfg.num_hidden_layers)

    # --- mascheratura pruning nel gate (identica per entrambe le metriche: gli hook girano su forward) ---
    hooks = []
    if a.k > 0:
        n_mask = int(round(E * a.k / 100.0))
        masks = {}
        if a.random:
            import random as _r
            rng = _r.Random(a.seed)
            for i in range(NL):
                idxs = rng.sample(range(E), n_mask)
                m = torch.zeros(E, dtype=torch.bool, device='cuda'); m[torch.tensor(idxs, device='cuda')] = True
                masks[i] = m
            log(f"CONTROLLO RANDOM: {n_mask}/{E} expert a caso per layer (seed {a.seed})")
        else:
            mj = json.load(open(a.maskfile))
            bottom = mj.get(a.maskkey)
            if bottom is None:  # NIENTE fallback silenzioso: bottom50pct e' troncato a K=50 -> mask SBAGLIATA per K>50
                raise SystemExit(f"maskfile {a.maskfile} privo di '{a.maskkey}': rigenera con step_f.py/reap_saliency.py")
            for i in range(NL):
                assert len(bottom[str(i)]) >= n_mask, f"layer {i}: maskfile ha {len(bottom[str(i)])} expert < n_mask={n_mask} (K troppo alto per questo ranking)"
                idxs = bottom[str(i)][:n_mask]
                m = torch.zeros(E, dtype=torch.bool, device='cuda'); m[torch.tensor(idxs, device='cuda')] = True
                masks[i] = m
            log(f"mask da {a.maskfile} [{a.maskkey}]")
        def mk(li):
            mask = masks[li]
            def hook(mod, inp, out):
                logits, rw, se = out
                Lg = logits.clone(); Lg[:, mask] = float('-inf')
                probs = torch.softmax(Lg.float(), dim=-1)
                tv, ti = torch.topk(probs, topk, dim=-1)
                tv = (tv / tv.sum(-1, keepdim=True).clamp_min(1e-9)).to(rw.dtype)
                return (logits, tv, ti.to(se.dtype))
            return hook
        hooks = [model.model.layers[i].mlp.gate.register_forward_hook(mk(i)) for i in range(NL)]
        log(f"PRUNING attivo: mascherati {n_mask}/{E} expert per layer (K={a.k}%)")
    else:
        log("FULL (nessun mask)")

    rows = [json.loads(l) if l.strip().startswith('{') else l.rstrip('\n')
            for l in open(a.prompts, encoding='utf-8') if l.strip()]

    if a.metric == 'perplexity':
        # FORWARD-ONLY: nessun generate -> nessuna ricompilazione per-shape (ok 235B).
        total_nll = 0.0; total_tok = 0; n_used = 0
        for i, ex in enumerate(rows):
            text = load_text(ex, tok)
            enc = tok(text, return_tensors='pt', truncation=True, max_length=a.maxlen).to('cuda')
            ids = enc['input_ids']
            if ids.shape[1] < 2: continue
            with torch.no_grad():
                out = model(input_ids=ids, labels=ids)
            ntok = ids.shape[1] - 1
            total_nll += float(out.loss) * ntok; total_tok += ntok; n_used += 1
            if (i + 1) % 25 == 0: log(f"  {i+1}/{len(rows)}  ppl_run={math.exp(total_nll/max(1,total_tok)):.3f}")
        for h in hooks: h.remove()
        mean_nll = total_nll / max(1, total_tok)
        res = {'tag': a.tag, 'k': a.k, 'metric': 'perplexity', 'model': a.model, 'prompts': a.prompts,
               'random': a.random, 'seed': a.seed, 'maskfile': None if a.random else a.maskfile, 'maskkey': a.maskkey,
               'n': n_used, 'tokens': total_tok, 'nll': mean_nll, 'perplexity': math.exp(mean_nll)}
        json.dump(res, open(f"{a.out}/eval_{a.tag}.json", 'w'), ensure_ascii=False, indent=1)
        log(f"=== [{a.tag}] K={a.k}% PPL={res['perplexity']:.3f} (nll={mean_nll:.4f}, {n_used} doc, {total_tok} tok) ===")
        open(f"/root/PRUNE_{a.tag}_DONE", 'w').close()
        return

    # --- metric == 'field': generate greedy + accuracy per-campo (comportamento storico) ---
    ok = Counter(); tot = Counter(); pf = 0
    for i, ex in enumerate(rows):
        gold = json.loads(ex['messages'][2]['content'])
        enc = tok.apply_chat_template(ex['messages'][:2], add_generation_prompt=True, enable_thinking=False,
                                      return_tensors='pt', return_dict=True).to('cuda')
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=160, do_sample=False, pad_token_id=tok.eos_token_id)
        pred = parse_json(tok.decode(out[0, enc['input_ids'].shape[1]:], skip_special_tokens=True))
        if pred is None: pf += 1; continue
        for f in CAT:
            tot[f] += 1
            if (pred.get(f) or None) == (gold.get(f) or None): ok[f] += 1
        for f in NUM:
            tot[f] += 1
            if num_eq(pred.get(f), gold.get(f)): ok[f] += 1
        if (i + 1) % 25 == 0: log(f"  {i+1}/{len(rows)}")
    for h in hooks: h.remove()
    acc = {f: ok[f] / max(1, tot[f]) for f in CAT + NUM}
    overall = sum(ok.values()) / max(1, sum(tot.values()))
    F6 = [f for f in CAT + NUM if f != 'validity']  # overall a 6 campi (validity escluso by-design)
    overall_excl = sum(ok[f] for f in F6) / max(1, sum(tot[f] for f in F6))
    res = {'tag': a.tag, 'k': a.k, 'metric': 'field', 'model': a.model, 'n': len(rows), 'parse_fail': pf,
           'random': a.random, 'seed': a.seed, 'maskfile': None if a.random else a.maskfile, 'maskkey': a.maskkey,
           'accuracy': acc, 'overall': overall, 'overall_excl_validity': overall_excl}
    json.dump(res, open(f"{a.out}/eval_{a.tag}.json", 'w'), ensure_ascii=False, indent=1)
    log(f"=== [{a.tag}] K={a.k}% parse_fail={pf} overall_field_acc={100*overall:.1f}% ===")
    for f in CAT + NUM: log(f"  {f:16} ({100*acc[f]:.1f}%)")
    open(f"/root/PRUNE_{a.tag}_DONE", 'w').close()

if __name__ == '__main__':
    main()
