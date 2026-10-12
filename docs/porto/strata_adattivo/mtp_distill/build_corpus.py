"""build_corpus.py - dalle conversazioni dell'owner (Claude Code, Codex, DSH Desktop) ai turni puliti del corpus MTP.

    python build_corpus.py --out D:\\ds4_work\\mtp_distill\\corpus [--workers 6] [--claude DIR] [--codex DIR] [--dsh DIR]

Per ogni file di sessione estrae le conversazioni (turni utente / assistente con le chiamate ai tool e i loro
risultati), le bonifica con scrub.py PRIMA di scrivere qualunque byte, deduplica le risposte ripetute (sessioni
riprese, compattazioni) e scrive shard jsonl: una riga = una conversazione

    {"id", "source": "claude"|"codex"|"dsh", "model", "on_policy": bool, "messages": [{"role", "content",
     "tool_calls": [{"name", "arguments": {...}}]}, ...], "stats": {...}}

I messaggi sono gia' nel formato che il template Qwen (`serve/chat_template.jinja`) accetta: `system`, `user`,
`assistant` (con `tool_calls`), `tool`.  I pensieri NON ci sono: Claude Code e DSH li registrano vuoti, Codex li cifra;
il template rende quindi `<think>\\n\\n</think>` (come con enable_thinking=false).  `on_policy` marca i turni generati
dal target stesso (Qwen3.8 via gateway / provider strata-local): sono pochi, vengono messi per primi da
render_sequences.py.

Statistiche (solo conteggi, mai valori): conversazioni, messaggi per ruolo, caratteri per ruolo, quota di codice
(argomenti dei tool + risultati + blocchi ```), quota di italiano sul testo dell'assistente (stopword), segreti e dati
personali tolti per tipo, token STIMATI (caratteri / 3.6; il conteggio esatto lo fa render_sequences.py).
Nessun dato personale finisce in stdout: nomi file e percorsi dei progetti non vengono stampati, solo contati.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import os
import re
import sys
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrub import Scrubber  # noqa: E402

MAX_TOOL_CHARS = 6000       # un risultato di tool piu' lungo e' tenuto testa (4/5) + coda (1/5)
MAX_SYSTEM_CHARS = 6000
MAX_USER_CHARS = 20000
MAX_ASSISTANT_CHARS = 40000
MIN_ASSISTANT_CHARS = 1
SHARD_BYTES = 48 << 20

IT_STOP = set("di che il la non per con una sono della del le dei nel alla come anche questo questa più ma se "
              "essere ha gli dalla delle nella quando perché tutto fatto ora dove quindi anche già poi solo "
              "così dopo prima senza fare sul sulla fra tra nei negli alle allo agli ogni altro altra stesso "
              "verifica controlla aggiorna modifica file riga righe commit errore funziona pronto".split())
EN_STOP = set("the and of to is in that it for with as on this be are was by at from or an not have has will "
              "can which would should could their there then than been were into these those about also only "
              "just check update change file line lines commit error works ready".split())
_WORD = re.compile(r"[A-Za-zÀ-ÿ']+")
_FENCE = re.compile(r"```[\s\S]*?```")


def truncate(text: str, limit: int) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    head = limit * 4 // 5
    tail = limit - head
    cut = len(text) - head - tail
    return text[:head] + f"\n…[troncati {cut} caratteri]…\n" + text[-tail:]


def lang_counts(text: str) -> tuple[int, int]:
    """(parole italiane, parole inglesi) fra le stopword del testo non-codice."""
    it = en = 0
    for w in _WORD.findall(_FENCE.sub(" ", text).lower()):
        if w in IT_STOP:
            it += 1
        elif w in EN_STOP:
            en += 1
    return it, en


def code_chars(text: str) -> int:
    return sum(len(m.group(0)) for m in _FENCE.finditer(text))


# ------------------------------------------------------------------------------------------------ normalizzazione
class Conv:
    def __init__(self, cid: str, source: str):
        self.id = cid
        self.source = source
        self.model = None
        self.on_policy = False
        self.messages: list[dict] = []
        self.tool_names: dict[str, str] = {}   # call id -> name

    def system(self, text: str):
        text = (text or "").strip()
        if not text:
            return
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = truncate(self.messages[0]["content"] + "\n\n" + text, MAX_SYSTEM_CHARS)
        elif not self.messages:
            self.messages.append({"role": "system", "content": truncate(text, MAX_SYSTEM_CHARS)})
        else:   # un system in mezzo: il template lo rifiuta, diventa un turno utente
            self.user(text)

    def user(self, text: str):
        text = (text or "").strip()
        if not text:
            return
        if self.messages and self.messages[-1]["role"] == "user":
            self.messages[-1]["content"] = truncate(self.messages[-1]["content"] + "\n\n" + text, MAX_USER_CHARS)
        else:
            self.messages.append({"role": "user", "content": truncate(text, MAX_USER_CHARS)})

    def assistant(self, text: str, tool_calls: list[dict], model: str | None):
        text = (text or "").strip()
        tool_calls = [tc for tc in tool_calls if tc.get("name")]
        if not text and not tool_calls:
            return
        if model and not self.model:
            self.model = model
        m = {"role": "assistant", "content": truncate(text, MAX_ASSISTANT_CHARS)}
        if tool_calls:
            m["tool_calls"] = tool_calls
        if self.messages and self.messages[-1]["role"] == "assistant":   # blocchi dello stesso messaggio API
            prev = self.messages[-1]
            if prev.get("tool_calls") and text:   # testo dopo una chiamata: nuovo turno (il template non lo rende)
                self.messages.append(m)
            else:
                prev["content"] = truncate((prev["content"] + "\n\n" + text).strip(), MAX_ASSISTANT_CHARS)
                if tool_calls:
                    prev.setdefault("tool_calls", []).extend(tool_calls)
        else:
            self.messages.append(m)

    def tool(self, text: str):
        text = truncate((text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)) or "", MAX_TOOL_CHARS)
        if not self.messages or self.messages[-1]["role"] not in ("assistant", "tool"):
            self.user(text)   # un risultato senza chiamata: contesto utente
            return
        self.messages.append({"role": "tool", "content": text if text.strip() else "(nessun output)"})

    def finish(self) -> dict | None:
        msgs = self.messages
        # il template vuole un primo turno utente (dopo il system) e un ultimo turno utile
        while msgs and msgs[-1]["role"] not in ("assistant",):
            msgs.pop()
        if not any(m["role"] == "assistant" for m in msgs) or not any(m["role"] == "user" for m in msgs):
            return None
        # un assistant subito dopo il system o in testa: il template vuole user prima
        first_non_sys = 1 if msgs and msgs[0]["role"] == "system" else 0
        while len(msgs) > first_non_sys and msgs[first_non_sys]["role"] != "user":
            msgs.pop(first_non_sys)
        if not any(m["role"] == "assistant" for m in msgs):
            return None
        return {"id": self.id, "source": self.source, "model": self.model, "on_policy": self.on_policy, "messages": msgs}


def content_text(content) -> str:
    """Il testo di un `content` Anthropic/OpenAI (stringa o lista di blocchi)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, str):
                parts.append(b)
            elif isinstance(b, dict):
                t = b.get("type")
                if t in ("text", "input_text", "output_text") or (t is None and "text" in b):
                    parts.append(str(b.get("text", "")))
                elif t in ("image", "input_image", "image_url"):
                    parts.append("[immagine]")
                elif t == "tool_result":
                    parts.append(content_text(b.get("content")))
        return "\n".join(p for p in parts if p)
    if content is None:
        return ""
    return str(content)


def is_on_policy_model(model: str | None, provider: str | None = None) -> bool:
    m = (model or "").lower()
    p = (provider or "").lower()
    return "gguf" in m or "qwen" in m or "strata" in p


# ------------------------------------------------------------------------------------------------ Claude Code
def parse_claude(path: str) -> list[dict]:
    convs: dict[str, Conv] = {}
    order: list[str] = []
    stem = hashlib.sha1(path.encode("utf-8", "replace")).hexdigest()[:12]
    last_msg_id: dict[str, str | None] = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"type":"user"' not in line and '"type":"assistant"' not in line and '"type": "user"' not in line \
                    and '"type": "assistant"' not in line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            t = o.get("type")
            if t not in ("user", "assistant"):
                continue
            key = "main" if not o.get("isSidechain") else "agent:" + str(o.get("agentId") or o.get("parentUuid") or "x")
            if key not in convs:
                convs[key] = Conv(f"claude-{stem}-{len(order)}", "claude")
                order.append(key)
            c = convs[key]
            m = o.get("message") or {}
            content = m.get("content")
            if t == "user":
                if isinstance(content, list):
                    texts = []
                    for b in content:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "tool_result":
                            c.tool(content_text(b.get("content")))
                        elif b.get("type") == "text":
                            texts.append(b.get("text", ""))
                        elif b.get("type") in ("image",):
                            texts.append("[immagine]")
                    if texts:
                        c.user("\n".join(texts))
                else:
                    c.user(content_text(content))
                last_msg_id[key] = None
            else:
                model = m.get("model")
                if is_on_policy_model(model):
                    c.on_policy = True
                text_parts, calls = [], []
                for b in content if isinstance(content, list) else [{"type": "text", "text": content_text(content)}]:
                    if not isinstance(b, dict):
                        continue
                    bt = b.get("type")
                    if bt == "text":
                        text_parts.append(b.get("text", ""))
                    elif bt == "tool_use":
                        args = b.get("input")
                        calls.append({"name": str(b.get("name", "tool")), "arguments": args if isinstance(args, dict) else {"input": args}})
                        c.tool_names[str(b.get("id"))] = str(b.get("name", "tool"))
                c.assistant("\n".join(text_parts), calls, model)
    out = []
    for k in order:
        d = convs[k].finish()
        if d:
            out.append(d)
    return out


# ------------------------------------------------------------------------------------------------ Codex
def parse_codex(path: str) -> list[dict]:
    stem = hashlib.sha1(path.encode("utf-8", "replace")).hexdigest()[:12]
    c = Conv(f"codex-{stem}", "codex")
    seen_dev = False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"response_item"' not in line and '"turn_context"' not in line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            p = o.get("payload") or {}
            if o.get("type") == "turn_context":
                if p.get("model") and not c.model:
                    c.model = p.get("model")
                continue
            if o.get("type") != "response_item":
                continue
            pt = p.get("type")
            if pt == "message":
                role = p.get("role")
                text = content_text(p.get("content"))
                if role == "developer":
                    if not seen_dev:
                        c.system(text)
                        seen_dev = True
                    else:
                        c.user(text)
                elif role == "user":
                    c.user(text)
                elif role == "assistant":
                    c.assistant(text, [], c.model)
            elif pt == "function_call":
                args = p.get("arguments")
                try:
                    args = json.loads(args) if isinstance(args, str) else args
                except Exception:
                    args = {"arguments": args}
                c.assistant("", [{"name": str(p.get("name", "tool")), "arguments": args if isinstance(args, dict) else {"input": args}}], c.model)
            elif pt == "custom_tool_call":
                c.assistant("", [{"name": str(p.get("name", "tool")), "arguments": {"input": p.get("input", "")}}], c.model)
            elif pt in ("function_call_output", "custom_tool_call_output"):
                c.tool(content_text(p.get("output")))
    d = c.finish()
    return [d] if d else []


# ------------------------------------------------------------------------------------------------ DSH Desktop
def parse_dsh(path: str) -> list[dict]:
    import zstandard
    stem = hashlib.sha1(path.encode("utf-8", "replace")).hexdigest()[:12]
    c = Conv(f"dsh-{stem}", "dsh")
    raw = open(path, "rb").read()
    with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw), read_across_frames=True) as r:
        data = r.read()
    for line in data.decode("utf-8", "replace").splitlines():
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        t = o.get("type")
        d = o.get("data") or {}
        if t == "request/header":
            cfg = ((d.get("header") or {}).get("config") or {})
            if cfg.get("model") and not c.model:
                c.model = cfg.get("model")
            if is_on_policy_model(cfg.get("model"), cfg.get("provider")):
                c.on_policy = True
        elif t == "system/message":
            c.system(content_text((d.get("message") or {}).get("content")))
        elif t == "developer/message":
            c.user(content_text((d.get("message") or {}).get("content")))
        elif t == "user/message":
            c.user(content_text(d.get("content")))
        elif t == "assistant/message":
            m = d.get("message") or {}
            text_parts, calls = [], []
            for b in m.get("content") or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    text_parts.append(b.get("text", ""))
                elif b.get("type") == "tool-call":
                    args = b.get("arguments")
                    try:
                        args = json.loads(args) if isinstance(args, str) else args
                    except Exception:
                        args = {"arguments": args}
                    calls.append({"name": str(b.get("name", "tool")), "arguments": args if isinstance(args, dict) else {"input": args}})
            c.assistant("\n".join(text_parts), calls, c.model)
        elif t == "tool/result":
            m = d.get("message") or {}
            c.tool(content_text(m.get("content")))
    d = c.finish()
    return [d] if d else []


# ------------------------------------------------------------------------------------------------ bonifica + statistiche
def scrub_conv(conv: dict, sc: Scrubber) -> dict:
    for m in conv["messages"]:
        m["content"] = sc.scrub(m.get("content") or "")
        if m.get("tool_calls"):
            m["tool_calls"] = [{"name": sc.scrub(tc["name"]), "arguments": sc.scrub_obj(tc.get("arguments") or {})}
                               for tc in m["tool_calls"]]
    return conv


def conv_stats(conv: dict) -> dict:
    s = Counter()
    it = en = 0
    for m in conv["messages"]:
        r = m["role"]
        n = len(m.get("content") or "")
        s[f"chars_{r}"] += n
        s[f"msgs_{r}"] += 1
        if r == "assistant":
            s["chars_code"] += code_chars(m.get("content") or "")
            a, b = lang_counts(m.get("content") or "")
            it += a
            en += b
            for tc in m.get("tool_calls") or []:
                j = json.dumps(tc.get("arguments"), ensure_ascii=False)
                s["chars_toolargs"] += len(j)
                s["chars_code"] += len(j)
                s["tool_calls"] += 1
        elif r == "tool":
            s["chars_code"] += n
    s["it_words"] = it
    s["en_words"] = en
    s["chars_total"] = sum(v for k, v in s.items() if k.startswith("chars_") and k not in ("chars_code", "chars_toolargs"))
    s["chars_total"] += s["chars_toolargs"]
    return dict(s)


def work(job) -> tuple[str, list[dict], dict, str | None]:
    source, path = job
    sc = Scrubber()
    try:
        if source == "claude":
            convs = parse_claude(path)
        elif source == "codex":
            convs = parse_codex(path)
        else:
            convs = parse_dsh(path)
    except Exception as e:   # un file rotto non ferma il corpus
        return source, [], {}, f"{type(e).__name__}"
    out = []
    for c in convs:
        scrub_conv(c, sc)
        c["stats"] = conv_stats(c)
        out.append(c)
    return source, out, dict(sc.counts), None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--claude", default=os.path.expanduser(r"~\.claude\projects"))
    ap.add_argument("--codex", default=os.path.expanduser(r"~\.codex\sessions"))
    ap.add_argument("--dsh", default=os.path.join(os.environ.get("APPDATA", ""), "dsh-desktop", "harness", "sessions"))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0, help="prova: solo i primi N file per fonte")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for src, root, pat in (("claude", a.claude, "**/*.jsonl"), ("codex", a.codex, "**/*.jsonl"),
                           ("dsh", a.dsh, "**/session.v4.jsonl.zstd")):
        if not root or not os.path.isdir(root):
            print(f"{src}: cartella assente, saltata")
            continue
        files = sorted(glob.glob(os.path.join(root, pat), recursive=True))
        if a.limit:
            files = files[: a.limit]
        jobs += [(src, f) for f in files]
        print(f"{src}: {len(files)} file, {sum(os.path.getsize(f) for f in files) / 1e9:.2f} GB")
    t0 = time.time()
    stats = Counter()
    redact = Counter()
    per_source = {s: Counter() for s in ("claude", "codex", "dsh")}
    errors = Counter()
    seen_hashes: set[str] = set()
    shard_i, shard_bytes, shard = 0, 0, None

    def open_shard():
        nonlocal shard, shard_i, shard_bytes
        if shard:
            shard.close()
        shard = open(out / f"conv_{shard_i:04d}.jsonl", "w", encoding="utf-8")
        shard_i += 1
        shard_bytes = 0

    open_shard()
    with Pool(max(1, a.workers)) as pool:
        for k, (source, convs, counts, err) in enumerate(pool.imap_unordered(work, jobs, chunksize=1)):
            redact.update(counts)
            if err:
                errors[f"{source}:{err}"] += 1
            for c in convs:
                # dedup: le stesse risposte dell'assistente (sessione ripresa / copia) contano una volta
                h = hashlib.sha1("\n".join(m["content"] for m in c["messages"] if m["role"] == "assistant").encode("utf-8", "replace")).hexdigest()
                if h in seen_hashes:
                    stats["dup_convs"] += 1
                    continue
                seen_hashes.add(h)
                line = json.dumps(c, ensure_ascii=False) + "\n"
                shard.write(line)
                shard_bytes += len(line)
                if shard_bytes > SHARD_BYTES:
                    open_shard()
                stats["convs"] += 1
                if c["on_policy"]:
                    stats["convs_on_policy"] += 1
                    per_source[source]["on_policy"] += 1
                per_source[source]["convs"] += 1
                for key, v in c["stats"].items():
                    stats[key] += v
                    per_source[source][key] += v
            if (k + 1) % 50 == 0:
                print(f"  {k + 1}/{len(jobs)} file, {stats['convs']} conversazioni, {time.time() - t0:.0f} s", flush=True)
    shard.close()
    total = stats["chars_total"] or 1
    report = {
        "files": len(jobs), "seconds": round(time.time() - t0, 1), "errors": dict(errors),
        "conversations": stats["convs"], "duplicates_skipped": stats["dup_convs"], "on_policy_conversations": stats["convs_on_policy"],
        "messages": {r: stats[f"msgs_{r}"] for r in ("system", "user", "assistant", "tool")},
        "tool_calls": stats["tool_calls"],
        "chars": {r: stats[f"chars_{r}"] for r in ("system", "user", "assistant", "tool")},
        "chars_total": total,
        "code_share": round(stats["chars_code"] / total, 3),
        "italian_share_assistant_text": round(stats["it_words"] / max(1, stats["it_words"] + stats["en_words"]), 3),
        "tokens_estimated_total": int(total / 3.6),
        "tokens_estimated_assistant": int((stats["chars_assistant"] + stats["chars_toolargs"]) / 3.6),
        "redactions_by_type": dict(redact),
        "redactions_total": sum(redact.values()),
        "per_source": {s: dict(v) for s, v in per_source.items()},
        "shards": shard_i,
    }
    (out / "corpus_stats.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
