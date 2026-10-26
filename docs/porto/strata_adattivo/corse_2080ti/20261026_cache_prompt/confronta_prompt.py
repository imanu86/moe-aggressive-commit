"""Rende le richieste catturate con il template del server e trova il primo token diverso fra richieste consecutive.
uso: python confronta_prompt.py <root_strata_source> <pack> <cartella_richieste>"""
import json, sys
from pathlib import Path
root, pack, rd = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path[:0] = [str(root), str(root / "tools")]
from strata_tokenizer import Tokenizer
from serve.frontend import ChatTemplate, anthropic_to_messages
d = pack / "tokenizer"
vocab = json.loads((d / "vocab.json").read_text(encoding="utf-8"))
tokens = [None] * len(vocab)
for t, n in vocab.items(): tokens[n] = t
tok = Tokenizer(tokens, (d / "merges.txt").read_text(encoding="utf-8").splitlines(),
                json.loads((d / "token_type.json").read_text(encoding="utf-8")))
tpl = ChatTemplate(d / "chat_template.jinja")
res = []
for f in sorted(rd.glob("req_*.json")):
    req = json.loads(f.read_text(encoding="utf-8"))
    m, tools, kw = anthropic_to_messages(req)
    text = tpl.render(m, tools, **kw)
    ids = tok.encode(text, parse_special=True)
    res.append((f.name, text, ids)); print(f.name, "token", len(ids), "kw", kw)
for (na, ta, ia), (nb, tb, ib) in zip(res, res[1:]):
    n = next((i for i, (x, y) in enumerate(zip(ia, ib)) if x != y), min(len(ia), len(ib)))
    print(f"\n{na} -> {nb}: primo token diverso = {n} (su {len(ia)} / {len(ib)})")
    print(" A:", repr(tok.decode(ia[max(0, n - 12):n + 25])))
    print(" B:", repr(tok.decode(ib[max(0, n - 12):n + 25])))
