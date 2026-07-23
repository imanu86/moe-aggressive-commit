#!/usr/bin/env python3
"""Build a ds4 Q1_0 routed-expert GGUF sidecar from GPTQ-Q1 NPZ files.

The ds4 runtime layout was verified against ds4.c/ds4_cuda.cu:
    block_q1_0 = little-endian fp16 scale, then 16 little-bit-order sign bytes
and the GGML/GGUF type id is 41.

The current q1_0_sidecar_bind requires complete 3-D expert tensors.  Experts
not listed in --experts are therefore dequantized from the base IQ2_XXS/Q2_K
tensor and requantized to Q1_0.  Runtime identity/control tensors are copied
byte-for-byte from the base model as required by the same binder.
"""

from __future__ import annotations

import argparse
import base64
import math
import mmap
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Sequence

import numpy as np


GGUF_MAGIC = 0x46554747
GGUF_VERSION = 3
DEFAULT_ALIGNMENT = 32
Q1_TYPE_ID = 41
Q1_BLOCK_WEIGHTS = 128
Q1_BLOCK_BYTES = 18

GGUF_VALUE_TYPE_UINT32 = 4
GGUF_VALUE_TYPE_STRING = 8
GGUF_VALUE_TYPE_ARRAY = 9
GGUF_SCALAR_VALUE_BYTES = {
    0: 1,   # UINT8
    1: 1,   # INT8
    2: 2,   # UINT16
    3: 2,   # INT16
    4: 4,   # UINT32
    5: 4,   # INT32
    6: 4,   # FLOAT32
    7: 1,   # BOOL
    10: 8,  # UINT64
    11: 8,  # INT64
    12: 8,  # FLOAT64
}

# Copied from tools/ds4_q1_sidecar_converter.py (RUNTIME_REQUIRED_METADATA_KEYS).
RUNTIME_REQUIRED_METADATA_KEYS = (
    "general.name",
    "deepseek4.block_count",
    "deepseek4.embedding_length",
    "deepseek4.vocab_size",
    "deepseek4.attention.head_count",
    "deepseek4.attention.head_count_kv",
    "deepseek4.attention.key_length",
    "deepseek4.attention.value_length",
    "deepseek4.rope.dimension_count",
    "deepseek4.attention.q_lora_rank",
    "deepseek4.attention.output_lora_rank",
    "deepseek4.attention.output_group_count",
    "deepseek4.expert_count",
    "deepseek4.expert_used_count",
    "deepseek4.expert_feed_forward_length",
    "deepseek4.expert_shared_count",
    "deepseek4.hash_layer_count",
    "deepseek4.expert_group_count",
    "deepseek4.expert_group_used_count",
    "deepseek4.attention.sliding_window",
    "deepseek4.attention.indexer.head_count",
    "deepseek4.attention.indexer.key_length",
    "deepseek4.attention.indexer.top_k",
    "deepseek4.hyper_connection.count",
    "deepseek4.hyper_connection.sinkhorn_iterations",
    "deepseek4.attention.compress_ratios",
    "deepseek4.swiglu_clamp_exp",
    "deepseek4.rope.scaling.original_context_length",
    "deepseek4.rope.freq_base",
    "deepseek4.rope.scaling.factor",
    "deepseek4.rope.scaling.yarn_beta_fast",
    "deepseek4.rope.scaling.yarn_beta_slow",
    "deepseek4.attention.compress_rope_freq_base",
    "deepseek4.expert_weights_scale",
    "deepseek4.attention.layer_norm_rms_epsilon",
    "deepseek4.hyper_connection.epsilon",
    "deepseek4.expert_weights_norm",
)
PARSED_METADATA_KEYS = frozenset((*RUNTIME_REQUIRED_METADATA_KEYS, "general.alignment"))

# GGML block geometry needed by the DS4 base and copied control tensors.
GGUF_TENSOR_BLOCK = {
    0: (1, 4),       # F32
    1: (1, 2),       # F16
    2: (32, 18),     # Q4_0
    3: (32, 20),     # Q4_1
    6: (32, 22),     # Q5_0
    7: (32, 24),     # Q5_1
    8: (32, 34),     # Q8_0
    9: (32, 40),     # Q8_1
    10: (256, 84),   # Q2_K
    11: (256, 110),  # Q3_K
    12: (256, 144),  # Q4_K
    13: (256, 176),  # Q5_K
    14: (256, 210),  # Q6_K
    15: (256, 292),  # Q8_K
    16: (256, 66),   # IQ2_XXS
    17: (256, 74),   # IQ2_XS
    18: (256, 98),   # IQ3_XXS
    19: (256, 50),   # IQ1_S
    20: (32, 18),    # IQ4_NL
    21: (256, 110),  # IQ3_S
    22: (256, 82),   # IQ2_S
    23: (256, 136),  # IQ4_XS
    24: (1, 1),      # I8
    25: (1, 2),      # I16
    26: (1, 4),      # I32
    27: (1, 8),      # I64
    28: (1, 8),      # F64
    29: (256, 56),   # IQ1_M
    30: (1, 2),      # BF16
    41: (128, 18),   # Q1_0 (DS4 extension)
}

PART_SUFFIX = {
    "gate": "ffn_gate_exps.weight",
    "up": "ffn_up_exps.weight",
    "down": "ffn_down_exps.weight",
}

# Tables from tools/ds4_q1_ref_tables.inc, whose provenance is
# ggml-org/llama.cpp commit 635cdd5fcc5bdeb8ec2e108bb2a40acf62d9039b.
_IQ2_SIGNS_B64 = (
    "AIGCA4QFBoeICQqLDI2OD5AREpMUlZYXGJmaG5wdHp+gISKjJKWmJyipqiusLS6v"
    "MLGyM7Q1Nre4OTq7PL2+P8BBQsNExcZHSMnKS8xNTs9Q0dJT1FVW19hZWttc3d5"
    "fYOHiY+RlZufoaWrrbO3ub/BxcvN09fZ3ePn6e/x9fv8="
)
_IQ2_GRID_B64 = (
    "CAgICAgICAgrCAgICAgICBkZCAgICAgICCsICAgICAgrKwgICAgICBkIGQgICAgIC"
    "BkZCAgICAgICCsICAgICCsIKwgICAgICCsrCAgICAgrKysICAgICBkICBkICAgICBk"
    "IGQgICAgICBkZCAgICAgrGRkICAgIGQgrGQgICAgIGSsZCAgICAgICCsICAgIKwgIK"
    "wgICAgrKwgrCAgICCsIKysICAgIGQgICBkICAgIGQgIGQgICAgIGQgZCAgIGRkZCB"
    "kICAgICAgZGQgICAgZCCsZCAgICCsZKxkICAgICAgIKwgICCsICAgrCAgIKwgrCCsI"
    "CAgrCAgrKwgICBkICAgIGQgICBkICAgZCAgICBkICBkICBkIKwgIGQgICBkrCAgZC"
    "AgICAgZCBkICCsICBkIGQgICCsIGQgZCAgICCsZCBkICBkICCsIGQgICBkIKwgZCA"
    "gICBkrCBkICAgZKysIGQgICAgICBkZCAgrCAgIGRkICAgrCAgZGQgICAgrCBkZCAgr"
    "GQgZGRkICBkrKxkZGQgICAgIKxkZCAgZCBkrGRkICBkrCAgrGQgICAgZCCsZCAgICA"
    "gZKxkICAgZCCsrGQgICBkrKysZCAgICAgICCsICBkZCAgIKwgICCsICAgrCAgIGRkI"
    "CCsICAgrKwgIKwgIGQgIGQgrCAgIGQgZCCsICAgIGRkIKwgIKwgZGQgrCAgIKwgrC"
    "CsICAgZCAgZKwgICAgIGRkrCAgrCAgIKysICAgZGQgrKwgIGQgICAgIGQgIGQgICAg"
    "ZCAgIGQgICBkIGQgrCAgIGQgICAgZCAgZCAgIKxkICBkICBkIKwgIGQgICBkrCAgZ"
    "CBkZGSsICBkICAgICBkIGQgIKwgIGQgZCAgIKwgZCBkICAgZGRkIGQgrKxkZGQgZC"
    "AgICCsZCBkICBkrCCsIGQgZGQgZKwgZCAgICAgIGRkICCsICAgZGQgICCsICBkZCB"
    "kZKwgIGRkIGSsIGQgZGQgICAgrCBkZCAgrGQgZGRkIKwgrGRkZGQgICAgIKxkZCCs"
    "ZGQgrGRkIGQgICAgrGQgIGQgICCsZCAgIGQgIKxkICAgIGQgrGQgZCAgrCCsZCAgI"
    "CAgZKxkIGRkICBkrGQgICCsrGSsZCBkIGRkrKxkICAgICAgIKwgrCAgICAgrCCsrCA"
    "gICCsICBkIGQgIKwgZCCsZCAgrCAgICCsICCsIKwgIKwgIKwgZKysIGQgrCAgrCBk"
    "ZCCsICAgICCsIKwgrCAgIKwgrCBkICAgIGSsICBkICAgZKwgICBkICBkrCAgICBkIG"
    "SsIKxkZGQgZKwgICAgIGRkrCBkICBkZGSsICBkrGRkZKwgICBkrKxkrCAgrCAgIKy"
    "sICAgrCAgrKwgIGRkrCCsrCAgZCBkrKysIGQgICAgICBkIGQgICAgIGQgIGQgICAgZ"
    "CCsZCAgICBkZCCsICAgIGQgZKwgICAgZCAgIGQgICBkIKwgZCAgIGSsZGRkICAgZC"
    "AgrGQgICBkZCAgrCAgIGQgZCCsICAgZCAgZKwgICBkICAgIGQgIGQgIKwgZCAgZGQ"
    "grGRkICBkICAgrGQgIGRkZCCsZCAgZGQgICCsICBkICBkIKwgIGQgrCBkrCAgZKxk"
    "ZGSsICBkIKysZKwgIGQgICAgIGQgZCCsICAgZCBkICCsICBkIGQgICCsIGQgZGSsZ"
    "KwgZCBkrCBkIGRkIGQgZKwgZGQgZCAgICCsZCBkZCAgICCsIGQgZCAgIKwgZCAgZ"
    "CAgrCBkICAgZCCsIGRkZCBkIKwgZCAgICBkrCBkIKxkZGSsIGRkIKxkZKwgZKwgIK"
    "xkrCBkZGQgZKysIGQgIGSsrKwgZCAgICAgIGRkIKwgICAgZGRkIGQgICBkZGSsZCA"
    "gIGRkICCsICAgZGQgICCsICBkZCCsIKwgIGRkIGQgIGQgZGSsICBkZCBkZCBkrKx"
    "kIGRkZCBkrKwgZGQgIGSsIGRkZKwgZKwgZGRkrKwgIGRkZGRkICAgrGRkZCBkZGS"
    "sZGRkICAgICCsZGRkIGQgIKxkZGSsZCAgrGRkIGSsZCCsZGQgICBkZKxkZCCsICC"
    "srGRkIGQgICAgrGQgIGQgICCsZCAgIGQgIKxkIKysZCAgrGQgICAgZCCsZGRkZGR"
    "kIKxkIKxkIKwgrGQgIKxkrCCsZCAgICAgZKxkZGQgICBkrGQgIGQgZGSsZKwgZCB"
    "kZKxkIGQgrGRkrGSsICBkIKysZCAgICAgICCsrCAgICAgIKysrCAgICAgrGQgIGQgI"
    "CCsrCAgrCAgIKwgZCAgZCAgrCCsZCBkICCsICAgZGQgIKxkIGQgrCAgrGQgICAgZC"
    "CsIGQgICBkIKwgIGQgIGQgrGRkZCAgZCCsICAgZCBkIKwgIKxkIGQgrCAgICBkZCC"
    "srGQgZGRkIKwgZGSsZGQgrGSsICCsZCCsICAgZKxkIKwgIKxkrGQgrKwgICAgrCCs"
    "IGQgIGSsIKxkIGQgrKwgrCBkICAgIGSsICBkICAgZKwgZKwgICBkrCAgIGQgIGSsZ"
    "CCsrCAgZKysZGQgZCBkrCAgIKxkIGSsZGQgZKwgZKwgICAgIGRkrKwgrCAgZGSsIG"
    "QgZCBkZKxkIGRkZGRkrGQgIKwgrGSsICCsIGSsZKysICAgICCsrCAgZGQgIKysZGQ"
    "grCAgrKxkrCAgZCCsrCAgICCsIKysIKxkICBkrKwgIGRkIKysrCBkICBkrKys="
)
_IQ2_SIGNS = np.frombuffer(base64.b64decode(_IQ2_SIGNS_B64), dtype=np.uint8)
_IQ2_GRID = np.frombuffer(base64.b64decode(_IQ2_GRID_B64), dtype=np.uint8).reshape(256, 8)


@dataclass(frozen=True)
class GgufMetadata:
    key: str
    value_type: int
    value: int | str | None
    raw_value: bytes


@dataclass(frozen=True)
class GgufTensorInfo:
    name: str
    dims: tuple[int, ...]
    type_id: int
    offset: int
    nbytes: int


@dataclass(frozen=True)
class GgufModel:
    path: Path
    tensors: dict[str, GgufTensorInfo]
    metadata: dict[str, GgufMetadata]
    data_start: int
    alignment: int
    size: int


@dataclass
class OutputTensor:
    name: str
    dims: tuple[int, ...]
    type_id: int
    nbytes: int
    offset: int = 0
    base_info: GgufTensorInfo | None = None
    part: str | None = None


def _align(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _gguf_string(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw


def _read_exact(f: BinaryIO, size: int) -> bytes:
    data = f.read(size)
    if len(data) != size:
        raise ValueError("unexpected EOF while parsing GGUF")
    return data


def _read_file_string(f: BinaryIO) -> str:
    (size,) = struct.unpack("<Q", _read_exact(f, 8))
    return _read_exact(f, size).decode("utf-8")


def _skip_value(f: BinaryIO, value_type: int) -> None:
    if value_type == GGUF_VALUE_TYPE_STRING:
        (size,) = struct.unpack("<Q", _read_exact(f, 8))
        f.seek(size, os.SEEK_CUR)
        return
    if value_type == GGUF_VALUE_TYPE_ARRAY:
        array_type, count = struct.unpack("<IQ", _read_exact(f, 12))
        if array_type == GGUF_VALUE_TYPE_STRING:
            for _ in range(count):
                (size,) = struct.unpack("<Q", _read_exact(f, 8))
                f.seek(size, os.SEEK_CUR)
            return
        if array_type not in GGUF_SCALAR_VALUE_BYTES:
            raise ValueError(f"unsupported GGUF array element type {array_type}")
        f.seek(GGUF_SCALAR_VALUE_BYTES[array_type] * count, os.SEEK_CUR)
        return
    if value_type not in GGUF_SCALAR_VALUE_BYTES:
        raise ValueError(f"unsupported GGUF metadata type {value_type}")
    f.seek(GGUF_SCALAR_VALUE_BYTES[value_type], os.SEEK_CUR)


def _read_raw_value(f: BinaryIO, value_type: int) -> bytes:
    start = f.tell()
    _skip_value(f, value_type)
    end = f.tell()
    f.seek(start)
    return _read_exact(f, end - start)


def _tensor_nbytes(dims: Iterable[int], type_id: int) -> int:
    if type_id not in GGUF_TENSOR_BLOCK:
        raise ValueError(f"unsupported GGML type id {type_id}")
    block_elems, block_bytes = GGUF_TENSOR_BLOCK[type_id]
    elements = math.prod(tuple(dims))
    if elements % block_elems:
        raise ValueError(f"type {type_id} tensor is not block-aligned")
    return elements // block_elems * block_bytes


def parse_gguf_header(path: Path) -> GgufModel:
    """Parse the GGUF v3 header while retaining required metadata verbatim."""
    path = path.resolve()
    file_size = path.stat().st_size
    metadata: dict[str, GgufMetadata] = {}
    raw_tensors: list[tuple[str, tuple[int, ...], int, int]] = []
    with path.open("rb") as f:
        magic, version = struct.unpack("<II", _read_exact(f, 8))
        if magic != GGUF_MAGIC or version != GGUF_VERSION:
            raise ValueError(f"{path} is not GGUF v3")
        tensor_count, kv_count = struct.unpack("<QQ", _read_exact(f, 16))
        for _ in range(kv_count):
            key = _read_file_string(f)
            (value_type,) = struct.unpack("<I", _read_exact(f, 4))
            if key not in PARSED_METADATA_KEYS:
                _skip_value(f, value_type)
                continue
            raw_value = _read_raw_value(f, value_type)
            value: int | str | None = None
            if value_type == GGUF_VALUE_TYPE_UINT32:
                value = struct.unpack_from("<I", raw_value)[0]
            elif value_type == GGUF_VALUE_TYPE_STRING:
                (size,) = struct.unpack_from("<Q", raw_value)
                value = raw_value[8 : 8 + size].decode("utf-8")
            metadata[key] = GgufMetadata(key, value_type, value, raw_value)
        for _ in range(tensor_count):
            name = _read_file_string(f)
            (n_dims,) = struct.unpack("<I", _read_exact(f, 4))
            dims = struct.unpack("<" + "Q" * n_dims, _read_exact(f, 8 * n_dims))
            type_id, offset = struct.unpack("<IQ", _read_exact(f, 12))
            raw_tensors.append((name, tuple(map(int, dims)), int(type_id), int(offset)))
        alignment_meta = metadata.get("general.alignment")
        alignment = int(alignment_meta.value) if alignment_meta and alignment_meta.value is not None else DEFAULT_ALIGNMENT
        if alignment <= 0 or alignment & (alignment - 1):
            raise ValueError(f"invalid GGUF alignment {alignment}")
        data_start = _align(f.tell(), alignment)

    tensors: dict[str, GgufTensorInfo] = {}
    for name, dims, type_id, offset in raw_tensors:
        nbytes = _tensor_nbytes(dims, type_id)
        if data_start + offset + nbytes > file_size:
            raise ValueError(f"tensor {name} extends beyond EOF")
        if name in tensors:
            raise ValueError(f"duplicate tensor name {name}")
        tensors[name] = GgufTensorInfo(name, dims, type_id, offset, nbytes)
    return GgufModel(path, tensors, metadata, data_start, alignment, file_size)


def _metadata_bytes(entries: Sequence[GgufMetadata]) -> bytes:
    out = bytearray()
    for entry in entries:
        out += _gguf_string(entry.key)
        out += struct.pack("<I", entry.value_type)
        out += entry.raw_value
    return bytes(out)


def _metadata_uint(model: GgufModel, key: str) -> int:
    entry = model.metadata.get(key)
    if entry is None or entry.value_type != GGUF_VALUE_TYPE_UINT32 or not isinstance(entry.value, int):
        raise ValueError(f"metadata {key} must be UINT32")
    return entry.value


def _semantic_metadata(model: GgufModel) -> list[GgufMetadata]:
    missing = [key for key in RUNTIME_REQUIRED_METADATA_KEYS if key not in model.metadata]
    if missing:
        raise ValueError(f"base model lacks required sidecar metadata: {missing}")
    entries = [model.metadata[key] for key in RUNTIME_REQUIRED_METADATA_KEYS]
    if "general.alignment" in model.metadata:
        entries.append(model.metadata["general.alignment"])
    return entries


def _parse_experts(csv: str) -> tuple[int, ...]:
    try:
        values = tuple(int(item.strip()) for item in csv.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--experts must be a CSV of integer ids") from exc
    if not values:
        raise argparse.ArgumentTypeError("--experts must not be empty")
    if len(set(values)) != len(values) or any(value < 0 for value in values):
        raise argparse.ArgumentTypeError("--experts must contain unique non-negative ids")
    return tuple(sorted(values))


def _expert_out_dir(root: Path, expert: int) -> Path:
    candidates = (
        root / f"e{expert}" / "out",
        root / f"gptq_e{expert}" / "out",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        f"expert {expert}: expected {candidates[0]} or {candidates[1]}"
    )


def _npz_path(root: Path, expert: int, part: str) -> Path:
    path = _expert_out_dir(root, expert) / f"{part}.q1.npz"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _load_gptq_npz(
    root: Path,
    expert: int,
    part: str,
    expected_out: int,
    expected_in: int,
) -> tuple[np.ndarray, np.ndarray]:
    path = _npz_path(root, expert, part)
    with np.load(path, allow_pickle=False) as data:
        required = {"sign_bits", "scales", "shape", "block_size"}
        missing = required.difference(data.files)
        if missing:
            raise ValueError(f"{path}: missing keys {sorted(missing)}")
        sign_bits = np.asarray(data["sign_bits"])
        scales = np.asarray(data["scales"])
        shape = tuple(int(x) for x in np.asarray(data["shape"]).reshape(-1))
        block_size = int(np.asarray(data["block_size"]).reshape(()))

    expected_blocks = expected_in // Q1_BLOCK_WEIGHTS
    if expected_in % Q1_BLOCK_WEIGHTS:
        raise ValueError(f"{part}: input dimension {expected_in} is not divisible by 128")
    if shape != (expected_out, expected_in):
        raise ValueError(f"{path}: shape {shape}, expected {(expected_out, expected_in)}")
    if block_size != Q1_BLOCK_WEIGHTS:
        raise ValueError(f"{path}: block_size {block_size}, expected 128")
    if sign_bits.dtype != np.uint8 or sign_bits.shape != (expected_out, expected_blocks, 16):
        raise ValueError(
            f"{path}: sign_bits must be uint8[{expected_out},{expected_blocks},16], "
            f"got {sign_bits.dtype}{sign_bits.shape}"
        )
    if scales.dtype.kind != "f" or scales.dtype.itemsize != 2 or scales.shape != (expected_out, expected_blocks):
        raise ValueError(
            f"{path}: scales must be float16[{expected_out},{expected_blocks}], "
            f"got {scales.dtype}{scales.shape}"
        )
    return np.ascontiguousarray(sign_bits), np.ascontiguousarray(scales, dtype="<f2")


def _pack_gptq_expert(sign_bits: np.ndarray, scales: np.ndarray) -> bytes:
    flat_scales = np.ascontiguousarray(scales, dtype="<f2").reshape(-1)
    flat_signs = np.ascontiguousarray(sign_bits, dtype=np.uint8).reshape(-1, 16)
    blocks = np.empty((flat_scales.size, Q1_BLOCK_BYTES), dtype=np.uint8)
    blocks[:, :2] = flat_scales.view(np.uint8).reshape(-1, 2)
    blocks[:, 2:] = flat_signs
    return blocks.tobytes()


def _pack_q1_values(values: np.ndarray) -> bytes:
    blocks_in = np.ascontiguousarray(values, dtype=np.float32).reshape(-1, Q1_BLOCK_WEIGHTS)
    scales = np.mean(np.abs(blocks_in), axis=1, dtype=np.float32).astype("<f2")
    signs = np.packbits(blocks_in >= 0.0, axis=1, bitorder="little")
    blocks = np.empty((blocks_in.shape[0], Q1_BLOCK_BYTES), dtype=np.uint8)
    blocks[:, :2] = scales.view(np.uint8).reshape(-1, 2)
    blocks[:, 2:] = signs
    return blocks.tobytes()


def _dequant_q2_k(payload: bytes) -> np.ndarray:
    raw = np.frombuffer(payload, dtype=np.uint8)
    if raw.size % 84:
        raise ValueError("Q2_K expert payload is not block-aligned")
    blocks = raw.reshape(-1, 84)
    scales = blocks[:, :16]
    qs = blocks[:, 16:80]
    d = np.frombuffer(blocks[:, 80:82].copy().tobytes(), dtype="<f2").astype(np.float32)
    dmin = np.frombuffer(blocks[:, 82:84].copy().tobytes(), dtype="<f2").astype(np.float32)
    values = np.empty((blocks.shape[0], 256), dtype=np.float32)
    out_pos = 0
    scale_pos = 0
    for half in range(2):
        q = qs[:, half * 32 : (half + 1) * 32]
        shift = 0
        for _ in range(4):
            for segment in range(2):
                sc = scales[:, scale_pos]
                dl = d * (sc & 0x0F).astype(np.float32)
                ml = dmin * (sc >> 4).astype(np.float32)
                quant = ((q[:, segment * 16 : (segment + 1) * 16] >> shift) & 3).astype(np.float32)
                values[:, out_pos : out_pos + 16] = dl[:, None] * quant - ml[:, None]
                out_pos += 16
                scale_pos += 1
            shift += 2
    return values


def _dequant_iq2_xxs(payload: bytes) -> np.ndarray:
    raw = np.frombuffer(payload, dtype=np.uint8)
    if raw.size % 66:
        raise ValueError("IQ2_XXS expert payload is not block-aligned")
    blocks = raw.reshape(-1, 66)
    d = np.frombuffer(blocks[:, :2].copy().tobytes(), dtype="<f2").astype(np.float32)
    groups = blocks[:, 2:].reshape(-1, 8, 8)
    grid_ids = groups[:, :, :4]
    aux1 = (
        groups[:, :, 4].astype(np.uint32)
        | (groups[:, :, 5].astype(np.uint32) << 8)
        | (groups[:, :, 6].astype(np.uint32) << 16)
        | (groups[:, :, 7].astype(np.uint32) << 24)
    )
    shifts = np.asarray((0, 7, 14, 21), dtype=np.uint32)
    sign_ids = (aux1[:, :, None] >> shifts[None, None, :]) & 127
    sign_bytes = _IQ2_SIGNS[sign_ids]
    masks = (1 << np.arange(8, dtype=np.uint8))[None, None, None, :]
    negative = (sign_bytes[:, :, :, None] & masks) != 0
    magnitudes = _IQ2_GRID[grid_ids].astype(np.float32)
    signed = np.where(negative, -magnitudes, magnitudes)
    db = d[:, None] * (0.5 + (aux1 >> 28).astype(np.float32)) * 0.25
    return (db[:, :, None, None] * signed).reshape(-1, 256)


def _base_expert_payload(
    base_map: mmap.mmap,
    base: GgufModel,
    info: GgufTensorInfo,
    expert: int,
) -> bytes:
    if len(info.dims) != 3:
        raise ValueError(f"{info.name}: expected a 3-D expert tensor")
    in_dim, out_dim, expert_count = info.dims
    if not 0 <= expert < expert_count:
        raise ValueError(f"{info.name}: expert {expert} is out of range")
    block_elems, block_bytes = GGUF_TENSOR_BLOCK[info.type_id]
    if in_dim % block_elems:
        raise ValueError(f"{info.name}: rows are not aligned for type {info.type_id}")
    source_expert_bytes = out_dim * (in_dim // block_elems) * block_bytes
    start = base.data_start + info.offset + expert * source_expert_bytes
    payload = bytes(base_map[start : start + source_expert_bytes])
    if len(payload) != source_expert_bytes:
        raise ValueError(f"{info.name}: truncated base expert {expert}")
    if info.type_id == Q1_TYPE_ID:
        return payload
    if info.type_id == 10:
        values = _dequant_q2_k(payload)
    elif info.type_id == 16:
        values = _dequant_iq2_xxs(payload)
    else:
        raise ValueError(
            f"{info.name}: missing experts can only be filled from Q2_K (10), "
            f"IQ2_XXS (16), or Q1_0 (41), not type {info.type_id}"
        )
    expected_values = in_dim * out_dim
    if values.size != expected_values:
        raise AssertionError(f"{info.name}: fallback dequantized {values.size}, expected {expected_values}")
    return _pack_q1_values(values)


def _control_tensor_names(base: GgufModel, layer: int) -> list[str]:
    block_count = _metadata_uint(base, "deepseek4.block_count")
    hash_layer_count = _metadata_uint(base, "deepseek4.hash_layer_count")
    if not 0 <= layer < block_count:
        raise ValueError(f"--layer {layer} is outside 0..{block_count - 1}")
    names: list[str] = []
    for il in range(block_count):
        names.extend((f"blk.{il}.attn_norm.weight", f"blk.{il}.ffn_norm.weight"))
        if il >= hash_layer_count:
            names.append(f"blk.{il}.exp_probs_b.bias")
    names.append(f"blk.{layer}.ffn_gate_inp.weight")
    missing = [name for name in names if name not in base.tensors]
    if missing:
        raise ValueError(f"base model lacks runtime identity tensors: {missing[:8]}")
    return names


def _make_output_tensors(base: GgufModel, layer: int) -> list[OutputTensor]:
    tensors: list[OutputTensor] = []
    for name in _control_tensor_names(base, layer):
        info = base.tensors[name]
        tensors.append(OutputTensor(name, info.dims, info.type_id, info.nbytes, base_info=info))
    for part, suffix in PART_SUFFIX.items():
        name = f"blk.{layer}.{suffix}"
        info = base.tensors.get(name)
        if info is None:
            raise ValueError(f"base model lacks {name}")
        if len(info.dims) != 3:
            raise ValueError(f"{name}: expected dimensions [in,out,expert]")
        in_dim, out_dim, expert_count = info.dims
        if in_dim % Q1_BLOCK_WEIGHTS:
            raise ValueError(f"{name}: input dimension {in_dim} is not divisible by 128")
        nbytes = expert_count * out_dim * (in_dim // Q1_BLOCK_WEIGHTS) * Q1_BLOCK_BYTES
        tensors.append(OutputTensor(name, info.dims, Q1_TYPE_ID, nbytes, base_info=info, part=part))
    return tensors


def _build_header(
    metadata: Sequence[GgufMetadata],
    tensors: Sequence[OutputTensor],
    alignment: int,
) -> bytes:
    offset = 0
    for tensor in tensors:
        tensor.offset = offset
        offset = _align(offset + tensor.nbytes, alignment)
    header = bytearray(struct.pack("<IIQQ", GGUF_MAGIC, GGUF_VERSION, len(tensors), len(metadata)))
    header += _metadata_bytes(metadata)
    for tensor in tensors:
        header += _gguf_string(tensor.name)
        header += struct.pack("<I", len(tensor.dims))
        header += struct.pack("<" + "Q" * len(tensor.dims), *tensor.dims)
        header += struct.pack("<IQ", tensor.type_id, tensor.offset)
    header += bytes(_align(len(header), alignment) - len(header))
    return bytes(header)


def _write_zeros(f: BinaryIO, size: int) -> None:
    zero = bytes(1024 * 1024)
    while size:
        take = min(size, len(zero))
        f.write(zero[:take])
        size -= take


def _copy_mmap_range(dst: BinaryIO, src: mmap.mmap, start: int, size: int) -> None:
    chunk_size = 8 * 1024 * 1024
    for pos in range(start, start + size, chunk_size):
        dst.write(src[pos : min(pos + chunk_size, start + size)])


def _preflight_gptq(
    root: Path,
    viable: set[int],
    tensors: Sequence[OutputTensor],
) -> None:
    for tensor in tensors:
        if tensor.part is None:
            continue
        in_dim, out_dim, _ = tensor.dims
        for expert in sorted(viable):
            _load_gptq_npz(root, expert, tensor.part, out_dim, in_dim)


def write_sidecar(
    base: GgufModel,
    gptq_root: Path,
    layer: int,
    experts: tuple[int, ...],
    out_path: Path,
) -> list[OutputTensor]:
    metadata = _semantic_metadata(base)
    tensors = _make_output_tensors(base, layer)
    expert_tensors = [tensor for tensor in tensors if tensor.part is not None]
    assert expert_tensors
    expert_count = expert_tensors[0].dims[2]
    if any(tensor.dims[2] != expert_count for tensor in expert_tensors):
        raise ValueError("base gate/up/down tensors disagree on expert count")
    if expert_count != _metadata_uint(base, "deepseek4.expert_count"):
        raise ValueError("base expert tensor count disagrees with deepseek4.expert_count")
    if experts[-1] >= expert_count:
        raise ValueError(f"expert id {experts[-1]} is outside 0..{expert_count - 1}")
    viable = set(experts)
    _preflight_gptq(gptq_root, viable, tensors)

    header = _build_header(metadata, tensors, base.alignment)
    out_path = out_path.resolve()
    if out_path.exists():
        raise FileExistsError(f"refusing to overwrite {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = out_path.with_name(f"{out_path.name}.partial.{os.getpid()}")
    if temporary.exists():
        raise FileExistsError(f"temporary output already exists: {temporary}")

    try:
        with base.path.open("rb") as base_file, temporary.open("xb") as dst:
            with mmap.mmap(base_file.fileno(), 0, access=mmap.ACCESS_READ) as base_map:
                dst.write(header)
                data_start = len(header)
                for tensor in tensors:
                    desired = data_start + tensor.offset
                    if dst.tell() > desired:
                        raise AssertionError(f"writer passed offset for {tensor.name}")
                    _write_zeros(dst, desired - dst.tell())
                    assert tensor.base_info is not None
                    if tensor.part is None:
                        source_start = base.data_start + tensor.base_info.offset
                        _copy_mmap_range(dst, base_map, source_start, tensor.nbytes)
                    else:
                        in_dim, out_dim, count = tensor.dims
                        expert_bytes = out_dim * (in_dim // Q1_BLOCK_WEIGHTS) * Q1_BLOCK_BYTES
                        for expert in range(count):
                            if expert in viable:
                                signs, scales = _load_gptq_npz(
                                    gptq_root, expert, tensor.part, out_dim, in_dim
                                )
                                payload = _pack_gptq_expert(signs, scales)
                            else:
                                payload = _base_expert_payload(
                                    base_map, base, tensor.base_info, expert
                                )
                            if len(payload) != expert_bytes:
                                raise AssertionError(
                                    f"{tensor.name} expert {expert}: {len(payload)} bytes, "
                                    f"expected {expert_bytes}"
                                )
                            dst.write(payload)
                    if dst.tell() != desired + tensor.nbytes:
                        raise AssertionError(f"writer size mismatch for {tensor.name}")
        os.replace(temporary, out_path)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return tensors


def _dequant_q1_block(block: bytes) -> np.ndarray:
    if len(block) != Q1_BLOCK_BYTES:
        raise ValueError("Q1_0 block must be exactly 18 bytes")
    scale = float(np.frombuffer(block[:2], dtype="<f2")[0])
    bits = np.unpackbits(np.frombuffer(block[2:], dtype=np.uint8), bitorder="little")
    return np.where(bits != 0, scale, -scale).astype(np.float32)


def verify_sidecar(
    base: GgufModel,
    gptq_root: Path,
    layer: int,
    experts: tuple[int, ...],
    out_path: Path,
) -> None:
    sidecar = parse_gguf_header(out_path)
    for key in RUNTIME_REQUIRED_METADATA_KEYS:
        if key not in sidecar.metadata:
            raise AssertionError(f"written sidecar lacks metadata {key}")
        if sidecar.metadata[key].value_type != base.metadata[key].value_type:
            raise AssertionError(f"metadata type mismatch for {key}")
        if sidecar.metadata[key].raw_value != base.metadata[key].raw_value:
            raise AssertionError(f"metadata value mismatch for {key}")
    if sidecar.metadata["general.name"].value != base.metadata["general.name"].value:
        raise AssertionError("general.name differs from base model")

    control_names = _control_tensor_names(base, layer)
    with (
        base.path.open("rb") as base_file,
        out_path.open("rb") as sidecar_file,
        mmap.mmap(base_file.fileno(), 0, access=mmap.ACCESS_READ) as base_map,
        mmap.mmap(sidecar_file.fileno(), 0, access=mmap.ACCESS_READ) as sidecar_map,
    ):
        for name in control_names:
            source = base.tensors[name]
            written = sidecar.tensors.get(name)
            if written is None or (written.dims, written.type_id, written.nbytes) != (
                source.dims,
                source.type_id,
                source.nbytes,
            ):
                raise AssertionError(f"copied control tensor descriptor mismatch: {name}")
            source_start = base.data_start + source.offset
            written_start = sidecar.data_start + written.offset
            if base_map[source_start : source_start + source.nbytes] != sidecar_map[
                written_start : written_start + written.nbytes
            ]:
                raise AssertionError(f"control tensor is not byte-identical: {name}")

        for suffix in PART_SUFFIX.values():
            name = f"blk.{layer}.{suffix}"
            source = base.tensors[name]
            written = sidecar.tensors.get(name)
            if written is None or written.type_id != Q1_TYPE_ID or written.dims != source.dims:
                raise AssertionError(f"invalid written Q1_0 tensor {name}")

        # End-to-end source-NPZ -> GGUF block -> dequantized values check.
        sample_expert = experts[0]
        sample_part = "gate"
        sample_name = f"blk.{layer}.{PART_SUFFIX[sample_part]}"
        written = sidecar.tensors[sample_name]
        in_dim, out_dim, _ = written.dims
        expert_bytes = out_dim * (in_dim // Q1_BLOCK_WEIGHTS) * Q1_BLOCK_BYTES
        block_start = sidecar.data_start + written.offset + sample_expert * expert_bytes
        written_block = bytes(sidecar_map[block_start : block_start + Q1_BLOCK_BYTES])
        signs, scales = _load_gptq_npz(
            gptq_root, sample_expert, sample_part, out_dim, in_dim
        )
        source_scale = np.asarray(scales[0, 0], dtype="<f2").tobytes()
        source_signs = signs[0, 0].tobytes()
        if written_block[:2] != source_scale or written_block[2:] != source_signs:
            raise AssertionError("written sample block does not match source NPZ bytes")
        source_bits = np.unpackbits(signs[0, 0], bitorder="little")
        expected = np.where(source_bits != 0, float(scales[0, 0]), -float(scales[0, 0])).astype(np.float32)
        np.testing.assert_array_equal(_dequant_q1_block(written_block), expected)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert GPTQ-Q1 expert NPZ files into a ds4 Q1_0 GGUF sidecar."
    )
    parser.add_argument("--gptq-root", required=True, type=Path)
    parser.add_argument("--layer", required=True, type=int)
    parser.add_argument("--experts", required=True, type=_parse_experts)
    parser.add_argument("--base-model", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.gptq_root.is_dir():
        raise NotADirectoryError(args.gptq_root)
    if not args.base_model.is_file():
        raise FileNotFoundError(args.base_model)
    base = parse_gguf_header(args.base_model)
    written = write_sidecar(
        base=base,
        gptq_root=args.gptq_root.resolve(),
        layer=args.layer,
        experts=args.experts,
        out_path=args.out,
    )
    verify_sidecar(
        base=base,
        gptq_root=args.gptq_root.resolve(),
        layer=args.layer,
        experts=args.experts,
        out_path=args.out.resolve(),
    )
    q1_bytes = sum(tensor.nbytes for tensor in written if tensor.type_id == Q1_TYPE_ID)
    print(
        f"OK: {args.out.resolve()} ({q1_bytes} Q1_0 bytes); "
        f"verified metadata, identity tensors, and one NPZ round-trip block."
    )
    print(
        f"For this single-layer sidecar set DS4_Q1_0_LAYER_FIRST={args.layer}, "
        f"DS4_Q1_0_LAYER_LAST={args.layer}, and "
        f"DS4_Q1_0_EXPERT_SIDECAR={args.out.resolve()}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, AssertionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
