#!/usr/bin/env python3
"""CPU-only binary/Q1 extension for the DS4 ternary-B single expert probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

import ds4_ternary_b_probe as probe


def vector_metrics(x: np.ndarray, q: np.ndarray) -> dict:
    xf = x.astype(np.float64, copy=False)
    qf = q.astype(np.float64, copy=False)
    dot = float(np.dot(xf, qf))
    x2 = float(np.dot(xf, xf))
    q2 = float(np.dot(qf, qf))
    err = xf - qf
    return {
        "cosine": dot / math.sqrt(max(x2 * q2, 1e-30)),
        "nmse": float(np.dot(err, err) / max(x2, 1e-30)),
        "max_abs_error": float(np.max(np.abs(err))),
    }


def binary_refit_g128(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    groups = x.reshape(-1, 128)
    signs = np.where(groups >= 0, 1.0, -1.0).astype(np.float32)
    scales = np.mean(np.abs(groups), axis=1).astype(np.float32)
    q = (signs * scales[:, None]).reshape(-1)
    return q, signs.reshape(-1), scales


def q1_signs_scales(payload: bytes) -> tuple[np.ndarray, np.ndarray]:
    if len(payload) % 18:
        raise RuntimeError("Q1 payload is not block-aligned")
    n = len(payload) // 18
    signs = np.empty(n * 128, dtype=np.float32)
    scales = np.empty(n, dtype=np.float32)
    for b in range(n):
        block = payload[b * 18:(b + 1) * 18]
        scales[b] = float(probe.f16(int.from_bytes(block[0:2], "little")))
        bits = np.unpackbits(np.frombuffer(block[2:18], dtype=np.uint8), bitorder="little").astype(np.float32)
        signs[b * 128:(b + 1) * 128] = 2.0 * bits - 1.0
    return signs, scales


def read_dequant_teacher(model: Path, ds4_c: Path, layer: int, expert: int):
    grid = probe.parse_c_array_u64(ds4_c, "iq2xxs_grid")
    signs_table = probe.parse_c_array_u8(ds4_c, "ksigns_iq2xs", 128)
    probe.self_test_decoders(grid, signs_table)
    tensors, data_base, alignment = probe.parse_gguf(model)
    names = {
        "gate": f"blk.{layer}.ffn_gate_exps.weight",
        "up": f"blk.{layer}.ffn_up_exps.weight",
        "down": f"blk.{layer}.ffn_down_exps.weight",
    }
    out = {}
    with model.open("rb") as f:
        for role, name in names.items():
            t = tensors[name]
            payload, off, row_bytes, expert_bytes = probe.expert_payload(f, t, expert)
            if t.type_id == probe.TYPE_IQ2_XXS:
                x = probe.dequant_iq2_xxs(payload, grid, signs_table)
            elif t.type_id == probe.TYPE_Q2_K:
                x = probe.dequant_q2_k(payload)
            else:
                raise RuntimeError(f"unexpected teacher type {t.type_id}")
            out[role] = {"tensor": t, "payload": payload, "offset": off, "row_bytes": row_bytes, "expert_bytes": expert_bytes, "x": x}
    return out, {"data_base": data_base, "alignment": alignment}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", default=r"C:\ds4-models\ds4-2bit.gguf")
    ap.add_argument("--q1", default=r"C:\ds4-models\ds4-q1-layers0-42-derived.gguf")
    ap.add_argument("--ds4-c", default=r"C:\Users\imanu\Documents\Codex\2026-07-07\cia\work\ds4-win-publish-g126-20260718-v2\ds4.c")
    ap.add_argument("--ternary-receipt", default=r"work\ternary_b_microprobe\ternary_b_probe_receipt.json")
    ap.add_argument("--layer", type=int, default=3)
    ap.add_argument("--expert", type=int, default=0)
    ap.add_argument("--out", default=r"work\ternary_b_microprobe\binary_extension_receipt.json")
    args = ap.parse_args()

    started = time.time()
    teacher_path = Path(args.teacher)
    q1_path = Path(args.q1)
    ds4_c = Path(args.ds4_c)
    ternary = json.loads(Path(args.ternary_receipt).read_text(encoding="utf-8"))
    if ternary["selection"]["layer"] != args.layer or ternary["selection"]["expert"] != args.expert:
        raise RuntimeError("ternary receipt selection does not match binary extension selection")

    teacher, teacher_meta = read_dequant_teacher(teacher_path, ds4_c, args.layer, args.expert)
    q1_tensors, q1_data_base, q1_alignment = probe.parse_gguf(q1_path)
    wanted = {
        "gate": f"blk.{args.layer}.ffn_gate_exps.weight",
        "up": f"blk.{args.layer}.ffn_up_exps.weight",
        "down": f"blk.{args.layer}.ffn_down_exps.weight",
    }
    receipt = {
        "schema": "ds4_binary_extension_single_expert_v1",
        "mode": "CPU-only read-only; no activation traces; no end-to-end claims",
        "selection": ternary["selection"],
        "teacher": {"path": str(teacher_path), "bytes": teacher_path.stat().st_size},
        "q1_sidecar": {
            "path": str(q1_path),
            "bytes": q1_path.stat().st_size,
            "expected_expert_bytes": 3538944,
            "expected_bpw": 1.125,
            "data_base": q1_data_base,
            "alignment": q1_alignment,
        },
        "decoder_self_test": probe.self_test_decoders(
            probe.parse_c_array_u64(ds4_c, "iq2xxs_grid"),
            probe.parse_c_array_u8(ds4_c, "ksigns_iq2xs", 128),
        ),
        "tensors": {},
        "ternary_reference": {
            "expert_curves": ternary["phase1"]["expert"]["curves"],
            "note": "copied from ternary probe receipt for same expert",
        },
    }

    expert_teacher = []
    expert_q1 = []
    expert_refit = []
    with q1_path.open("rb") as f:
        for role, name in wanted.items():
            if name not in q1_tensors:
                raise RuntimeError(f"Q1 sidecar missing tensor {name}")
            tq1 = q1_tensors[name]
            if tq1.type_id != probe.TYPE_Q1_0:
                raise RuntimeError(f"Q1 sidecar tensor {name} has type {tq1.type_id}, expected 41")
            payload, off, row_bytes, expert_bytes = probe.expert_payload(f, tq1, args.expert)
            if role in ("gate", "up") and expert_bytes != 1179648:
                raise RuntimeError(f"unexpected Q1 {role} bytes {expert_bytes}")
            if role == "down" and expert_bytes != 1179648:
                raise RuntimeError(f"unexpected Q1 down bytes {expert_bytes}")
            x = teacher[role]["x"]
            q1 = probe.dequant_q1_0(payload)
            refit, refit_signs, refit_scales = binary_refit_g128(x)
            existing_signs, existing_scales = q1_signs_scales(payload)
            scale_delta = existing_scales.astype(np.float64) - refit_scales.astype(np.float64)
            sign_mismatch = float(np.mean(existing_signs != refit_signs))
            rec = {
                "name": name,
                "q1_dtype": "Q1_0",
                "q1_type_id": tq1.type_id,
                "shape": list(tq1.dims),
                "q1_tensor_physical_offset": tq1.physical_offset,
                "q1_expert_physical_offset": off,
                "q1_row_bytes": row_bytes,
                "q1_expert_bytes": expert_bytes,
                "q1_payload_sha256": hashlib.sha256(payload).hexdigest(),
                "teacher_payload_sha256": hashlib.sha256(teacher[role]["payload"]).hexdigest(),
                "existing_q1_vs_teacher": vector_metrics(x, q1),
                "refit_binary_vs_teacher": vector_metrics(x, refit),
                "existing_vs_refit_binary": vector_metrics(refit, q1),
                "scale_sign_delta": {
                    "scale_mean_abs_delta": float(np.mean(np.abs(scale_delta))),
                    "scale_max_abs_delta": float(np.max(np.abs(scale_delta))),
                    "scale_rmse_delta": float(math.sqrt(np.mean(scale_delta * scale_delta))),
                    "sign_mismatch_rate": sign_mismatch,
                },
            }
            receipt["tensors"][role] = rec
            expert_teacher.append(x)
            expert_q1.append(q1)
            expert_refit.append(refit)

    xt = np.concatenate(expert_teacher)
    xq1 = np.concatenate(expert_q1)
    xrefit = np.concatenate(expert_refit)
    receipt["expert"] = {
        "q1_total_expert_bytes": sum(v["q1_expert_bytes"] for v in receipt["tensors"].values()),
        "q1_expected_expert_bytes_match": sum(v["q1_expert_bytes"] for v in receipt["tensors"].values()) == 3538944,
        "existing_q1_vs_teacher": vector_metrics(xt, xq1),
        "refit_binary_vs_teacher": vector_metrics(xt, xrefit),
        "existing_vs_refit_binary": vector_metrics(xrefit, xq1),
    }
    receipt["interpretation"] = (
        "If refit_binary_vs_teacher is close to existing_q1_vs_teacher, the present Q1 issue is not primarily "
        "the Q1_0 byte format; it is the lack of training/recovery or activation-aware refit. "
        "If refit is materially better, the conversion recipe/scale-sign fit is suspect before format."
    )
    receipt["elapsed_seconds"] = time.time() - started
    Path(args.out).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "receipt": args.out, "elapsed_seconds": receipt["elapsed_seconds"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
