"""coverage_dsv2.py — PASSO 1 del metodo "osserva-poi-comprimi" (NON predittivo).

Misura la headroom di compressione del metodo a DUE PASSATE (osserva un prompt -> comprimi il resto ->
ri-esegui). Tre metriche, perche' la domanda giusta e' PER-PROMPT, non aggregata:

  A) PER-PROMPT working set: quanti expert/layer accende UN SINGOLO prompt. E' il soffitto di
     compressione per il caso "ri-esegui lo stesso prompt": tutto cio' che non e' nel set e' spegnibile
     quasi-lossless per quel prompt (router deterministico -> riseleziona gli stessi).
  B) UNIONE su tutti i prompt: il working set se NON specializzi (caso pessimo, prompt eterogenei).
  C) STABILITA cross-prompt (Jaccard medio): quanto i working set di prompt DIVERSI si sovrappongono.
     Alta su un dominio narrow => un set osservato una volta vale per tutto il dominio
     (osserva-una-volta-comprimi-sempre). Bassa => serve ri-osservare ad ogni prompt.

Solo prefill + conteggio routing (niente generazione lenta, niente predizione).

Uso:  python -u scripts/coverage_dsv2.py --source codegen --n 8
      python -u scripts/coverage_dsv2.py --prompts-file C:/Users/imanu/llama/casino_test_input.json --n 20
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
import os
import statistics as st


def load_prompts(source: str, prompts_file: str, n: int):
    if prompts_file:
        with open(prompts_file, encoding="utf-8") as fh:
            raw = fh.read().strip()
        out = []
        # prova come JSON (array di dict/str) poi come JSONL
        try:
            data = json.loads(raw)
            seq = data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            seq = [json.loads(l) for l in raw.splitlines() if l.strip()]
        for o in seq:
            if isinstance(o, str):
                out.append(o)
            elif isinstance(o, dict):
                p = o.get("prompt") or o.get("text") or o.get("content") or o.get("input")
                if isinstance(p, list):
                    p = " ".join(str(x) for x in p)
                if p:
                    out.append(str(p))
        return out[:n]
    from msc.validator.python_unit_tests import PythonUnitTestValidator
    return [it.prompt for it in PythonUnitTestValidator("data/codegen_problems.jsonl").items()[:n]]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--memmap", default="D:/dsv2_memmap")
    p.add_argument("--source", default="codegen")
    p.add_argument("--prompts-file", default="")
    p.add_argument("--n", type=int, default=8)
    p.add_argument("--cap", type=int, default=16)
    args = p.parse_args()

    import torch
    from transformers import AutoTokenizer
    from validate_probe_dsv2 import load_nonexpert_on_gpu, open_memmaps, ExpertsRoutingCapture, HF
    from msc.hierarchy.olmoe_cache import install_expert_cache, MemmapBacking
    from msc.instrument.router_hooks import RouterHookSpec

    prompts = load_prompts(args.source, args.prompts_file, args.n)
    print(f"[cov] {len(prompts)} prompt da '{args.prompts_file or args.source}'")

    tok = AutoTokenizer.from_pretrained(HF)
    model, cfg = load_nonexpert_on_gpu(HF, "cuda", torch.bfloat16)
    gu, dn = open_memmaps(args.memmap)
    h = install_expert_cache(model, args.cap, {i: set() for i in range(cfg.num_hidden_layers)},
                             backing_factory=lambda li, e: MemmapBacking(gu, dn, li, int(e.num_experts)))
    first_moe = RouterHookSpec.for_model(HF).first_moe_layer
    E = int(cfg.n_routed_experts)
    os.makedirs("runs", exist_ok=True)

    # cattura PER-PROMPT: working set (set di expert per layer) di ciascun prompt
    per_prompt_sets = []   # [ {layer: set(experts)} ]  uno per prompt
    union_counts = collections.defaultdict(collections.Counter)
    for i, prompt in enumerate(prompts):
        tp = f"runs/_cov_p{i}.jsonl"
        enc = tok.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True,
                                      return_tensors="pt", return_dict=True).to("cuda")
        with ExpertsRoutingCapture(model, first_moe, tp):
            with torch.no_grad():
                model(**enc)
        sets = collections.defaultdict(set)
        with open(tp, encoding="utf-8") as fh:
            for line in fh:
                o = json.loads(line)
                ly = int(o["layer"])
                for e in o["topk_ids"]:
                    sets[ly].add(int(e)); union_counts[ly][int(e)] += 1
        per_prompt_sets.append(sets)
        os.remove(tp)
        ntok = enc["input_ids"].shape[1]
        meanset = st.mean(len(s) for s in sets.values()) if sets else 0
        print(f"[cov] prompt {i+1}/{len(prompts)} ({ntok} tok): working set medio {meanset:.0f}/{E} expert/layer", flush=True)
    h.remove()

    layers = sorted(union_counts)

    # A) PER-PROMPT working set medio (su tutti i layer e tutti i prompt)
    per_prompt_mean = [st.mean(len(ps[ly]) for ly in layers) for ps in per_prompt_sets]
    A = st.mean(per_prompt_mean)
    # B) UNIONE per layer
    union_sizes = [len(union_counts[ly]) for ly in layers]
    B = st.mean(union_sizes)
    # C) Jaccard medio cross-prompt per layer
    jac = []
    for ly in layers:
        ss = [ps[ly] for ps in per_prompt_sets if ps[ly]]
        for a, b in itertools.combinations(ss, 2):
            u = len(a | b)
            if u:
                jac.append(len(a & b) / u)
    C = st.mean(jac) if jac else float("nan")

    print(f"\n=== DS2-Lite (E={E}/layer), {len(prompts)} prompt da '{args.prompts_file or args.source}' ===")
    print(f"A) PER-PROMPT working set:  {A:.1f}/{E} expert/layer  "
          f"=> per UN prompt comprimibile ~{100*(1-A/E):.0f}% degli expert")
    print(f"B) UNIONE su tutti i prompt: {B:.1f}/{E} expert/layer  "
          f"=> senza specializzare comprimibile ~{100*(1-B/E):.0f}%")
    print(f"C) Jaccard medio cross-prompt: {C:.2f}  "
          f"=> {'ALTO: stesso set tra prompt (osserva-1-volta-comprimi-sempre)' if C>0.6 else 'BASSO: ogni prompt usa un set diverso (ri-osserva ogni volta)'}")
    print(f"\n[cov] LETTURA: A basso = un prompt usa pochi expert (margine per-prompt). "
          f"C alto = il margine vale per tutto il dominio. Servono ENTRAMBI per 'osserva-poi-comprimi' su dominio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
