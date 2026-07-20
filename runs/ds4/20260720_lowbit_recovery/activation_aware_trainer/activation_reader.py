#!/usr/bin/env python3
"""Fail-closed activation trace reader for one DS4 expert.

The adapter is intentionally narrow: it validates a manifest plus small binary
arrays and yields batches without knowing anything about GGUF files. The final
G129 trace manifest can map into this schema by producing the same arrays.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np


SCHEMA = "ds4_activation_trace_manifest_v1"


@dataclass(frozen=True)
class TraceBatch:
    x: np.ndarray
    route_gate: np.ndarray
    token: np.ndarray
    call: np.ndarray
    request_epoch: np.ndarray


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_npy_checked(base: Path, spec: dict, max_bytes: int) -> np.ndarray:
    rel = spec["path"]
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise RuntimeError(f"unsafe trace path: {rel}")
    path = base / rel
    if not path.exists():
        raise RuntimeError(f"missing trace file: {path}")
    actual_size = path.stat().st_size
    if actual_size > max_bytes:
        raise RuntimeError(f"budget exceeded for {rel}: {actual_size} > {max_bytes}")
    expected_sha = spec["sha256"]
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha:
        raise RuntimeError(f"sha mismatch for {rel}: {actual_sha} != {expected_sha}")
    arr = np.load(path, allow_pickle=False)
    expected_shape = tuple(spec["shape"])
    if arr.shape != expected_shape:
        raise RuntimeError(f"shape mismatch for {rel}: {arr.shape} != {expected_shape}")
    expected_dtype = np.dtype(spec["dtype"])
    if arr.dtype != expected_dtype:
        raise RuntimeError(f"dtype mismatch for {rel}: {arr.dtype} != {expected_dtype}")
    return arr


class ManifestTraceReader:
    """Canonical trace reader for input-vector plus routing metadata."""

    def __init__(self, manifest_path: str | Path, *, expected_layer: int, expected_expert: int):
        self.manifest_path = Path(manifest_path)
        self.base = self.manifest_path.parent
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self._validate_header(expected_layer, expected_expert)
        budget = int(self.manifest["budget"]["max_file_bytes"])
        files = self.manifest["files"]
        self.x = load_npy_checked(self.base, files["input_vectors"], budget)
        self.route_gate = load_npy_checked(self.base, files["route_gate"], budget)
        self.top_k = load_npy_checked(self.base, files["top_k"], budget)
        self.token = load_npy_checked(self.base, files["token"], budget)
        self.call = load_npy_checked(self.base, files["call"], budget)
        self.epoch = load_npy_checked(self.base, files["request_epoch"], budget)
        self._validate_arrays()

    def _validate_header(self, expected_layer: int, expected_expert: int) -> None:
        m = self.manifest
        if m.get("schema") != SCHEMA:
            raise RuntimeError(f"bad schema: {m.get('schema')}")
        if int(m["layer"]) != expected_layer:
            raise RuntimeError(f"layer mismatch: {m['layer']} != {expected_layer}")
        if int(m["expert"]) != expected_expert:
            raise RuntimeError(f"expert mismatch: {m['expert']} != {expected_expert}")
        if int(m["request_epoch"]) != int(m["expected_request_epoch"]):
            raise RuntimeError("request_epoch mismatch in manifest header")
        if int(m["dimensions"]["input"]) <= 0:
            raise RuntimeError("invalid input dimension")
        if int(m["dimensions"]["top_k"]) <= 0:
            raise RuntimeError("invalid top_k dimension")

    def _validate_arrays(self) -> None:
        n, d = self.x.shape
        if d != int(self.manifest["dimensions"]["input"]):
            raise RuntimeError(f"input dimension mismatch: {d}")
        one_d = {
            "route_gate": self.route_gate,
            "token": self.token,
            "call": self.call,
            "request_epoch": self.epoch,
        }
        for name, arr in one_d.items():
            if arr.shape != (n,):
                raise RuntimeError(f"{name} length mismatch: {arr.shape} != {(n,)}")
        if self.top_k.shape != (n, int(self.manifest["dimensions"]["top_k"])):
            raise RuntimeError("top_k shape mismatch")
        if not np.all(self.epoch == int(self.manifest["request_epoch"])):
            raise RuntimeError("request_epoch mismatch in rows")
        if not np.all(np.any(self.top_k == int(self.manifest["expert"]), axis=1)):
            raise RuntimeError("expert missing from at least one top_k row")
        if not np.all(np.isfinite(self.x)) or not np.all(np.isfinite(self.route_gate)):
            raise RuntimeError("non-finite trace values")

    def batches(self, batch_size: int) -> Iterator[TraceBatch]:
        if batch_size <= 0:
            raise RuntimeError("batch_size must be positive")
        n = self.x.shape[0]
        for start in range(0, n, batch_size):
            stop = min(start + batch_size, n)
            yield TraceBatch(
                x=self.x[start:stop],
                route_gate=self.route_gate[start:stop],
                token=self.token[start:stop],
                call=self.call[start:stop],
                request_epoch=self.epoch[start:stop],
            )
