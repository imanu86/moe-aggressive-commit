"""Costruisce un corpus GENERALE italiano (wikipedia-it) per l'esperimento dominio-vs-generale.
Elimina il confondente LINGUA (IT come il dominio BonusX), a differenza di wikitext-EN.
Output: /workspace/general_it.jsonl con righe {"text": ...}. Uso: python build_general_it.py [N]
"""
import json, sys
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
from datasets import load_dataset
ds = load_dataset("wikimedia/wikipedia", "20231101.it", split="train", streaming=True)
out = open("/workspace/general_it.jsonl", "w", encoding="utf-8")
n = 0
for r in ds:
    t = (r.get("text") or "").strip()
    if len(t) < 600:
        continue
    out.write(json.dumps({"text": t[:3000]}, ensure_ascii=False) + "\n")
    n += 1
    if n >= N:
        break
out.close()
print(f"wrote {n} passaggi generali IT in /workspace/general_it.jsonl")
