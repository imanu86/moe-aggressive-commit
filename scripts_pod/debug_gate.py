"""Debug: cosa ritorna model.model.layers[i].mlp.gate su un modello (bf16 vs gptqmodel)?
Serve a capire se l'hook di prune_validate ('logits, rw, se = out') e' valido sul 235B gptqmodel.
Uso: python debug_gate.py --model Qwen/Qwen3-235B-A22B-GPTQ-Int4 --gptqmodel
"""
import argparse, torch
from transformers import AutoTokenizer

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--gptqmodel', action='store_true')
    a = ap.parse_args()
    if a.gptqmodel:
        from gptqmodel import GPTQModel, BACKEND
        gm = GPTQModel.load(a.model, backend=BACKEND.TORCH, device_map={'': 0}); model = gm.model; tok = gm.tokenizer
    else:
        from transformers import AutoModelForCausalLM
        tok = AutoTokenizer.from_pretrained(a.model)
        model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map={'': 0})
    model.eval()
    mlp = model.model.layers[0].mlp
    print('MLP type:', type(mlp).__name__)
    print('gate type:', type(mlp.gate).__name__)
    cap = {}
    def hook(mod, inp, out): cap['out'] = out
    h = mlp.gate.register_forward_hook(hook)
    enc = tok('The quick brown fox jumps over the lazy dog.', return_tensors='pt').to('cuda')
    with torch.no_grad(): model(**enc)
    h.remove()
    out = cap.get('out')
    print('GATE OUT type:', type(out))
    if isinstance(out, (tuple, list)):
        print('  tuple/list len =', len(out))
        for i, x in enumerate(out):
            print(f'   [{i}] {type(x).__name__} shape={getattr(x,"shape",None)} dtype={getattr(x,"dtype",None)}')
    else:
        print('  tensor shape', getattr(out, 'shape', None), 'dtype', getattr(out, 'dtype', None))
    print('cfg: num_experts', model.config.num_experts, 'num_experts_per_tok', model.config.num_experts_per_tok,
          'num_hidden_layers', model.config.num_hidden_layers)
    print('DEBUG_GATE_DONE')

if __name__ == '__main__':
    main()
