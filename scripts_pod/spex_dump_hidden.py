"""SPEX +hidden DUMP per-token: logit di confidenza per-layer/per-expert dal predittore hidden.
Estende hidden_predict.py: invece del solo recall aggregato, ADDESTRA la confidence head lineare
(W@h_L + b, BCE verso gli expert del layer L+1) sui doc di TRAIN, poi DUMPA le logit per OGNI token.
Queste logit sono l'input grezzo (pre-sigmoid) per la STS + lo scheduler del loop DSpark-fedele, in locale.

Hook identici a hidden_predict.py: mlp.gate -> top-k expert per layer (verita'); layer output -> hidden h_L.
Split PER DOCUMENTO (train = primi trainfrac dei doc) per evitare leakage; STS/loop useranno calib/test locali.

Output: /root/hidden_scores_<tag>.npz
  scores   : float16 [T, NL-1, E]   logit confidence head per (token, layer L, expert) su L->L+1
  experts  : int16   [T, NL, k]     top-k reali per allineamento/label (copia della trace)
  doclens  : int64   [Ndoc]
  n_experts, topk, n_layers, n_train_docs (scalari)
Uso: python spex_dump_hidden.py --model Qwen/Qwen3-30B-A3B --prompts /workspace/general_it.jsonl --tag q30_gen
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
    ap.add_argument('--limit', type=int, default=200); ap.add_argument('--maxtok', type=int, default=512)
    ap.add_argument('--trainfrac', type=float, default=0.6)   # doc di train per la confidence head
    ap.add_argument('--steps', type=int, default=200); ap.add_argument('--lr', type=float, default=1e-2)
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
    Hd = {i: [] for i in range(NL)}; Ex = {i: [] for i in range(NL)}; doclens = []
    with torch.no_grad():
        for j, ex in enumerate(rows):
            enc = tok(get_text(ex, tok), return_tensors='pt', truncation=True, max_length=a.maxtok).to('cuda')
            HID.clear(); EXP.clear(); model(**enc)
            n = HID[0].shape[0]; doclens.append(n)
            for i in range(NL):
                Hd[i].append(HID[i]); Ex[i].append(EXP[i])
            if (j + 1) % 40 == 0: log(f"  fwd {j+1}/{len(rows)}  tok cumul {sum(doclens)}")
    for h in hooks: h.remove()
    Hd = {i: torch.cat(Hd[i]).float() for i in range(NL)}      # [T,H] per layer
    Ex = {i: torch.cat(Ex[i]).long() for i in range(NL)}        # [T,k] per layer
    doclens = np.array(doclens, dtype=np.int64)
    T = Hd[0].shape[0]; H = Hd[0].shape[1]; dev = 'cuda'
    # split PER DOC: primi trainfrac dei doc = train per la head
    cum = np.cumsum(doclens); ntr_doc = max(1, int(round(len(doclens) * a.trainfrac)))
    tr_tok = int(cum[ntr_doc - 1])   # token dei primi ntr_doc doc
    log(f"T={T} H={H} NL={NL} E={E} k={topk} | train head su {ntr_doc}/{len(doclens)} doc = {tr_tok} tok")
    scores = np.zeros((T, NL - 1, E), dtype=np.float16)
    exp_arr = np.stack([Ex[i].numpy().astype(np.int16) for i in range(NL)], axis=1)  # [T,NL,k]
    for L in range(NL - 1):
        X = Hd[L].to(dev)
        Yh = torch.zeros(T, E, device=dev); Yh.scatter_(1, Ex[L + 1].to(dev), 1.0)
        Xtr, Ytr = X[:tr_tok], Yh[:tr_tok]
        W = torch.zeros(H, E, device=dev, requires_grad=True); b = torch.zeros(E, device=dev, requires_grad=True)
        opt = torch.optim.Adam([W, b], lr=a.lr)
        for _ in range(a.steps):
            opt.zero_grad(); loss = F.binary_cross_entropy_with_logits(Xtr @ W + b, Ytr); loss.backward(); opt.step()
        with torch.no_grad():
            sc = (X @ W + b).to(torch.float16).cpu().numpy()   # [T,E] logit per OGNI token
        scores[:, L, :] = sc
        del X, Yh, W, b, opt; torch.cuda.empty_cache()
        if L % 12 == 0: log(f"  head L{L} done")
    np.savez_compressed(f"{a.out}/hidden_scores_{a.tag}.npz",
                        scores=scores, experts=exp_arr, doclens=doclens,
                        n_experts=E, topk=topk, n_layers=NL, n_train_docs=ntr_doc)
    log(f"=== [{a.tag}] hidden_scores {scores.shape} (T,NL-1,E) + experts {exp_arr.shape} -> hidden_scores_{a.tag}.npz ===")
    open(f"/root/HIDDENSC_{a.tag}_DONE", 'w').close()

if __name__ == '__main__':
    main()
