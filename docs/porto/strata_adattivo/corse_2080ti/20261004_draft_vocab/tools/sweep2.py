"""Combination sweep: which parts at which coverage, with the held-out sets (union semantics == chained --corpus runs)."""
from __future__ import annotations
import json, pickle, sys
from array import array
from pathlib import Path
WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORK / "tools"))
import draft_vocab as DV, strata_tokenizer as ST  # upstream, unmodified
GGUF = r"C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf"
RT = Path(r"D:\ds4_work\strata\Strata-data\mtp\rt")
RK = Path(r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep")
ids_of = lambda p: list(array("i", p.read_bytes()))
tok = ST.Tokenizer.from_gguf(GGUF)
base = ids_of(RT / "draft_vocab.bin"); B = set(base)
FR = set(ids_of(WORK / "scratch" / "upstream_draft_vocab_fr.bin"))
def counts(n):
    pk = WORK / "scratch" / f"counts_{n}.pkl"
    if pk.exists(): return pickle.loads(pk.read_bytes())
    c = DV.corpus_counts(tok, [WORK / "corpus" / f"{n}.txt"]); pk.write_bytes(pickle.dumps(c)); return c
P = {n: counts(n) for n in ("it_train", "en_prose", "code", "json")}
H = {n: tok.encode((WORK / "heldout" / f"{n}.txt").read_text(encoding="utf-8")) for n in ("it_ood", "it_ind", "en_ind", "code_ind", "json_ind")}
A = {n: json.loads((RK / n / "result.json").read_text(encoding="utf-8"))["generated_ids"] for n in ("A-code", "A-ledger", "A-explain")}
cov = lambda ids, s: 100 * sum(i in s for i in ids) / len(ids)
def show(label, s):
    print(f"{label:<28}{len(s):>8,}{len(s)-len(B):>8,} | " + " ".join(f"{k}:{cov(v, s):5.1f}" for k, v in H.items()) + " | " + " ".join(f"{k[2:]}:{cov(v, s):5.1f}" for k, v in A.items()))
print(f"{'':<28}{'size':>8}{'added':>8} | held-out coverage % | answers %")
show("current (en)", B)
show("fr (upstream shipped)", FR)
pick = lambda n, c: set(DV.covering(P[n], c))
for ci in (0.98, 0.99, 0.995):
    show(f"it{ci}", B | pick("it_train", ci))
for cc in (0.99, 0.995):
    show(f"it.99+code{cc}+json+en", B | pick("it_train", .99) | pick("code", cc) | pick("json", cc) | pick("en_prose", cc))
for ci in (0.99, 0.995):
    s = B | pick("it_train", ci) | pick("code", .99) | pick("json", .99) | pick("en_prose", .99)
    show(f"it{ci}+code.99+json.99+en.99", s)
    show(f"  ... + fr", s | FR)
show("it.99 only code.99 (no en/json)", B | pick("it_train", .99) | pick("code", .99))
print()
# marginal contribution of each part to the union (c=0.99)
u = B | pick("it_train", .99) | pick("code", .99) | pick("json", .99) | pick("en_prose", .99)
for n in ("it_train", "code", "json", "en_prose"):
    only = pick(n, .99) - B
    others = (u - (pick(n, .99) - B))
    print(f"{n}: adds {len(only):,} not in base; {len(only - (u - only)) if False else len(only)} of which unique-to-part:", len(only - (B | set().union(*[pick(m, .99) for m in P if m != n]))))
