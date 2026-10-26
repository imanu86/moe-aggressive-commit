import json, sys
from pathlib import Path
root, pack = Path(sys.argv[1]), Path(sys.argv[2])
sys.path[:0] = [str(root), str(root / "tools")]
from strata_tokenizer import Tokenizer
from serve.frontend import ChatTemplate, anthropic_to_messages
d = pack / "tokenizer"
vocab = json.loads((d / "vocab.json").read_text(encoding="utf-8")); tokens = [None] * len(vocab)
for t, n in vocab.items(): tokens[n] = t
tok = Tokenizer(tokens, (d / "merges.txt").read_text(encoding="utf-8").splitlines(), json.loads((d / "token_type.json").read_text(encoding="utf-8")))
tpl = ChatTemplate(d / "chat_template.jinja")
req = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
def n(tools):
    r = dict(req, tools=tools); m, t, kw = anthropic_to_messages(r)
    txt = tpl.render(m[:1] + m[1:2], t, **kw)   # system + first user: la parte prima dell'ultimo user non conta qui
    return len(tok.encode(txt, parse_special=True))
base = n(req["tools"]); print("totale (sistema+primo user)", base)
groups = {}
for t in req["tools"]:
    g = t["name"].split("__")[1] if t["name"].startswith("mcp__") else "interni"
    groups.setdefault(g, []).append(t)
for g, ts in groups.items():
    rest = [t for t in req["tools"] if t not in ts]
    print(f"{g:14s} {len(ts):2d} tool = {base - n(rest)} token")
for t in req["tools"]:
    if t["name"].startswith("mcp__"):
        print(f"  {t['name']:40s} {base - n([x for x in req['tools'] if x is not t])}")
