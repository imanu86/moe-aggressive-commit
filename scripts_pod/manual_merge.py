"""Merge manuale LoRA+router nel base Qwen3-30B (per-expert SEPARATO), sui safetensors. Version-independent.

Base (verificato): model.layers.L.mlp.experts.{e}.{gate,up,down}_proj.weight
  gate_proj [I,H]=[768,2048], up_proj [768,2048], down_proj [H,I]=[2048,768]; mlp.gate [E,H]=[128,2048]
Adapter (fused, come rappresenta transformers 5.x):
  gate_up: lora_A [E*64,H]=[8192,2048], lora_B [2I,E*64]=[1536,8192]  (experts.base_layer.*)
  down:    lora_A [E*32,I]=[4096,768],  lora_B [H,E*32]=[2048,4096]   (experts.*)
  attn q/k/v/o: standard. gate: modules_to_save -> full replace.
Split fused->per-expert: de_gu[e]=scale*(B_gu[:,e*r:] @ A_gu[e*r:]) = [2I,H]; gate=de_gu[:I], up=de_gu[I:] (gate PRIMA di up).
Scale = alpha/r = 2.0 (gate_up 128/64; down 64/32). Orientamenti diretti; mismatch -> errore esplicito (no corruzione).

Uso: python manual_merge.py --check | python manual_merge.py
"""
import argparse, glob, json, os, re, shutil, time
import torch
from safetensors import safe_open
from safetensors.torch import save_file

BASE_SNAP = glob.glob('/workspace/hf/hub/models--Qwen--Qwen3-30B-A3B/snapshots/*/')[0]
ADP = '/workspace/qwen3-bonusx-lora/adapter_model.safetensors'
OUT = '/workspace/qwen3-bonusx-merged'
SCALE = 2.0
I = 768  # moe_intermediate_size

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def load_adapter():
    adp = {}
    with safe_open(ADP, framework='pt') as f:
        for k in f.keys():
            adp[k] = f.get_tensor(k).float()
    return adp

def add_delta(W, d, label):
    """W [out,in] fp16; d [out,in] o trasposto. Ritorna W+d nello stesso dtype."""
    if d.shape == W.shape:
        pass
    elif d.shape == (W.shape[1], W.shape[0]):
        d = d.t()
    else:
        raise SystemExit(f"[FATAL] {label}: d{tuple(d.shape)} vs W{tuple(W.shape)}")
    return (W.float() + d).to(W.dtype)

def batched_de(A, B, E, scale):
    """A [E*r, in], B [out, E*r] -> DE [E, out, in] = scale * bmm(B_e, A_e) per expert (bmm, no loop)."""
    r = A.shape[0] // E
    Ar = A.reshape(E, r, A.shape[1])                       # [E, r, in]
    Bp = B.reshape(B.shape[0], E, r).permute(1, 0, 2)      # [E, out, r]
    return scale * torch.bmm(Bp, Ar)                       # [E, out, in]

_de_cache = {}
def get_de(adp, L):
    if L not in _de_cache:
        pre = f"base_model.model.model.layers.{L}"
        DE_GU = batched_de(adp[f"{pre}.mlp.experts.base_layer.lora_A.weight"],
                           adp[f"{pre}.mlp.experts.base_layer.lora_B.weight"], 128, SCALE)  # [E,2I,H]
        DE_DN = batched_de(adp[f"{pre}.mlp.experts.lora_A.weight"],
                           adp[f"{pre}.mlp.experts.lora_B.weight"], 128, SCALE)             # [E,H,I]
        _de_cache[L] = (DE_GU, DE_DN)
    return _de_cache[L]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true'); a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    adp = load_adapter(); log(f"adapter tensori: {len(adp)}  snap={BASE_SNAP}")
    index = json.load(open(BASE_SNAP+'model.safetensors.index.json'))['weight_map']
    shards = sorted(set(index.values()))
    n = {'attn': 0, 'gate': 0, 'gu': 0, 'dn': 0}
    for shard in shards:
        with safe_open(BASE_SNAP+shard, framework='pt') as f:
            tensors = {k: f.get_tensor(k) for k in f.keys()}
        for k in list(tensors.keys()):
            m = re.match(r'model\.layers\.(\d+)\.(.+)', k)
            if not m: continue
            L = int(m.group(1)); rest = m.group(2)
            if a.check and L != 0: continue
            pre = f"base_model.model.model.layers.{L}"
            am = re.match(r'self_attn\.(q|k|v|o)_proj\.weight', rest)
            em = re.match(r'mlp\.experts\.(\d+)\.(gate|up|down)_proj\.weight', rest)
            if am:
                A = adp.get(f"{pre}.self_attn.{am.group(1)}_proj.lora_A.weight")
                B = adp.get(f"{pre}.self_attn.{am.group(1)}_proj.lora_B.weight")
                if A is None: continue
                tensors[k] = add_delta(tensors[k], SCALE*(B@A), k); n['attn'] += 1
                if a.check: log(f"  attn {am.group(1)} L{L}: ok {tuple(tensors[k].shape)}")
            elif rest == 'mlp.gate.weight':
                g = adp.get(f"{pre}.mlp.gate.weight")
                if g is None: continue
                assert g.shape == tensors[k].shape, (k, g.shape, tensors[k].shape)
                tensors[k] = g.to(tensors[k].dtype); n['gate'] += 1
                if a.check: log(f"  gate(router) L{L}: replace ok")
            elif em:
                e = int(em.group(1)); which = em.group(2)
                DE_GU, DE_DN = get_de(adp, L)
                if which == 'gate':
                    dpart = DE_GU[e][:I]; tensors[k] = add_delta(tensors[k], dpart, k); n['gu'] += 1
                elif which == 'up':
                    dpart = DE_GU[e][I:]; tensors[k] = add_delta(tensors[k], dpart, k); n['gu'] += 1
                else:  # down
                    dpart = DE_DN[e]; tensors[k] = add_delta(tensors[k], dpart, k); n['dn'] += 1
                if a.check and e == 0: log(f"  experts.0.{which} L{L}: part{tuple(dpart.shape)} W{tuple(tensors[k].shape)} ||d||/||W||={dpart.norm().item()/max(1e-9,tensors[k].float().norm().item()):.4f}")
        if a.check:
            log(f"[CHECK] layer0: {n} — STOP dry-run"); return
        save_file(tensors, OUT+'/'+shard, metadata={'format': 'pt'})
        _de_cache.clear()
        log(f"saved {shard}  cumul={n}")
    for fn in ['model.safetensors.index.json','config.json','generation_config.json',
               'tokenizer.json','tokenizer_config.json','vocab.json','merges.txt','special_tokens_map.json']:
        if os.path.exists(BASE_SNAP+fn): shutil.copy(BASE_SNAP+fn, OUT+'/'+fn)
    log(f"=== MANUAL MERGE DONE: {n} ===")
    open('/root/MANUAL_MERGE_DONE', 'w').close()

if __name__ == '__main__':
    main()
