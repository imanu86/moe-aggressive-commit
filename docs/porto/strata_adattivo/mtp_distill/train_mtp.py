"""train_mtp.py - distillazione del layer MTP sulle catture del target (KL top-20 srotolata, come #97).

    python train_mtp.py --bf16 D:\\ds4_work\\strata\\Strata-data\\mtp --rt D:\\ds4_work\\strata\\Strata-data\\mtp\\rt_it48k \\
        --gguf <shard 1 del target> --strata <worktree Strata> --seqs D:\\...\\seqs --capture D:\\...\\capture \\
        --out D:\\ds4_work\\mtp_distill\\runs\\ft1 --steps 4 --epochs 1 --lr 3e-5 --accum 4 --split-by-conv 12

Dati: per ogni sequenza (render_sequences.py) i file di cattura (capture_driver.py + STRATA_MTP_CAPTURE): R_p (residuo finale
del target, bf16) e top-20 (id, log-prob) alle posizioni p = 0..n-2.  Catena del drafter dalla cella c: passo j consuma
(R^(j)_c, token c+j+1) alla posizione rope c+j e predice il token c+j+2; il suo residuo d'uscita e' l'ingresso del passo
j+1; le sue K/V alle celle c+1..c+j sono quelle della catena stessa (come nel motore).  La catena gira solo sulle celle
"attive": quelle che in qualche passo predicono un token generato (gen = 1) con la distribuzione del target disponibile.

Perdita: per passo j e cella valida, KL(q || p) con q = top-20 del target rinormalizzato sui token del sottoinsieme del
draft head (rt/draft_vocab.bin: il motore non puo' proporre altro) e p = softmax dei logits del drafter sullo stesso
sottoinsieme; --nll-weight pesa ogni cella per exp(nll) (= p_target del token vero: dove il target era incerto sul testo
altrui il bersaglio e' rumoroso).  Pesi per passo --step-weights.  Allenabili ~89M (mtp_model.TRAINABLE_PREFIXES).
Precisione: parametri f32; matmul in bf16 (Ampere+) o fp16 con GradScaler (Turing); --dtype per forzare.

Valutazione (prima del training, ogni --eval-every passi e alla fine, sullo split heldout), per passo j:
  greedy: accettazione (argmax del drafter == top-1 del target), quota "offerta" (p_draft >= --spec-min-p), entrambe, e la
          lunghezza media della catena greedy accettata;
  campionata (--eval-sampling "nome:T,top_p,top_k;..."): accettazione attesa dello speculative sampling,
          sum_x min(p_T(x), q_T(x)) con temperatura / top-k / top-p applicati a target (top-20) e drafter.
Split: quello dell'indice (un pezzo ogni 33) oppure --split-by-conv N: heldout = le conversazioni con crc32 % N == 0
(pezzi della stessa conversazione mai da entrambe le parti).

Scrive in --out: trainable.safetensors (i pesi affinati, nomi corti: l'ingresso di export_mtp.py), log.jsonl, eval.json.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
import zlib
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mtp_model as M  # noqa: E402

torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction = False


def split_of(entry: dict, by_conv: int) -> str:
    if by_conv <= 0:
        return entry["split"]
    return "heldout" if zlib.crc32(entry["conv"].encode()) % by_conv == 0 else "train"


class CaptureData:
    """Le sequenze catturate: ids/gen del render + R e top-k della cattura (memmap)."""

    def __init__(self, seqs: Path, capture: Path, split: str, topk: int = 20, max_len: int = 0, limit: int = 0,
                 by_conv: int = 0):
        self.ids_all = np.fromfile(seqs / "seqs_ids.i32", dtype=np.int32)
        self.gen_all = np.fromfile(seqs / "seqs_gen.u8", dtype=np.uint8)
        index = json.loads((seqs / "seqs_index.json").read_text())
        cmap = json.loads((capture / "capture_map.json").read_text())
        self.items = []
        for e in index:
            m = cmap.get(str(e["i"]))
            if not m or not m.get("ok") or split_of(e, by_conv) != split:
                continue
            base = capture / m["run"] / f"seq_{m['k']}"
            self.items.append((e, base, int(m["n"])))
            if limit and len(self.items) >= limit:
                break
        self.topk, self.max_len, self.capture = topk, max_len, capture

    def __len__(self):
        return len(self.items)

    def tokens(self) -> int:
        return sum(n for _, _, n in self.items)

    def get(self, i: int):
        e, base, n = self.items[i]
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
        nll = np.fromfile(str(base) + ".nll.f32", dtype=np.float32)
        if self.max_len and m > self.max_len:   # prova: una finestra corta che contenga token generati
            cand = [p for p in range(0, m - self.max_len + 1) if gen[p: p + self.max_len + 1].sum() >= 4]
            s = random.choice(cand) if cand else random.randint(0, m - self.max_len)
            R, top_ids, top_lp, nll = R[s: s + self.max_len], top_ids[s: s + self.max_len], top_lp[s: s + self.max_len], nll[s: s + self.max_len]
            ids, gen = ids[s: s + self.max_len + 1], gen[s: s + self.max_len + 1]
            m = self.max_len
        return {"R": torch.from_numpy(R.view(np.int16)).view(torch.bfloat16), "ids": torch.from_numpy(ids),
                "gen": torch.from_numpy(gen.astype(np.int64)), "top_ids": torch.from_numpy(top_ids),
                "top_lp": torch.from_numpy(top_lp), "nll": torch.from_numpy(nll), "m": m, "conv": e["conv"]}


def parse_sampling(spec: str) -> list[tuple[str, float, float, int]]:
    out = []
    for part in [s for s in spec.split(";") if s.strip()]:
        name, vals = part.split(":")
        t, tp, tk = vals.split(",")
        out.append((name.strip(), float(t), float(tp), int(tk)))
    return out


def truncate(p: torch.Tensor, temperature: float, top_p: float, top_k: int) -> torch.Tensor:
    """p [b, V] probabilita' (non necessariamente normalizzate) -> la distribuzione campionata: top-k, top-p, temperatura."""
    p = p / p.sum(-1, keepdim=True).clamp_min(1e-12)
    keep = torch.ones_like(p, dtype=torch.bool)
    if top_k > 0 and top_k < p.shape[-1]:
        kth = torch.topk(p, top_k, dim=-1).values[:, -1:]
        keep &= p >= kth
    if 0.0 < top_p < 1.0:
        sp, si = torch.sort(p, dim=-1, descending=True)
        cum = sp.cumsum(-1) - sp
        keep_sorted = cum < top_p                    # il token che supera la soglia resta (come llama.cpp)
        keep &= torch.zeros_like(keep).scatter(1, si, keep_sorted)
    logp = torch.log(p.clamp_min(1e-30)) / max(temperature, 1e-6)
    logp = logp.masked_fill(~keep, float("-inf"))
    return torch.softmax(logp, dim=-1)


def step_losses(model: M.MtpLayer, inv_map: torch.Tensor, batch: dict, steps: int, device, spec_min_p: float,
                sampling: list, head_chunk: int = 1024, nll_weight: bool = False, with_metrics: bool = True):
    """La catena srotolata su una sequenza: per passo j la KL media sulle celle valide e le metriche di accettazione."""
    R = batch["R"].to(device).float()                           # [m, HCN]
    ids = batch["ids"].to(device)                               # [n]
    gen = batch["gen"].to(device)
    top_ids, top_lp = batch["top_ids"].to(device), batch["top_lp"].to(device)
    nll = batch["nll"].to(device)
    m = batch["m"]
    L = m - steps                                               # celle con ingressi per ogni passo: c <= m - 1 - steps
    if L < 8:
        return None
    cells = torch.arange(L, device=device)
    ids_in = ids[: L + steps + 1]
    ids_in = torch.cat([ids_in, ids_in.new_full((max(0, L + steps + 1 - ids_in.numel()),), 0)])
    # le celle attive: in qualche passo predicono un token generato con il target disponibile
    valid_j = []
    for j in range(steps):
        pos = cells + j + 1
        v = (pos <= m - 1) & (pos + 1 < ids.numel()) & (gen[torch.clamp(pos + 1, max=ids.numel() - 1)] == 1)
        valid_j.append(v)
    active = torch.stack(valid_j).any(0).nonzero(as_tuple=True)[0]
    if active.numel() == 0:
        return None
    active, samples = model.chain(R[:L], ids_in, steps, active)
    out = {"loss": 0.0, "steps": [], "kl_terms": [], "active": int(active.numel()), "sampled": {}}
    alive = torch.ones(active.numel(), dtype=torch.bool, device=device)
    chain_len = torch.zeros(active.numel(), dtype=torch.float32, device=device)
    base_valid = valid_j[0][active]
    for j, sample in enumerate(samples):
        pos = active + j + 1
        valid = valid_j[j][active]
        tid = top_ids[pos.clamp(max=m - 1)]                     # [A, K]
        tlp = top_lp[pos.clamp(max=m - 1)]
        sub = inv_map[tid.clamp(min=0)]                         # indice nel sottoinsieme o -1
        keep = (sub >= 0) & (tid >= 0)
        q = torch.where(keep, tlp.float().exp(), torch.zeros_like(tlp))
        qs = q.sum(-1)
        valid = valid & (qs > 1e-6)
        q = q / qs.clamp_min(1e-9).unsqueeze(-1)
        cw = nll[pos.clamp(max=m - 1)].float().exp().clamp(0.0, 1.0) if nll_weight else torch.ones_like(qs)
        idx = valid.nonzero(as_tuple=True)[0]
        n_valid = int(idx.numel())
        if n_valid == 0:
            out["steps"].append({"n": 0})
            out["kl_terms"].append(torch.zeros((), device=device))
            continue
        kl_sum = torch.zeros((), device=device, dtype=torch.float32)
        wsum = 0.0
        acc = off = both = 0
        samp_acc = {name: 0.0 for name, *_ in sampling}
        ok_step = torch.zeros(active.numel(), dtype=torch.bool, device=device)
        for c0 in range(0, n_valid, head_chunk):
            sel = idx[c0: c0 + head_chunk]
            logits = model.head(sample[sel])                    # [b, Vd] f32
            logp = torch.log_softmax(logits, dim=-1)
            lp_t = torch.gather(logp, 1, sub[sel].clamp(min=0))  # [b, K]
            qq = q[sel]
            kl = (qq * (torch.log(qq.clamp_min(1e-12)) - lp_t)).sum(-1)   # KL(q || p) sui top-k tenuti
            kl_sum = kl_sum + (kl * cw[sel]).sum()
            wsum += float(cw[sel].sum())
            if with_metrics:
                with torch.no_grad():
                    pmax, amax = logp.max(-1)
                    match = amax == sub[sel][:, 0]               # top-1 del target (il primo id e' il piu' probabile)
                    offered = pmax.exp() >= spec_min_p
                    acc += int(match.sum()); off += int(offered.sum()); both += int((match & offered).sum())
                    ok_step[sel] = match & offered
                    if sampling:
                        pdraft = logp.exp()                      # [b, Vd]
                        qt = torch.zeros_like(pdraft).scatter(1, sub[sel].clamp(min=0), qq)   # il target sul sottoinsieme
                        for name, temp, top_p, top_k in sampling:
                            pt = truncate(qt, temp, top_p, top_k)
                            pd = truncate(pdraft, temp, top_p, top_k)
                            samp_acc[name] += float(torch.minimum(pt, pd).sum(-1).sum())
        kl_mean = kl_sum / max(wsum, 1e-9)
        rec = {"n": n_valid, "kl": float(kl_mean.detach())}
        if with_metrics:
            rec.update({"acc": acc / n_valid, "offered": off / n_valid, "acc_offered": both / n_valid,
                        "sampled": {k: v / n_valid for k, v in samp_acc.items()}})
            alive = alive & ok_step & valid
            chain_len += alive.float()
        out["steps"].append(rec)
        out["kl_terms"].append(kl_mean)
    if with_metrics:
        out["chain_len"] = float(chain_len[base_valid].mean()) if bool(base_valid.any()) else 0.0
        out["chain_cells"] = int(base_valid.sum())
    return out


def evaluate(model, inv_map, data: CaptureData, steps, device, spec_min_p, sampling, max_items: int) -> dict:
    model.eval()
    agg = [dict(n=0, kl=0.0, acc=0.0, offered=0.0, acc_offered=0.0, sampled={name: 0.0 for name, *_ in sampling}) for _ in range(steps)]
    chain_n, chain_sum, tokens = 0, 0.0, 0
    t0 = time.time()
    for i in range(min(len(data), max_items)):
        b = data.get(i)
        with torch.no_grad():
            r = step_losses(model, inv_map, b, steps, device, spec_min_p, sampling)
        if r is None:
            continue
        tokens += b["m"]
        for j, s in enumerate(r["steps"]):
            if s["n"]:
                agg[j]["n"] += s["n"]
                for k in ("kl", "acc", "offered", "acc_offered"):
                    agg[j][k] += s[k] * s["n"]
                for k, v in s["sampled"].items():
                    agg[j]["sampled"][k] += v * s["n"]
        chain_n += r["chain_cells"]
        chain_sum += r["chain_len"] * r["chain_cells"]
    res = {"steps": []}
    for s in agg:
        n = max(1, s["n"])
        res["steps"].append({"n": s["n"], "kl": round(s["kl"] / n, 4), "acc": round(s["acc"] / n, 4),
                             "offered": round(s["offered"] / n, 4), "acc_offered": round(s["acc_offered"] / n, 4),
                             "sampled": {k: round(v / n, 4) for k, v in s["sampled"].items()}})
    res["chain_len_mean"] = round(chain_sum / max(1, chain_n), 4)
    res["chain_cells"] = chain_n
    res["tokens"] = tokens
    res["seconds"] = round(time.time() - t0, 1)
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
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--max-steps", type=int, default=0, help="prova: ferma dopo N passi di ottimizzazione")
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--accum", type=int, default=4, help="sequenze per passo di ottimizzazione")
    ap.add_argument("--clip", type=float, default=1.0)
    ap.add_argument("--weight-decay", type=float, default=0.0)
    ap.add_argument("--spec-min-p", type=float, default=0.5)
    ap.add_argument("--nll-weight", action="store_true", help="pesa le celle per p_target(token vero)")
    ap.add_argument("--eval-every", type=int, default=50)
    ap.add_argument("--eval-items", type=int, default=64)
    ap.add_argument("--eval-only", action="store_true", help="solo l'eval iniziale (diagnosi, es. --experts bf16)")
    ap.add_argument("--eval-sampling", default="think:1.0,0.95,20;nothink:0.7,0.8,0",
                    help="nome:T,top_p,top_k;... (gli harness: T=1 top_p .95 top_k 20 col ragionamento; T=.7 top_p .8 senza)")
    ap.add_argument("--split-by-conv", type=int, default=0, help="heldout = conversazioni con crc32 %% N == 0 (0: split dell'indice)")
    ap.add_argument("--max-len", type=int, default=0, help="prova: finestre casuali di al piu' N posizioni")
    ap.add_argument("--limit-items", type=int, default=0, help="prova: solo N sequenze di training")
    ap.add_argument("--experts", choices=["q2", "bf16"], default="q2")
    ap.add_argument("--no-train-fc", action="store_true", help="congela fc_embedding / fc_hidden / pre_fc_norm (come #97)")
    ap.add_argument("--hnorm-stream", action="store_true", help="--mtp-hnorm stream del motore (default: una RMS su 10240)")
    ap.add_argument("--full-head", action="store_true", help="logits su tutto il vocabolario invece del sottoinsieme")
    ap.add_argument("--dtype", choices=["auto", "bf16", "fp16", "f32"], default="auto")
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
    dtype = {"auto": None, "bf16": torch.bfloat16, "fp16": torch.float16, "f32": torch.float32}[a.dtype]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(a.cache) if a.cache else out.parent / "cache"
    sampling = parse_sampling(a.eval_sampling)
    t0 = time.time()
    model, dvocab = M.build_model(Path(a.bf16), Path(a.rt), Path(a.gguf), Path(a.strata) / "tools", cache, device,
                                  experts_mode=a.experts, hnorm_per_stream=a.hnorm_stream, train_fc=not a.no_train_fc,
                                  full_head=a.full_head, dtype=dtype)
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
    print(f"modello pronto in {time.time() - t0:.0f} s: {n_tr / 1e6:.1f}M parametri allenabili, sottoinsieme testa {dvocab.numel()}, "
          f"device {device}, dtype {model.dt}, esperti {a.experts}", flush=True)
    train = CaptureData(Path(a.seqs), Path(a.capture), "train", max_len=a.max_len, limit=a.limit_items, by_conv=a.split_by_conv)
    held = CaptureData(Path(a.seqs), Path(a.capture), "heldout", max_len=a.max_len, by_conv=a.split_by_conv)
    print(f"sequenze: train {len(train)} ({train.tokens()} token), heldout {len(held)} ({held.tokens()} token)", flush=True)
    evals = {"config": {k: v for k, v in vars(a).items()}}
    if len(held):
        ev = evaluate(model, inv_map, held, a.steps, device, a.spec_min_p, sampling, a.eval_items)
        evals["step_0"] = ev
        print("eval iniziale:", json.dumps(ev), flush=True)
        (out / "eval.json").write_text(json.dumps(evals, indent=1), encoding="utf-8")
    if a.eval_only:
        return 0
    if not len(train):
        print("nessuna sequenza catturata nello split train")
        return 1
    weights = [float(x) for x in a.step_weights.split(",")] if a.step_weights else [1.0] * a.steps
    assert len(weights) == a.steps
    opt = torch.optim.AdamW(model.params.values(), lr=a.lr, betas=(0.9, 0.95), weight_decay=a.weight_decay)
    scaler = torch.amp.GradScaler("cuda", enabled=(model.dt == torch.float16))
    total_steps = a.max_steps or max(1, int(a.epochs * len(train) / a.accum))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / max(1, a.warmup)) *
                                              0.5 * (1 + math.cos(math.pi * min(1.0, s / max(1, total_steps)))))
    log = open(out / "log.jsonl", "a", encoding="utf-8")
    model.train()
    order = list(range(len(train)))
    step = 0
    k = 0
    seen_tokens = 0
    t_run = time.time()
    while step < total_steps:
        random.shuffle(order)
        useful = 0   # sequenze con almeno una cella valida in questo giro: zero = niente da imparare, non un ciclo infinito
        for i in order:
            b = train.get(i)
            r = step_losses(model, inv_map, b, a.steps, device, a.spec_min_p, [], nll_weight=a.nll_weight, with_metrics=(k % a.accum == 0))
            if r is None:
                continue
            loss = sum(w * t for w, t in zip(weights, r["kl_terms"]))   # KL media per passo, pesata
            if not isinstance(loss, torch.Tensor) or not loss.requires_grad:
                continue
            useful += 1
            scaler.scale(loss / a.accum).backward()
            seen_tokens += b["m"]
            k += 1
            if k % a.accum == 0:
                scaler.unscale_(opt)
                gn = torch.nn.utils.clip_grad_norm_(model.params.values(), a.clip)
                scaler.step(opt)
                scaler.update()
                sched.step()
                opt.zero_grad(set_to_none=True)
                step += 1
                rec = {"step": step, "loss": float(loss), "grad_norm": float(gn), "lr": sched.get_last_lr()[0],
                       "tokens": seen_tokens, "s": round(time.time() - t_run, 1), "active": r["active"],
                       "steps": [{kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in s.items() if kk != "sampled"} for s in r["steps"]]}
                log.write(json.dumps(rec) + "\n")
                log.flush()
                if step % 5 == 0 or step == 1:
                    accs = " ".join(f"{s.get('acc', 0):.3f}" for s in r["steps"])
                    print(f"passo {step}/{total_steps} loss {float(loss):.4f} acc/passo {accs} gn {float(gn):.2f} lr {sched.get_last_lr()[0]:.2e} "
                          f"{seen_tokens / max(1e-9, time.time() - t_run):.0f} tok/s mem {torch.cuda.max_memory_allocated() / 2**30 if device.type == 'cuda' else 0:.1f} GiB", flush=True)
                if step % a.eval_every == 0 and len(held) and step < total_steps:
                    ev = evaluate(model, inv_map, held, a.steps, device, a.spec_min_p, sampling, a.eval_items)
                    evals[f"step_{step}"] = ev
                    print(f"eval passo {step}:", json.dumps(ev), flush=True)
                    (out / "eval.json").write_text(json.dumps(evals, indent=1), encoding="utf-8")
                    save(model, out)
                if step >= total_steps:
                    break
        if useful == 0:
            print("nessuna sequenza con celle valide (token generati con top-k nel sottoinsieme): mi fermo", flush=True)
            break
    save(model, out)
    if len(held):
        ev = evaluate(model, inv_map, held, a.steps, device, a.spec_min_p, sampling, a.eval_items)
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
