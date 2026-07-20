#!/usr/bin/env python3
"""Streaming activation-aware probe for binary/ternary g128 expert candidates.

This is a CPU-only scaffold. It supports small deterministic probes and delta
checkpoints; it is not a full DS4 expert trainer until real activation traces
and an explicit run budget are supplied.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from activation_reader import ManifestTraceReader, TraceBatch


GROUP = 128


@dataclass
class ExpertWeights:
    gate: np.ndarray
    up: np.ndarray
    down: np.ndarray


@dataclass
class Metrics:
    output_nmse: float
    output_cosine: float
    weighted_nmse: float
    weighted_cosine: float
    samples: int


def silu(x: np.ndarray) -> np.ndarray:
    return x / (1.0 + np.exp(-x))


def expert_forward(w: ExpertWeights, x: np.ndarray) -> np.ndarray:
    gate = x @ w.gate.T
    up = x @ w.up.T
    hidden = silu(gate) * up
    return hidden @ w.down.T


def cosine_and_nmse(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    af = a.astype(np.float64, copy=False).reshape(-1)
    bf = b.astype(np.float64, copy=False).reshape(-1)
    dot = float(np.dot(af, bf))
    a2 = float(np.dot(af, af))
    b2 = float(np.dot(bf, bf))
    err = af - bf
    return dot / math.sqrt(max(a2 * b2, 1e-30)), float(np.dot(err, err) / max(a2, 1e-30))


def _check_matrix(name: str, w: np.ndarray) -> None:
    if w.ndim != 2 or w.shape[1] % GROUP != 0:
        raise RuntimeError(f"{name} must be 2D with input dimension multiple of {GROUP}: {w.shape}")
    if w.dtype != np.float32:
        raise RuntimeError(f"{name} must be float32")


def binary_g128(w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    _check_matrix("binary weight", w)
    blocks = w.reshape(w.shape[0], w.shape[1] // GROUP, GROUP)
    signs = np.where(blocks >= 0.0, 1.0, -1.0).astype(np.float32)
    scales = np.mean(np.abs(blocks), axis=2).astype(np.float32)
    q = (signs * scales[:, :, None]).reshape(w.shape).astype(np.float32)
    return q, scales


def ternary_g128(w: np.ndarray, k_nonzero: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    _check_matrix("ternary weight", w)
    if not (0 <= k_nonzero <= GROUP):
        raise RuntimeError("k_nonzero outside [0,128]")
    blocks = w.reshape(w.shape[0], w.shape[1] // GROUP, GROUP)
    masks = np.zeros_like(blocks, dtype=bool)
    if k_nonzero:
        idx = np.argpartition(np.abs(blocks), GROUP - k_nonzero, axis=2)[:, :, GROUP - k_nonzero:]
        np.put_along_axis(masks, idx, True, axis=2)
    denom = np.maximum(masks.sum(axis=2), 1).astype(np.float32)
    scales = (np.abs(blocks) * masks).sum(axis=2).astype(np.float32) / denom
    q = (np.sign(blocks) * masks * scales[:, :, None]).reshape(w.shape).astype(np.float32)
    return q, scales, masks


def quantize_expert_binary(w: ExpertWeights) -> tuple[ExpertWeights, dict]:
    gate, sg = binary_g128(w.gate)
    up, su = binary_g128(w.up)
    down, sd = binary_g128(w.down)
    return ExpertWeights(gate, up, down), {"gate_scale": sg, "up_scale": su, "down_scale": sd}


def quantize_expert_ternary(w: ExpertWeights, k_nonzero: int) -> tuple[ExpertWeights, dict]:
    gate, sg, mg = ternary_g128(w.gate, k_nonzero)
    up, su, mu = ternary_g128(w.up, k_nonzero)
    down, sd, md = ternary_g128(w.down, k_nonzero)
    return ExpertWeights(gate, up, down), {
        "gate_scale": sg,
        "up_scale": su,
        "down_scale": sd,
        "gate_mask": mg,
        "up_mask": mu,
        "down_mask": md,
    }


def evaluate_stream(teacher: ExpertWeights, candidate: ExpertWeights, batches: Iterable[TraceBatch]) -> Metrics:
    y_true_parts = []
    y_pred_parts = []
    yw_true_parts = []
    yw_pred_parts = []
    samples = 0
    for batch in batches:
        yt = expert_forward(teacher, batch.x)
        yp = expert_forward(candidate, batch.x)
        g = batch.route_gate.astype(np.float32)[:, None]
        y_true_parts.append(yt)
        y_pred_parts.append(yp)
        yw_true_parts.append(yt * g)
        yw_pred_parts.append(yp * g)
        samples += batch.x.shape[0]
    y_true = np.concatenate(y_true_parts, axis=0)
    y_pred = np.concatenate(y_pred_parts, axis=0)
    yw_true = np.concatenate(yw_true_parts, axis=0)
    yw_pred = np.concatenate(yw_pred_parts, axis=0)
    oc, on = cosine_and_nmse(y_true, y_pred)
    wc, wn = cosine_and_nmse(yw_true, yw_pred)
    return Metrics(on, oc, wn, wc, samples)


def tune_global_scale(
    teacher: ExpertWeights,
    candidate: ExpertWeights,
    trace_batches: list[TraceBatch],
    *,
    tensor_name: str,
    multipliers: tuple[float, ...] = (0.75, 0.875, 1.0, 1.125, 1.25),
) -> tuple[ExpertWeights, dict]:
    """Deterministic coordinate update over one tensor's global scale."""
    best_w = candidate
    best_m = evaluate_stream(teacher, candidate, trace_batches)
    tried = [{"multiplier": 1.0, "weighted_nmse": best_m.weighted_nmse}]
    for mul in multipliers:
        if mul == 1.0:
            continue
        trial = ExpertWeights(candidate.gate.copy(), candidate.up.copy(), candidate.down.copy())
        setattr(trial, tensor_name, getattr(trial, tensor_name) * np.float32(mul))
        m = evaluate_stream(teacher, trial, trace_batches)
        tried.append({"multiplier": mul, "weighted_nmse": m.weighted_nmse})
        if m.weighted_nmse < best_m.weighted_nmse:
            best_w, best_m = trial, m
    return best_w, {"tensor": tensor_name, "selected_weighted_nmse": best_m.weighted_nmse, "tried": tried}


def greedy_sign_flip_probe(
    teacher: ExpertWeights,
    candidate: ExpertWeights,
    trace_batches: list[TraceBatch],
    *,
    tensor_name: str,
    max_flips: int = 0,
    max_candidates: int = 32,
) -> tuple[ExpertWeights, dict]:
    """Bounded deterministic sign-flip coordinate probe.

    This is intentionally tiny and CPU-safe. It scans the first nonzero weights
    in row-major order and keeps only flips that improve gate-weighted NMSE.
    """
    if max_flips <= 0:
        return candidate, {"tensor": tensor_name, "applied": [], "evaluated": 0}
    current = ExpertWeights(candidate.gate.copy(), candidate.up.copy(), candidate.down.copy())
    best_m = evaluate_stream(teacher, current, trace_batches)
    w = getattr(current, tensor_name)
    coords = np.argwhere(w != 0.0)[:max_candidates]
    applied = []
    evaluated = 0
    for row, col in coords:
        if len(applied) >= max_flips:
            break
        trial = ExpertWeights(current.gate.copy(), current.up.copy(), current.down.copy())
        tw = getattr(trial, tensor_name)
        tw[row, col] = -tw[row, col]
        m = evaluate_stream(teacher, trial, trace_batches)
        evaluated += 1
        if m.weighted_nmse < best_m.weighted_nmse:
            current, best_m = trial, m
            applied.append({"row": int(row), "col": int(col), "weighted_nmse": best_m.weighted_nmse})
    return current, {"tensor": tensor_name, "applied": applied, "evaluated": evaluated}


def write_delta_checkpoint(path: str | Path, *, kind: str, metadata: dict, deltas: dict) -> None:
    path = Path(path)
    payload = {
        "schema": "ds4_activation_aware_delta_checkpoint_v1",
        "kind": kind,
        "metadata": metadata,
        "deltas": {k: np.asarray(v).tolist() for k, v in deltas.items()},
        "note": "small delta checkpoint only; no model tensor copy",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_teacher_npz(path: str | Path) -> ExpertWeights:
    data = np.load(path, allow_pickle=False)
    w = ExpertWeights(data["gate"].astype(np.float32), data["up"].astype(np.float32), data["down"].astype(np.float32))
    _check_matrix("gate", w.gate)
    _check_matrix("up", w.up)
    _check_matrix("down", w.down)
    return w


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--teacher-npz", required=True)
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--expert", type=int, required=True)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--mode", choices=["binary", "ternary"], default="binary")
    ap.add_argument("--ternary-k", type=int, default=48)
    ap.add_argument("--max-sign-flips", type=int, default=0)
    ap.add_argument("--checkpoint")
    args = ap.parse_args()

    reader = ManifestTraceReader(args.manifest, expected_layer=args.layer, expected_expert=args.expert)
    teacher = load_teacher_npz(args.teacher_npz)
    batches = list(reader.batches(args.batch_size))
    if args.mode == "binary":
        candidate, state = quantize_expert_binary(teacher)
    else:
        candidate, state = quantize_expert_ternary(teacher, args.ternary_k)
    tuned = []
    for tensor in ("gate", "up", "down"):
        candidate, info = tune_global_scale(teacher, candidate, batches, tensor_name=tensor)
        tuned.append(info)
    sign_flips = []
    if args.max_sign_flips:
        for tensor in ("gate", "up", "down"):
            candidate, info = greedy_sign_flip_probe(
                teacher,
                candidate,
                batches,
                tensor_name=tensor,
                max_flips=args.max_sign_flips,
            )
            sign_flips.append(info)
    metrics = evaluate_stream(teacher, candidate, batches)
    result = {
        "schema": "ds4_activation_aware_probe_result_v1",
        "mode": args.mode,
        "samples": metrics.samples,
        "output_cosine": metrics.output_cosine,
        "output_nmse": metrics.output_nmse,
        "weighted_cosine": metrics.weighted_cosine,
        "weighted_nmse": metrics.weighted_nmse,
        "updates": tuned,
        "sign_flips": sign_flips,
        "quality_scope": "trace-local probe only; no end-to-end claim",
    }
    if args.checkpoint:
        small = {k: v for k, v in state.items() if "scale" in k}
        write_delta_checkpoint(args.checkpoint, kind=args.mode, metadata=result, deltas=small)
        result["checkpoint"] = args.checkpoint
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
