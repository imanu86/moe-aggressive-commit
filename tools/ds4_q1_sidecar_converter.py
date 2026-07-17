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
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

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

SYNTHETIC_IQ2_TYPE_ID = 16
MANIFEST_SCHEMA = "ds4_q1_0_sidecar_manifest_v1"


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


def _tensor_nbytes(dims: Iterable[int], type_id: int) -> int:
    elems = math.prod(tuple(dims))
    if type_id == Q1_TYPE_ID:
        if elems % Q1_BLOCK_WEIGHTS:
            raise ValueError("Q1_0 tensor is not block aligned")
        return elems // Q1_BLOCK_WEIGHTS * Q1_BLOCK_BYTES
    if type_id == SYNTHETIC_IQ2_TYPE_ID:
        return elems * 2
    raise ValueError(f"unsupported synthetic type {type_id}")


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
    args = parser.parse_args()
    if args.cmd == "write-source-fixture":
        tensors = write_synthetic_iq2_fixture(Path(args.path), experts=args.experts)
        print(json.dumps({"tensors": [asdict(t) for t in tensors]}, indent=2, sort_keys=True))
    elif args.cmd == "convert":
        print(json.dumps(convert_synthetic_iq2_to_q1(Path(args.source), Path(args.sidecar), Path(args.manifest)), indent=2, sort_keys=True))
    elif args.cmd == "validate":
        print(json.dumps(validate_manifest(Path(args.source), Path(args.sidecar), Path(args.manifest)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
