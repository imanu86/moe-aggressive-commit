"""train_mtp.py - distillazione del layer MTP sulle catture del target (KL top-20 srotolata, come #97).

    python train_mtp.py --bf16 D:\\ds4_work\\strata\\Strata-data\\mtp --rt D:\\ds4_work\\strata\\Strata-data\\mtp\\rt_it48k \\
        --gguf <shard 1 del target> --strata <worktree Strata> --seqs D:\\...\\seqs --capture D:\\...\\capture \\
        --out D:\\ds4_work\\mtp_distill\\runs\\ft1 --steps 4 --epochs 2 --lr 3e-5 --accum 4

Dati: per ogni sequenza (render_sequences.py) i file di cattura (capture_driver.py + STRATA_MTP_CAPTURE): R_p (residuo finale
del target, bf16) e top-20 (id, log-prob) alle posizioni p = 0..n-2.  Catena del drafter dalla cella c: passo j consuma
(R^(j)_c, token c+j+1) alla posizione rope c+j e predice il token c+j+2; il suo residuo d'uscita e' l'ingresso del passo
j+1; le sue K/V alle celle c+1..c+j sono quelle della catena stessa (come nel motore: i passi scrivono le proprie celle).

Perdita: per passo j e cella c valida (il token predetto c+j+2 e' un token generato, gen = 1, e la distribuzione del target
alla posizione c+j+1 esiste), KL(q || p) con q = top-20 del target rinormalizzato sui token del sottoinsieme del draft head
(rt/draft_vocab.bin: il motore non puo' proporre altro) e p = softmax dei logits del drafter sullo stesso sottoinsieme.
Pesi per passo --step-weights (default uguali).  Allenabili: ~89M (mtp_model.TRAINABLE_PREFIXES); esperti instradati, testa,
embedding congelati.  Precisione: parametri f32, matmul in bf16 (autocast) su CUDA.

Valutazione (prima del training e a ogni --eval-every passi, sul set `heldout`): per passo j accettazione greedy
(argmax del drafter sul sottoinsieme == top-1 del target), quota di bozze "offerte" (p_draft >= --spec-min-p, 0.5 come il
Daily) e lunghezza media della catena accettata (bozze consecutive offerte e giuste), tutto sulle sole celle generate.

Scrive in --out: trainable.safetensors (i pesi affinati, nomi corti: l'ingresso di export_mtp.py), log.jsonl, eval.json.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mtp_model as M  # noqa: E402


class CaptureData:
    """Le sequenze catturate: ids/gen del render + R e top-k della cattura (memmap)."""

    def __init__(self, seqs: Path, capture: Path, split: str, topk: int = 20, max_len: int = 0, limit: int = 0):
        self.ids_all = np.fromfile(seqs / "seqs_ids.i32", dtype=np.int32)
        self.gen_all = np.fromfile(seqs / "seqs_gen.u8", dtype=np.uint8)
        index = json.loads((seqs / "seqs_index.json").read_text())
        cmap = json.loads((capture / "capture_map.json").read_text())
        self.items = []
        for e in index:
            m = cmap.get(str(e["i"]))
            if not m or not m.get("ok") or e["split"] != split:
                continue
            base = capture / m["run"] / f"seq_{m['k']}"
            self.items.append((e, base))
            if limit and len(self.items) >= limit:
                break
        self.topk, self.max_len, self.capture = topk, max_len, capture

    def __len__(self):
        return len(self.items)

    def get(self, i: int):
        e, base = self.items[i]
        n = e["n"]
        ids = self.ids_all[e["off"]: e["off"] + n].astype(np.int64)
        gen = self.gen_all[e["off"]: e["off"] + n]
        m = n - 1   # posizioni catturate 0..n-2
        tok = np.fromfile(str(base) + ".tok.i32", dtype=np.int32)
        if tok.shape[0] != m or not np.array_equal(tok, ids[:m]):
            raise ValueError(f"cattura {base}: token diversi dal render")
        R = np.fromfile(str(base) + ".r.bf16", dtype=np.uint16).reshape(m, M.HCN)
        top = np.fromfile(str(base) + ".top.bin", dtype=np.uint8).reshape(m, self.topk * 8)
        top_ids = top[:, : self.topk * 4].copy().view(np.int32).astype(np.int64)
        top_lp = top[:, self.topk * 4:].copy().view(np.float32)
        if self.max_len and m > self.max_len:   # prova: una finestra casuale corta
            s = random.randint(0, m - self.max_len)
            R, top_ids, top_lp = R[s: s + self.max_len], top_ids[s: s + self.max_len], top_lp[s: s + self.max_len]
            ids, gen = ids[s: s + self.max_len + 1], gen[s: s + self.max_len + 1]
            m = self.max_len
        return {"R": torch.from_numpy(R.view(np.int16)).view(torch.bfloat16), "ids": torch.from_numpy(ids),
                "gen": torch.from_numpy(gen.astype(np.int64)), "top_ids": torch.from_numpy(top_ids),
                "top_lp": torch.from_numpy(top_lp), "m": m}


def step_losses(model: M.MtpLayer, inv_map: torch.Tensor, batch: dict, steps: int, device, spec_min_p: float,
                head_chunk: int = 1024):
    """La catena srotolata su una sequenza: per passo j la KL media sulle celle valide e le metriche di accettazione."""
    R = batch["R"].to(device).unsqueeze(0)                      # [1, m, HCN]
    ids = batch["ids"].to(device)                               # [n]
    gen = batch["gen"].to(device)
    top_ids, top_lp = batch["top_ids"].to(device), batch["top_lp"].to(device)
    m = batch["m"]
    L = m - steps                                               # celle con ingressi per ogni passo: c <= m - 1 - steps
    if L < 8:
        return None
    R = R[:, :L]
    ids_in = ids[: L + steps + 1]                               # ids[c + j + 1] per c < L, j < steps
    ids_in = torch.cat([ids_in, ids_in.new_full((max(0, L + steps + 1 - ids_in.numel()),), 0)]).unsqueeze(0)
    samples = model.chain(R, ids_in, steps)
    out = {"loss": 0.0, "steps": [], "kl_terms": []}
    total = 0.0
    for j, sample in enumerate(samples):
        # il target alla posizione c + j + 1, il token predetto c + j + 2
        pos = torch.arange(L, device=device) + j + 1
        valid = (pos <= m - 1) & (pos + 1 < ids.numel()) & (gen[torch.clamp(pos + 1, max=ids.numel() - 1)] == 1)
        tid = top_ids[pos.clamp(max=m - 1)]                     # [L, K]
        tlp = top_lp[pos.clamp(max=m - 1)]
        sub = inv_map[tid.clamp(min=0)]                         # indice nel sottoinsieme o -1
        keep = (sub >= 0) & (tid >= 0)
        q = torch.where(keep, tlp.float().exp(), torch.zeros_like(tlp))
        qs = q.sum(-1)
        valid = valid & (qs > 1e-6)
        q = q / qs.clamp_min(1e-9).unsqueeze(-1)
        idx = valid.nonzero(as_tuple=True)[0]
        n_valid = int(idx.numel())
        if n_valid == 0:
            out["steps"].append({"n": 0})
            out["kl_terms"].append(torch.zeros((), device=device))
            continue
        kl_sum = torch.zeros((), device=device, dtype=torch.float32)
        acc = off = both = 0
        for c0 in range(0, n_valid, head_chunk):
            sel = idx[c0: c0 + head_chunk]
            logits = model.head(sample[0, sel])                 # [b, Vd] f32
            logp = torch.log_softmax(logits, dim=-1)
            lp_t = torch.gather(logp, 1, sub[sel].clamp(min=0))  # [b, K]
            qq = q[sel]
            kl = (qq * (torch.log(qq.clamp_min(1e-12)) - lp_t)).sum(-1)   # KL(q || p) sui top-k tenuti
            kl_sum = kl_sum + kl.sum()
            with torch.no_grad():
                pmax, amax = logp.max(-1)
                match = amax == sub[sel][:, 0]                   # top-1 del target (il primo id e' il piu' probabile)
                offered = pmax.exp() >= spec_min_p
                acc += int(match.sum()); off += int(offered.sum()); both += int((match & offered).sum())
        out["steps"].append({"n": n_valid, "kl": float(kl_sum.detach()) / n_valid, "acc": acc / n_valid,
                             "offered": off / n_valid, "acc_offered": both / n_valid})
        out["kl_terms"].append(kl_sum / n_valid)
        total = total + kl_sum / n_valid
    out["loss"] = total
    return out


@torch.no_grad()
def chain_metrics(model: M.MtpLayer, inv_map: torch.Tensor, dvocab: torch.Tensor, batch: dict, steps: int, device,
                  spec_min_p: float):
    """Lunghezza media della catena accettata: bozze consecutive offerte (p >= min_p) e uguali al top-1 del target."""
    R = batch["R"].to(device).unsqueeze(0)
    ids, gen = batch["ids"].to(device), batch["gen"].to(device)
    top_ids = batch["top_ids"].to(device)
    m = batch["m"]
    L = m - steps
    if L < 8:
        return None
    ids_in = ids[: L + steps + 1]
    ids_in = torch.cat([ids_in, ids_in.new_full((max(0, L + steps + 1 - ids_in.numel()),), 0)]).unsqueeze(0)
    samples = model.chain(R[:, :L], ids_in, steps)
    alive = torch.ones(L, dtype=torch.bool, device=device)
    length = torch.zeros(L, dtype=torch.float32, device=device)
    cells = torch.arange(L, device=device)
    base_valid = gen[torch.clamp(cells + 2, max=ids.numel() - 1)] == 1
    per_step = []
    for j, sample in enumerate(samples):
        pos = cells + j + 1
        logits = model.head(sample[0])
        p = torch.softmax(logits, -1)
        pmax, amax = p.max(-1)
        ok = (dvocab[amax] == top_ids[pos.clamp(max=m - 1), 0]) & (pmax >= spec_min_p) & (pos <= m - 1)
        alive = alive & ok
        length += alive.float()
        per_step.append(float(ok[base_valid].float().mean()) if base_valid.any() else 0.0)
    return {"n": int(base_valid.sum()), "chain_len": float(length[base_valid].mean()) if base_valid.any() else 0.0,
            "acc_offered_by_step": per_step}


def evaluate(model, inv_map, dvocab, data: CaptureData, steps, device, spec_min_p, max_items: int) -> dict:
    model.eval()
    agg = [dict(n=0, kl=0.0, acc=0.0, offered=0.0, acc_offered=0.0) for _ in range(steps)]
    chain_n, chain_sum = 0, 0.0
    for i in range(min(len(data), max_items)):
        b = data.get(i)
        with torch.no_grad(), torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
            r = step_losses(model, inv_map, b, steps, device, spec_min_p)
            cm = chain_metrics(model, inv_map, dvocab, b, steps, device, spec_min_p)
        if r is None:
            continue
        for j, s in enumerate(r["steps"]):
            if s["n"]:
                agg[j]["n"] += s["n"]
                for k in ("kl", "acc", "offered", "acc_offered"):
                    agg[j][k] += s[k] * s["n"]
        if cm:
            chain_n += cm["n"]
            chain_sum += cm["chain_len"] * cm["n"]
    res = {"steps": []}
    for s in agg:
        n = max(1, s["n"])
        res["steps"].append({"n": s["n"], "kl": round(s["kl"] / n, 4), "acc": round(s["acc"] / n, 4),
                             "offered": round(s["offered"] / n, 4), "acc_offered": round(s["acc_offered"] / n, 4)})
    res["chain_len_mean"] = round(chain_sum / max(1, chain_n), 4)
    res["chain_cells"] = chain_n
    model.train()
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bf16", required=True)
    ap.add_argument("--rt", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--strata", required=True, help="worktree Strata (tools/gguf_reader.py)")
    ap.add_argument("--seqs", required=True)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache", default=None, help="cache embedding/testa dequantizzati (default <out>/../cache)")
    ap.add_argument("--steps", type=int, default=4, help="passi srotolati della catena")
    ap.add_argument("--step-weights", default="", help="pesi per passo, es. 1,0.8,0.6,0.5 (default uguali)")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--max-steps", type=int, default=0, help="prova: ferma dopo N passi di ottimizzazione")
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--warmup", type=int, default=50)
    ap.add_argument("--accum", type=int, default=4, help="sequenze per passo di ottimizzazione")
    ap.add_argument("--clip", type=float, default=1.0)
    ap.add_argument("--weight-decay", type=float, default=0.0)
    ap.add_argument("--spec-min-p", type=float, default=0.5)
    ap.add_argument("--eval-every", type=int, default=100)
    ap.add_argument("--eval-items", type=int, default=64)
    ap.add_argument("--max-len", type=int, default=0, help="prova: finestre casuali di al piu' N posizioni")
    ap.add_argument("--limit-items", type=int, default=0, help="prova: solo N sequenze di training")
    ap.add_argument("--experts", choices=["q2", "bf16"], default="q2")
    ap.add_argument("--no-train-fc", action="store_true", help="congela fc_embedding / fc_hidden / pre_fc_norm (come #97)")
    ap.add_argument("--hnorm-stream", action="store_true", help="--mtp-hnorm stream del motore (default: una RMS su 10240)")
    ap.add_argument("--full-head", action="store_true", help="logits su tutto il vocabolario invece del sottoinsieme")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--resume", help="trainable.safetensors da cui ripartire")
    ap.add_argument("--threads", type=int, default=0, help="thread CPU di torch (prove locali: pochi, per non disturbare)")
    a = ap.parse_args()
    if a.threads:
        torch.set_num_threads(a.threads)
    torch.manual_seed(a.seed)
    random.seed(a.seed)
    device = torch.device(a.device)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(a.cache) if a.cache else out.parent / "cache"
    t0 = time.time()
    model, dvocab = M.build_model(Path(a.bf16), Path(a.rt), Path(a.gguf), Path(a.strata) / "tools", cache, device,
                                  experts_mode=a.experts, hnorm_per_stream=a.hnorm_stream, train_fc=not a.no_train_fc,
                                  full_head=a.full_head)
    n_vocab = model.embed.shape[0]
    inv_map = torch.full((n_vocab,), -1, dtype=torch.long, device=device)
    inv_map[dvocab] = torch.arange(dvocab.numel(), device=device)
    if a.resume:
        from safetensors.torch import load_file
        sd = load_file(a.resume)
        with torch.no_grad():
            for k, v in sd.items():
                model.params[k.replace(".", "__")].copy_(v.to(device))
    n_tr = sum(p.numel() for p in model.params.values())
    print(f"modello pronto in {time.time() - t0:.0f} s: {n_tr / 1e6:.1f}M parametri allenabili, sottoinsieme testa {dvocab.numel()}, device {device}", flush=True)
    train = CaptureData(Path(a.seqs), Path(a.capture), "train", max_len=a.max_len, limit=a.limit_items)
    held = CaptureData(Path(a.seqs), Path(a.capture), "heldout", max_len=a.max_len)
    print(f"sequenze: train {len(train)}, heldout {len(held)}", flush=True)
    if not len(train):
        print("nessuna sequenza catturata nello split train")
        return 1
    weights = [float(x) for x in a.step_weights.split(",")] if a.step_weights else [1.0] * a.steps
    assert len(weights) == a.steps
    opt = torch.optim.AdamW(model.params.values(), lr=a.lr, betas=(0.9, 0.95), weight_decay=a.weight_decay)
    total_steps = a.max_steps or max(1, int(a.epochs * len(train) / a.accum))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / max(1, a.warmup)) *
                                              0.5 * (1 + math.cos(math.pi * min(1.0, s / max(1, total_steps)))))
    log = open(out / "log.jsonl", "a", encoding="utf-8")
    evals = {}
    if len(held):
        ev = evaluate(model, inv_map, dvocab, held, a.steps, device, a.spec_min_p, a.eval_items)
        evals["step_0"] = ev
        print("eval iniziale:", json.dumps(ev), flush=True)
    model.train()
    order = list(range(len(train)))
    step = 0
    k = 0
    seen_tokens = 0
    t_run = time.time()
    while step < total_steps:
        random.shuffle(order)
        for i in order:
            b = train.get(i)
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                r = step_losses(model, inv_map, b, a.steps, device, a.spec_min_p)
            if r is None:
                continue
            loss = sum(w * t for w, t in zip(weights, r["kl_terms"]))   # KL media per passo, pesata
            if not isinstance(loss, torch.Tensor) or not loss.requires_grad:
                continue
            (loss / a.accum).backward()
            seen_tokens += b["m"]
            k += 1
            if k % a.accum == 0:
                gn = torch.nn.utils.clip_grad_norm_(model.params.values(), a.clip)
                opt.step()
                sched.step()
                opt.zero_grad(set_to_none=True)
                step += 1
                rec = {"step": step, "loss": float(loss), "grad_norm": float(gn), "lr": sched.get_last_lr()[0],
                       "tokens": seen_tokens, "s": round(time.time() - t_run, 1),
                       "steps": [{kk: round(v, 4) if isinstance(v, float) else v for kk, v in s.items()} for s in r["steps"]]}
                log.write(json.dumps(rec) + "\n")
                log.flush()
                if step % 10 == 0 or step == 1:
                    accs = " ".join(f"{s.get('acc', 0):.3f}" for s in r["steps"])
                    print(f"passo {step}/{total_steps} loss {float(loss):.4f} acc/passo {accs} lr {sched.get_last_lr()[0]:.2e} "
                          f"{seen_tokens / max(1e-9, time.time() - t_run):.0f} tok/s", flush=True)
                if step % a.eval_every == 0 and len(held):
                    ev = evaluate(model, inv_map, dvocab, held, a.steps, device, a.spec_min_p, a.eval_items)
                    evals[f"step_{step}"] = ev
                    print(f"eval passo {step}:", json.dumps(ev), flush=True)
                    (out / "eval.json").write_text(json.dumps(evals, indent=1), encoding="utf-8")
                    save(model, out)
                if step >= total_steps:
                    break
    save(model, out)
    if len(held):
        ev = evaluate(model, inv_map, dvocab, held, a.steps, device, a.spec_min_p, a.eval_items)
        evals["final"] = ev
        print("eval finale:", json.dumps(ev), flush=True)
    (out / "eval.json").write_text(json.dumps(evals, indent=1), encoding="utf-8")
    print(f"fatto: {step} passi, {seen_tokens} token visti, {(time.time() - t_run) / 60:.1f} min -> {out}")
    return 0


def save(model: M.MtpLayer, out: Path):
    from safetensors.torch import save_file
    save_file({k: v.detach().cpu().contiguous() for k, v in model.trainable_tensors().items()}, str(out / "trainable.safetensors"))


if __name__ == "__main__":
    sys.exit(main())
