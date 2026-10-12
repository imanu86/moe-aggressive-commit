"""ood_prompts.py - un piccolo set di prompt fuori dal dominio del corpus (niente dati personali) per bench_pack.py.

    python3 ood_prompts.py --gguf <shard 1 del GGUF> --strata <worktree Strata> --out $D/ood_seqs
    python3 bench_pack.py ... --seqs $D/ood_seqs --n 16 --prompt-tokens 0 --max-new 256 --mtp A --mtp B

Inglese generico, domande brevi in italiano non tecnico, JSON / tool-call, riassunti.  Resi con il template del server
(add_generation_prompt: il modello parte da `<|im_start|>assistant\\n`, come nell'uso reale) e scritti nel formato di
render_sequences (seqs_ids.i32, seqs_gen.u8, seqs_index.json) con split heldout.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import render_sequences as RS

TEXT = ("The city council met on Tuesday to discuss the new bike lanes planned for the river district. Supporters said "
        "the lanes would cut traffic and make the area safer for children walking to school, while several shop owners "
        "worried about losing parking spaces in front of their stores. After two hours of debate the council agreed to "
        "build a pilot section of one kilometre, measure traffic and sales for six months, and vote again in spring.")
TESTO = ("La biblioteca del paese restera' chiusa per tutto il mese di agosto per lavori di ristrutturazione: verranno "
         "rifatti l'impianto elettrico e il tetto della sala lettura. Durante la chiusura i libri in prestito potranno "
         "essere restituiti nella cassetta accanto all'ingresso, e il servizio di prestito a domicilio per gli anziani "
         "continuera' il martedi' e il venerdi'. La riapertura e' prevista per il primo settembre con un orario piu' lungo.")
TOOLS = [{"type": "function", "function": {"name": "get_weather", "description": "Current weather for a city",
                                           "parameters": {"type": "object", "properties": {
                                               "city": {"type": "string"}, "unit": {"type": "string",
                                                                                    "enum": ["celsius", "fahrenheit"]}},
                                               "required": ["city"]}}}]

PROMPTS = [
    ("en", [{"role": "user", "content": "Explain in simple terms why the sky is blue."}], None),
    ("en", [{"role": "user", "content": "Write a short poem about autumn leaves."}], None),
    ("en", [{"role": "user", "content": "What are three tips for sleeping better? Keep it brief."}], None),
    ("en", [{"role": "user", "content": "Compare trains and planes for a 600 km trip in Europe."}], None),
    ("it", [{"role": "user", "content": "Che differenza c'e' tra un museo e una galleria d'arte?"}], None),
    ("it", [{"role": "user", "content": "Mi consigli una ricetta semplice per una cena estiva?"}], None),
    ("it", [{"role": "user", "content": "Perche' in autunno le foglie cambiano colore?"}], None),
    ("it", [{"role": "user", "content": "Come posso imparare a nuotare da adulto?"}], None),
    ("json", [{"role": "user", "content": "Return a JSON object describing a book with fields title, author, year and "
                                          "tags (an array of strings). Output only the JSON."}], None),
    ("json", [{"role": "user", "content": "Converti in JSON questa lista: mele 3, pere 5, banane 2. Usa un array di "
                                          "oggetti con nome e quantita'."}], None),
    ("tool", [{"role": "user", "content": "What's the weather like in Lisbon right now, in celsius?"}], TOOLS),
    ("tool", [{"role": "user", "content": "Che tempo fa a Torino?"}], TOOLS),
    ("sum", [{"role": "user", "content": "Summarize this news item in two sentences:\n\n" + TEXT}], None),
    ("sum", [{"role": "user", "content": "Riassumi in tre punti elenco:\n\n" + TESTO}], None),
    ("sum", [{"role": "user", "content": "Give a one-line headline for this text:\n\n" + TEXT}], None),
    ("en", [{"role": "user", "content": "List five countries in South America and their capitals."}], None),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--strata", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    RS._init(a.gguf, a.strata)
    tpl, tok = RS._G["tpl"], RS._G["tok"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ids_all, gen_all, index = [], [], []
    for k, (kind, msgs, tools) in enumerate(PROMPTS):
        text = tpl.render(messages=msgs, tools=tools, add_generation_prompt=True)
        ids = tok.encode(text, parse_special=True)
        index.append({"i": k, "off": len(ids_all), "n": len(ids), "conv": f"ood-{kind}-{k}", "source": "ood",
                      "on_policy": False, "split": "heldout", "kind": kind})
        ids_all += ids
        gen_all += [0] * len(ids)
    np.asarray(ids_all, dtype=np.int32).tofile(out / "seqs_ids.i32")
    np.asarray(gen_all, dtype=np.uint8).tofile(out / "seqs_gen.u8")
    (out / "seqs_index.json").write_text(json.dumps(index))
    print(f"{len(index)} prompt, {len(ids_all)} token, lunghezze {[e['n'] for e in index]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
