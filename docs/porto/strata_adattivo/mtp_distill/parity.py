"""parity.py - il drafter in PyTorch (mtp_model.py) contro il drafter del motore (STRATA_MTP_DUMP), stessi ingressi.

    python parity.py --dump <file del dump> --seqs <seqs> --capture <capture della stessa corsa> \\
        --bf16 ... --rt ... --gguf ... --strata ... [--steps 4]

La corsa: capture_driver.py --keep-mtp --max-new 8 --dump <file> --split heldout --count 50 --trunc 1500 [--mtp-dir rt_it48k].
Per ogni richiesta il motore legge il prompt (n token: la cattura ha R e top-20 alle posizioni 0..n-2) e poi decodifica;
il PRIMO draft di ogni richiesta parte dalla cella n-1 (p = n-1, a = 0, T = 1): il dump ha la sua R (dalla finestra di
decode), il token d'ingresso (il primo token generato) e, per ogni passo eseguito, bozza, probabilita' e i logit della
testa di bozza (ordine del sottoinsieme).  Qui si ricostruisce la stessa catena: R delle celle 0..n-2 dalla cattura (le
chiavi dell'attenzione), R_{n-1} e i token dal dump (i passi successivi prendono le bozze del motore come ingresso), e si
confrontano per passo argmax (deve coincidere >= 99%) e KL(motore || torch) (deve stare sotto 0,01), piu' |delta p_max|.
I record di draft successivi (p + a > n - 1) sono saltati: le loro celle precedenti sono token generati, senza R catturata.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mtp_model as M  # noqa: E402

MAGIC = 0x4D545044


def read_dump(path: Path):
    """Generatore dei record del dump (vedi mtp.cpp, mtp_dump_file)."""
    data = np.memmap(path, dtype=np.uint8, mode="r")
    o = 0
    n_bytes = data.shape[0]
    while o + 28 <= n_bytes:
        magic, nvd, hcn, T = struct.unpack_from("<iiii", data, o); o += 16
        if magic != MAGIC:
            raise ValueError(f"dump corrotto a {o - 16}")
        (p,) = struct.unpack_from("<q", data, o); o += 8
        a, n_steps = struct.unpack_from("<ii", data, o); o += 8
        tokens = np.frombuffer(data[o:o + 4 * T], dtype=np.int32).copy(); o += 4 * T
        R = np.frombuffer(data[o:o + 4 * hcn], dtype=np.float32).copy(); o += 4 * hcn
        steps = []
        for _ in range(n_steps):
            draft, prob = struct.unpack_from("<if", data, o); o += 8
            logits = np.frombuffer(data[o:o + 4 * nvd], dtype=np.float32).copy(); o += 4 * nvd
            steps.append((draft, prob, logits))
        yield {"nvd": nvd, "hcn": hcn, "T": T, "p": p, "a": a, "tokens": tokens, "R": R, "steps": steps}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", required=True)
    ap.add_argument("--seqs", required=True)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--bf16", required=True)
    ap.add_argument("--rt", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--strata", required=True)
    ap.add_argument("--cache", default=None)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--dtype", choices=["auto", "bf16", "fp16", "f32"], default="auto")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--out", default="", help="json del risultato")
    a = ap.parse_args()
    device = torch.device(a.device)
    dtype = {"auto": None, "bf16": torch.bfloat16, "fp16": torch.float16, "f32": torch.float32}[a.dtype]
    cache = Path(a.cache) if a.cache else Path(a.capture).parent / "cache"
    model, dvocab = M.build_model(Path(a.bf16), Path(a.rt), Path(a.gguf), Path(a.strata) / "tools", cache, device, dtype=dtype)
    model.eval()
    seqs = Path(a.seqs)
    capture = Path(a.capture)
    cmap = json.loads((capture / "capture_map.json").read_text())
    ids_all = np.fromfile(seqs / "seqs_ids.i32", dtype=np.int32)
    index = {e["i"]: e for e in json.loads((seqs / "seqs_index.json").read_text())}
    # i record del dump sono nell'ordine delle richieste del run: la k-esima richiesta e' seq_k del run della cattura
    runs = sorted({m["run"] for m in cmap.values()})
    if len(runs) != 1:
        print(f"attenzione: {len(runs)} run nella cattura; uso l'ultimo ({runs[-1]})")
    run = runs[-1]
    by_k = {m["k"]: (int(i), m) for i, m in cmap.items() if m["run"] == run}
    stats = [dict(n=0, match=0, kl=0.0, dp=0.0, kl_max=0.0) for _ in range(a.steps)]
    k_req = -1
    last_p = None
    for rec in read_dump(Path(a.dump)):
        if rec["T"] == 1 and rec["a"] == 0 and (last_p is None or rec["p"] <= last_p):
            k_req += 1                      # un nuovo prompt: il primo draft parte da p = n - 1 dopo una lettura da zero
        last_p = rec["p"] + rec["a"]
        if k_req not in by_k:
            continue
        i, m = by_k[k_req]
        n = int(m["n"])
        if rec["p"] + rec["a"] != n - 1 or not m.get("ok"):
            continue                        # un draft successivo (celle generate prima, senza R catturata)
        e = index[i]
        ids = ids_all[e["off"]: e["off"] + n].astype(np.int64)
        base = capture / run / f"seq_{m['k']}"
        Rcap = np.fromfile(str(base) + ".r.bf16", dtype=np.uint16).reshape(n - 1, M.HCN)
        R = torch.cat([torch.from_numpy(Rcap.view(np.int16)).view(torch.bfloat16).float(),
                       torch.from_numpy(rec["R"]).unsqueeze(0)], dim=0).to(device)         # [n, HCN]
        chain_tokens = [int(rec["tokens"][rec["a"]])] + [int(d) for d, _, _ in rec["steps"][:-1]]
        ids_in = torch.from_numpy(np.concatenate([ids, np.array(chain_tokens, dtype=np.int64), np.zeros(a.steps + 1, dtype=np.int64)])).to(device)
        n_steps = min(len(rec["steps"]), a.steps)
        active = torch.tensor([n - 1], device=device)
        with torch.no_grad():
            _, samples = model.chain(R, ids_in, n_steps, active)
            for j in range(n_steps):
                lt = model.head(samples[j])[0]                                  # [Vd] torch
                le = torch.from_numpy(rec["steps"][j][2]).to(device)            # [Vd] motore
                if le.numel() != lt.numel():
                    raise SystemExit(f"vocabolari diversi: motore {le.numel()}, torch {lt.numel()} (stesso rt?)")
                pe, pt = torch.softmax(le, -1), torch.softmax(lt, -1)
                kl = float((pe * (torch.log(pe.clamp_min(1e-30)) - torch.log(pt.clamp_min(1e-30)))).sum())
                s = stats[j]
                s["n"] += 1
                s["match"] += int(int(pe.argmax()) == int(pt.argmax()))
                s["kl"] += kl
                s["kl_max"] = max(s["kl_max"], kl)
                s["dp"] += abs(float(pe.max()) - float(pt.max()))
                if s["n"] <= 3 or int(pe.argmax()) != int(pt.argmax()):
                    print(f"  seq {i} passo {j}: motore {int(dvocab[pe.argmax()])} p={float(pe.max()):.3f} (dump {rec['steps'][j][0]} {rec['steps'][j][1]:.3f}) "
                          f"torch {int(dvocab[pt.argmax()])} p={float(pt.max()):.3f} KL {kl:.4f}")
    res = {}
    ok = True
    for j, s in enumerate(stats):
        if s["n"] == 0:
            continue
        r = {"n": s["n"], "argmax_agree": s["match"] / s["n"], "kl_mean": s["kl"] / s["n"], "kl_max": s["kl_max"], "dpmax_mean": s["dp"] / s["n"]}
        res[f"step_{j}"] = r
        print(f"passo {j}: n {s['n']}, argmax uguale {r['argmax_agree']:.4f}, KL media {r['kl_mean']:.5f} (max {r['kl_max']:.4f}), |dp_max| {r['dpmax_mean']:.4f}")
        ok &= r["argmax_agree"] >= 0.99 and r["kl_mean"] < 0.01
    print("PARITA' OK" if ok and res else "PARITA' NON RAGGIUNTA" if res else "nessun record confrontabile")
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1))
    return 0 if ok and res else 1


if __name__ == "__main__":
    sys.exit(main())
