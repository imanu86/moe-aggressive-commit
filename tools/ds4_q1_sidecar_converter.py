"""DS4 Q1_0 sidecar converter and validator.

Synthetic fixtures exercise metadata, offsets, provenance, and hashes. Real
IQ2_XXS/Q2_K payload conversion is enabled only through the explicitly bound
reference helper and remains an IQ2-derived transport experiment, not a claim
that Q1_0 preserves full-model quality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import mmap
import os
import subprocess
import struct
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

try:
    from tools.ds4_q1_smoke import (
        GGUF_MAGIC,
        GGUF_VERSION,
        Q1_BLOCK_BYTES,
        Q1_BLOCK_WEIGHTS,
        Q1_TYPE_ID,
        SyntheticGgufTensor,
        _align,
        _gguf_string,
        deterministic_values,
        quantize_q1_0,
        read_synthetic_q1_gguf,
    )
except ModuleNotFoundError:
    from ds4_q1_smoke import (
        GGUF_MAGIC,
        GGUF_VERSION,
        Q1_BLOCK_BYTES,
        Q1_BLOCK_WEIGHTS,
        Q1_TYPE_ID,
        SyntheticGgufTensor,
        _align,
        _gguf_string,
        deterministic_values,
        quantize_q1_0,
        read_synthetic_q1_gguf,
    )

SYNTHETIC_IQ2_TYPE_ID = 25
SYNTHETIC_Q2_TYPE_ID = 25
MANIFEST_SCHEMA = "ds4_q1_0_sidecar_manifest_v1"
RUNTIME_MANIFEST_SCHEMA = "ds4_q1_0_runtime_sidecar_manifest_v1"
RUNTIME_EXTENSION_MANIFEST_SCHEMA = "ds4_q1_0_runtime_sidecar_extension_manifest_v1"
REAL_DEQUANT_BLOCKED_MESSAGE = (
    "BLOCKED: real IQ2_XXS/Q2_K -> Q1_0 conversion requires provenance-verified "
    "production dequantizers and block-level golden tests; synthetic int16 fixture "
    "conversion must not be used for real DS4 payloads"
)
REAL_DEQUANT_PRIMARY_SOURCE = (
    "ggml-org/llama.cpp commit 635cdd5fcc5bdeb8ec2e108bb2a40acf62d9039b; "
    "ggml/src/ggml-quants.c dequantize_row_iq2_xxs, dequantize_row_q2_K, "
    "quantize_row_q1_0_ref, dequantize_row_q1_0, quantize_q1_0; "
    "ggml/src/ggml-common.h block layouts"
)
RUNTIME_QUALITY_NOTE = (
    "production IQ2_XXS/Q2_K -> float -> Q1_0 reference conversion for real "
    "payloads; not quality-optimal"
)
GGUF_VALUE_TYPE_UINT32 = 4
GGUF_VALUE_TYPE_STRING = 8
GGUF_VALUE_TYPE_ARRAY = 9
GGUF_SCALAR_VALUE_BYTES = {
    0: 1,
    1: 1,
    2: 2,
    3: 2,
    4: 4,
    5: 4,
    6: 4,
    7: 1,
    10: 8,
    11: 8,
    12: 8,
}
GGUF_TENSOR_BLOCK = {
    0: (1, 4),
    1: (1, 2),
    8: (32, 34),
    10: (256, 84),
    12: (256, 144),
    16: (256, 66),
    19: (256, 50),
    24: (1, 1),
    25: (1, 2),
    26: (1, 4),
    27: (1, 8),
    28: (1, 8),
    30: (1, 2),
    41: (128, 18),
}
RUNTIME_COPY_TENSOR_SUFFIXES = ("attn_norm.weight", "ffn_norm.weight")
RUNTIME_COPY_ROUTED_SUFFIX = "exp_probs_b.bias"
RUNTIME_COPY_ROUTER_SUFFIX = "ffn_gate_inp.weight"
RUNTIME_ROUTED_SUFFIXES = {
    "gate": "ffn_gate_exps.weight",
    "up": "ffn_up_exps.weight",
    "down": "ffn_down_exps.weight",
}
RUNTIME_REQUIRED_METADATA_KEYS = {
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
}


@dataclass(frozen=True)
class SyntheticSourceTensor:
    name: str
    dims: tuple[int, ...]
    type_id: int
    offset: int
    nbytes: int
    sha256: str


@dataclass(frozen=True)
class ConvertedTensor:
    name: str
    source_type_id: int
    q1_type_id: int
    dims: tuple[int, ...]
    source_offset: int
    q1_offset: int
    source_sha256: str
    q1_sha256: str
    q1_nbytes: int


@dataclass(frozen=True)
class GgufTensorInfo:
    name: str
    dims: tuple[int, ...]
    type_id: int
    offset: int
    nbytes: int


@dataclass(frozen=True)
class GgufMetadata:
    key: str
    value_type: int
    value: int | str | None
    raw_value: bytes | None = None


@dataclass(frozen=True)
class GgufModel:
    path: Path
    tensors: dict[str, GgufTensorInfo]
    metadata: dict[str, GgufMetadata]
    data_start: int
    size: int


@dataclass(frozen=True)
class RuntimeSidecarPlan:
    layer: int
    layers: tuple[int, ...]
    source: Path
    output: Path
    manifest: Path
    tensors_to_copy: tuple[str, ...]
    tensors_to_convert: tuple[str, ...]
    estimated_read_bytes: int
    estimated_output_bytes: int
    note: str = "estimate only; no model payload read"


@dataclass(frozen=True)
class RuntimeSidecarExtensionPlan:
    primary: Path
    base_sidecar: Path
    output: Path
    manifest: Path
    layers: tuple[int, ...]
    base_layers: tuple[int, ...]
    primary_copy_tensors: tuple[str, ...]
    primary_convert_tensors: tuple[str, ...]
    base_reuse_tensors: tuple[str, ...]
    estimated_primary_read_bytes: int
    estimated_base_read_bytes: int
    estimated_output_bytes: int
    note: str = "estimate only; no model payload read"


@dataclass(frozen=True)
class RuntimeTensorManifest:
    name: str
    action: str
    source_type_id: int
    output_type_id: int
    dims: tuple[int, ...]
    source_offset: int
    source_nbytes: int
    output_offset: int
    output_nbytes: int
    source_sha256: str
    output_sha256: str


@dataclass(frozen=True)
class GgufWriteTensor:
    name: str
    dims: tuple[int, ...]
    type_id: int
    payload: bytes
    offset: int = field(default=0)


def _tensor_nbytes(dims: Iterable[int], type_id: int) -> int:
    elems = math.prod(tuple(dims))
    if type_id in GGUF_TENSOR_BLOCK:
        block_elems, block_bytes = GGUF_TENSOR_BLOCK[type_id]
        if elems % block_elems:
            raise ValueError(f"tensor type {type_id} is not block aligned")
        return elems // block_elems * block_bytes
    raise ValueError(f"unsupported synthetic type {type_id}")


def _read_gguf_string(data: bytes | mmap.mmap, pos: int) -> tuple[str, int]:
    (n,) = struct.unpack_from("<Q", data, pos)
    pos += 8
    value = data[pos : pos + n].decode("utf-8")
    return value, pos + n


def _read_exact(f, n: int) -> bytes:
    data = f.read(n)
    if len(data) != n:
        raise ValueError("unexpected EOF while parsing GGUF")
    return data


def _read_file_string(f) -> str:
    (n,) = struct.unpack("<Q", _read_exact(f, 8))
    return _read_exact(f, n).decode("utf-8")


def _skip_file_value(f, value_type: int) -> None:
    if value_type == GGUF_VALUE_TYPE_STRING:
        (n,) = struct.unpack("<Q", _read_exact(f, 8))
        f.seek(n, 1)
        return
    if value_type == GGUF_VALUE_TYPE_ARRAY:
        array_type, n = struct.unpack("<IQ", _read_exact(f, 12))
        if array_type == GGUF_VALUE_TYPE_STRING:
            for _ in range(n):
                (size,) = struct.unpack("<Q", _read_exact(f, 8))
                f.seek(size, 1)
            return
        if array_type not in GGUF_SCALAR_VALUE_BYTES:
            raise ValueError(f"unsupported GGUF array value type {array_type}")
        f.seek(GGUF_SCALAR_VALUE_BYTES[array_type] * n, 1)
        return
    if value_type not in GGUF_SCALAR_VALUE_BYTES:
        raise ValueError(f"unsupported GGUF metadata value type {value_type}")
    f.seek(GGUF_SCALAR_VALUE_BYTES[value_type], 1)


def _read_metadata_raw_value(f, value_type: int) -> bytes:
    start = f.tell()
    _skip_file_value(f, value_type)
    end = f.tell()
    f.seek(start)
    raw = _read_exact(f, end - start)
    return raw


def parse_gguf_header(path: Path) -> GgufModel:
    size = path.stat().st_size
    metadata: dict[str, GgufMetadata] = {}
    raw: list[tuple[str, tuple[int, ...], int, int]] = []
    with path.open("rb") as f:
        magic, version = struct.unpack("<II", _read_exact(f, 8))
        if magic != GGUF_MAGIC or version != GGUF_VERSION:
            raise ValueError("expected GGUF v3")
        tensor_count, kv_count = struct.unpack("<QQ", _read_exact(f, 16))
        for _ in range(kv_count):
            key = _read_file_string(f)
            (value_type,) = struct.unpack("<I", _read_exact(f, 4))
            if key in RUNTIME_REQUIRED_METADATA_KEYS:
                raw_value = _read_metadata_raw_value(f, value_type)
            else:
                _skip_file_value(f, value_type)
                continue
            if value_type == GGUF_VALUE_TYPE_UINT32:
                (value,) = struct.unpack_from("<I", raw_value, 0)
                metadata[key] = GgufMetadata(key, value_type, value, raw_value)
            elif value_type == GGUF_VALUE_TYPE_STRING:
                (n,) = struct.unpack_from("<Q", raw_value, 0)
                metadata[key] = GgufMetadata(key, value_type, raw_value[8 : 8 + n].decode("utf-8"), raw_value)
            else:
                metadata[key] = GgufMetadata(key, value_type, None, raw_value)
        for _ in range(tensor_count):
            name = _read_file_string(f)
            (n_dims,) = struct.unpack("<I", _read_exact(f, 4))
            dims = tuple(int(d) for d in struct.unpack("<" + "Q" * n_dims, _read_exact(f, 8 * n_dims)))
            type_id, offset = struct.unpack("<IQ", _read_exact(f, 12))
            raw.append((name, dims, int(type_id), int(offset)))
        data_start = _align(f.tell())
    tensors: dict[str, GgufTensorInfo] = {}
    for name, dims, type_id, offset in raw:
        nbytes = _tensor_nbytes(dims, type_id)
        if data_start + offset + nbytes > size:
            raise ValueError(f"tensor {name} extends past file end")
        tensors[name] = GgufTensorInfo(name, dims, type_id, offset, nbytes)
    return GgufModel(path=path, tensors=tensors, metadata=metadata, data_start=data_start, size=size)


def _metadata_bytes(entries: Sequence[GgufMetadata]) -> bytes:
    out = bytearray()
    for entry in entries:
        out += _gguf_string(entry.key)
        out += struct.pack("<I", entry.value_type)
        if entry.raw_value is not None:
            out += entry.raw_value
            continue
        if entry.value_type == GGUF_VALUE_TYPE_UINT32:
            out += struct.pack("<I", int(entry.value))
        elif entry.value_type == GGUF_VALUE_TYPE_STRING:
            out += _gguf_string(str(entry.value))
        else:
            raise ValueError(f"unsupported metadata type {entry.value_type}")
    return bytes(out)


def write_gguf(path: Path, metadata: Sequence[GgufMetadata], tensors: Sequence[GgufWriteTensor]) -> list[GgufTensorInfo]:
    offset = 0
    planned: list[GgufWriteTensor] = []
    for tensor in tensors:
        planned.append(GgufWriteTensor(tensor.name, tensor.dims, tensor.type_id, tensor.payload, offset))
        offset = _align(offset + len(tensor.payload))
    header = bytearray()
    header += struct.pack("<I", GGUF_MAGIC)
    header += struct.pack("<I", GGUF_VERSION)
    header += struct.pack("<Q", len(planned))
    header += struct.pack("<Q", len(metadata))
    header += _metadata_bytes(metadata)
    for tensor in planned:
        header += _gguf_string(tensor.name)
        header += struct.pack("<I", len(tensor.dims))
        for dim in tensor.dims:
            header += struct.pack("<Q", dim)
        header += struct.pack("<I", tensor.type_id)
        header += struct.pack("<Q", tensor.offset)
    payload_prefix = _align(len(header)) - len(header)
    payload = bytearray(payload_prefix)
    infos: list[GgufTensorInfo] = []
    for tensor in planned:
        while len(payload) < payload_prefix + tensor.offset:
            payload.append(0)
        payload += tensor.payload
        infos.append(GgufTensorInfo(tensor.name, tensor.dims, tensor.type_id, tensor.offset, len(tensor.payload)))
        while len(payload) < payload_prefix + _align(tensor.offset + len(tensor.payload)):
            payload.append(0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + bytes(payload))
    return infos


def _tensor_payload(mm: mmap.mmap, model: GgufModel, tensor: GgufTensorInfo) -> bytes:
    start = model.data_start + tensor.offset
    return bytes(mm[start : start + tensor.nbytes])


def _sha256_payload(mm: mmap.mmap, model: GgufModel, tensor: GgufTensorInfo) -> str:
    return hashlib.sha256(_tensor_payload(mm, model, tensor)).hexdigest()


def _sha256_file_streaming(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _helper_manifest_record() -> dict[str, object] | None:
    tool = _q1_ref_tool()
    if tool is None:
        return None
    resolved = tool.resolve()
    return {
        "path": str(resolved),
        "size": resolved.stat().st_size,
        "sha256": _sha256_file_streaming(resolved),
    }


def _int16_payload_to_q1(payload: bytes, dims: tuple[int, ...]) -> bytes:
    elems = math.prod(dims)
    if elems * 2 != len(payload):
        raise ValueError("synthetic int16 payload size mismatch")
    values = [struct.unpack_from("<h", payload, i * 2)[0] / 2048.0 for i in range(elems)]
    out = bytearray()
    for block_start in range(0, elems, Q1_BLOCK_WEIGHTS):
        out += quantize_q1_0(values[block_start : block_start + Q1_BLOCK_WEIGHTS]).pack()
    return bytes(out)


def _runtime_tensor_rows(dims: tuple[int, ...]) -> tuple[int, int]:
    if not dims:
        raise ValueError("runtime tensor dims are empty")
    ncols = int(dims[0])
    if ncols <= 0:
        raise ValueError("runtime tensor row width is empty")
    elems = math.prod(dims)
    if elems % ncols:
        raise ValueError("runtime tensor dims do not form whole rows")
    return elems // ncols, ncols


def _q1_ref_tool() -> Path | None:
    value = os.environ.get("DS4_Q1_REF_TOOL")
    if not value:
        return None
    path = Path(value)
    if not path.exists():
        raise ValueError(f"DS4_Q1_REF_TOOL does not exist: {path}")
    return path


def _convert_real_payload_to_q1(payload: bytes, info: GgufTensorInfo) -> bytes:
    tool = _q1_ref_tool()
    if tool is None:
        raise ValueError(
            f"{REAL_DEQUANT_BLOCKED_MESSAGE}; set DS4_Q1_REF_TOOL to the built "
            "CPU reference helper before converting real type16/type10 payloads"
        )
    nrows, ncols = _runtime_tensor_rows(info.dims)
    type_arg = "iq2_xxs" if info.type_id == 16 else "q2_k"
    proc = subprocess.run(
        [str(tool), "convert", type_arg, str(nrows), str(ncols)],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(
            f"Q1_0 reference helper failed for {info.name}: "
            f"exit={proc.returncode} stderr={proc.stderr.decode('utf-8', errors='replace')}"
        )
    expected = math.prod(info.dims) // Q1_BLOCK_WEIGHTS * Q1_BLOCK_BYTES
    if len(proc.stdout) != expected:
        raise ValueError(f"Q1_0 reference helper returned {len(proc.stdout)} bytes, expected {expected}")
    return proc.stdout


def _payload_to_q1(payload: bytes, info: GgufTensorInfo) -> bytes:
    if info.type_id == SYNTHETIC_IQ2_TYPE_ID:
        return _int16_payload_to_q1(payload, info.dims)
    if info.type_id in {16, 10}:
        return _convert_real_payload_to_q1(payload, info)
    raise ValueError(f"{REAL_DEQUANT_BLOCKED_MESSAGE}; unsupported={info.name}:type{info.type_id}")


def _parse_synthetic_gguf(path: Path) -> tuple[list[SyntheticSourceTensor], int, bytes]:
    data = path.read_bytes()
    if len(data) < 24:
        raise ValueError("fixture is too small")
    magic, version = struct.unpack_from("<II", data, 0)
    if magic != GGUF_MAGIC or version != GGUF_VERSION:
        raise ValueError("fixture is not GGUF v3")
    tensor_count, kv_count = struct.unpack_from("<QQ", data, 8)
    if kv_count != 0:
        raise ValueError("fixture parser expects zero key-values")
    pos = 24
    raw: list[tuple[str, tuple[int, ...], int, int, int]] = []
    for _ in range(tensor_count):
        name_len = struct.unpack_from("<Q", data, pos)[0]
        pos += 8
        name = data[pos : pos + name_len].decode("utf-8")
        pos += name_len
        n_dims = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        dims = tuple(int(d) for d in struct.unpack_from("<" + "Q" * n_dims, data, pos))
        pos += 8 * n_dims
        type_id, offset = struct.unpack_from("<IQ", data, pos)
        pos += 12
        raw.append((name, dims, int(type_id), int(offset), _tensor_nbytes(dims, int(type_id))))
    data_start = _align(pos)
    tensors: list[SyntheticSourceTensor] = []
    for name, dims, type_id, offset, nbytes in raw:
        start = data_start + offset
        end = start + nbytes
        if end > len(data):
            raise ValueError("source tensor extends past file end")
        tensors.append(
            SyntheticSourceTensor(
                name=name,
                dims=dims,
                type_id=type_id,
                offset=offset,
                nbytes=nbytes,
                sha256=hashlib.sha256(data[start:end]).hexdigest(),
            )
        )
    return tensors, data_start, data


def write_synthetic_iq2_fixture(path: Path, experts: int = 2) -> list[SyntheticSourceTensor]:
    if experts <= 0:
        raise ValueError("experts must be positive")
    names = (
        "blk.3.ffn_gate_exps.weight",
        "blk.3.ffn_up_exps.weight",
        "blk.3.ffn_down_exps.weight",
    )
    dims = (Q1_BLOCK_WEIGHTS, 1, experts)
    tensors: list[tuple[str, tuple[int, ...], int, int, int]] = []
    offset = 0
    for name in names:
        nbytes = _tensor_nbytes(dims, SYNTHETIC_IQ2_TYPE_ID)
        tensors.append((name, dims, SYNTHETIC_IQ2_TYPE_ID, offset, nbytes))
        offset = _align(offset + nbytes)
    header = bytearray()
    header += struct.pack("<I", GGUF_MAGIC)
    header += struct.pack("<I", GGUF_VERSION)
    header += struct.pack("<Q", len(tensors))
    header += struct.pack("<Q", 0)
    for name, dims_i, type_id, tensor_offset, _nbytes in tensors:
        header += _gguf_string(name)
        header += struct.pack("<I", len(dims_i))
        for dim in dims_i:
            header += struct.pack("<Q", dim)
        header += struct.pack("<I", type_id)
        header += struct.pack("<Q", tensor_offset)
    payload_prefix = _align(len(header)) - len(header)
    payload = bytearray(payload_prefix)
    for tensor_index, (_name, dims_i, _type_id, tensor_offset, nbytes) in enumerate(tensors):
        while len(payload) < tensor_offset:
            payload.append(0)
        values = deterministic_values(math.prod(dims_i), seed=101 + tensor_index)
        for value in values:
            q = max(-32768, min(32767, int(round(value * 2048.0))))
            payload += struct.pack("<h", q)
        if len(payload) != payload_prefix + tensor_offset + nbytes:
            raise AssertionError("synthetic IQ2 payload accounting mismatch")
        while len(payload) < payload_prefix + _align(tensor_offset + nbytes):
            payload.append(0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + bytes(payload))
    parsed, _data_start, _data = _parse_synthetic_gguf(path)
    return parsed


def _source_values(data: bytes, data_start: int, tensor: SyntheticSourceTensor) -> list[float]:
    start = data_start + tensor.offset
    count = math.prod(tensor.dims)
    return [struct.unpack_from("<h", data, start + 2 * i)[0] / 2048.0 for i in range(count)]


def convert_synthetic_iq2_to_q1(source: Path, sidecar: Path, manifest: Path) -> dict[str, object]:
    source_tensors, data_start, data = _parse_synthetic_gguf(source)
    if not source_tensors:
        raise ValueError("source fixture has no tensors")
    out_tensors: list[SyntheticGgufTensor] = []
    out_payload = bytearray()
    converted: list[ConvertedTensor] = []
    offset = 0
    for tensor in source_tensors:
        if tensor.type_id != SYNTHETIC_IQ2_TYPE_ID:
            raise ValueError("converter expects synthetic IQ2 source tensors")
        values = _source_values(data, data_start, tensor)
        if len(values) % Q1_BLOCK_WEIGHTS:
            raise ValueError("source tensor is not Q1 block aligned")
        while len(out_payload) < offset:
            out_payload.append(0)
        q1_blob = bytearray()
        for block_start in range(0, len(values), Q1_BLOCK_WEIGHTS):
            q1_blob += quantize_q1_0(values[block_start : block_start + Q1_BLOCK_WEIGHTS]).pack()
        out_payload += q1_blob
        out_tensors.append(
            SyntheticGgufTensor(
                name=tensor.name,
                dims=tensor.dims,
                type_id=Q1_TYPE_ID,
                offset=offset,
                nbytes=len(q1_blob),
            )
        )
        converted.append(
            ConvertedTensor(
                name=tensor.name,
                source_type_id=tensor.type_id,
                q1_type_id=Q1_TYPE_ID,
                dims=tensor.dims,
                source_offset=tensor.offset,
                q1_offset=offset,
                source_sha256=tensor.sha256,
                q1_sha256=hashlib.sha256(q1_blob).hexdigest(),
                q1_nbytes=len(q1_blob),
            )
        )
        while len(out_payload) < _align(offset + len(q1_blob)):
            out_payload.append(0)
        offset = len(out_payload)

    header = bytearray()
    header += struct.pack("<I", GGUF_MAGIC)
    header += struct.pack("<I", GGUF_VERSION)
    header += struct.pack("<Q", len(out_tensors))
    header += struct.pack("<Q", 0)
    for tensor in out_tensors:
        header += _gguf_string(tensor.name)
        header += struct.pack("<I", len(tensor.dims))
        for dim in tensor.dims:
            header += struct.pack("<Q", dim)
        header += struct.pack("<I", tensor.type_id)
        header += struct.pack("<Q", tensor.offset)
    side_payload_start = _align(len(header))
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_bytes(bytes(header) + bytes(side_payload_start - len(header)) + bytes(out_payload))

    sidecar_tensors = read_synthetic_q1_gguf(sidecar)
    manifest_obj: dict[str, object] = {
        "schema": MANIFEST_SCHEMA,
        "derived": True,
        "quality_note": "synthetic deterministic IQ2/Q2 -> float -> Q1_0 conversion; not quality-optimal",
        "source": {
            "path": str(source),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
        "sidecar": {
            "path": str(sidecar),
            "sha256": hashlib.sha256(sidecar.read_bytes()).hexdigest(),
        },
        "tensors": [asdict(t) for t in converted],
    }
    manifest.write_text(json.dumps(manifest_obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validate_manifest(source, sidecar, manifest)
    if [(t.name, t.offset, t.type_id) for t in sidecar_tensors] != [
        (t.name, t.q1_offset, Q1_TYPE_ID) for t in converted
    ]:
        raise ValueError("sidecar tensor identity/offset validation failed")
    return manifest_obj


def _required_runtime_metadata(model: GgufModel) -> list[GgufMetadata]:
    required = ["general.name"]
    missing = [key for key in required if key not in model.metadata]
    if missing:
        raise ValueError(f"missing runtime sidecar metadata: {missing}")
    return list(model.metadata.values())


def _runtime_metadata_manifest(metadata: Sequence[GgufMetadata]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for m in metadata:
        raw = m.raw_value
        out.append(
            {
                "key": m.key,
                "value_type": m.value_type,
                "value": m.value,
                "raw_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
            }
        )
    return out


def _runtime_layers_from_range(layer_first: int = 3, layer_last: int = 42) -> tuple[int, ...]:
    if not (3 <= layer_first <= layer_last <= 42):
        raise ValueError("runtime Q1_0 sidecar target layer range must be in 3..42")
    return tuple(range(layer_first, layer_last + 1))


def runtime_sidecar_tensor_names_for_layers(layers: Sequence[int], n_layers: int = 43) -> tuple[list[str], list[str]]:
    layer_tuple = tuple(int(layer) for layer in layers)
    if not layer_tuple:
        raise ValueError("runtime Q1_0 sidecar layer list must not be empty")
    if any(layer < 3 or layer > 42 for layer in layer_tuple):
        raise ValueError("runtime Q1_0 sidecar target layers must be in 3..42")
    if len(set(layer_tuple)) != len(layer_tuple):
        raise ValueError("runtime Q1_0 sidecar target layers must be unique")
    copy_names: list[str] = []
    for il in range(n_layers):
        for suffix in RUNTIME_COPY_TENSOR_SUFFIXES:
            copy_names.append(f"blk.{il}.{suffix}")
    for il in range(3, 43):
        copy_names.append(f"blk.{il}.{RUNTIME_COPY_ROUTED_SUFFIX}")
    # Primary router IDs address the experts stored in this sidecar.
    for layer in layer_tuple:
        copy_names.append(f"blk.{layer}.{RUNTIME_COPY_ROUTER_SUFFIX}")
    convert_names = []
    for layer in layer_tuple:
        convert_names.extend(f"blk.{layer}.{suffix}" for suffix in RUNTIME_ROUTED_SUFFIXES.values())
    return copy_names, convert_names


def runtime_sidecar_tensor_names(layer: int, n_layers: int = 43) -> tuple[list[str], list[str]]:
    if not (3 <= layer <= 42):
        raise ValueError("runtime Q1_0 sidecar target layer must be in 3..42")
    return runtime_sidecar_tensor_names_for_layers((layer,), n_layers=n_layers)


def _extension_layers_from_range(layer_first: int = 0, layer_last: int = 42) -> tuple[int, ...]:
    if not (0 <= layer_first <= layer_last <= 42):
        raise ValueError("runtime Q1_0 extension layer range must be in 0..42")
    return tuple(range(layer_first, layer_last + 1))


def _runtime_primary_tensors_for_layers(layers: Sequence[int]) -> tuple[list[str], list[str]]:
    copy_names: list[str] = []
    convert_names: list[str] = []
    for layer in layers:
        copy_names.append(f"blk.{layer}.{RUNTIME_COPY_ROUTER_SUFFIX}")
        convert_names.extend(f"blk.{layer}.{suffix}" for suffix in RUNTIME_ROUTED_SUFFIXES.values())
    return copy_names, convert_names


def estimate_runtime_sidecar_plan(
    source: Path,
    output: Path,
    manifest: Path,
    layer: int = 3,
) -> RuntimeSidecarPlan:
    layers = (layer,)
    copy_names, convert_names = runtime_sidecar_tensor_names_for_layers(layers)
    model = parse_gguf_header(source)
    missing = [name for name in copy_names + convert_names if name not in model.tensors]
    if missing:
        raise ValueError(f"source model missing tensors required for runtime sidecar: {missing[:8]}")
    read_bytes = sum(model.tensors[name].nbytes for name in copy_names + convert_names)
    q1_bytes = 0
    for name in convert_names:
        info = model.tensors[name]
        elems = math.prod(info.dims)
        if elems % Q1_BLOCK_WEIGHTS:
            raise ValueError(f"{name} is not Q1 block aligned")
        q1_bytes += elems // Q1_BLOCK_WEIGHTS * Q1_BLOCK_BYTES
    output_bytes = sum(model.tensors[name].nbytes for name in copy_names) + q1_bytes
    return RuntimeSidecarPlan(
        layer=layer,
        layers=layers,
        source=source,
        output=output,
        manifest=manifest,
        tensors_to_copy=tuple(copy_names),
        tensors_to_convert=tuple(convert_names),
        estimated_read_bytes=read_bytes,
        estimated_output_bytes=output_bytes,
    )


def estimate_runtime_layer_range_sidecar_plan(
    source: Path,
    output: Path,
    manifest: Path,
    layer_first: int = 3,
    layer_last: int = 42,
) -> RuntimeSidecarPlan:
    layers = _runtime_layers_from_range(layer_first, layer_last)
    copy_names, convert_names = runtime_sidecar_tensor_names_for_layers(layers)
    model = parse_gguf_header(source)
    missing = [name for name in copy_names + convert_names if name not in model.tensors]
    if missing:
        raise ValueError(f"source model missing tensors required for runtime sidecar: {missing[:8]}")
    read_bytes = sum(model.tensors[name].nbytes for name in copy_names + convert_names)
    q1_bytes = 0
    for name in convert_names:
        info = model.tensors[name]
        elems = math.prod(info.dims)
        if elems % Q1_BLOCK_WEIGHTS:
            raise ValueError(f"{name} is not Q1 block aligned")
        q1_bytes += elems // Q1_BLOCK_WEIGHTS * Q1_BLOCK_BYTES
    output_bytes = sum(model.tensors[name].nbytes for name in copy_names) + q1_bytes
    return RuntimeSidecarPlan(
        layer=layers[0],
        layers=layers,
        source=source,
        output=output,
        manifest=manifest,
        tensors_to_copy=tuple(copy_names),
        tensors_to_convert=tuple(convert_names),
        estimated_read_bytes=read_bytes,
        estimated_output_bytes=output_bytes,
    )


def estimate_runtime_extension_layer_range_plan(
    primary: Path,
    base_sidecar: Path,
    output: Path,
    manifest: Path,
    convert_layer_first: int = 0,
    convert_layer_last: int = 2,
    base_layer_first: int = 3,
    base_layer_last: int = 42,
) -> RuntimeSidecarExtensionPlan:
    layers = _extension_layers_from_range(convert_layer_first, convert_layer_last)
    base_layers = _runtime_layers_from_range(base_layer_first, base_layer_last)
    primary_model = parse_gguf_header(primary)
    base_model = parse_gguf_header(base_sidecar)
    primary_copy, primary_convert = _runtime_primary_tensors_for_layers(layers)
    missing_primary = [name for name in primary_copy + primary_convert if name not in primary_model.tensors]
    if missing_primary:
        raise ValueError(f"primary model missing tensors required for runtime extension: {missing_primary[:8]}")
    for name in primary_convert:
        info = primary_model.tensors[name]
        elems = math.prod(info.dims)
        if elems % Q1_BLOCK_WEIGHTS:
            raise ValueError(f"{name} is not Q1 block aligned")
    missing_base = []
    bad_base = []
    for layer in base_layers:
        for suffix in (RUNTIME_COPY_ROUTER_SUFFIX, *RUNTIME_ROUTED_SUFFIXES.values()):
            name = f"blk.{layer}.{suffix}"
            info = base_model.tensors.get(name)
            if info is None:
                missing_base.append(name)
            elif suffix in RUNTIME_ROUTED_SUFFIXES.values() and info.type_id != Q1_TYPE_ID:
                bad_base.append(f"{name}:type{info.type_id}")
    if missing_base:
        raise ValueError(f"base Q1 sidecar missing routed tensors: {missing_base[:8]}")
    if bad_base:
        raise ValueError(f"base sidecar routed tensors must already be Q1_0: {bad_base[:8]}")
    collisions = [name for name in primary_copy + primary_convert if name in base_model.tensors]
    if collisions:
        raise ValueError(f"base sidecar already contains tensors owned by extension: {collisions[:8]}")
    q1_bytes = 0
    for name in primary_convert:
        info = primary_model.tensors[name]
        q1_bytes += math.prod(info.dims) // Q1_BLOCK_WEIGHTS * Q1_BLOCK_BYTES
    primary_copy_bytes = sum(primary_model.tensors[name].nbytes for name in primary_copy)
    base_bytes = sum(info.nbytes for info in base_model.tensors.values())
    return RuntimeSidecarExtensionPlan(
        primary=primary,
        base_sidecar=base_sidecar,
        output=output,
        manifest=manifest,
        layers=layers,
        base_layers=base_layers,
        primary_copy_tensors=tuple(primary_copy),
        primary_convert_tensors=tuple(primary_convert),
        base_reuse_tensors=tuple(base_model.tensors.keys()),
        estimated_primary_read_bytes=sum(primary_model.tensors[name].nbytes for name in primary_copy + primary_convert),
        estimated_base_read_bytes=base_bytes,
        estimated_output_bytes=base_bytes + primary_copy_bytes + q1_bytes,
    )


def _runtime_conversion_preflight(model: GgufModel, tensor_names: Sequence[str]) -> None:
    unsupported = [
        (name, model.tensors[name].type_id)
        for name in tensor_names
        if model.tensors[name].type_id not in {SYNTHETIC_IQ2_TYPE_ID, 16, 10}
    ]
    if unsupported:
        detail = ", ".join(f"{name}:type{type_id}" for name, type_id in unsupported)
        raise ValueError(f"{REAL_DEQUANT_BLOCKED_MESSAGE}; unsupported={detail}")
    real = [
        (name, model.tensors[name].type_id)
        for name in tensor_names
        if model.tensors[name].type_id in {16, 10}
    ]
    if real and _q1_ref_tool() is None:
        detail = ", ".join(f"{name}:type{type_id}" for name, type_id in real)
        raise ValueError(
            f"{REAL_DEQUANT_BLOCKED_MESSAGE}; DS4_Q1_REF_TOOL not set; real={detail}"
        )


def convert_runtime_valid_single_layer_sidecar(
    source: Path,
    output: Path,
    manifest: Path,
    layer: int = 3,
) -> dict[str, object]:
    plan = estimate_runtime_sidecar_plan(source, output, manifest, layer)
    return _convert_runtime_sidecar_from_plan(plan)


def convert_runtime_valid_layer_range_sidecar(
    source: Path,
    output: Path,
    manifest: Path,
    layer_first: int = 3,
    layer_last: int = 42,
) -> dict[str, object]:
    plan = estimate_runtime_layer_range_sidecar_plan(source, output, manifest, layer_first, layer_last)
    return _convert_runtime_sidecar_from_plan(plan)


def _convert_runtime_sidecar_from_plan(plan: RuntimeSidecarPlan) -> dict[str, object]:
    source = plan.source
    output = plan.output
    manifest = plan.manifest
    temporary_output = output.with_name(f"{output.name}.partial.{os.getpid()}")
    temporary_manifest = manifest.with_name(f"{manifest.name}.partial.{os.getpid()}")
    if output.exists() or manifest.exists():
        raise FileExistsError("runtime Q1_0 output or manifest already exists")
    model = parse_gguf_header(source)
    _runtime_conversion_preflight(model, plan.tensors_to_convert)
    metadata = _required_runtime_metadata(model)
    tensor_names = list(plan.tensors_to_copy) + list(plan.tensors_to_convert)
    planned: list[dict[str, object]] = []
    output_offset = 0
    for name in tensor_names:
        info = model.tensors[name]
        if name in plan.tensors_to_convert:
            output_type = Q1_TYPE_ID
            output_nbytes = (
                math.prod(info.dims) // Q1_BLOCK_WEIGHTS * Q1_BLOCK_BYTES
            )
        else:
            output_type = info.type_id
            output_nbytes = info.nbytes
        planned.append(
            {
                "name": name,
                "info": info,
                "type_id": output_type,
                "offset": output_offset,
                "nbytes": output_nbytes,
            }
        )
        output_offset = _align(output_offset + output_nbytes)

    header = bytearray()
    header += struct.pack("<I", GGUF_MAGIC)
    header += struct.pack("<I", GGUF_VERSION)
    header += struct.pack("<Q", len(planned))
    header += struct.pack("<Q", len(metadata))
    header += _metadata_bytes(metadata)
    for item in planned:
        info = item["info"]
        assert isinstance(info, GgufTensorInfo)
        header += _gguf_string(str(item["name"]))
        header += struct.pack("<I", len(info.dims))
        for dim in info.dims:
            header += struct.pack("<Q", dim)
        header += struct.pack("<I", int(item["type_id"]))
        header += struct.pack("<Q", int(item["offset"]))
    data_start = _align(len(header))

    output.parent.mkdir(parents=True, exist_ok=True)
    records: list[RuntimeTensorManifest] = []
    by_name = {str(item["name"]): item for item in planned}
    chunk_size = 8 * 1024 * 1024
    workers = int(os.environ.get("DS4_Q1_CONVERTER_WORKERS", "3"))
    if workers < 1 or workers > 3:
        raise ValueError("DS4_Q1_CONVERTER_WORKERS must be in 1..3")

    with source.open("rb") as source_file, temporary_output.open("xb") as output_file:
        with mmap.mmap(source_file.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            output_file.write(header)
            output_file.write(b"\0" * (data_start - len(header)))

            def position_output(item: dict[str, object]) -> None:
                target = data_start + int(item["offset"])
                if output_file.tell() > target:
                    raise ValueError("runtime sidecar output offset moved backwards")
                if output_file.tell() < target:
                    output_file.write(b"\0" * (target - output_file.tell()))

            for name in plan.tensors_to_copy:
                item = by_name[name]
                info = model.tensors[name]
                position_output(item)
                source_hash = hashlib.sha256()
                start = model.data_start + info.offset
                end = start + info.nbytes
                for cursor in range(start, end, chunk_size):
                    payload = mm[cursor : min(cursor + chunk_size, end)]
                    source_hash.update(payload)
                    output_file.write(payload)
                digest = source_hash.hexdigest()
                records.append(
                    RuntimeTensorManifest(
                        name=name,
                        action="copy_byte_identical",
                        source_type_id=info.type_id,
                        output_type_id=int(item["type_id"]),
                        dims=info.dims,
                        source_offset=info.offset,
                        source_nbytes=info.nbytes,
                        output_offset=int(item["offset"]),
                        output_nbytes=int(item["nbytes"]),
                        source_sha256=digest,
                        output_sha256=digest,
                    )
                )

            def convert_one(name: str) -> tuple[str, str, bytes]:
                info = model.tensors[name]
                source_payload = _tensor_payload(mm, model, info)
                source_sha = hashlib.sha256(source_payload).hexdigest()
                converted = _payload_to_q1(source_payload, info)
                if len(converted) != int(by_name[name]["nbytes"]):
                    raise ValueError(
                        f"Q1_0 converted size mismatch for {name}: "
                        f"{len(converted)} != {by_name[name]['nbytes']}"
                    )
                return source_sha, hashlib.sha256(converted).hexdigest(), converted

            with ThreadPoolExecutor(max_workers=workers) as executor:
                convert_names = list(plan.tensors_to_convert)
                for first in range(0, len(convert_names), 3):
                    batch = convert_names[first : first + 3]
                    converted_batch = list(executor.map(convert_one, batch))
                    for name, converted_result in zip(batch, converted_batch):
                        source_sha, output_sha, output_payload = converted_result
                        item = by_name[name]
                        info = model.tensors[name]
                        position_output(item)
                        output_file.write(output_payload)
                        records.append(
                            RuntimeTensorManifest(
                                name=name,
                                action="convert_iq2_or_q2_to_q1_0",
                                source_type_id=info.type_id,
                                output_type_id=int(item["type_id"]),
                                dims=info.dims,
                                source_offset=info.offset,
                                source_nbytes=info.nbytes,
                                output_offset=int(item["offset"]),
                                output_nbytes=len(output_payload),
                                source_sha256=source_sha,
                                output_sha256=output_sha,
                            )
                        )
                    del converted_batch

            if output_file.tell() < data_start + output_offset:
                output_file.write(
                    b"\0" * (data_start + output_offset - output_file.tell())
                )
            output_file.flush()
            os.fsync(output_file.fileno())

    record_by_name = {record.name: record for record in records}
    ordered_records = [record_by_name[name] for name in tensor_names]
    obj: dict[str, object] = {
        "schema": RUNTIME_MANIFEST_SCHEMA,
        "layer": plan.layer,
        "layers": list(plan.layers),
        "layer_first": plan.layers[0],
        "layer_last": plan.layers[-1],
        "derived_from_IQ2": True,
        "not_quality_optimal": True,
        "quality_note": RUNTIME_QUALITY_NOTE,
        "conversion_source": REAL_DEQUANT_PRIMARY_SOURCE,
        "helper": _helper_manifest_record(),
        "source": {"path": str(source), "size": model.size},
        "output": {
            "path": str(output),
            "size": temporary_output.stat().st_size,
            "sha256": _sha256_file_streaming(temporary_output),
        },
        "estimated_read_bytes": plan.estimated_read_bytes,
        "estimated_output_bytes": plan.estimated_output_bytes,
        "metadata": _runtime_metadata_manifest(metadata),
        "converter_workers": workers,
        "streaming_writer": True,
        "peak_converted_tensors": min(workers, 3),
        "tensors": [asdict(t) for t in ordered_records],
        "full_quality_path": "rebuild Q1_0 from richer checkpoint/original precision weights, not from IQ2-derived values",
    }
    temporary_manifest.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validate_runtime_sidecar_manifest(source, temporary_output, temporary_manifest)
    os.replace(temporary_output, output)
    os.replace(temporary_manifest, manifest)
    return obj


def convert_runtime_extension_layer_range_sidecar(
    primary: Path,
    base_sidecar: Path,
    output: Path,
    manifest: Path,
    convert_layer_first: int = 0,
    convert_layer_last: int = 2,
    base_layer_first: int = 3,
    base_layer_last: int = 42,
) -> dict[str, object]:
    plan = estimate_runtime_extension_layer_range_plan(
        primary,
        base_sidecar,
        output,
        manifest,
        convert_layer_first=convert_layer_first,
        convert_layer_last=convert_layer_last,
        base_layer_first=base_layer_first,
        base_layer_last=base_layer_last,
    )
    primary_model = parse_gguf_header(primary)
    base_model = parse_gguf_header(base_sidecar)
    _runtime_conversion_preflight(primary_model, plan.primary_convert_tensors)
    metadata = _required_runtime_metadata(primary_model)
    for meta in metadata:
        base_meta = base_model.metadata.get(meta.key)
        if base_meta is None or base_meta.raw_value != meta.raw_value:
            raise ValueError(f"base sidecar metadata provenance mismatch: {meta.key}")

    tensor_items: list[dict[str, object]] = []
    output_offset = 0
    for source_role, model, names in (
        ("base_sidecar", base_model, plan.base_reuse_tensors),
        ("primary", primary_model, plan.primary_copy_tensors),
    ):
        for name in names:
            info = model.tensors[name]
            tensor_items.append(
                {
                    "name": name,
                    "source_role": source_role,
                    "source_action": "reuse_q1_byte_identical_from_base" if source_role == "base_sidecar" else "copy_primary_byte_identical",
                    "info": info,
                    "type_id": info.type_id,
                    "offset": output_offset,
                    "nbytes": info.nbytes,
                }
            )
            output_offset = _align(output_offset + info.nbytes)
    for name in plan.primary_convert_tensors:
        info = primary_model.tensors[name]
        output_nbytes = math.prod(info.dims) // Q1_BLOCK_WEIGHTS * Q1_BLOCK_BYTES
        tensor_items.append(
            {
                "name": name,
                "source_role": "primary",
                "source_action": "convert_primary_iq2_or_q2_to_q1_0",
                "info": info,
                "type_id": Q1_TYPE_ID,
                "offset": output_offset,
                "nbytes": output_nbytes,
            }
        )
        output_offset = _align(output_offset + output_nbytes)
    names = [str(item["name"]) for item in tensor_items]
    if len(names) != len(set(names)):
        raise ValueError("runtime extension would create duplicate tensor names")

    header = bytearray()
    header += struct.pack("<I", GGUF_MAGIC)
    header += struct.pack("<I", GGUF_VERSION)
    header += struct.pack("<Q", len(tensor_items))
    header += struct.pack("<Q", len(metadata))
    header += _metadata_bytes(metadata)
    for item in tensor_items:
        info = item["info"]
        assert isinstance(info, GgufTensorInfo)
        header += _gguf_string(str(item["name"]))
        header += struct.pack("<I", len(info.dims))
        for dim in info.dims:
            header += struct.pack("<Q", dim)
        header += struct.pack("<I", int(item["type_id"]))
        header += struct.pack("<Q", int(item["offset"]))
    data_start = _align(len(header))

    temporary_output = output.with_name(f"{output.name}.partial.{os.getpid()}")
    temporary_manifest = manifest.with_name(f"{manifest.name}.partial.{os.getpid()}")
    if output.exists() or manifest.exists():
        raise FileExistsError("runtime Q1_0 extension output or manifest already exists")
    output.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    chunk_size = 8 * 1024 * 1024
    try:
        with (
            primary.open("rb") as primary_file,
            base_sidecar.open("rb") as base_file,
            temporary_output.open("xb") as output_file,
        ):
            with (
                mmap.mmap(primary_file.fileno(), 0, access=mmap.ACCESS_READ) as primary_mm,
                mmap.mmap(base_file.fileno(), 0, access=mmap.ACCESS_READ) as base_mm,
            ):
                output_file.write(header)
                output_file.write(b"\0" * (data_start - len(header)))

                def position_output(item: dict[str, object]) -> None:
                    target = data_start + int(item["offset"])
                    if output_file.tell() > target:
                        raise ValueError("runtime extension output offset moved backwards")
                    if output_file.tell() < target:
                        output_file.write(b"\0" * (target - output_file.tell()))

                def copy_from_model(item: dict[str, object], model: GgufModel, mm: mmap.mmap) -> tuple[str, str]:
                    info = item["info"]
                    assert isinstance(info, GgufTensorInfo)
                    position_output(item)
                    h = hashlib.sha256()
                    start = model.data_start + info.offset
                    end = start + info.nbytes
                    for cursor in range(start, end, chunk_size):
                        payload = mm[cursor : min(cursor + chunk_size, end)]
                        h.update(payload)
                        output_file.write(payload)
                    return h.hexdigest(), h.hexdigest()

                for item in tensor_items:
                    info = item["info"]
                    assert isinstance(info, GgufTensorInfo)
                    source_role = str(item["source_role"])
                    action = str(item["source_action"])
                    if action == "convert_primary_iq2_or_q2_to_q1_0":
                        source_payload = _tensor_payload(primary_mm, primary_model, info)
                        source_sha = hashlib.sha256(source_payload).hexdigest()
                        converted = _payload_to_q1(source_payload, info)
                        if len(converted) != int(item["nbytes"]):
                            raise ValueError(f"Q1_0 converted size mismatch for {item['name']}")
                        position_output(item)
                        output_file.write(converted)
                        output_sha = hashlib.sha256(converted).hexdigest()
                    elif source_role == "base_sidecar":
                        source_sha, output_sha = copy_from_model(item, base_model, base_mm)
                    elif source_role == "primary":
                        source_sha, output_sha = copy_from_model(item, primary_model, primary_mm)
                    else:
                        raise ValueError(f"unknown runtime extension source role: {source_role}")
                    records.append(
                        {
                            "name": str(item["name"]),
                            "action": action,
                            "source_role": source_role,
                            "source_type_id": info.type_id,
                            "output_type_id": int(item["type_id"]),
                            "dims": list(info.dims),
                            "source_offset": info.offset,
                            "source_nbytes": info.nbytes,
                            "output_offset": int(item["offset"]),
                            "output_nbytes": int(item["nbytes"]),
                            "source_sha256": source_sha,
                            "output_sha256": output_sha,
                        }
                    )

                if output_file.tell() < data_start + output_offset:
                    output_file.write(b"\0" * (data_start + output_offset - output_file.tell()))
                output_file.flush()
                os.fsync(output_file.fileno())

        obj: dict[str, object] = {
            "schema": RUNTIME_EXTENSION_MANIFEST_SCHEMA,
            "derived_from_IQ2": True,
            "not_quality_optimal": True,
            "quality_note": RUNTIME_QUALITY_NOTE,
            "conversion_source": REAL_DEQUANT_PRIMARY_SOURCE,
            "layers": list(range(0, 43)),
            "converted_layers": list(plan.layers),
            "base_reused_layers": list(plan.base_layers),
            "helper": _helper_manifest_record(),
            "primary": {
                "path": str(primary),
                "size": primary_model.size,
                "sha256": _sha256_file_streaming(primary),
            },
            "base_sidecar": {
                "path": str(base_sidecar),
                "size": base_model.size,
                "sha256": _sha256_file_streaming(base_sidecar),
            },
            "output": {
                "path": str(output),
                "size": temporary_output.stat().st_size,
                "sha256": _sha256_file_streaming(temporary_output),
            },
            "estimated_primary_read_bytes": plan.estimated_primary_read_bytes,
            "estimated_base_read_bytes": plan.estimated_base_read_bytes,
            "estimated_output_bytes": plan.estimated_output_bytes,
            "metadata": _runtime_metadata_manifest(metadata),
            "streaming_writer": True,
            "extension_strategy": "reuse base Q1 tensors byte-identically; convert only missing primary layers",
            "tensors": records,
        }
        temporary_manifest.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        validate_runtime_extension_manifest(primary, base_sidecar, temporary_output, temporary_manifest)
        os.replace(temporary_output, output)
        os.replace(temporary_manifest, manifest)
        return obj
    except Exception:
        for path in (temporary_output, temporary_manifest):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        raise


def _runtime_manifest_layers(obj: dict[str, object]) -> tuple[int, ...]:
    if "layers" in obj:
        raw_layers = obj["layers"]
        if not isinstance(raw_layers, list):
            raise ValueError("runtime manifest layers must be a list")
        layers = tuple(int(layer) for layer in raw_layers)
        expected = _runtime_layers_from_range(int(obj.get("layer_first", layers[0])), int(obj.get("layer_last", layers[-1])))
        if layers != expected:
            raise ValueError("runtime manifest layer range mismatch")
        return layers
    return (int(obj["layer"]),)


def validate_runtime_sidecar_manifest(source: Path, output: Path, manifest: Path) -> dict[str, object]:
    obj = json.loads(manifest.read_text(encoding="utf-8"))
    if obj.get("schema") != RUNTIME_MANIFEST_SCHEMA:
        raise ValueError("unexpected runtime manifest schema")
    if obj.get("derived_from_IQ2") is not True or obj.get("not_quality_optimal") is not True:
        raise ValueError("runtime sidecar must be marked derived and not quality-optimal")
    if obj.get("quality_note") != RUNTIME_QUALITY_NOTE:
        raise ValueError("runtime quality note/provenance mismatch")
    if obj.get("conversion_source") != REAL_DEQUANT_PRIMARY_SOURCE:
        raise ValueError("runtime conversion source provenance mismatch")
    if "blocked_real_dequant_source" in obj:
        raise ValueError("stale blocked_real_dequant_source field is not allowed")
    model = parse_gguf_header(source)
    sidecar = parse_gguf_header(output)
    if obj.get("output", {}).get("sha256") != _sha256_file_streaming(output):
        raise ValueError("runtime sidecar full hash mismatch")
    helper = obj.get("helper")
    current_helper = _helper_manifest_record()
    if current_helper is not None:
        if helper != current_helper:
            raise ValueError("runtime helper provenance mismatch")
    elif helper is not None:
        helper_path = Path(str(helper.get("path", "")))
        if not helper_path.exists():
            raise ValueError("runtime helper provenance path is unavailable")
        expected = {
            "path": str(helper_path.resolve()),
            "size": helper_path.stat().st_size,
            "sha256": _sha256_file_streaming(helper_path),
        }
        if helper != expected:
            raise ValueError("runtime helper provenance mismatch")
    if "general.name" not in sidecar.metadata or sidecar.metadata["general.name"].value != model.metadata["general.name"].value:
        raise ValueError("general.name provenance mismatch")
    metadata_records = obj.get("metadata", [])
    metadata_by_key = {m["key"]: m for m in metadata_records}
    if len(metadata_by_key) != len(metadata_records):
        raise ValueError("duplicate runtime metadata records")
    for key, src_meta in model.metadata.items():
        side_meta = sidecar.metadata.get(key)
        rec = metadata_by_key.get(key)
        if side_meta is None or rec is None:
            raise ValueError(f"missing runtime metadata record: {key}")
        raw_sha = hashlib.sha256(src_meta.raw_value or b"").hexdigest()
        if (
            side_meta.value_type != src_meta.value_type
            or side_meta.value != src_meta.value
            or rec.get("value_type") != src_meta.value_type
            or rec.get("value") != src_meta.value
            or rec.get("raw_sha256") != raw_sha
        ):
            raise ValueError(f"runtime metadata provenance mismatch: {key}")
    records = obj.get("tensors", [])
    if not isinstance(records, list):
        raise ValueError("runtime tensor records must be a list")
    layers = _runtime_manifest_layers(obj)
    copy_names, convert_names = runtime_sidecar_tensor_names_for_layers(layers)
    expected_names = list(copy_names) + list(convert_names)
    record_names = [rec.get("name") for rec in records]
    if len(record_names) != len(set(record_names)):
        raise ValueError("duplicate runtime tensor records")
    if set(record_names) != set(expected_names):
        raise ValueError("runtime tensor record set mismatch")
    for name in expected_names:
        if name not in sidecar.tensors:
            raise ValueError(f"missing runtime sidecar tensor: {name}")
    with source.open("rb") as sf, output.open("rb") as of:
        with mmap.mmap(sf.fileno(), 0, access=mmap.ACCESS_READ) as smm, mmap.mmap(of.fileno(), 0, access=mmap.ACCESS_READ) as omm:
            for rec in records:
                src = model.tensors[rec["name"]]
                out = sidecar.tensors[rec["name"]]
                if src.offset != rec["source_offset"] or out.offset != rec["output_offset"]:
                    raise ValueError(f"offset mismatch for {rec['name']}")
                if out.type_id != rec["output_type_id"]:
                    raise ValueError(f"type mismatch for {rec['name']}")
                if _sha256_payload(smm, model, src) != rec["source_sha256"]:
                    raise ValueError(f"source hash mismatch for {rec['name']}")
                if _sha256_payload(omm, sidecar, out) != rec["output_sha256"]:
                    raise ValueError(f"output hash mismatch for {rec['name']}")
                if rec["action"] == "copy_byte_identical":
                    if rec["source_sha256"] != rec["output_sha256"]:
                        raise ValueError(f"copy tensor is not byte-identical: {rec['name']}")
                elif rec["action"] == "convert_iq2_or_q2_to_q1_0":
                    if rec["output_type_id"] != Q1_TYPE_ID:
                        raise ValueError(f"converted tensor is not Q1_0: {rec['name']}")
                else:
                    raise ValueError(f"unknown tensor action {rec['action']}")
    return obj


def validate_runtime_extension_manifest(primary: Path, base_sidecar: Path, output: Path, manifest: Path) -> dict[str, object]:
    obj = json.loads(manifest.read_text(encoding="utf-8"))
    if obj.get("schema") != RUNTIME_EXTENSION_MANIFEST_SCHEMA:
        raise ValueError("unexpected runtime extension manifest schema")
    if obj.get("derived_from_IQ2") is not True or obj.get("not_quality_optimal") is not True:
        raise ValueError("runtime extension must be marked derived and not quality-optimal")
    if obj.get("quality_note") != RUNTIME_QUALITY_NOTE:
        raise ValueError("runtime extension quality note/provenance mismatch")
    if obj.get("conversion_source") != REAL_DEQUANT_PRIMARY_SOURCE:
        raise ValueError("runtime extension conversion source provenance mismatch")
    if obj.get("primary", {}).get("sha256") != _sha256_file_streaming(primary):
        raise ValueError("runtime extension primary full hash mismatch")
    if obj.get("base_sidecar", {}).get("sha256") != _sha256_file_streaming(base_sidecar):
        raise ValueError("runtime extension base sidecar full hash mismatch")
    if obj.get("output", {}).get("sha256") != _sha256_file_streaming(output):
        raise ValueError("runtime extension output full hash mismatch")
    helper = obj.get("helper")
    current_helper = _helper_manifest_record()
    if current_helper is not None:
        if helper != current_helper:
            raise ValueError("runtime extension helper provenance mismatch")
    elif helper is not None:
        helper_path = Path(str(helper.get("path", "")))
        if not helper_path.exists():
            raise ValueError("runtime extension helper provenance path is unavailable")
        expected = {
            "path": str(helper_path.resolve()),
            "size": helper_path.stat().st_size,
            "sha256": _sha256_file_streaming(helper_path),
        }
        if helper != expected:
            raise ValueError("runtime extension helper provenance mismatch")

    primary_model = parse_gguf_header(primary)
    base_model = parse_gguf_header(base_sidecar)
    out_model = parse_gguf_header(output)
    for key, src_meta in primary_model.metadata.items():
        out_meta = out_model.metadata.get(key)
        base_meta = base_model.metadata.get(key)
        if out_meta is None or base_meta is None:
            raise ValueError(f"runtime extension missing metadata: {key}")
        if out_meta.raw_value != src_meta.raw_value or base_meta.raw_value != src_meta.raw_value:
            raise ValueError(f"runtime extension metadata provenance mismatch: {key}")

    raw_converted_layers = obj.get("converted_layers")
    if not isinstance(raw_converted_layers, list):
        raise ValueError("runtime extension converted_layers must be a list")
    converted_layers = tuple(int(layer) for layer in raw_converted_layers)
    if converted_layers != _extension_layers_from_range(converted_layers[0], converted_layers[-1]):
        raise ValueError("runtime extension converted layer range mismatch")
    primary_copy, primary_convert = _runtime_primary_tensors_for_layers(converted_layers)
    expected_names = list(base_model.tensors.keys()) + primary_copy + primary_convert
    records = obj.get("tensors", [])
    if not isinstance(records, list):
        raise ValueError("runtime extension tensor records must be a list")
    record_names = [rec.get("name") for rec in records]
    if len(record_names) != len(set(record_names)):
        raise ValueError("duplicate runtime extension tensor records")
    if set(record_names) != set(expected_names):
        raise ValueError("runtime extension tensor record set mismatch")
    if set(out_model.tensors.keys()) != set(expected_names):
        raise ValueError("runtime extension output tensor set mismatch")

    raw_base_layers = obj.get("base_reused_layers")
    if not isinstance(raw_base_layers, list):
        raise ValueError("runtime extension base_reused_layers must be a list")
    base_layers = tuple(int(layer) for layer in raw_base_layers)
    if base_layers != _runtime_layers_from_range(base_layers[0], base_layers[-1]):
        raise ValueError("runtime extension base layer range mismatch")
    for layer in base_layers:
        for suffix in RUNTIME_ROUTED_SUFFIXES.values():
            name = f"blk.{layer}.{suffix}"
            if base_model.tensors[name].type_id != Q1_TYPE_ID:
                raise ValueError(f"base reused routed tensor is not Q1_0: {name}")
    with (
        primary.open("rb") as primary_file,
        base_sidecar.open("rb") as base_file,
        output.open("rb") as output_file,
    ):
        with (
            mmap.mmap(primary_file.fileno(), 0, access=mmap.ACCESS_READ) as primary_mm,
            mmap.mmap(base_file.fileno(), 0, access=mmap.ACCESS_READ) as base_mm,
            mmap.mmap(output_file.fileno(), 0, access=mmap.ACCESS_READ) as output_mm,
        ):
            by_name = {rec["name"]: rec for rec in records}
            for name in expected_names:
                rec = by_name[name]
                source_role = rec.get("source_role")
                source_model = base_model if source_role == "base_sidecar" else primary_model
                source_mm = base_mm if source_role == "base_sidecar" else primary_mm
                if name not in source_model.tensors:
                    raise ValueError(f"runtime extension source tensor missing: {name}")
                src = source_model.tensors[name]
                out = out_model.tensors[name]
                if src.offset != rec["source_offset"] or out.offset != rec["output_offset"]:
                    raise ValueError(f"runtime extension offset mismatch for {name}")
                if out.type_id != rec["output_type_id"]:
                    raise ValueError(f"runtime extension type mismatch for {name}")
                if _sha256_payload(source_mm, source_model, src) != rec["source_sha256"]:
                    raise ValueError(f"runtime extension source hash mismatch for {name}")
                if _sha256_payload(output_mm, out_model, out) != rec["output_sha256"]:
                    raise ValueError(f"runtime extension output hash mismatch for {name}")
                action = rec.get("action")
                if action in {"reuse_q1_byte_identical_from_base", "copy_primary_byte_identical"}:
                    if rec["source_sha256"] != rec["output_sha256"]:
                        raise ValueError(f"runtime extension byte-identical copy mismatch for {name}")
                elif action == "convert_primary_iq2_or_q2_to_q1_0":
                    if rec["output_type_id"] != Q1_TYPE_ID:
                        raise ValueError(f"runtime extension converted tensor is not Q1_0: {name}")
                else:
                    raise ValueError(f"unknown runtime extension tensor action {action}")
    return obj


def runtime_plan_to_json(plan: RuntimeSidecarPlan) -> dict[str, object]:
    obj = asdict(plan)
    obj["source"] = str(plan.source)
    obj["output"] = str(plan.output)
    obj["manifest"] = str(plan.manifest)
    obj["layers"] = list(plan.layers)
    return obj


def runtime_extension_plan_to_json(plan: RuntimeSidecarExtensionPlan) -> dict[str, object]:
    obj = asdict(plan)
    obj["primary"] = str(plan.primary)
    obj["base_sidecar"] = str(plan.base_sidecar)
    obj["output"] = str(plan.output)
    obj["manifest"] = str(plan.manifest)
    obj["layers"] = list(plan.layers)
    return obj


def validate_manifest(source: Path, sidecar: Path, manifest: Path) -> dict[str, object]:
    obj = json.loads(manifest.read_text(encoding="utf-8"))
    if obj.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    if not obj.get("derived"):
        raise ValueError("manifest must mark sidecar as derived")
    if obj["source"]["sha256"] != hashlib.sha256(source.read_bytes()).hexdigest():
        raise ValueError("source hash mismatch")
    if obj["sidecar"]["sha256"] != hashlib.sha256(sidecar.read_bytes()).hexdigest():
        raise ValueError("sidecar hash mismatch")
    source_tensors, _data_start, _data = _parse_synthetic_gguf(source)
    sidecar_tensors = read_synthetic_q1_gguf(sidecar)
    manifest_tensors = obj.get("tensors", [])
    if len(manifest_tensors) != len(source_tensors) or len(sidecar_tensors) != len(source_tensors):
        raise ValueError("tensor count mismatch")
    for src, q1, rec in zip(source_tensors, sidecar_tensors, manifest_tensors):
        if src.name != q1.name or src.name != rec["name"]:
            raise ValueError("tensor identity mismatch")
        if src.offset != rec["source_offset"] or q1.offset != rec["q1_offset"]:
            raise ValueError("tensor offset mismatch")
        if rec["q1_type_id"] != Q1_TYPE_ID or q1.type_id != Q1_TYPE_ID:
            raise ValueError("Q1 type mismatch")
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    make = sub.add_parser("write-source-fixture")
    make.add_argument("path")
    make.add_argument("--experts", type=int, default=2)
    conv = sub.add_parser("convert")
    conv.add_argument("source")
    conv.add_argument("sidecar")
    conv.add_argument("manifest")
    val = sub.add_parser("validate")
    val.add_argument("source")
    val.add_argument("sidecar")
    val.add_argument("manifest")
    est = sub.add_parser("estimate-runtime")
    est.add_argument("source")
    est.add_argument("sidecar")
    est.add_argument("manifest")
    est.add_argument("--layer", type=int, default=42)
    est_range = sub.add_parser("estimate-runtime-layer-range")
    est_range.add_argument("source")
    est_range.add_argument("sidecar")
    est_range.add_argument("manifest")
    est_range.add_argument("--layer-first", type=int, default=3)
    est_range.add_argument("--layer-last", type=int, default=42)
    rconv = sub.add_parser("convert-runtime-single-layer")
    rconv.add_argument("source")
    rconv.add_argument("sidecar")
    rconv.add_argument("manifest")
    rconv.add_argument("--layer", type=int, default=42)
    rconv_range = sub.add_parser("convert-runtime-layer-range")
    rconv_range.add_argument("source")
    rconv_range.add_argument("sidecar")
    rconv_range.add_argument("manifest")
    rconv_range.add_argument("--layer-first", type=int, default=3)
    rconv_range.add_argument("--layer-last", type=int, default=42)
    ext_est = sub.add_parser("estimate-extend-runtime-layer-range")
    ext_est.add_argument("primary")
    ext_est.add_argument("base_sidecar")
    ext_est.add_argument("sidecar")
    ext_est.add_argument("manifest")
    ext_est.add_argument("--convert-layer-first", type=int, default=0)
    ext_est.add_argument("--convert-layer-last", type=int, default=2)
    ext_est.add_argument("--base-layer-first", type=int, default=3)
    ext_est.add_argument("--base-layer-last", type=int, default=42)
    ext = sub.add_parser("extend-runtime-layer-range")
    ext.add_argument("primary")
    ext.add_argument("base_sidecar")
    ext.add_argument("sidecar")
    ext.add_argument("manifest")
    ext.add_argument("--convert-layer-first", type=int, default=0)
    ext.add_argument("--convert-layer-last", type=int, default=2)
    ext.add_argument("--base-layer-first", type=int, default=3)
    ext.add_argument("--base-layer-last", type=int, default=42)
    rval = sub.add_parser("validate-runtime")
    rval.add_argument("source")
    rval.add_argument("sidecar")
    rval.add_argument("manifest")
    ext_val = sub.add_parser("validate-runtime-extension")
    ext_val.add_argument("primary")
    ext_val.add_argument("base_sidecar")
    ext_val.add_argument("sidecar")
    ext_val.add_argument("manifest")
    args = parser.parse_args()
    if args.cmd == "write-source-fixture":
        tensors = write_synthetic_iq2_fixture(Path(args.path), experts=args.experts)
        print(json.dumps({"tensors": [asdict(t) for t in tensors]}, indent=2, sort_keys=True))
    elif args.cmd == "convert":
        print(json.dumps(convert_synthetic_iq2_to_q1(Path(args.source), Path(args.sidecar), Path(args.manifest)), indent=2, sort_keys=True))
    elif args.cmd == "validate":
        print(json.dumps(validate_manifest(Path(args.source), Path(args.sidecar), Path(args.manifest)), indent=2, sort_keys=True))
    elif args.cmd == "estimate-runtime":
        print(json.dumps(runtime_plan_to_json(estimate_runtime_sidecar_plan(Path(args.source), Path(args.sidecar), Path(args.manifest), layer=args.layer)), indent=2, sort_keys=True))
    elif args.cmd == "estimate-runtime-layer-range":
        print(json.dumps(runtime_plan_to_json(estimate_runtime_layer_range_sidecar_plan(Path(args.source), Path(args.sidecar), Path(args.manifest), layer_first=args.layer_first, layer_last=args.layer_last)), indent=2, sort_keys=True))
    elif args.cmd == "convert-runtime-single-layer":
        print(json.dumps(convert_runtime_valid_single_layer_sidecar(Path(args.source), Path(args.sidecar), Path(args.manifest), layer=args.layer), indent=2, sort_keys=True))
    elif args.cmd == "convert-runtime-layer-range":
        print(json.dumps(convert_runtime_valid_layer_range_sidecar(Path(args.source), Path(args.sidecar), Path(args.manifest), layer_first=args.layer_first, layer_last=args.layer_last), indent=2, sort_keys=True))
    elif args.cmd == "validate-runtime":
        print(json.dumps(validate_runtime_sidecar_manifest(Path(args.source), Path(args.sidecar), Path(args.manifest)), indent=2, sort_keys=True))
    elif args.cmd == "estimate-extend-runtime-layer-range":
        print(json.dumps(runtime_extension_plan_to_json(estimate_runtime_extension_layer_range_plan(Path(args.primary), Path(args.base_sidecar), Path(args.sidecar), Path(args.manifest), convert_layer_first=args.convert_layer_first, convert_layer_last=args.convert_layer_last, base_layer_first=args.base_layer_first, base_layer_last=args.base_layer_last)), indent=2, sort_keys=True))
    elif args.cmd == "extend-runtime-layer-range":
        print(json.dumps(convert_runtime_extension_layer_range_sidecar(Path(args.primary), Path(args.base_sidecar), Path(args.sidecar), Path(args.manifest), convert_layer_first=args.convert_layer_first, convert_layer_last=args.convert_layer_last, base_layer_first=args.base_layer_first, base_layer_last=args.base_layer_last), indent=2, sort_keys=True))
    elif args.cmd == "validate-runtime-extension":
        print(json.dumps(validate_runtime_extension_manifest(Path(args.primary), Path(args.base_sidecar), Path(args.sidecar), Path(args.manifest)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
