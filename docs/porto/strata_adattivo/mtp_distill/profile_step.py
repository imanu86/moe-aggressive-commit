"""profile_step.py - un passo della catena con un timer per fase (dove va il tempo su CPU o su GPU).

    python profile_step.py --bf16 ... --rt ... --gguf ... --strata ... --seqs <seqs> --capture <capture> --tokens 16 --steps 3 --threads 2

Misura: costruzione del modello (blocco BF16, embedding/testa dalla cache, sottoinsieme della testa), lettura di una
sequenza, poi dentro step_losses: front (embedding, fc, HC, K/V), attend, rest (HC, router, esperti, condiviso, mixer),
caricamento degli esperti (ExpertBank.get: quante chiamate, quanti distinti), head, backward.
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mtp_model as M  # noqa: E402
import train_mtp as T  # noqa: E402

TIMES: Counter = Counter()
CALLS: Counter = Counter()


def timed(obj, name: str):
    f = getattr(obj, name)

    def g(*a, **k):
        t = time.perf_counter()
        r = f(*a, **k)
        TIMES[name] += time.perf_counter() - t
        CALLS[name] += 1
        return r
    setattr(obj, name, g)


def main() -> int:
    ap = argparse.ArgumentParser()
    for k in ("bf16", "rt", "gguf", "strata", "seqs", "capture"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--tokens", type=int, default=16)
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--cache", default=None, help="cache embedding/testa (default <capture>/../cache)")
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    device = torch.device(a.device)
    t0 = time.perf_counter()
    dense = M.load_bf16_block(Path(a.bf16))
    print(f"blocco BF16 letto: {time.perf_counter() - t0:.1f} s", flush=True)
    t = time.perf_counter()
    model, dvocab = M.build_model(Path(a.bf16), Path(a.rt), Path(a.gguf), Path(a.strata) / "tools",
                                  Path(a.cache) if a.cache else Path(a.capture).parent / "cache", device)
    print(f"build_model: {time.perf_counter() - t:.1f} s", flush=True)
    n_vocab = model.embed.shape[0]
    inv_map = torch.full((n_vocab,), -1, dtype=torch.long, device=device)
    inv_map[dvocab] = torch.arange(dvocab.numel(), device=device)
    data = T.CaptureData(Path(a.seqs), Path(a.capture), "train", max_len=a.tokens)
    t = time.perf_counter()
    b = data.get(0)
    print(f"lettura sequenza ({b['m']} posizioni): {time.perf_counter() - t:.2f} s", flush=True)
    for name in ("front", "attend", "rest", "head", "gr_read"):
        timed(model, name)
    timed(model.experts, "get")
    timed(model.experts, "_load")
    t = time.perf_counter()
    r = T.step_losses(model, inv_map, b, a.steps, device, 0.5)
    fwd = time.perf_counter() - t
    print(f"forward (step_losses, {a.steps} passi): {fwd:.1f} s", flush=True)
    t = time.perf_counter()
    loss = sum(r["kl_terms"])
    if isinstance(loss, torch.Tensor) and loss.requires_grad:
        loss.backward()
        print(f"backward: {time.perf_counter() - t:.1f} s", flush=True)
    else:
        print("backward saltato: nessuna cella valida (gen = 1 con top-k nel sottoinsieme) in questa finestra", flush=True)
    for k, v in sorted(TIMES.items(), key=lambda kv: -kv[1]):
        print(f"  {k:10s} {v:8.2f} s  ({CALLS[k]} chiamate)")
    print("per passo:", [{kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in s.items()} for s in r["steps"]])
    print(f"totale {time.perf_counter() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
