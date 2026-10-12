"""selftest.py - prova in piccolo di tutta la catena SENZA GPU ne' motore: cattura finta -> train_mtp.py (pochi passi,
CPU) -> export_mtp.py -> controllo del pacco.

    python selftest.py --seqs D:\\ds4_work\\mtp_distill\\seqs_smoke --work D:\\ds4_work\\mtp_distill\\work\\selftest \\
        --bf16 D:\\ds4_work\\strata\\Strata-data\\mtp --rt D:\\ds4_work\\strata\\Strata-data\\mtp\\rt_it48k --gguf <shard 1> --strata <worktree>

La cattura finta ha lo stesso formato di STRATA_MTP_CAPTURE (seq_<k>.tok.i32 / .r.bf16 / .top.bin / .nll.f32 / .json e
capture_map.json del driver): R casuale (normale, scala 1), top-20 con il token vero del render in testa (p = 0,6) e 19 id
casuali.  Serve a esercitare lettura, catena srotolata, perdita, metriche, salvataggio ed export: NON dice nulla sulla
qualita' del drafter (per quella servono le catture vere del target sul pod).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def fake_capture(seqs: Path, out: Path, n_seqs: int, topk: int = 20, hcn: int = 10240, max_len: int = 160, seed: int = 7):
    rnd = np.random.default_rng(seed)
    index = json.loads((seqs / "seqs_index.json").read_text())
    ids_all = np.fromfile(seqs / "seqs_ids.i32", dtype=np.int32)
    run = out / "run_fake"
    run.mkdir(parents=True, exist_ok=True)
    cmap = {}
    picked = [e for e in index if e["split"] == "train"][: n_seqs - 1] + [e for e in index if e["split"] == "heldout"][:1]
    # per la prova le sequenze sono accorciate: il render finto deve combaciare -> si riscrive un piccolo seqs accorciato
    new_ids, new_gen, new_index = [], [], []
    gen_all = np.fromfile(seqs / "seqs_gen.u8", dtype=np.uint8)
    off = 0
    for k, e in enumerate(picked):
        n = min(e["n"], max_len)
        ids = ids_all[e["off"]: e["off"] + n]
        gen = gen_all[e["off"]: e["off"] + n]
        m = n - 1
        base = run / f"seq_{k}"
        ids[:m].astype("<i4").tofile(str(base) + ".tok.i32")
        R = (rnd.standard_normal((m, hcn)).astype(np.float32) * 1.0)
        ((R.view(np.uint32) + 0x7FFF + ((R.view(np.uint32) >> 16) & 1)) >> 16).astype(np.uint16).tofile(str(base) + ".r.bf16")
        top = np.empty((m, topk * 8), dtype=np.uint8)
        tid = rnd.integers(0, 248320, size=(m, topk)).astype(np.int32)
        tid[:, 0] = ids[1: m + 1]                      # il top-1 del "target" e' il token vero successivo
        lp = np.full((m, topk), np.log(0.4 / (topk - 1)), dtype=np.float32)
        lp[:, 0] = np.log(0.6)
        top[:, : topk * 4] = tid.view(np.uint8)
        top[:, topk * 4:] = lp.view(np.uint8)
        top.tofile(str(base) + ".top.bin")
        np.full(m, np.log(0.6), dtype=np.float32).tofile(str(base) + ".nll.f32")
        (base.with_suffix(".json")).write_text(json.dumps({"n": m, "hcn": hcn, "topk": topk, "n_vocab": 248320, "first_pos": 0}))
        cmap[str(k)] = {"run": "run_fake", "k": k, "n": n, "ok": True}
        new_index.append({"i": k, "off": off, "n": n, "conv": e["conv"], "source": e["source"], "on_policy": e["on_policy"],
                          "split": e["split"]})
        new_ids.append(ids)
        new_gen.append(gen)
        off += n
    (out / "capture_map.json").write_text(json.dumps(cmap))
    sq = out / "seqs"
    sq.mkdir(exist_ok=True)
    np.concatenate(new_ids).astype("<i4").tofile(sq / "seqs_ids.i32")
    np.concatenate(new_gen).tofile(sq / "seqs_gen.u8")
    (sq / "seqs_index.json").write_text(json.dumps(new_index))
    return sq


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seqs", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--bf16", required=True)
    ap.add_argument("--rt", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--strata", required=True)
    ap.add_argument("--n-seqs", type=int, default=4)
    ap.add_argument("--max-len", type=int, default=160)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--threads", type=int, default=2, help="thread CPU di torch")
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    sq = fake_capture(Path(a.seqs), work / "capture", a.n_seqs, max_len=a.max_len)
    print(f"[1/3] cattura finta: {a.n_seqs} sequenze di <= {a.max_len} token in {work / 'capture'} ({time.time() - t0:.1f} s)")
    run = work / "run"
    cmd = [sys.executable, str(HERE / "train_mtp.py"), "--bf16", a.bf16, "--rt", a.rt, "--gguf", a.gguf, "--strata", a.strata,
           "--seqs", str(sq), "--capture", str(work / "capture"), "--out", str(run), "--cache", str(Path(a.work).parent / "cache"),
           "--steps", "3", "--max-steps", "2", "--accum", "1", "--eval-items", "1", "--eval-every", "1000", "--lr", "1e-4",
           "--device", a.device, "--warmup", "1", "--threads", str(a.threads)]
    print("[2/3] train_mtp.py (CPU, 2 passi, catena di 3)...", flush=True)
    r = subprocess.run(cmd, text=True, capture_output=True)
    sys.stdout.write(r.stdout[-4000:])
    if r.returncode != 0:
        sys.stdout.write(r.stderr[-4000:])
        print("train_mtp.py FALLITO")
        return 1
    cmd = [sys.executable, str(HERE / "export_mtp.py"), "--bf16", a.bf16, "--rt", a.rt, "--weights", str(run / "trainable.safetensors"),
           "--out", str(work / "rt_selftest")]
    print("[3/3] export_mtp.py...", flush=True)
    r = subprocess.run(cmd, text=True, capture_output=True)
    sys.stdout.write(r.stdout[-3000:])
    if r.returncode != 0:
        sys.stdout.write(r.stderr[-3000:])
        print("export_mtp.py FALLITO")
        return 1
    rep = json.loads((work / "rt_selftest" / "export_report.json").read_text())
    moved = [t for t in rep["tensors"] if t["moved_rel_rms"] > 0]
    ref = json.loads((Path(a.rt).parent / "mtp-inventory.json").read_text()) if (Path(a.rt).parent / "mtp-inventory.json").exists() else None
    ok_layout = (work / "rt_selftest" / "dense.txt").read_text().split() and (work / "rt_selftest" / "experts.bin").stat().st_size == (Path(a.rt) / "experts.bin").stat().st_size
    print(f"pacco esportato: {len(rep['tensors'])} tensori, {len(moved)} toccati dal training, experts.bin copiato: {bool(ok_layout)}")
    print(f"selftest OK in {(time.time() - t0) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
