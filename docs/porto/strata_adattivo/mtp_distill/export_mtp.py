"""export_mtp.py - dai pesi affinati al pacco MTP del motore (stesso layout di rt_it48k: dense.bin, dense.txt,
experts.bin, draft_vocab.bin).

    python export_mtp.py --bf16 D:\\ds4_work\\strata\\Strata-data\\mtp --rt D:\\ds4_work\\strata\\Strata-data\\mtp\\rt_it48k \\
        --weights D:\\ds4_work\\mtp_distill\\runs\\ft1\\trainable.safetensors --out D:\\ds4_work\\strata\\Strata-data\\mtp\\rt_it48k_ft1

Riproduce esattamente tools/mtp_pack.py + tools/mtp_rt.py per i tensori densi: proiezioni grandi in Q8_0 (arrotondamento di
riferimento ggml), hyper-connection e router in BF16, norme in F32 con il "+1" di Gemma, un tensore ogni 256 byte,
ordine alfabetico del nome completo `mtp.*` (l'ordine del GGUF intermedio).  Gli esperti instradati sono congelati:
experts.bin e draft_vocab.bin sono copiati dal pacco sorgente.  Senza --weights esporta il blocco BF16 originale: il
risultato deve essere IDENTICO byte per byte a rt_it48k (e' la verifica del percorso: --check-against).

I pesi affinati arrivano in f32 (nome corto -> tensore): sono prima arrotondati a BF16 (il formato del checkpoint),
poi trattati come gli originali.  Il report confronta per ogni tensore l'errore relativo RMS fra pesi affinati e
originali (quanto si e' mosso il training) e, per i Q8_0, l'errore di quantizzazione.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mtp_model import short_name, bf16_bits_to_f32  # noqa: E402

Q8 = {"fc_embedding.weight", "fc_hidden.weight", "self_attn.q_proj.weight", "self_attn.k_proj.weight",
      "self_attn.v_proj.weight", "self_attn.o_proj.weight", "self_attn.indexer.index_qk_proj.weight",
      "mlp.shared_expert.gate_proj.weight", "mlp.shared_expert.up_proj.weight", "mlp.shared_expert.down_proj.weight"}


def f32_to_bf16_bits(x: np.ndarray) -> np.ndarray:
    """Arrotondamento al pari (come torch .to(bfloat16))."""
    u = np.ascontiguousarray(x, dtype=np.float32).view(np.uint32)
    return ((u + 0x7FFF + ((u >> 16) & 1)) >> 16).astype(np.uint16)


def q8_0(x: np.ndarray) -> bytes:
    """Copia di tools/mtp_rt.py::q8_0 (ggml quantize_row_q8_0_ref)."""
    b = x.reshape(-1, 32).astype(np.float32)
    amax = np.abs(b).max(axis=1)
    d = amax / 127.0
    inv = np.where(d > 0, 1.0 / np.where(d > 0, d, 1.0), 0.0).astype(np.float32)
    v = b * inv[:, None]
    q = (np.sign(v) * np.floor(np.abs(v) + 0.5)).astype(np.int8)
    out = np.empty((b.shape[0], 34), dtype=np.uint8)
    out[:, :2] = d.astype(np.float16).view(np.uint8).reshape(-1, 2)
    out[:, 2:] = q.view(np.uint8)
    return out.tobytes()


def dequant_q8_0(raw: bytes, n: int) -> np.ndarray:
    b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 34)
    d = b[:, :2].copy().view(np.float16).astype(np.float32)
    return (b[:, 2:].view(np.int8).astype(np.float32) * d).reshape(-1)[:n]


def load_weights(path: Path) -> dict[str, np.ndarray]:
    if path.suffix == ".safetensors":
        from safetensors.numpy import load_file
        return {k: np.asarray(v, dtype=np.float32) for k, v in load_file(str(path)).items()}
    import torch
    sd = torch.load(path, map_location="cpu")
    return {k.replace("__", "."): v.float().numpy() for k, v in sd.items()}


def export(bf16_dir: Path, rt_dir: Path, out: Path, weights: dict[str, np.ndarray] | None) -> dict:
    manifest = json.loads((bf16_dir / "mtp-manifest.json").read_text())
    out.mkdir(parents=True, exist_ok=True)
    lines, report = [], []
    off = 0
    with open(out / "dense.bin", "wb") as f:
        for t in sorted(manifest, key=lambda t: t["name"]):
            if "mlp.experts." in t["name"]:
                continue
            short = short_name(t["name"])
            shape = t["shape"]
            orig_bits = np.fromfile(bf16_dir / t["file"].replace("\\", "/"), dtype="<u2").reshape(shape)
            moved = 0.0
            if weights is not None and short in weights:
                w = weights[short].reshape(shape)
                bits = f32_to_bf16_bits(w)
                o32, n32 = bf16_bits_to_f32(orig_bits), bf16_bits_to_f32(bits)
                moved = float(np.sqrt(((n32 - o32) ** 2).mean()) / (np.sqrt((o32 ** 2).mean()) + 1e-12))
            else:
                bits = orig_bits
            entry = {"tensor": short, "moved_rel_rms": round(moved, 6)}
            if len(shape) == 1:    # norma: F32 con il +1 (vLLM GemmaRMSNorm)
                arr = bf16_bits_to_f32(bits).astype(np.float32) + 1.0
                raw, kind, rows, cols = arr.tobytes(), "f32", 1, arr.size
            else:
                u16 = bits.reshape(shape[0], -1)
                rows, cols = u16.shape
                if short in Q8:
                    f32 = bf16_bits_to_f32(u16)
                    raw, kind = q8_0(f32), "q8_0"
                    back = dequant_q8_0(raw, f32.size)
                    entry["q8_rel_rms_err"] = round(float(np.sqrt(((back - f32.reshape(-1)) ** 2).mean()) /
                                                          (np.sqrt((f32 ** 2).mean()) + 1e-12)), 6)
                else:
                    raw, kind = u16.astype("<u2").tobytes(), "bf16"
            pad = (-off) % 256
            f.write(b"\0" * pad)
            off += pad
            f.write(raw)
            lines.append(f"{short} {kind} {rows} {cols} {off} {len(raw)}")
            off += len(raw)
            entry.update(kind=kind, bytes=len(raw))
            report.append(entry)
    (out / "dense.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for name in ("experts.bin", "draft_vocab.bin"):
        shutil.copyfile(rt_dir / name, out / name)
    return {"dense_bytes": off, "tensors": report}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bf16", required=True, help="cartella con mtp-manifest.json e tensors/")
    ap.add_argument("--rt", required=True, help="il pacco sorgente (experts.bin e draft_vocab.bin copiati da qui)")
    ap.add_argument("--weights", help="trainable.safetensors (o .pt) di train_mtp.py; assente = blocco originale")
    ap.add_argument("--out", required=True)
    ap.add_argument("--check-against", help="confronta dense.bin/dense.txt byte per byte con questa cartella")
    a = ap.parse_args()
    weights = load_weights(Path(a.weights)) if a.weights else None
    rep = export(Path(a.bf16), Path(a.rt), Path(a.out), weights)
    rep["weights"] = a.weights
    if a.check_against:
        ref = Path(a.check_against)
        same_bin = sha(ref / "dense.bin") == sha(Path(a.out) / "dense.bin")
        same_txt = (ref / "dense.txt").read_bytes() == (Path(a.out) / "dense.txt").read_bytes()
        same_exp = sha(ref / "experts.bin") == sha(Path(a.out) / "experts.bin")
        rep["check"] = {"dense_bin_identical": same_bin, "dense_txt_identical": same_txt, "experts_identical": same_exp}
        print(f"verifica contro {ref}: dense.bin {'IDENTICO' if same_bin else 'DIVERSO'}, dense.txt "
              f"{'IDENTICO' if same_txt else 'DIVERSO'}, experts.bin {'IDENTICO' if same_exp else 'DIVERSO'}")
    (Path(a.out) / "export_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    moved = [t for t in rep["tensors"] if t["moved_rel_rms"] > 0]
    print(f"dense.bin {rep['dense_bytes']} B, {len(rep['tensors'])} tensori, {len(moved)} modificati dal training")
    for t in moved:
        print(f"  {t['tensor']}: spostamento rel. RMS {t['moved_rel_rms']:.4f}" + (f", err. Q8_0 {t['q8_rel_rms_err']:.4f}" if "q8_rel_rms_err" in t else ""))
    return 0 if not a.check_against or all(rep["check"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
