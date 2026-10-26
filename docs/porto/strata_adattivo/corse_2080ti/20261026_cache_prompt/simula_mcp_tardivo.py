"""Simula: turno 0 senza i 7 tool di cgc-infra (MCP non ancora connesso), turno 1 con tutti i 41. Primo token diverso."""
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
def ids(tools):
    m, t, kw = anthropic_to_messages(dict(req, tools=tools)); return tok.encode(tpl.render(m, t, **kw), parse_special=True)
full = req["tools"]
def diff(a, b, label):
    n = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    print(f"{label}: turno0={len(a)} turno1={len(b)} primo token diverso={n}  -> checkpoint 16384 {'PERSO' if n < 16384 else 'ok'}")
    print("   turno0:", repr(tok.decode(a[max(0, n-6):n+8])), "\n   turno1:", repr(tok.decode(b[max(0, n-6):n+8])))
a = ids([t for t in full if not t["name"].startswith("mcp__cgc-infra__")])
diff(a, ids(full), "senza cgc-infra -> tutti")
a2 = ids([t for t in full if not t["name"].startswith("mcp__promo-sil__")])
diff(a2, ids(full), "senza promo-sil -> tutti (coda dell'elenco)")
