"""capture_driver.py - fa leggere al motore Strata (branch lab/mtp-capture) le sequenze del corpus e raccoglie i residui
finali e i top-20 del target (STRATA_MTP_CAPTURE).

    python capture_driver.py --exe <strata.exe> --config <strata-iq3_xxs.json> \\
        --seqs D:\\ds4_work\\mtp_distill\\seqs --out D:\\ds4_work\\mtp_distill\\capture [--first 0 --count N] [--extra "..."]

Avvia `strata --serve` con gli argomenti della config di setup.py meno il drafter e le cache, piu' quelli della cattura:
  --prompt-cache 0          nessun riuso: le posizioni partono sempre da 0
  --spec 8                  finestre di 8 righe (kVerifyMaxT) per la coda del prompt (--short-read, 64 di default)
  (default) il grosso del prompt passa dal prefill batched (`--prefill` della config): l'hook cattura dai chunk
            (Prefill::on_chunk -> MtpCapture::chunk, testa e top-k su GPU) alla velocita' del prefill
  --windows                 come prima: --short-read 1000000000, tutto il prompt dalle finestre teacher-forced (lento)
e con STRATA_MTP_CAPTURE=<out>/run_<ts>.  Per ogni sequenza manda `GEN <max-new> ckpt=0 <id,id,...>`, aspetta DONE/ERR e
verifica le dimensioni dei file (n-1 posizioni: il motore cattura [0, n-1), l'ultimo token e' il riempitivo del render).
Scrive <out>/capture_map.json: per sequenza {run, k, n, ok}; una ripresa salta le sequenze gia' buone e apre un nuovo run
(il contatore k del motore riparte da 0 a ogni avvio).  Stampa il ritmo (token/s) ogni 20 sequenze.

Parita' (parity.py): --keep-mtp tiene `--mtp` e `--spec-min-p` della config (il drafter gira), --max-new 8 fa produrre
qualche finestra, --dump <file> accende STRATA_MTP_DUMP (i logit di ogni passo di bozza); --trunc N accorcia i prompt a N
token; --split heldout prende solo quello split.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import zlib

CAPTURE_ARGS = ["--prompt-cache", "0", "--spec", "8"]
WINDOWS_ARGS = ["--short-read", "1000000000"]
DROP_ARGS = {"--mtp": 1, "--mtp-window": 1, "--mtp-max-t": 1, "--mtp-q4": 1, "--mtp-draft-vocab": 1, "--mtp-hnorm": 1,
             "--prompt-cache": 1, "--prompt-cache-tail": 0, "--prompt-cache-every": 1, "--prompt-cache-file": 1,
             "--prompt-cache-root": 1, "--conversation-cache-mib": 1, "--conversation-cache-slots": 1, "--spec": 1,
             "--spec-min-p": 1, "--short-read": 1, "--pipeline-windows": 1, "--vision": 0, "--batch": 1}
KEEP_MTP = {"--mtp", "--mtp-window", "--mtp-max-t", "--mtp-q4", "--mtp-draft-vocab", "--mtp-hnorm", "--spec-min-p"}


def engine_args(cfg: dict, extra: list[str], windows: bool = False, keep_mtp: bool = False, mtp_dir: str = "") -> list[str]:
    args = list(cfg["args"])
    out = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in DROP_ARGS and not (keep_mtp and a in KEEP_MTP):
            i += 1 + DROP_ARGS[a]
            continue
        if a == "--mtp" and keep_mtp and mtp_dir:   # il pacco della parita' (rt_it48k), non quello della config
            out += [a, mtp_dir]
            i += 2
            continue
        out.append(a)
        i += 1
    cap = list(CAPTURE_ARGS)
    if keep_mtp:   # il Daily: --spec 4 (la config); la cattura a finestre di 8 non serve con il drafter acceso
        cap = ["--prompt-cache", "0", "--spec", "4"]
    return out + cap + (WINDOWS_ARGS if windows else []) + extra


class Engine:
    def __init__(self, exe: str, args: list[str], env: dict, cwd: str | None, log_path: Path):
        self.log = open(log_path, "a", encoding="utf-8")
        self.p = subprocess.Popen([exe, "--serve", *args], cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self.log, text=True, bufsize=1, env=env)
        for line in self.p.stdout:
            if line.startswith("READY"):
                return
            if line.startswith("ERR"):
                raise SystemExit("il motore ha risposto " + line.strip())
        raise SystemExit(f"il motore si e' fermato prima di READY: vedi {log_path}")

    def send(self, line: str):
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()

    def wait_done(self) -> str:
        for line in self.p.stdout:
            if line.startswith("DONE") or line.startswith("ERR"):
                return line.strip()
        return "ERR engine exited"

    def close(self):
        try:
            self.send("QUIT")
        except Exception:
            pass
        try:
            self.p.wait(timeout=60)
        except Exception:
            self.p.kill()
        self.log.close()


def check_files(run_dir: Path, k: int, n: int, hcn: int, topk: int) -> bool:
    base = run_dir / f"seq_{k}"
    want = n - 1
    try:
        meta = json.loads((base.with_suffix(".json")).read_text())
    except Exception:
        return False
    if meta.get("n") != want or meta.get("first_pos") != 0:
        return False
    sizes = {".tok.i32": want * 4, ".r.bf16": want * hcn * 2, ".top.bin": want * topk * 8, ".nll.f32": want * 4}
    return all((run_dir / f"seq_{k}{ext}").stat().st_size == size for ext, size in sizes.items())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", required=True)
    ap.add_argument("--config", required=True, help="la strata-<model>.json scritta da setup.py (args, cwd, lib_dirs, env)")
    ap.add_argument("--seqs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--count", type=int, default=0, help="0 = tutte")
    ap.add_argument("--split", default="", help="solo le sequenze di questo split (train / heldout)")
    ap.add_argument("--by-conv", type=int, default=0, help="con --split: heldout = conversazioni con crc32 %% N == 0 (train_mtp --split-by-conv)")
    ap.add_argument("--topk", type=int, default=20)
    ap.add_argument("--hcn", type=int, default=10240)
    ap.add_argument("--extra", default="", help="altri argomenti del motore")
    ap.add_argument("--max-seq", type=int, default=0, help="prova: ferma dopo N sequenze buone in questo run")
    ap.add_argument("--windows", action="store_true", help="tutto il prompt dalle finestre teacher-forced (lento)")
    ap.add_argument("--keep-mtp", action="store_true", help="tiene il drafter della config (parita')")
    ap.add_argument("--mtp-dir", default="", help="con --keep-mtp: il pacco MTP da usare al posto di quello della config")
    ap.add_argument("--max-new", type=int, default=1, help="token generati per richiesta (GEN N)")
    ap.add_argument("--dump", default="", help="STRATA_MTP_DUMP=<file>: i logit del drafter per passo (parita')")
    ap.add_argument("--trunc", type=int, default=0, help="accorcia ogni prompt a N token (parita')")
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    seqs = Path(a.seqs)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    index = json.loads((seqs / "seqs_index.json").read_text())
    ids_all = np.fromfile(seqs / "seqs_ids.i32", dtype=np.int32)
    map_path = out / "capture_map.json"
    cmap = json.loads(map_path.read_text()) if map_path.exists() else {}
    def split_of(e):
        if a.by_conv <= 0:
            return e["split"]
        return "heldout" if zlib.crc32(e["conv"].encode()) % a.by_conv == 0 else "train"
    pool = [e for e in index if not a.split or split_of(e) == a.split]
    todo = [e for e in pool[a.first: a.first + a.count if a.count else None] if not cmap.get(str(e["i"]), {}).get("ok")]
    print(f"{len(index)} sequenze, {len(todo)} da catturare")
    if not todo:
        return 0
    run = f"run_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir = out / run
    run_dir.mkdir()
    env = dict(os.environ)
    env.update(cfg.get("env") or {})
    env["STRATA_MTP_CAPTURE"] = str(run_dir)
    env["STRATA_MTP_CAPTURE_TOPK"] = str(a.topk)
    if a.dump:
        env["STRATA_MTP_DUMP"] = a.dump
    libs = cfg.get("lib_dirs") or []
    if libs:
        key = "PATH" if os.name == "nt" else "LD_LIBRARY_PATH"
        env[key] = os.pathsep.join(libs + [env.get(key, "")])
    args = engine_args(cfg, a.extra.split(), windows=a.windows, keep_mtp=a.keep_mtp, mtp_dir=a.mtp_dir)
    print("motore:", a.exe, " ".join(args))
    eng = Engine(a.exe, args, env, cfg.get("cwd"), out / f"{run}.engine.log")
    t0 = time.time()
    tokens = 0
    good = 0
    try:
        for j, e in enumerate(todo):
            ids = ids_all[e["off"]: e["off"] + e["n"]]
            n = e["n"]
            if a.trunc and n > a.trunc:
                ids = ids[: a.trunc]
                n = a.trunc
            k = j   # il contatore del motore in questo run
            eng.send(f"GEN {a.max_new} ckpt=0 " + ",".join(map(str, ids.tolist())))
            done = eng.wait_done()
            ok = done.startswith("DONE") and check_files(run_dir, k, n, a.hcn, a.topk)
            cmap[str(e["i"])] = {"run": run, "k": k, "n": n, "ok": ok}
            if not ok:
                print(f"  seq {e['i']}: NON catturata ({done[:80]})", flush=True)
            else:
                good += 1
                tokens += n
            if (j + 1) % 20 == 0 or j + 1 == len(todo):
                dt = time.time() - t0
                print(f"  {j + 1}/{len(todo)} sequenze, {tokens} token, {tokens / max(dt, 1e-9):.0f} tok/s, {dt / 60:.1f} min", flush=True)
                map_path.write_text(json.dumps(cmap))
            if a.max_seq and good >= a.max_seq:
                break
    finally:
        map_path.write_text(json.dumps(cmap))
        eng.close()
    print(f"catturate {good} sequenze, {tokens} token, in {(time.time() - t0) / 60:.1f} min -> {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
