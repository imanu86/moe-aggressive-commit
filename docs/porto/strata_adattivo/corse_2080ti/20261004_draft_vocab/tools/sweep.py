"""Size/coverage trade-off of the candidate subset, offline (tokenizer only, no GPU, no engine).

Uses the upstream functions (tools/draft_vocab.py of v0.1.39: corpus_counts, covering, outside) unchanged.
Token counts of the corpus parts are cached in scratch/counts_*.pkl.
"""
from __future__ import annotations

import json
import pickle
import sys
from array import array
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORK / "tools"))
import draft_vocab as DV  # noqa: E402  (upstream, unmodified)
import strata_tokenizer as ST  # noqa: E402

GGUF = r"C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf"
RT = Path(r"D:\ds4_work\strata\Strata-data\mtp\rt")
RK = Path(r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep")


def ids_of(p: Path) -> list[int]:
    return list(array("i", p.read_bytes()))


def cached_counts(tok, name: str, path: Path):
    pk = WORK / "scratch" / f"counts_{name}.pkl"
    if pk.exists():
        return pickle.loads(pk.read_bytes())
    c = DV.corpus_counts(tok, [path])
    pk.write_bytes(pickle.dumps(c))
    return c


def cov(ids_seq, subset) -> float:
    return sum(1 for i in ids_seq if i in subset) / len(ids_seq) if ids_seq else float("nan")


def main() -> int:
    tok = ST.Tokenizer.from_gguf(GGUF)
    base = ids_of(RT / "draft_vocab.bin")
    fr = ids_of(WORK / "scratch" / "upstream_draft_vocab_fr.bin")
    assert fr[:len(base)] == base, "the upstream French subset must start with the current one"
    base_set, fr_set = set(base), set(fr)

    parts = {n: cached_counts(tok, n, WORK / "corpus" / f"{n}.txt") for n in ("it_train", "en_prose", "code", "json")}
    held = {}
    for n in ("it_ood", "it_ind"):
        held[n] = tok.encode((WORK / "heldout" / f"{n}.txt").read_text(encoding="utf-8"))
    ans = {n: json.loads((RK / n / "result.json").read_text(encoding="utf-8"))["generated_ids"]
           for n in ("A-code", "A-ledger", "A-explain")}
    for n, c in parts.items():
        print(f"corpus {n}: {sum(c.values()):,} token occurrences, {len(c):,} distinct; outside base {DV.outside(c, base):.2%}")
    for n, ids in held.items():
        print(f"held-out {n}: {len(ids):,} tokens; in base {cov(ids, base_set):.2%}; in fr {cov(ids, fr_set):.2%}")
    print("answers in base:", {n: round(100 * cov(v, base_set), 1) for n, v in ans.items()})

    def row(label, subset):
        s = set(subset)
        return (f"{label:<34} size {len(s):>7,}  +{len(s) - len(base_set):>6,}  "
                f"it_train {cov(list(parts['it_train'].elements()), s):.2%}  "
                f"it_ind {cov(held['it_ind'], s):.2%}  it_ood {cov(held['it_ood'], s):.2%}  "
                f"A-explain {cov(ans['A-explain'], s):.2%}  A-ledger {cov(ans['A-ledger'], s):.2%}")

    print()
    print("== Italian coverage sweep (union with the CURRENT subset)")
    for c in (0.90, 0.95, 0.97, 0.98, 0.985, 0.99, 0.995, 0.999):
        add = set(DV.covering(parts["it_train"], c))
        print(row(f"it c={c}", base_set | add))
    print()
    print("== Italian coverage sweep (union with the upstream FR subset = current + 5,686 French)")
    for c in (0.95, 0.98, 0.99, 0.995):
        add = set(DV.covering(parts["it_train"], c))
        print(row(f"fr+it c={c}", fr_set | add))
    print()
    print("== code / json / english parts over the current subset")
    for n in ("code", "json", "en_prose"):
        for c in (0.99, 0.995, 0.999):
            add = set(DV.covering(parts[n], c))
            print(f"{n} c={c}: picks {len(add):,}, not in base {len(add - base_set):,}; "
                  f"outside base {DV.outside(parts[n], base):.3%} -> outside union {DV.outside(parts[n], base_set | add):.3%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
