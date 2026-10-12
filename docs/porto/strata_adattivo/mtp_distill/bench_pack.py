"""bench_pack.py - accettazione delle bozze di un pacco MTP sul motore vero: stessi prompt, greedy, pacco A contro pacco B.

    python bench_pack.py --exe <strata> --config <strata-iq3_xxs.json> --seqs <seqs> --mtp /data/mtp/rt_it48k \\
        --mtp /data/mtp/rt_it48k_ft1 --n 24 --prompt-tokens 1024 --max-new 256

Per ogni --mtp avvia il motore (`--spec 4 --spec-min-p 0.5`, come il Daily; --prompt-cache 0), manda i primi
--prompt-tokens token di --n sequenze dello split heldout e legge dalla riga DONE le bozze accettate e offerte
(`DONE <generated> <prompt> <prompt ms> <decode ms> <finish> <accepted> <offered> ...`).  Stampa per pacco: token
generati, bozze accettate/offerte, token per finestra (1 + accettate/finestre ~ generati/(generati - accettate)) e t/s di
decode.  Greedy: a parita' di pacco i token generati sono gli stessi, cosi' due pacchi si confrontano sullo stesso testo
soltanto se il drafter non cambia l'uscita (non la cambia: la finestra di verifica decide ogni token).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import zlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from capture_driver import Engine, DROP_ARGS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--seqs", required=True)
    ap.add_argument("--mtp", action="append", required=True, help="una cartella pacco per volta (ripetibile)")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--prompt-tokens", type=int, default=1024)
    ap.add_argument("--max-new", type=int, default=256)
    ap.add_argument("--spec", default="4")
    ap.add_argument("--spec-min-p", default="0.5")
    ap.add_argument("--extra", default="")
    ap.add_argument("--by-conv", type=int, default=0, help="heldout = conversazioni con crc32 %% N == 0 (come train_mtp --split-by-conv)")
    ap.add_argument("--env", action="append", default=[], help="KEY=VAL per il motore (ripetibile)")
    ap.add_argument("--out", default="bench_pack.json")
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    seqs = Path(a.seqs)
    index = json.loads((seqs / "seqs_index.json").read_text())
    ids_all = np.fromfile(seqs / "seqs_ids.i32", dtype=np.int32)
    def split_of(e):
        if a.by_conv <= 0:
            return e["split"]
        return "heldout" if zlib.crc32(e["conv"].encode()) % a.by_conv == 0 else "train"
    held = [e for e in index if split_of(e) == "heldout" and e["n"] >= a.prompt_tokens][: a.n]
    prompts = [ids_all[e["off"]: e["off"] + min(e["n"], a.prompt_tokens)].tolist() for e in held]
    base = []
    args = list(cfg["args"])
    i = 0
    while i < len(args):
        if args[i] in DROP_ARGS:
            i += 1 + DROP_ARGS[args[i]]
            continue
        base.append(args[i])
        i += 1
    env = dict(os.environ)
    env.update(cfg.get("env") or {})
    for kv in a.env:
        k, _, v = kv.partition("=")
        env[k] = v
    libs = cfg.get("lib_dirs") or []
    if libs:
        key = "PATH" if os.name == "nt" else "LD_LIBRARY_PATH"
        env[key] = os.pathsep.join(libs + [env.get(key, "")])
    results = {}
    for mtp in a.mtp:
        eargs = base + ["--prompt-cache", "0", "--spec", a.spec, "--spec-min-p", a.spec_min_p, "--mtp", mtp] + a.extra.split()
        print(f"== {mtp}", flush=True)
        eng = Engine(a.exe, eargs, env, cfg.get("cwd"), Path(f"bench_{Path(mtp).name}.engine.log"))
        gen = acc = off = 0
        dec_ms = 0.0
        outs = []
        t0 = time.time()
        try:
            for p in prompts:
                eng.send(f"GEN {a.max_new} ckpt=0 " + ",".join(map(str, p)))
                toks = []
                for line in eng.p.stdout:
                    if line.startswith("T "):
                        toks.append(int(line.split()[1]))
                    elif line.startswith("DONE") or line.startswith("ERR"):
                        break
                f = line.split()
                if f[0] == "DONE" and len(f) >= 8:
                    gen += int(f[1]); dec_ms += float(f[4]); acc += int(f[6]); off += int(f[7])
                outs.append(toks)
        finally:
            eng.close()
        windows = max(1, gen - acc)
        r = {"generated": gen, "accepted": acc, "offered": off, "acceptance": round(acc / max(1, off), 4),
             "tokens_per_window": round(gen / windows, 3), "decode_tps": round(1000.0 * gen / max(1.0, dec_ms), 1),
             "seconds": round(time.time() - t0, 1)}
        results[mtp] = {"stats": r, "outputs": outs}
        print(json.dumps(r), flush=True)
    names = list(results)
    if len(names) == 2:
        same = sum(1 for x, y in zip(results[names[0]]["outputs"], results[names[1]]["outputs"]) if x == y)
        print(f"uscite identiche fra i due pacchi: {same}/{len(prompts)} (greedy: dovrebbero esserlo tutte)")
    Path(a.out).write_text(json.dumps({k: v["stats"] for k, v in results.items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
