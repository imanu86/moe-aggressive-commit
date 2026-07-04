"""MIXED-PRECISION (F6-integrazione): fake-quantizza i COLD experts (bottom-K per massa) a int4/int2,
eval perplexity su dominio+generale. Confronta: full | cold_int4 | cold_int2 | cold_dropped.
Mostra che COMPRIMERE i freddi (int2) perde MOLTO meno che DROPARLI -> la tua idea vs il pruning.
Uso: python mixed_precision_eval.py --model Qwen/Qwen3-30B-A3B --maskfile /workspace/stepf_base.json --k 50
"""
import argparse, json, time, math, os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def fake_quant(w, bits, group=128):
    out, inp = w.shape
    g = group if (inp % group == 0) else inp
    w2 = w.float().reshape(out, inp // g, g)
    maxv = w2.abs().amax(dim=-1, keepdim=True).clamp_min(1e-8)
    qmax = 2 ** (bits - 1) - 1
    scale = maxv / qmax
    q = torch.clamp(torch.round(w2 / scale), -qmax - 1, qmax)
    return (q * scale).reshape(out, inp).to(w.dtype)

def get_text(ex):
    if 'text' in ex: return ex['text']
    if 'messages' in ex: return "\n".join(str(m.get('content', '')) for m in ex['messages'])
    return str(ex)

def ppl(model, tok, rows, maxtok=320):
    nll = 0.0; tot = 0
    with torch.no_grad():
        for ex in rows:
            enc = tok(get_text(ex), return_tensors='pt', truncation=True, max_length=maxtok).to('cuda')
            ids = enc['input_ids']
            if ids.shape[1] < 2: continue
            out = model(input_ids=ids, labels=ids); n = ids.shape[1] - 1
            nll += float(out.loss) * n; tot += n
    return math.exp(nll / max(1, tot))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--maskfile', required=True)
    ap.add_argument('--k', type=int, default=50); ap.add_argument('--out', default='/root'); ap.add_argument('--tag', default='mp')
    a = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(a.model); log('load')
    model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map={'': 0}); model.eval()
    NL = int(model.config.num_hidden_layers); E = int(model.config.num_experts)
    n_mask = int(round(E * a.k / 100))
    cold = json.load(open(a.maskfile))['experts_by_mass_asc']
    dom = [json.loads(l) for l in open('/workspace/raft_eval.jsonl', encoding='utf-8')]
    gen = [json.loads(l) for l in open('/workspace/general_it.jsonl', encoding='utf-8')] if os.path.exists('/workspace/general_it.jsonl') else None
    # salva i pesi cold (su CPU, per non saturare la VRAM)
    saved = {}
    for l in range(NL):
        exp = model.model.layers[l].mlp.experts
        idx = torch.tensor(cold[str(l)][:n_mask])
        saved[l] = (idx, exp.gate_up_proj.data[idx].clone().cpu(), exp.down_proj.data[idx].clone().cpu())
    log(f"salvati {n_mask}/{E} cold-expert per layer")

    results = {}
    def eval_all(tag):
        r = {'domain': round(ppl(model, tok, dom), 3)}
        if gen: r['general'] = round(ppl(model, tok, gen), 3)
        results[tag] = r; log(f"{tag}: {r}")

    eval_all('full')
    for bits in (4, 2):
        for l in range(NL):
            exp = model.model.layers[l].mlp.experts; idx = saved[l][0]
            for e in idx.tolist():
                exp.gate_up_proj.data[e] = fake_quant(exp.gate_up_proj.data[e], bits)
                exp.down_proj.data[e] = fake_quant(exp.down_proj.data[e], bits)
        eval_all(f'cold_int{bits}')
        for l in range(NL):  # restore
            exp = model.model.layers[l].mlp.experts; idx, gu, dn = saved[l]
            exp.gate_up_proj.data[idx] = gu.to(exp.gate_up_proj.device, exp.gate_up_proj.dtype)
            exp.down_proj.data[idx] = dn.to(exp.down_proj.device, exp.down_proj.dtype)
    # cold dropped (= zero, approssima il pruning)
    for l in range(NL):
        exp = model.model.layers[l].mlp.experts; idx = saved[l][0]
        exp.gate_up_proj.data[idx] = 0; exp.down_proj.data[idx] = 0
    eval_all('cold_dropped')

    b = results['full']
    for t, r in results.items():
        dr = f" (dom {r['domain']/b['domain']:.2f}x)"
        gr = f" (gen {r['general']/b['general']:.2f}x)" if 'general' in r and 'general' in b else ""
        log(f"  {t:14}{dr}{gr}")
    json.dump({'tag': a.tag, 'k': a.k, 'results': results}, open(f"{a.out}/mixedprec_{a.tag}.json", 'w'), indent=1)
    open(f"/root/MIXEDPREC_{a.tag}_DONE", 'w').close()

if __name__ == '__main__':
    main()
