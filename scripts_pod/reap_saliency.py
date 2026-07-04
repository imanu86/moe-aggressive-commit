"""STEP F+ — SALIENCY REAP vera (arxiv 2510.13999, eq.9): per (layer,expert)
   REAP S_j = MEDIA CONDIZIONALE sui token attivi di  g_j * || f_j ||   (frequency-agnostic!)
     dove g_j = peso di routing, f_j = down_proj(act(gate)*up) = output dell'expert.
   EAN E_j = SOMMA (frequency-weighted) degli stessi contributi -> baseline "expert-activation-norm".
Differenza chiave vs la massa-di-routing usata finora: REAP normalizza per il NUMERO di token attivi,
quindi NON e' un proxy di frequenza -> primo test onesto "saliency > frequenza".

Produce ranking per-layer ASCENDENTE (coldest first) in 2 chiavi, entrambe consumabili da prune_validate --maskfile:
  experts_by_mass_asc  = ranking REAP (media condizionale)   <-- default di prune_validate
  experts_by_ean_asc   = ranking EAN (somma)                 <-- usare con prune_validate --maskkey experts_by_ean_asc

Uso: python reap_saliency.py --model Qwen/Qwen3-30B-A3B --tag base   -> /root/reap_saliency_base.json
Poi: python prune_validate.py --model Qwen/Qwen3-30B-A3B --k 50 --maskfile /root/reap_saliency_base.json --tag prune50_reap
"""
import argparse, json, time
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.models.qwen3_moe import modeling_qwen3_moe as M

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

SAL = {}   # (layer, expert) -> somma di g*||f||  (double)
CNT = {}   # (layer, expert) -> n. token attivi   (int)

def patched_forward(self, hidden_states, top_k_index, top_k_weights):
    final = torch.zeros_like(hidden_states)
    with torch.no_grad():
        em = F.one_hot(top_k_index, num_classes=self.num_experts).permute(2, 1, 0)
        hit = torch.greater(em.sum(dim=(-1, -2)), 0).nonzero()
    for ei in hit:
        ei = ei[0]
        if ei == self.num_experts: continue
        pos, tok = torch.where(em[ei])
        cs = hidden_states[tok]
        gate, up = F.linear(cs, self.gate_up_proj[ei]).chunk(2, dim=-1)
        inter = self.act_fn(gate) * up                                  # [n_tok, I]
        fj = F.linear(inter, self.down_proj[ei])                        # [n_tok, H]  output dell'expert
        g = top_k_weights[tok, pos]                                     # [n_tok]  peso di routing
        contrib = (g.double() * fj.double().norm(dim=-1)).sum()         # sum_token g*||f||
        key = (int(self.layer_id), int(ei))
        SAL[key] = (SAL[key] + contrib) if key in SAL else contrib
        CNT[key] = CNT.get(key, 0) + int(fj.shape[0])
        final.index_add_(0, tok, (fj * g[:, None]).to(final.dtype))
    return final

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--tag', required=True)
    ap.add_argument('--prompts', default='/workspace/raft_eval.jsonl'); ap.add_argument('--out', default='/root')
    ap.add_argument('--limit', type=int, default=152)
    a = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(a.model)
    log(f"load {a.model}")
    model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map={'': 0}); model.eval()
    NL = int(model.config.num_hidden_layers); E = int(model.config.num_experts)
    for i in range(NL):
        model.model.layers[i].mlp.experts.layer_id = i
    M.Qwen3MoeExperts.forward = patched_forward
    log(f"patched. NL={NL} E={E}")

    rows = [json.loads(l) for l in open(a.prompts, encoding='utf-8')][:a.limit]
    with torch.no_grad():
        for j, ex in enumerate(rows):
            enc = tok.apply_chat_template(ex['messages'][:2], add_generation_prompt=True,
                                          return_tensors='pt', return_dict=True).to('cuda')
            model(**enc)
            if (j + 1) % 25 == 0: log(f"  {j+1}/{len(rows)}")

    # ranking per-layer ASCENDENTE (coldest first). Expert mai attivati (CNT=0) -> REAP 0 -> piu' freddi.
    experts_by_mass_asc = {}    # per REAP (media condizionale) -> default consumato da prune_validate
    experts_by_ean_asc = {}     # per EAN (somma)
    reap_per_layer = {}; n_cnt0 = 0
    for l in range(NL):
        reap = []; ean = []
        for e in range(E):
            s = float(SAL.get((l, e), 0.0)); c = int(CNT.get((l, e), 0))
            r = (s / c) if c > 0 else 0.0
            if c == 0: n_cnt0 += 1
            reap.append((e, r)); ean.append((e, s))
        reap.sort(key=lambda x: x[1]); ean.sort(key=lambda x: x[1])   # ascendente
        experts_by_mass_asc[str(l)] = [e for e, _ in reap]
        experts_by_ean_asc[str(l)] = [e for e, _ in ean]
        reap_per_layer[str(l)] = {str(e): v for e, v in reap}
    res = {'tag': a.tag, 'E': E, 'n_layers': NL, 'metric': 'reap_eq9_conditional_mean',
           'n_expert_cnt0': n_cnt0,                       # copertura rada = confondente da dichiarare
           'experts_by_mass_asc': experts_by_mass_asc,    # REAP
           'experts_by_ean_asc': experts_by_ean_asc,      # EAN
           'reap': reap_per_layer}
    json.dump(res, open(f"{a.out}/reap_saliency_{a.tag}.json", 'w'), indent=1)
    log(f"=== [{a.tag}] REAP salvata: reap_saliency_{a.tag}.json (NL={NL}, E={E}, expert CNT=0: {n_cnt0}) ===")
    open(f"/root/REAP_{a.tag}_DONE", 'w').close()

if __name__ == '__main__':
    main()
