"""Track REAP-ds4 — corpora per l'eval ppl bias-mask (docs/REAP_DS4_eval_plan.md §3).

DOM: item raft_eval DISGIUNTI da quelli usati per la trace/mask (anti-overfit della
mask sul suo set di calibrazione): la trace ha usato extract {i*9, i=0..15} ∪ explain
{7,45,91,133}; qui si pesca dal complemento, in ordine, testo = user + "\n" + gold,
impacchettato in 4 chunk da ~2800 char (~750-800 tok). Testi KB GITIGNORED; nel
manifest committato: indici, sha256, char/chunk.

GEN: stesso metodo del ledger (build_general_it.py): wikimedia/wikipedia 20231101.it
streaming, articoli >=600 char troncati a 3000, impacchettati in 2 chunk da ~2900 char.
I chunk GEN si committano (contenuto wiki, CC-BY-SA, provenienza nel manifest).

Uso: python scripts/reap_build_eval_corpora.py
"""
import hashlib
import json
import os

RAFT = r"C:/Users/imanu/source/repos/bonus-kb/bonusx-kb/retrieval/ft/raft_eval.jsonl"
BASE = os.path.join(os.path.dirname(__file__), "..", "runs", "reap",
                    "2026-07-05_eval_biasmask", "corpus")
TRACE_EXTRACT = {i * 9 for i in range(16)}
TRACE_EXPLAIN = {7, 45, 91, 133}
USED_BY_TRACE = TRACE_EXTRACT | TRACE_EXPLAIN
DOM_CHUNKS, DOM_CHARS = 4, 2800
GEN_CHUNKS, GEN_CHARS = 2, 2900
# v2 (mandato paper-grade): >=10 chunk appaiati per bootstrap CI
V2_DOM_CHUNKS, V2_DOM_CHARS = 10, 2200
V2_GEN_CHUNKS, V2_GEN_CHARS = 10, 2200
V2_WIKI_ARTICLES = 40


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def pack(pieces, n_chunks, chars_per_chunk):
    chunks, cur, used = [], "", []
    cur_ids = []
    for pid, text in pieces:
        if len(cur) >= chars_per_chunk:
            chunks.append((cur, cur_ids))
            cur, cur_ids = "", []
            if len(chunks) == n_chunks:
                break
        cur += text + "\n\n"
        cur_ids.append(pid)
    if len(chunks) < n_chunks and cur:
        chunks.append((cur, cur_ids))
    assert len(chunks) == n_chunks, f"materiale insufficiente: {len(chunks)}"
    return chunks


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", action="store_true",
                    help="corpora v2: 10+10 chunk per bootstrap CI (mandato paper-grade)")
    a = ap.parse_args()
    base = BASE.replace("_eval_biasmask", "_eval_biasmask_v2") if a.v2 else BASE
    dom_chunks, dom_chars = (V2_DOM_CHUNKS, V2_DOM_CHARS) if a.v2 else (DOM_CHUNKS, DOM_CHARS)
    gen_chunks, gen_chars = (V2_GEN_CHUNKS, V2_GEN_CHARS) if a.v2 else (GEN_CHUNKS, GEN_CHARS)
    n_wiki = V2_WIKI_ARTICLES if a.v2 else 12

    os.makedirs(base, exist_ok=True)
    manifest = {"dom": [], "gen": [],
                "nota": "dom: raft_eval item DISGIUNTI dalla trace (anti-overfit mask); "
                        "gen: wikimedia/wikipedia 20231101.it come build_general_it.py"}

    rows = [json.loads(l) for l in open(RAFT, encoding="utf-8")]
    pieces = []
    for i, r in enumerate(rows):
        if i in USED_BY_TRACE:
            continue
        m = r["messages"]
        pieces.append((i, m[1]["content"] + "\n" + m[2]["content"]))
    for ci, (text, ids) in enumerate(pack(pieces, dom_chunks, dom_chars)):
        name = f"dom_chunk{ci}.txt"
        with open(os.path.join(base, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        manifest["dom"].append({"file": name, "raft_indices": ids,
                                "chars": len(text), "sha256": sha(text)})

    from datasets import load_dataset
    ds = load_dataset("wikimedia/wikipedia", "20231101.it", split="train",
                      streaming=True)
    wiki = []
    for j, r in enumerate(ds):
        t = (r.get("text") or "").strip()
        if len(t) < 600:
            continue
        wiki.append((r.get("title", f"art{j}"), t[:3000]))
        if len(wiki) >= n_wiki:
            break
    for ci, (text, titles) in enumerate(pack(wiki, gen_chunks, gen_chars)):
        name = f"gen_chunk{ci}.txt"
        with open(os.path.join(base, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        manifest["gen"].append({"file": name, "wiki_titles": titles,
                                "chars": len(text), "sha256": sha(text)})

    with open(os.path.join(base, "corpus_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    for k in ("dom", "gen"):
        tot = sum(c["chars"] for c in manifest[k])
        print(f"{k}: {len(manifest[k])} chunk, {tot} char (~{tot // 3.6:.0f} tok stimati)")
    print("manifest:", os.path.join(base, "corpus_manifest.json"))


if __name__ == "__main__":
    main()
