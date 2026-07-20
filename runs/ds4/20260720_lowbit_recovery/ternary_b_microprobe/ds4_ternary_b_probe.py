#!/usr/bin/env python3
"""
CPU-only DS4 single-expert ternary-B plausibility micro-probe.

Read-only by design:
- parses GGUF metadata and reads exactly one expert's gate/up/down byte ranges;
- does not copy or rewrite GGUFs;
- dequantizes only the selected expert in memory.

Decoder provenance:
- GGUF directory parsing follows the local ds4_iq1_s_bench.cu parser shape.
- IQ2_XXS/Q2_K layouts and math are transcribed from local ds4.c / ds4_cuda.cu.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import numpy as np


TYPE_Q2_K = 10
TYPE_IQ2_XXS = 16
TYPE_Q1_0 = 41
TYPE_NAMES = {TYPE_Q2_K: "Q2_K", TYPE_IQ2_XXS: "IQ2_XXS", TYPE_Q1_0: "Q1_0"}
QK_K = 256
N_EMBD = 4096
N_FF_EXP = 2048
N_EXPERT = 256


@dataclass(frozen=True)
class TensorInfo:
    name: str
    dims: tuple[int, ...]
    type_id: int
    rel_offset: int
    nbytes: int
    physical_offset: int


def read_exact(f: BinaryIO, n: int, what: str) -> bytes:
    b = f.read(n)
    if len(b) != n:
        raise RuntimeError(f"short read for {what}: wanted {n}, got {len(b)}")
    return b


def read_u32(f: BinaryIO, what: str) -> int:
    return struct.unpack("<I", read_exact(f, 4, what))[0]


def read_u64(f: BinaryIO, what: str) -> int:
    return struct.unpack("<Q", read_exact(f, 8, what))[0]


def read_str(f: BinaryIO) -> str:
    n = read_u64(f, "GGUF string length")
    if n > 1 << 24:
        raise RuntimeError(f"GGUF string too large: {n}")
    return read_exact(f, n, "GGUF string").decode("utf-8")


def scalar_size(type_id: int) -> int | None:
    return {
        0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1,
        10: 8, 11: 8, 12: 8,
    }.get(type_id)


def skip_value(f: BinaryIO, type_id: int, depth: int = 0) -> None:
    if depth > 8:
        raise RuntimeError("GGUF metadata nesting too deep")
    if type_id == 8:
        _ = read_str(f)
        return
    if type_id == 9:
        item_type = read_u32(f, "GGUF array type")
        n = read_u64(f, "GGUF array length")
        ss = scalar_size(item_type)
        if ss is not None:
            f.seek(n * ss, 1)
        elif item_type == 8:
            for _ in range(n):
                _ = read_str(f)
        else:
            for _ in range(n):
                skip_value(f, item_type, depth + 1)
        return
    ss = scalar_size(type_id)
    if ss is None:
        raise RuntimeError(f"unsupported GGUF metadata type {type_id}")
    f.seek(ss, 1)


def tensor_nbytes(type_id: int, elements: int) -> int:
    if type_id == TYPE_IQ2_XXS:
        return (elements // 256) * 66
    if type_id == TYPE_Q2_K:
        return (elements // 256) * 84
    if type_id == TYPE_Q1_0:
        return (elements // 128) * 18
    raise RuntimeError(f"unsupported tensor type in probe: {type_id}")


def parse_gguf(path: Path) -> tuple[dict[str, TensorInfo], int, int]:
    size = path.stat().st_size
    with path.open("rb") as f:
        if read_exact(f, 4, "GGUF magic") != b"GGUF":
            raise RuntimeError("not a GGUF file")
        version = read_u32(f, "GGUF version")
        if version != 3:
            raise RuntimeError(f"unsupported GGUF version {version}")
        n_tensors = read_u64(f, "GGUF tensor count")
        n_kv = read_u64(f, "GGUF metadata count")
        if n_tensors > 100000 or n_kv > 100000:
            raise RuntimeError("unreasonable GGUF header counts")
        alignment = 32
        for _ in range(n_kv):
            key = read_str(f)
            type_id = read_u32(f, "GGUF metadata type")
            if key == "general.alignment" and type_id == 4:
                alignment = read_u32(f, "GGUF alignment")
            else:
                skip_value(f, type_id)
        tensors_raw = []
        for _ in range(n_tensors):
            name = read_str(f)
            nd = read_u32(f, "GGUF tensor rank")
            if nd < 1 or nd > 4:
                raise RuntimeError(f"bad tensor rank for {name}: {nd}")
            dims = tuple(read_u64(f, "GGUF tensor dim") for _ in range(nd))
            type_id = read_u32(f, "GGUF tensor type")
            rel = read_u64(f, "GGUF tensor offset")
            elements = math.prod(dims)
            nbytes = tensor_nbytes(type_id, elements) if type_id in TYPE_NAMES else 0
            tensors_raw.append((name, dims, type_id, rel, nbytes))
        header_end = f.tell()
        data_base = ((header_end + alignment - 1) // alignment) * alignment
    out: dict[str, TensorInfo] = {}
    for name, dims, type_id, rel, nbytes in tensors_raw:
        phys = data_base + rel
        if nbytes and phys + nbytes > size:
            raise RuntimeError(f"tensor extent outside file: {name}")
        out[name] = TensorInfo(name, dims, type_id, rel, nbytes, phys)
    return out, data_base, alignment


def f16(bits: int) -> np.float32:
    return np.frombuffer(struct.pack("<H", bits), dtype=np.float16)[0].astype(np.float32)


def parse_c_array_u64(ds4_c: Path, name: str) -> np.ndarray:
    text = ds4_c.read_text(encoding="utf-8", errors="replace")
    m = re.search(rf"static const uint64_t {re.escape(name)}\[256\] = \{{(.*?)\}};", text, re.S)
    if not m:
        raise RuntimeError(f"could not find {name} in {ds4_c}")
    vals = [int(tok.strip(), 0) for tok in m.group(1).replace("\n", " ").split(",") if tok.strip()]
    if len(vals) != 256:
        raise RuntimeError(f"{name} length {len(vals)} != 256")
    arr = np.zeros((256, 8), dtype=np.float32)
    for g, v in enumerate(vals):
        for i in range(8):
            arr[g, i] = float((v >> (8 * i)) & 0xFF)
    return arr


def parse_c_array_u8(ds4_c: Path, name: str, n: int) -> np.ndarray:
    text = ds4_c.read_text(encoding="utf-8", errors="replace")
    m = re.search(rf"static const uint8_t {re.escape(name)}\[{n}\] = \{{(.*?)\}};", text, re.S)
    if not m:
        raise RuntimeError(f"could not find {name} in {ds4_c}")
    vals = [int(tok.strip(), 0) for tok in m.group(1).replace("\n", " ").split(",") if tok.strip()]
    if len(vals) != n:
        raise RuntimeError(f"{name} length {len(vals)} != {n}")
    return np.array(vals, dtype=np.uint8)


def dequant_iq2_xxs(payload: bytes, grid: np.ndarray, signs_table: np.ndarray) -> np.ndarray:
    if len(payload) % 66:
        raise RuntimeError("IQ2_XXS payload is not block-aligned")
    nblocks = len(payload) // 66
    out = np.empty(nblocks * 256, dtype=np.float32)
    for b in range(nblocks):
        block = payload[b * 66:(b + 1) * 66]
        d = float(f16(struct.unpack_from("<H", block, 0)[0]))
        qs = block[2:]
        pos = b * 256
        for ib32 in range(8):
            aux_g = struct.unpack_from("<I", qs, ib32 * 8 + 0)[0]
            aux_s = struct.unpack_from("<I", qs, ib32 * 8 + 4)[0]
            dl = d * (0.5 + float(aux_s >> 28)) * 0.25
            grids = [(aux_g >> (8 * i)) & 0xFF for i in range(4)]
            for half in range(2):
                for gg in range(2):
                    gi = half * 2 + gg
                    signs = int(signs_table[(aux_s >> (14 * half + 7 * gg)) & 127])
                    values = grid[grids[gi]].copy()
                    for lane in range(8):
                        if signs & (1 << lane):
                            values[lane] = -values[lane]
                    start = pos + ib32 * 32 + half * 16 + gg * 8
                    out[start:start + 8] = dl * values
    return out


def dequant_q2_k(payload: bytes) -> np.ndarray:
    if len(payload) % 84:
        raise RuntimeError("Q2_K payload is not block-aligned")
    nblocks = len(payload) // 84
    out = np.empty(nblocks * 256, dtype=np.float32)
    for b in range(nblocks):
        block = payload[b * 84:(b + 1) * 84]
        scales = block[0:16]
        qs = block[16:80]
        d = float(f16(struct.unpack_from("<H", block, 80)[0]))
        dmin = float(f16(struct.unpack_from("<H", block, 82)[0]))
        pos = b * 256
        for il in range(16):
            chunk = il // 8
            pair = il & 1
            shift = ((il // 2) & 3) * 2
            sc = scales[il]
            dl = d * float(sc & 0x0F)
            ml = dmin * float(sc >> 4)
            qoff = 32 * chunk + 16 * pair
            xoff = pos + chunk * 128 + ((il % 8) // 2) * 32 + pair * 16
            q = np.frombuffer(qs[qoff:qoff + 16], dtype=np.uint8).astype(np.float32)
            out[xoff:xoff + 16] = dl * ((q.astype(np.uint8) >> shift) & 3).astype(np.float32) - ml
    return out


def dequant_q1_0(payload: bytes) -> np.ndarray:
    if len(payload) % 18:
        raise RuntimeError("Q1_0 payload is not block-aligned")
    nblocks = len(payload) // 18
    out = np.empty(nblocks * 128, dtype=np.float32)
    for b in range(nblocks):
        block = payload[b * 18:(b + 1) * 18]
        d = float(f16(struct.unpack_from("<H", block, 0)[0]))
        qs = np.frombuffer(block[2:18], dtype=np.uint8)
        bits = np.unpackbits(qs, bitorder="little").astype(np.float32)
        out[b * 128:(b + 1) * 128] = d * (2.0 * bits - 1.0)
    return out


def self_test_decoders(grid: np.ndarray, signs_table: np.ndarray) -> dict:
    one = struct.pack("<H", np.float16(1.0).view(np.uint16).item())
    iq2_block = one + (b"\x00" * 64)
    iq2 = dequant_iq2_xxs(iq2_block, grid, signs_table)
    q2_block = bytearray(84)
    q2_block[0:16] = bytes([0x21] * 16)
    q2_block[16:80] = bytes([0xFF] * 64)
    struct.pack_into("<H", q2_block, 80, np.float16(1.0).view(np.uint16).item())
    struct.pack_into("<H", q2_block, 82, np.float16(0.5).view(np.uint16).item())
    q2 = dequant_q2_k(bytes(q2_block))
    q1_block = one + bytes([0xAA] * 16)
    q1 = dequant_q1_0(q1_block)
    q1_expected = np.tile(np.array([-1.0, 1.0], dtype=np.float32), 64)
    ok = bool(np.allclose(iq2, 1.0) and np.allclose(q2, 2.0) and np.allclose(q1, q1_expected))
    if not ok:
        raise RuntimeError("synthetic decoder self-test failed")
    return {
        "iq2_all_one_max_abs": float(np.max(np.abs(iq2 - 1.0))),
        "q2_all_two_max_abs": float(np.max(np.abs(q2 - 2.0))),
        "q1_alternating_max_abs": float(np.max(np.abs(q1 - q1_expected))),
        "pass": True,
    }


def expert_payload(f: BinaryIO, t: TensorInfo, expert: int) -> tuple[bytes, int, int, int]:
    if t.name.endswith("ffn_down_exps.weight"):
        rows, cols = N_EMBD, N_FF_EXP
    else:
        rows, cols = N_FF_EXP, N_EMBD
    if t.type_id == TYPE_IQ2_XXS:
        block_elems, block_bytes = 256, 66
    elif t.type_id == TYPE_Q2_K:
        block_elems, block_bytes = 256, 84
    elif t.type_id == TYPE_Q1_0:
        block_elems, block_bytes = 128, 18
    else:
        raise RuntimeError(f"unsupported expert tensor type: {t.type_id}")
    row_bytes = (cols // block_elems) * block_bytes
    expert_bytes = rows * row_bytes
    expected_dims = (cols, rows, N_EXPERT)
    if t.dims != expected_dims:
        raise RuntimeError(f"shape mismatch for {t.name}: got {t.dims}, expected {expected_dims}")
    off = t.physical_offset + expert * expert_bytes
    f.seek(off)
    payload = read_exact(f, expert_bytes, t.name)
    return payload, off, row_bytes, expert_bytes


def entropy_ternary(zero_frac: float) -> float:
    z = min(max(zero_frac, 0.0), 1.0)
    p = 1.0 - z
    h = 0.0
    if z > 0:
        h -= z * math.log2(z)
    if p > 0:
        h -= p * math.log2(p / 2.0)
    return h


def topk_ternary_metrics(x: np.ndarray, k: int, target_bpw: float) -> dict:
    groups = x.reshape(-1, 128)
    n_groups = groups.shape[0]
    if k <= 0:
        q = np.zeros_like(groups)
        scales = np.zeros(n_groups, dtype=np.float32)
    elif k >= 128:
        scales = np.mean(np.abs(groups), axis=1).astype(np.float32)
        q = np.sign(groups) * scales[:, None]
    else:
        a = np.abs(groups)
        top_idx = np.argpartition(a, 128 - k, axis=1)[:, 128 - k:]
        mask = np.zeros_like(groups, dtype=bool)
        np.put_along_axis(mask, top_idx, True, axis=1)
        counts = mask.sum(axis=1).astype(np.float32)
        scales = (a * mask).sum(axis=1) / np.maximum(counts, 1.0)
        q = np.sign(groups) * mask * scales[:, None]
    flat_q = q.reshape(-1)
    xf = x.astype(np.float64, copy=False)
    qf = flat_q.astype(np.float64, copy=False)
    dot = float(np.dot(xf, qf))
    x2 = float(np.dot(xf, xf))
    q2 = float(np.dot(qf, qf))
    err = xf - qf
    zero_frac = 1.0 - float(np.count_nonzero(flat_q)) / float(flat_q.size)
    return {
        "target_bpw": target_bpw,
        "k_nonzero_per_g128": k,
        "zero_frac": zero_frac,
        "entropy_ideal_bpw_plus_scale": entropy_ternary(zero_frac) + 0.125,
        "mask_sign_bpw_plus_scale": 2.125 - zero_frac,
        "base3_A_bpw": 1.7265625,
        "cosine": dot / math.sqrt(max(x2 * q2, 1e-30)),
        "nmse": float(np.dot(err, err) / max(x2, 1e-30)),
        "max_abs_error": float(np.max(np.abs(err))),
    }


def summarize_tensor(name: str, x: np.ndarray) -> dict:
    targets = [1.725, 1.50, 1.30, 1.15]
    curves = []
    for target in targets:
        k = max(0, min(128, int(math.floor((target - 1.125) * 128.0 + 1e-9))))
        curves.append(topk_ternary_metrics(x, k, target))
    return {
        "name": name,
        "values": int(x.size),
        "teacher_l2": float(np.linalg.norm(x.astype(np.float64))),
        "teacher_abs_max": float(np.max(np.abs(x))),
        "curves": curves,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=r"C:\ds4-models\ds4-2bit.gguf")
    ap.add_argument("--ds4-c", default=r"C:\Users\imanu\Documents\Codex\2026-07-07\cia\work\ds4-win-publish-g126-20260718-v2\ds4.c")
    ap.add_argument("--layer", type=int, default=3)
    ap.add_argument("--expert", type=int, default=0)
    ap.add_argument("--out", default="receipt.json")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    started = time.time()
    model = Path(args.model)
    ds4_c = Path(args.ds4_c)
    grid = parse_c_array_u64(ds4_c, "iq2xxs_grid")
    signs = parse_c_array_u8(ds4_c, "ksigns_iq2xs", 128)
    self_test = self_test_decoders(grid, signs)
    if args.self_test:
        print(json.dumps({"self_test": self_test}, indent=2))
        return 0

    if not (0 <= args.layer < 43 and 0 <= args.expert < 256):
        raise RuntimeError("layer/expert outside DS4 bounds")
    tensors, data_base, alignment = parse_gguf(model)
    wanted = {
        "gate": f"blk.{args.layer}.ffn_gate_exps.weight",
        "up": f"blk.{args.layer}.ffn_up_exps.weight",
        "down": f"blk.{args.layer}.ffn_down_exps.weight",
    }
    missing = [n for n in wanted.values() if n not in tensors]
    if missing:
        raise RuntimeError(f"missing tensors: {missing}")

    receipt = {
        "schema": "ds4_ternary_b_single_expert_probe_v1",
        "mode": "CPU-only read-only single expert",
        "model": {"path": str(model), "bytes": model.stat().st_size, "sha256_scope": "selected expert payloads only"},
        "selection": {
            "rule": "first non-hash routed layer after DS4_N_HASH_LAYER=3, expert 0",
            "layer": args.layer,
            "expert": args.expert,
        },
        "sources": {
            "gguf_parser": "local ds4_iq1_s_bench.cu parser pattern, reimplemented narrow in this workspace",
            "dequant": "transcribed from local ds4.c/ds4_cuda.cu IQ2_XXS/Q2_K layouts and dot_f32 math",
            "ds4_c": str(ds4_c),
        },
        "self_test": self_test,
        "gguf": {"data_base": data_base, "alignment": alignment},
        "phase0": {"status": "PASS", "tensors": {}},
        "phase1": {"status": "PASS", "note": "weight-domain baseline only; no activation traces used", "tensors": {}},
    }

    deq_parts = []
    with model.open("rb") as f:
        for role, name in wanted.items():
            t = tensors[name]
            payload, off, row_bytes, expert_bytes = expert_payload(f, t, args.expert)
            sha = hashlib.sha256(payload).hexdigest()
            receipt["phase0"]["tensors"][role] = {
                "name": name,
                "dtype": TYPE_NAMES[t.type_id],
                "type_id": t.type_id,
                "shape": list(t.dims),
                "tensor_physical_offset": t.physical_offset,
                "expert_physical_offset": off,
                "row_bytes": row_bytes,
                "expert_bytes": expert_bytes,
                "payload_sha256": sha,
            }
            if t.type_id == TYPE_IQ2_XXS:
                x = dequant_iq2_xxs(payload, grid, signs)
            elif t.type_id == TYPE_Q2_K:
                x = dequant_q2_k(payload)
            else:
                raise RuntimeError(f"unexpected type for {name}: {t.type_id}")
            expected_values = N_EMBD * N_FF_EXP
            if x.size != expected_values:
                raise RuntimeError(f"dequant size mismatch for {name}: {x.size}")
            deq_parts.append(x)
            receipt["phase1"]["tensors"][role] = summarize_tensor(role, x)

    expert = np.concatenate(deq_parts)
    receipt["phase1"]["expert"] = summarize_tensor("expert_gate_up_down_concat", expert)
    receipt["elapsed_seconds"] = time.time() - started
    out = Path(args.out)
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "receipt": str(out), "elapsed_seconds": receipt["elapsed_seconds"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
