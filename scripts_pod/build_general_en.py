"""Corpus generale EN (wikipedia-en) per le trace SPEX su OLMoE. Output /workspace/general_en.jsonl.
Usa wikimedia/wikipedia (repo namespaced, streaming) -- il repo nudo 'wikitext' non e' piu' valido nel nuovo datasets.
"""
import json, sys
from datasets import load_dataset
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
ds = load_dataset("wikimedia/wikipedia", "20231101.en", split="train", streaming=True)
out = open("/workspace/general_en.jsonl", "w", encoding="utf-8")
n = 0
for r in ds:
    t = (r.get("text") or "").strip()
    if len(t) < 600:
        continue
    out.write(json.dumps({"text": t[:1500]}) + "\n"); n += 1
    if n >= N:
        break
out.close(); print(f"wrote {n} passaggi EN in /workspace/general_en.jsonl")
