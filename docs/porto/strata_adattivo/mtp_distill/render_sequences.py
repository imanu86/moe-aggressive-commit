"""render_sequences.py - dal corpus (conversazioni pulite) alle sequenze di token per la cattura e il training.

    python render_sequences.py --corpus D:\\ds4_work\\mtp_distill\\corpus --out D:\\ds4_work\\mtp_distill\\seqs \\
        --gguf C:\\...\\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf --strata C:\\...\\Strata-wt\\candidate \\
        --target-tokens 3500000 --seq-len 4096

Ogni conversazione e' resa con il template del server (`serve/chat_template.jinja`, stesse impostazioni Jinja di
serve/frontend.py), spezzata ai confini `<|im_start|>` in segmenti, tokenizzata segmento per segmento con il tokenizzatore
di riferimento di Strata (tools/strata_tokenizer.py, dal GGUF) e divisa in pezzi di al piu' --seq-len token ai confini
dei segmenti.  Un token "generato" (gen = 1) e' un token che il modello produrrebbe: tutto cio' che segue
`<|im_start|>assistant\\n`, compreso `<|im_end|>`.  A ogni pezzo e' aggiunto un token di coda (`\\n`): la cattura perde
l'ultima posizione del prompt, e cosi' quella perduta e' il riempitivo.

Ordine: prima le conversazioni on-policy (generate dal target), poi a giro fra le fonti, mescolate con seme fisso, con un
tetto per conversazione; si ferma al budget.  Un pezzo ogni --heldout-every va nello split `heldout`.

Scrive: seqs_ids.i32 (int32, tutti i pezzi di seguito), seqs_gen.u8 (uint8 per token), seqs_index.json (per pezzo:
off, n, conv, source, on_policy, split), render_stats.json (conteggi esatti di token).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_corpus import lang_counts  # noqa: E402

_G = {}


def _init(gguf: str, strata: str):
    sys.path.insert(0, str(Path(strata) / "tools"))
    import strata_tokenizer as ST
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    from jinja2 import TemplateError

    def raise_exception(message):
        raise TemplateError(message)

    def tojson(x, ensure_ascii=False, indent=None, separators=None, sort_keys=False):
        return json.dumps(x, ensure_ascii=ensure_ascii, indent=indent, separators=separators, sort_keys=sort_keys)

    env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, extensions=["jinja2.ext.loopcontrols"])
    env.filters["tojson"] = tojson
    env.globals["raise_exception"] = raise_exception
    _G["tpl"] = env.from_string((Path(strata) / "serve" / "chat_template.jinja").read_text(encoding="utf-8"))
    _G["tok"] = ST.Tokenizer.from_gguf(gguf)
    _G["nl"] = _G["tok"].encode("\n")
    assert len(_G["nl"]) == 1


def render_conv(conv: dict) -> str | None:
    msgs = []
    for m in conv["messages"]:
        mm = {"role": m["role"], "content": m.get("content") or ""}
        if m.get("tool_calls"):
            mm["tool_calls"] = [{"function": {"name": tc["name"], "arguments": tc.get("arguments") or {}}} for tc in m["tool_calls"]]
        msgs.append(mm)
    try:
        return _G["tpl"].render(messages=msgs, tools=None, add_generation_prompt=False)
    except Exception:
        return None


_SEG = re.compile(r"(?=<\|im_start\|>)")
_ROLE = re.compile(r"^<\|im_start\|>(\w+)\n")


def work(job) -> dict:
    """Una conversazione -> i suoi pezzi {ids, gen} (liste), con contatori."""
    conv, seq_len, cap_tokens = job
    text = render_conv(conv)
    if text is None:
        return {"chunks": [], "err": 1}
    tok = _G["tok"]
    segs = [s for s in _SEG.split(text) if s]
    chunks, cur_ids, cur_gen = [], [], []

    def flush():
        if len(cur_ids) >= 64 and sum(cur_gen) >= 16:
            chunks.append({"ids": cur_ids + _G["nl"], "gen": cur_gen + [0]})

    total = 0
    it_words = en_words = 0
    for s in segs:
        m = _ROLE.match(s)
        role = m.group(1) if m else "user"
        ids = tok.encode(s, parse_special=True)
        if role == "assistant":
            head = len(tok.encode(m.group(0), parse_special=True))   # <|im_start|>assistant\n: prompt
            tail = 1 if s.endswith("\n") else 0                          # il \n dopo <|im_end|>: template
            gen = [0] * head + [1] * max(0, len(ids) - head - tail) + [0] * tail
            a, b = lang_counts(s)
            it_words += a
            en_words += b
        else:
            gen = [0] * len(ids)
        if len(ids) > seq_len - 1:
            ids, gen = ids[: seq_len - 1], gen[: seq_len - 1]
        if len(cur_ids) + len(ids) > seq_len - 1:
            flush()
            cur_ids, cur_gen = [], []
            if total >= cap_tokens:
                break
        cur_ids += ids
        cur_gen += gen
        total += len(ids)
    flush()
    return {"chunks": chunks, "err": 0, "it": it_words, "en": en_words}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--gguf", required=True, help="il primo shard GGUF del target: il suo tokenizzatore")
    ap.add_argument("--strata", required=True, help="il worktree di Strata (serve/chat_template.jinja, tools/strata_tokenizer.py)")
    ap.add_argument("--target-tokens", type=float, default=3.5e6)
    ap.add_argument("--seq-len", type=int, default=4096)
    ap.add_argument("--cap-per-conv", type=int, default=32768, help="token al massimo da una conversazione")
    ap.add_argument("--heldout-every", type=int, default=33)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed", type=int, default=20261012)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    convs = []
    for shard in sorted(Path(a.corpus).glob("conv_*.jsonl")):
        with open(shard, encoding="utf-8") as fh:
            for line in fh:
                c = json.loads(line)
                convs.append(c)
    rnd = random.Random(a.seed)
    on = [c for c in convs if c.get("on_policy")]
    by_src = {}
    for c in convs:
        if not c.get("on_policy"):
            by_src.setdefault(c["source"], []).append(c)
    for v in by_src.values():
        rnd.shuffle(v)
    order = list(on)
    srcs = sorted(by_src)
    i = 0
    while any(by_src[s] for s in srcs):
        s = srcs[i % len(srcs)]
        i += 1
        if by_src[s]:
            order.append(by_src[s].pop())
    print(f"{len(convs)} conversazioni ({len(on)} on-policy); budget {a.target_tokens:.0f} token, pezzi di {a.seq_len}")
    t0 = time.time()
    ids_all, gen_all, index = [], [], []
    stats = Counter()
    per_src = {}
    total = 0
    k = 0
    batch = max(8, 8 * a.workers)   # a lotti: il budget si raggiunge senza fermare un pool a meta' (terminate() su
    #                                  Windows cade in un send concorrente)
    with Pool(max(1, a.workers), initializer=_init, initargs=(a.gguf, a.strata)) as pool:
        for b0 in range(0, len(order), batch):
            convs_b = order[b0: b0 + batch]
            results = pool.map(work, [(c, a.seq_len, a.cap_per_conv) for c in convs_b], chunksize=1)
            for conv, res in zip(convs_b, results):
                stats["render_errors"] += res["err"]
                stats["it_words"] += res.get("it", 0)
                stats["en_words"] += res.get("en", 0)
                for ch in res["chunks"]:
                    if total >= a.target_tokens:
                        break
                    n = len(ch["ids"])
                    split = "heldout" if (k % a.heldout_every == a.heldout_every - 1) else "train"
                    index.append({"i": k, "off": total, "n": n, "conv": conv["id"], "source": conv["source"],
                                  "on_policy": bool(conv.get("on_policy")), "split": split})
                    ids_all.append(np.asarray(ch["ids"], dtype=np.int32))
                    gen_all.append(np.asarray(ch["gen"], dtype=np.uint8))
                    total += n
                    k += 1
                    ps = per_src.setdefault(conv["source"], Counter())
                    ps["tokens"] += n
                    ps["gen_tokens"] += int(sum(ch["gen"]))
                    ps["chunks"] += 1
                    stats["gen_tokens"] += int(sum(ch["gen"]))
                    if conv.get("on_policy"):
                        stats["on_policy_tokens"] += n
                    if split == "heldout":
                        stats["heldout_tokens"] += n
            print(f"  {len(index)} pezzi, {total} token, {time.time() - t0:.0f} s", flush=True)
            if total >= a.target_tokens:
                break
    np.concatenate(ids_all).tofile(out / "seqs_ids.i32")
    np.concatenate(gen_all).tofile(out / "seqs_gen.u8")
    (out / "seqs_index.json").write_text(json.dumps(index), encoding="utf-8")
    rep = {"chunks": len(index), "tokens": total, "gen_tokens": stats["gen_tokens"],
           "gen_share": round(stats["gen_tokens"] / max(1, total), 3), "heldout_tokens": stats["heldout_tokens"],
           "on_policy_tokens": stats["on_policy_tokens"], "seq_len": a.seq_len,
           "italian_share_assistant_text": round(stats["it_words"] / max(1, stats["it_words"] + stats["en_words"]), 3),
           "render_errors": stats["render_errors"], "per_source": {s: dict(v) for s, v in per_src.items()},
           "seconds": round(time.time() - t0, 1)}
    (out / "render_stats.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
