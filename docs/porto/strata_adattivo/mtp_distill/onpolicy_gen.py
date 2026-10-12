"""onpolicy_gen.py - risposte on-policy del target (Qwen3.8 nel motore Strata) per affinare la testa MTP.

    # 1. i prompt: i punti dove l'assistente inizia (gen 0 -> 1) nei pezzi del corpus, troncati a sinistra a un confine
    #    <|im_start|> entro --ctx token
    python3 onpolicy_gen.py prompts --seqs $D/seqs --out $D/onpolicy --ctx 2000 --per-chunk 2 --heldout-n 48
    # 2. la generazione: `strata --serve --batch N`, N richieste insieme (BGEN nelle slot), campionamento dell'uso reale
    python3 onpolicy_gen.py gen --exe $EXE --config $CFG --out $D/onpolicy --par 8 --max-new 512 --minutes 50
    # 3. le sequenze prompt + risposta nel formato di render_sequences (gen = 1 sui token di Qwen), per capture_driver
    python3 onpolicy_gen.py seqs --out $D/onpolicy

Protocollo del motore (serve/server.py): `GEN <max_new> keys ids` -> `T <id>`... `DONE`; con --batch:
`BGEN <slot> <max_new> keys ids` legge il prompt (righe di controllo, un'ammissione per volta, il primo token arriva come
`T <id>`), poi `BADM <slot> 1`; la slot decodifica con `BT <slot> <id>` fino a `BDONE <slot> <prodotti> <fine> <ms>`.
Con --par 1 si usa GEN (percorso solo, con le bozze MTP).  Ogni richiesta ha seed = il suo numero (riproducibile).
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import random
import subprocess
import sys
import threading
import time
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from capture_driver import DROP_ARGS  # noqa: E402

EOS = {248044, 248046}


def cmd_prompts(a) -> int:
    seqs = Path(a.seqs)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    index = json.loads((seqs / "seqs_index.json").read_text())
    ids_all = np.fromfile(seqs / "seqs_ids.i32", dtype=np.int32)
    gen_all = np.fromfile(seqs / "seqs_gen.u8", dtype=np.uint8)
    rng = random.Random(a.seed)
    im_start = None
    train, held = [], []
    for e in index:
        ids = ids_all[e["off"]: e["off"] + e["n"]]
        g = gen_all[e["off"]: e["off"] + e["n"]]
        starts = [p for p in range(1, len(g)) if g[p] == 1 and g[p - 1] == 0 and p >= a.min_ctx]
        if not starts:
            continue
        if im_start is None:
            im_start = int(ids[starts[0] - 3])
        heldout = zlib.crc32(e["conv"].encode()) % a.by_conv == 0
        pick = rng.sample(starts, min(len(starts), a.per_chunk))
        for p in pick:
            lo = max(0, p - a.ctx)
            if lo > 0:   # a sinistra: il primo <|im_start|> dopo il taglio
                cut = np.nonzero(ids[lo:p] == im_start)[0]
                if len(cut) == 0:
                    continue
                lo += int(cut[0])
            if p - lo < a.min_ctx:
                continue
            item = {"src": e["i"], "conv": e["conv"], "p": p, "lo": lo, "ids": ids[lo:p].tolist()}
            (held if heldout else train).append(item)
    rng.shuffle(train)
    rng.shuffle(held)
    items = held[: a.heldout_n] + train   # prima le heldout: l'eval on-policy c'e' anche se si ferma presto
    with open(out / "prompts.jsonl", "w") as fh:
        for r, it in enumerate(items):
            it["req"] = r
            it["split"] = "heldout" if r < min(len(held), a.heldout_n) else "train"
            fh.write(json.dumps(it) + "\n")
    lens = [len(it["ids"]) for it in items]
    print(f"im_start={im_start} prompt: {len(items)} ({min(len(held), a.heldout_n)} heldout, {len(train)} train), "
          f"lunghezza media {np.mean(lens):.0f}, token {sum(lens)}")
    return 0


class Engine:
    def __init__(self, exe, args, env, cwd, log_path):
        self.log = open(log_path, "a", encoding="utf-8")
        self.p = subprocess.Popen([exe, "--serve", *args], cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self.log, text=True, bufsize=1, env=env)
        self.q: queue.Queue = queue.Queue()
        for line in self.p.stdout:
            if line.startswith("READY"):
                break
            if line.startswith("ERR"):
                raise SystemExit("il motore ha risposto " + line.strip())
        else:
            raise SystemExit(f"il motore si e' fermato prima di READY: vedi {log_path}")
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.p.stdout:
            self.q.put(line.rstrip("\n"))
        self.q.put(None)

    def send(self, line):
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()

    def close(self):
        try:
            self.send("QUIT")
            self.p.wait(timeout=60)
        except Exception:
            self.p.kill()
        self.log.close()


def cmd_gen(a) -> int:
    out = Path(a.out)
    cfg = json.loads(Path(a.config).read_text())
    items = [json.loads(l) for l in open(out / "prompts.jsonl")]
    res_path = out / "gen.jsonl"
    done_reqs = set()
    if res_path.exists():
        done_reqs = {json.loads(l)["req"] for l in open(res_path)}
    todo = [it for it in items if it["req"] not in done_reqs][a.first:]
    if a.count:
        todo = todo[: a.count]
    args, i = [], 0
    raw = list(cfg["args"])
    while i < len(raw):
        if raw[i] in ("--prompt-cache", "--batch"):
            i += 1 + DROP_ARGS[raw[i]]
            continue
        args.append(raw[i])
        i += 1
    args += ["--prompt-cache", "0"]
    if a.par > 1:
        args += ["--batch", str(a.par)]
    args += a.extra.split()
    env = dict(os.environ)
    env.update(cfg.get("env") or {})
    if cfg.get("lib_dirs"):
        env["LD_LIBRARY_PATH"] = os.pathsep.join(cfg["lib_dirs"] + [env.get("LD_LIBRARY_PATH", "")])
    tag = time.strftime("%Y%m%d_%H%M%S")
    print("motore:", a.exe, " ".join(args), flush=True)
    eng = Engine(a.exe, args, env, cfg.get("cwd"), out / f"gen_{tag}.engine.log")
    keys = f" temperature={a.temperature} top_p={a.top_p} top_k={a.top_k}"
    fh = open(res_path, "a")
    t0 = time.time()
    deadline = t0 + a.minutes * 60 if a.minutes else None
    ntok = nreq = 0
    last_print = t0

    def report(force=False):
        nonlocal last_print
        now = time.time()
        if force or now - last_print >= 30:
            dt = now - t0
            print(f"  {nreq} risposte, {ntok} token generati, {ntok / max(dt, 1e-9):.1f} tok/s aggregati, "
                  f"{dt / 60:.1f} min", flush=True)
            last_print = now

    def write(it, toks, finish, ms):
        nonlocal ntok, nreq
        rec = {"req": it["req"], "split": it["split"], "src": it["src"], "conv": it["conv"], "p": it["p"],
               "lo": it["lo"], "n_prompt": len(it["ids"]), "gen": toks, "finish": finish, "ms": ms}
        fh.write(json.dumps(rec) + "\n")
        fh.flush()
        ntok += len(toks)
        nreq += 1

    try:
        if a.par <= 1:
            for it in todo:
                if deadline and time.time() > deadline:
                    break
                ts = time.time()
                eng.send(f"GEN {a.max_new}{keys} seed={it['req']} ckpt=0 " + ",".join(map(str, it["ids"])))
                toks, fin = [], "?"
                while True:
                    line = eng.q.get()
                    if line is None:
                        raise SystemExit("motore uscito")
                    if line.startswith("T "):
                        toks.append(int(line.split()[1]))
                    elif line.startswith("DONE") or line.startswith("ERR"):
                        fin = line[:120]
                        break
                write(it, toks, fin, int((time.time() - ts) * 1000))
                report()
        else:
            slots = {s: None for s in range(a.par)}   # slot -> (item, tokens, t_start)
            pending = list(todo)
            admitting = None
            stop_admit = False
            while True:
                if deadline and time.time() > deadline:
                    stop_admit = True
                if admitting is None and pending and not stop_admit:
                    free = [s for s, v in slots.items() if v is None]
                    if free:
                        s = free[0]
                        it = pending.pop(0)
                        slots[s] = (it, [], time.time())
                        admitting = s
                        eng.send(f"BGEN {s} {a.max_new}{keys} seed={it['req']} ckpt=0 " + ",".join(map(str, it["ids"])))
                if admitting is None and all(v is None for v in slots.values()) and (not pending or stop_admit):
                    break
                try:
                    line = eng.q.get(timeout=5)
                except queue.Empty:
                    report()
                    continue
                if line is None:
                    raise SystemExit("motore uscito")
                f = line.split()
                if not f:
                    continue
                if f[0] == "T" and admitting is not None:
                    slots[admitting][1].append(int(f[1]))
                elif f[0] == "BADM":
                    s = int(f[1])
                    if f[2:3] != ["1"]:   # non ammessa: la richiesta e' finita durante la lettura (o errore)
                        it, toks, ts = slots[s]
                        if toks:
                            write(it, toks, "badm0 " + line[:80], int((time.time() - ts) * 1000))
                        slots[s] = None
                    admitting = None
                elif f[0] == "BT":
                    s = int(f[1])
                    if slots.get(s) is not None:
                        slots[s][1].append(int(f[2]))
                elif f[0] == "BDONE":
                    s = int(f[1])
                    if slots.get(s) is not None:
                        it, toks, ts = slots[s]
                        write(it, toks, line[:120], int((time.time() - ts) * 1000))
                        slots[s] = None
                elif f[0] == "DONE" and admitting is not None:
                    # la richiesta e' finita gia' nella lettura (EOS al primo token, max_new 1): niente slot
                    pass
                elif f[0] == "ERR":
                    print("  motore:", line[:200], flush=True)
                    if admitting is not None:
                        slots[admitting] = None
                        admitting = None
                report()
    finally:
        report(force=True)
        fh.close()
        eng.close()
    return 0


def cmd_seqs(a) -> int:
    out = Path(a.out)
    items = {json.loads(l)["req"]: json.loads(l) for l in open(out / "prompts.jsonl")}
    recs = [json.loads(l) for l in open(out / "gen.jsonl")]
    sd = out / "seqs"
    sd.mkdir(exist_ok=True)
    ids_out, gen_out, index = [], [], []
    off = ntok = ngen = 0
    nl = a.nl
    for r in recs:
        g = r["gen"]
        if len(g) < a.min_gen:
            continue
        p = items[r["req"]]["ids"]
        ids = p + g + [nl]
        gm = [0] * len(p) + [1] * len(g) + [0]
        index.append({"i": len(index), "off": off, "n": len(ids), "conv": r["conv"], "source": "qwen-onpolicy",
                      "on_policy": True, "split": r["split"], "req": r["req"], "src": r["src"]})
        ids_out += ids
        gen_out += gm
        off += len(ids)
        ntok += len(ids)
        ngen += len(g)
    np.asarray(ids_out, dtype=np.int32).tofile(sd / "seqs_ids.i32")
    np.asarray(gen_out, dtype=np.uint8).tofile(sd / "seqs_gen.u8")
    (sd / "seqs_index.json").write_text(json.dumps(index))
    stats = {"seqs": len(index), "tokens": ntok, "generated": ngen,
             "heldout_seqs": sum(e["split"] == "heldout" for e in index)}
    (sd / "render_stats.json").write_text(json.dumps(stats, indent=1))
    print(stats)
    return 0


def cmd_mix(a) -> int:
    """Un corpus misto per train_mtp: sequenze e catture di piu' sorgenti (seqs:capture[:quota]) in una cartella sola,
    con i run delle catture collegati (symlink) e la capture_map rinumerata.  quota = frazione delle sequenze train
    da tenere (le heldout restano tutte)."""
    out = Path(a.out)
    (out / "seqs").mkdir(parents=True, exist_ok=True)
    cap = out / "capture"
    cap.mkdir(exist_ok=True)
    rng = random.Random(a.seed)
    ids_out, gen_out, index, cmap = [], [], [], {}
    off = 0
    for spec in a.src:
        parts = spec.split(":")
        sd, cd = Path(parts[0]), Path(parts[1])
        quota = float(parts[2]) if len(parts) > 2 else 1.0
        idx = json.loads((sd / "seqs_index.json").read_text())
        ids_all = np.fromfile(sd / "seqs_ids.i32", dtype=np.int32)
        gen_all = np.fromfile(sd / "seqs_gen.u8", dtype=np.uint8)
        m = json.loads((cd / "capture_map.json").read_text())
        kept = 0
        for e in idx:
            mm = m.get(str(e["i"]))
            if not mm or not mm.get("ok"):
                continue
            held = zlib.crc32(e["conv"].encode()) % a.by_conv == 0
            if not held and rng.random() >= quota:
                continue
            link = cap / mm["run"]
            if not link.exists():
                link.symlink_to((cd / mm["run"]).resolve())
            n = e["n"]
            ne = dict(e, i=len(index), off=off, src_dir=str(sd))
            cmap[str(ne["i"])] = dict(mm)
            index.append(ne)
            ids_out.append(ids_all[e["off"]: e["off"] + n])
            gen_out.append(gen_all[e["off"]: e["off"] + n])
            off += n
            kept += 1
        print(f"{spec}: {kept} sequenze")
    np.concatenate(ids_out).astype(np.int32).tofile(out / "seqs" / "seqs_ids.i32")
    np.concatenate(gen_out).astype(np.uint8).tofile(out / "seqs" / "seqs_gen.u8")
    (out / "seqs" / "seqs_index.json").write_text(json.dumps(index))
    (cap / "capture_map.json").write_text(json.dumps(cmap))
    print(f"misto: {len(index)} sequenze, {off} token, {int(sum(g.sum() for g in gen_out))} generati")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prompts")
    p.add_argument("--seqs", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--ctx", type=int, default=2000)
    p.add_argument("--min-ctx", type=int, default=64)
    p.add_argument("--per-chunk", type=int, default=2)
    p.add_argument("--heldout-n", type=int, default=48)
    p.add_argument("--by-conv", type=int, default=10)
    p.add_argument("--seed", type=int, default=20261012)
    g = sub.add_parser("gen")
    g.add_argument("--exe", required=True)
    g.add_argument("--config", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--par", type=int, default=8)
    g.add_argument("--max-new", type=int, default=512)
    g.add_argument("--temperature", type=float, default=1.0)
    g.add_argument("--top-p", type=float, default=0.95)
    g.add_argument("--top-k", type=int, default=20)
    g.add_argument("--minutes", type=float, default=0)
    g.add_argument("--first", type=int, default=0)
    g.add_argument("--count", type=int, default=0)
    g.add_argument("--extra", default="")
    s = sub.add_parser("seqs")
    s.add_argument("--out", required=True)
    s.add_argument("--min-gen", type=int, default=16)
    s.add_argument("--nl", type=int, default=198, help="il token '\\n' di coda (riempitivo della cattura)")
    x = sub.add_parser("mix")
    x.add_argument("--out", required=True)
    x.add_argument("--src", action="append", required=True, help="seqs_dir:capture_dir[:quota train]")
    x.add_argument("--by-conv", type=int, default=10)
    x.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    return {"prompts": cmd_prompts, "gen": cmd_gen, "seqs": cmd_seqs, "mix": cmd_mix}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
