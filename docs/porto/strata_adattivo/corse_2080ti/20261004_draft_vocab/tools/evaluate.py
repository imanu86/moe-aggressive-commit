"""Validate the candidate files and measure coverage old vs new, offline (tokenizer only).

Checks per file: size % 4 == 0, int32 little endian, ids in [0, vocab), no duplicates, the current subset is a prefix.
Coverage = share of the tokens of a text/answer whose id is in the subset (what the draft head could ever propose).
Writes out/coverage.json and prints a markdown table.
"""
from __future__ import annotations

import json
import sys
from array import array
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORK / "tools"))
import strata_tokenizer as ST  # noqa: E402  (upstream, unmodified)

GGUF = r"C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf"
RT = Path(r"D:\ds4_work\strata\Strata-data\mtp\rt")
RK = Path(r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep")
ROW_BYTES = 1760          # Q5_K output.weight row of 2560 elements (the engine log: 40,525 ids = 68.0 MiB)

SUBSETS = {
    "current (rt/draft_vocab.bin)": RT / "draft_vocab.bin",
    "candidate it+code+json+en": WORK / "out" / "draft_vocab_it_code_en.bin",
    "variant + French": WORK / "out" / "draft_vocab_it_code_en_fr.bin",
}


def load(p: Path) -> list[int]:
    raw = p.read_bytes()
    assert len(raw) % 4 == 0, f"{p}: size not a multiple of 4"
    a = array("i")
    a.frombytes(raw)
    if sys.byteorder == "big":
        a.byteswap()
    return list(a)


def main() -> int:
    tok = ST.Tokenizer.from_gguf(GGUF)
    n = len(tok.tokens)
    ids = {k: load(p) for k, p in SUBSETS.items()}
    cur = ids["current (rt/draft_vocab.bin)"]
    for k, v in ids.items():
        assert all(0 <= i < n for i in v), f"{k}: id outside the vocabulary"
        assert len(set(v)) == len(v), f"{k}: duplicate ids"
        assert v[:len(cur)] == cur, f"{k}: the current subset is not a prefix"
        assert set(cur) <= set(v), f"{k}: not a superset"
        print(f"OK {k}: {len(v):,} ids, {len(v) * 4:,} bytes, superset+prefix of current, no duplicates, max id {max(v)}")
    print("special ids kept:", {name: (i in set(cur)) for name, i in
                                {"eos 248046": 248046, "bos/pad 248044": 248044, "im_start 248045": 248045}.items()})

    sets = {k: set(v) for k, v in ids.items()}
    texts = {}
    for name in ("A-code", "A-ledger", "A-explain"):
        texts[f"answer {name}"] = json.loads((RK / name / "result.json").read_text(encoding="utf-8"))["generated_ids"]
    # every other explain / code / ledger answer of the same folder (same prompts, other runs): a robustness check only
    extra = {"explain": [], "code": [], "ledger": []}
    for d in sorted(RK.iterdir()):
        r = d / "result.json"
        if d.is_dir() and r.exists() and d.name not in ("A-code", "A-ledger", "A-explain"):
            for kind in extra:
                if d.name.endswith("-" + kind):
                    try:
                        g = json.loads(r.read_text(encoding="utf-8")).get("generated_ids")
                    except Exception:
                        g = None
                    if g:
                        extra[kind].append(g)
    for kind, lst in extra.items():
        flat = [i for g in lst for i in g]
        if flat:
            texts[f"{len(lst)} other {kind} runs (same prompt)"] = flat
    held = {
        "held-out Italian, other domain (course texts, KB)": "it_ood",
        "held-out Italian, same repos": "it_ind",
        "held-out English docs": "en_ind",
        "held-out C++/Python code": "code_ind",
        "held-out JSON (pretty+minified)": "json_ind",
    }
    for label, name in held.items():
        texts[label] = tok.encode((WORK / "heldout" / f"{name}.txt").read_text(encoding="utf-8"))

    rows = []
    for label, seq in texts.items():
        rec = {"text": label, "tokens": len(seq)}
        for k, s in sets.items():
            rec[k] = round(100 * sum(1 for i in seq if i in s) / len(seq), 2)
        rows.append(rec)
    names = list(SUBSETS)
    print()
    print("| test text | tokens | " + " | ".join(names) + " |")
    print("|---|---:|" + "---:|" * len(names))
    for r in rows:
        print(f"| {r['text']} | {r['tokens']:,} | " + " | ".join(f"{r[k]:.1f}%" for k in names) + " |")

    cost = {}
    for k, v in ids.items():
        cost[k] = {"ids": len(v), "head_MiB": round(len(v) * ROW_BYTES / 1048576, 1),
                   "extra_head_bytes_per_draft_step": (len(v) - len(cur)) * ROW_BYTES,
                   "file_bytes": len(v) * 4}
    print()
    for k, c in cost.items():
        print(k, c)
    (WORK / "out" / "coverage.json").write_text(json.dumps({"coverage": rows, "cost": cost}, indent=1), encoding="utf-8")

    # what is still missing in the Italian answer
    miss = [i for i in texts["answer A-explain"] if i not in sets["candidate it+code+json+en"]]
    print("\nA-explain tokens still outside the candidate:", len(miss),
          [tok.token_bytes(i).decode("utf-8", "replace") for i in miss])
    return 0


if __name__ == "__main__":
    sys.exit(main())
