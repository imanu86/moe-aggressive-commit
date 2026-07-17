"""Synthetic DS4 Q1_0 sidecar converter and validator.

This tool deliberately works only on tiny synthetic fixtures. It models the
deterministic path `IQ2/Q2 -> float -> Q1_0` for metadata, offset, provenance,
and hash validation, but it is not quality-optimal and must not be used as an
accuracy claim for a real DS4 model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import mmap
import struct
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
    source: Path
    output: Path
    manifest: Path
    tensors_to_copy: tuple[str, ...]
    tensors_to_convert: tuple[str, ...]
    estimated_read_bytes: int
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


def _int16_payload_to_q1(payload: bytes, dims: tuple[int, ...]) -> bytes:
    elems = math.prod(dims)
    if elems * 2 != len(payload):
        raise ValueError("synthetic int16 payload size mismatch")
    values = [struct.unpack_from("<h", payload, i * 2)[0] / 2048.0 for i in range(elems)]
    out = bytearray()
    for block_start in range(0, elems, Q1_BLOCK_WEIGHTS):
        out += quantize_q1_0(values[block_start : block_start + Q1_BLOCK_WEIGHTS]).pack()
    return bytes(out)


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


def runtime_sidecar_tensor_names(layer: int, n_layers: int = 43) -> tuple[list[str], list[str]]:
    if not (3 <= layer <= 42):
        raise ValueError("runtime Q1_0 sidecar target layer must be in 3..42")
    copy_names: list[str] = []
    for il in range(n_layers):
        for suffix in RUNTIME_COPY_TENSOR_SUFFIXES:
            copy_names.append(f"blk.{il}.{suffix}")
    for il in range(3, 43):
        copy_names.append(f"blk.{il}.{RUNTIME_COPY_ROUTED_SUFFIX}")
    convert_names = [
        f"blk.{layer}.{suffix}" for suffix in RUNTIME_ROUTED_SUFFIXES.values()
    ]
    return copy_names, convert_names


def estimate_runtime_sidecar_plan(
    source: Path,
    output: Path,
    manifest: Path,
    layer: int = 3,
) -> RuntimeSidecarPlan:
    copy_names, convert_names = runtime_sidecar_tensor_names(layer)
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
        source=source,
        output=output,
        manifest=manifest,
        tensors_to_copy=tuple(copy_names),
        tensors_to_convert=tuple(convert_names),
        estimated_read_bytes=read_bytes,
        estimated_output_bytes=output_bytes,
    )


def _runtime_conversion_preflight(model: GgufModel, tensor_names: Sequence[str]) -> None:
    unsupported = [
        (name, model.tensors[name].type_id)
        for name in tensor_names
        if model.tensors[name].type_id != SYNTHETIC_IQ2_TYPE_ID
    ]
    if unsupported:
        detail = ", ".join(f"{name}:type{type_id}" for name, type_id in unsupported)
        raise ValueError(f"{REAL_DEQUANT_BLOCKED_MESSAGE}; unsupported={detail}")


def convert_runtime_valid_single_layer_sidecar(
    source: Path,
    output: Path,
    manifest: Path,
    layer: int = 3,
) -> dict[str, object]:
    plan = estimate_runtime_sidecar_plan(source, output, manifest, layer)
    model = parse_gguf_header(source)
    _runtime_conversion_preflight(model, plan.tensors_to_convert)
    metadata = _required_runtime_metadata(model)
    write_tensors: list[GgufWriteTensor] = []
    records: list[RuntimeTensorManifest] = []
    with source.open("rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            for name in list(plan.tensors_to_copy) + list(plan.tensors_to_convert):
                info = model.tensors[name]
                source_payload = _tensor_payload(mm, model, info)
                source_sha = hashlib.sha256(source_payload).hexdigest()
                if name in plan.tensors_to_convert:
                    output_type = Q1_TYPE_ID
                    output_payload = _int16_payload_to_q1(source_payload, info.dims)
                    action = "convert_iq2_or_q2_to_q1_0"
                else:
                    output_type = info.type_id
                    output_payload = source_payload
                    action = "copy_byte_identical"
                output_offset = sum(_align(len(t.payload)) for t in write_tensors)
                write_tensors.append(GgufWriteTensor(name, info.dims, output_type, output_payload))
                records.append(
                    RuntimeTensorManifest(
                        name=name,
                        action=action,
                        source_type_id=info.type_id,
                        output_type_id=output_type,
                        dims=info.dims,
                        source_offset=info.offset,
                        source_nbytes=info.nbytes,
                        output_offset=output_offset,
                        output_nbytes=len(output_payload),
                        source_sha256=source_sha,
                        output_sha256=hashlib.sha256(output_payload).hexdigest(),
                    )
                )
    written = write_gguf(output, metadata, write_tensors)
    written_by_name = {t.name: t for t in written}
    adjusted: list[RuntimeTensorManifest] = []
    for rec in records:
        actual = written_by_name[rec.name]
        adjusted.append(
            RuntimeTensorManifest(
                name=rec.name,
                action=rec.action,
                source_type_id=rec.source_type_id,
                output_type_id=rec.output_type_id,
                dims=rec.dims,
                source_offset=rec.source_offset,
                source_nbytes=rec.source_nbytes,
                output_offset=actual.offset,
                output_nbytes=actual.nbytes,
                source_sha256=rec.source_sha256,
                output_sha256=rec.output_sha256,
            )
        )
    obj: dict[str, object] = {
        "schema": RUNTIME_MANIFEST_SCHEMA,
        "layer": layer,
        "derived_from_IQ2": True,
        "not_quality_optimal": True,
        "quality_note": "deterministic IQ2XXS/Q2_K-style int16 fixture dequant -> float -> Q1_0; not quality-optimal",
        "source": {"path": str(source), "size": model.size},
        "output": {
            "path": str(output),
            "size": output.stat().st_size,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        },
        "estimated_read_bytes": plan.estimated_read_bytes,
        "estimated_output_bytes": plan.estimated_output_bytes,
        "metadata": [
            {"key": m.key, "value_type": m.value_type, "value": m.value}
            for m in metadata
        ],
        "tensors": [asdict(t) for t in adjusted],
        "full_quality_path": "rebuild Q1_0 from richer checkpoint/original precision weights, not from IQ2-derived values",
        "blocked_real_dequant_source": REAL_DEQUANT_PRIMARY_SOURCE,
    }
    manifest.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validate_runtime_sidecar_manifest(source, output, manifest)
    return obj


def validate_runtime_sidecar_manifest(source: Path, output: Path, manifest: Path) -> dict[str, object]:
    obj = json.loads(manifest.read_text(encoding="utf-8"))
    if obj.get("schema") != RUNTIME_MANIFEST_SCHEMA:
        raise ValueError("unexpected runtime manifest schema")
    if obj.get("derived_from_IQ2") is not True or obj.get("not_quality_optimal") is not True:
        raise ValueError("runtime sidecar must be marked derived and not quality-optimal")
    model = parse_gguf_header(source)
    sidecar = parse_gguf_header(output)
    if "general.name" not in sidecar.metadata or sidecar.metadata["general.name"].value != model.metadata["general.name"].value:
        raise ValueError("general.name provenance mismatch")
    records = obj.get("tensors", [])
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


def runtime_plan_to_json(plan: RuntimeSidecarPlan) -> dict[str, object]:
    obj = asdict(plan)
    obj["source"] = str(plan.source)
    obj["output"] = str(plan.output)
    obj["manifest"] = str(plan.manifest)
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
    rconv = sub.add_parser("convert-runtime-single-layer")
    rconv.add_argument("source")
    rconv.add_argument("sidecar")
    rconv.add_argument("manifest")
    rconv.add_argument("--layer", type=int, default=42)
    rval = sub.add_parser("validate-runtime")
    rval.add_argument("source")
    rval.add_argument("sidecar")
    rval.add_argument("manifest")
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
    elif args.cmd == "convert-runtime-single-layer":
        print(json.dumps(convert_runtime_valid_single_layer_sidecar(Path(args.source), Path(args.sidecar), Path(args.manifest), layer=args.layer), indent=2, sort_keys=True))
    elif args.cmd == "validate-runtime":
        print(json.dumps(validate_runtime_sidecar_manifest(Path(args.source), Path(args.sidecar), Path(args.manifest)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
