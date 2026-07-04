"""Dump routing traces per PIU' corpora in UN SOLO caricamento del modello (235B gptqmodel lento da caricare).
Hook su mlp.gate -> top-k per layer (gate 235B = tuple len 3, out[0]=logits[n,E])."""
import argparse, json, time, numpy as np, torch
def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
BUF = {}
def mk_hook(li, topk):
    def hook(mod, inp, out):
        logits = out[0] if isinstance(out, (tuple, list)) else out
        lg = logits.reshape(-1, logits.shape[-1])
        BUF[li] = torch.topk(lg, topk, dim=-1).indices.to(torch.int16).cpu()
    return hook
def get_text(ex):
    if isinstance(ex, dict):
        if 'text' in ex: return ex['text']
        if 'messages' in ex: return "\n".join(str(m.get('content','')) for m in ex['messages'])
    return str(ex)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--out', default='/workspace')
    ap.add_argument('--maxtok', type=int, default=384); ap.add_argument('--gptqmodel', action='store_true')
    ap.add_argument('--jobs', nargs='+', required=True)
    a = ap.parse_args()
    log(f"load {a.model} gptqmodel={a.gptqmodel}")
    if a.gptqmodel:
        from gptqmodel import GPTQModel, BACKEND
        gm = GPTQModel.load(a.model, backend=BACKEND.TORCH, device_map={'':0}); model=gm.model; tok=gm.tokenizer
    else:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(a.model)
        model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map={'':0})
    model.eval(); cfg=model.config
    NL=int(cfg.num_hidden_layers); topk=int(getattr(cfg,'num_experts_per_tok',8)); E=int(cfg.num_experts)
    hooks=[]
    for i in range(NL):
        mlp=model.model.layers[i].mlp
        if hasattr(mlp,'gate'): hooks.append(mlp.gate.register_forward_hook(mk_hook(i,topk)))
    log(f"hooks {len(hooks)}/{NL} topk={topk} E={E}")
    for job in a.jobs:
        tag,f,lim=job.split(':'); lim=int(lim)
        rows=[json.loads(l) if l.strip().startswith('{') else l for l in open(f,encoding='utf-8') if l.strip()][:lim]
        all_e=[]; doclens=[]; t0=time.time()
        with torch.no_grad():
            for j,ex in enumerate(rows):
                enc=tok(get_text(ex),return_tensors='pt',truncation=True,max_length=a.maxtok).to('cuda')
                BUF.clear(); model(**enc)
                ls=sorted(BUF.keys()); arr=torch.stack([BUF[i] for i in ls],dim=0).permute(1,0,2).numpy().astype(np.int16)
                all_e.append(arr); doclens.append(arr.shape[0])
                if (j+1)%25==0: log(f"  {tag} {j+1}/{len(rows)} tok {sum(doclens)} ({(time.time()-t0)/(j+1):.1f}s/p)")
        Earr=np.concatenate(all_e,axis=0)
        np.savez_compressed(f"{a.out}/traces_q235_{tag}.npz",experts=Earr,doclens=np.array(doclens),n_experts=E,topk=topk,n_layers=Earr.shape[1])
        log(f"=== {tag} {Earr.shape} -> traces_q235_{tag}.npz ==="); open(f"/workspace/TR_{tag}_DONE",'w').close()
    for h in hooks: h.remove()
    open("/workspace/T235_DONE",'w').close(); log("ALL 235B traces done")
main()
