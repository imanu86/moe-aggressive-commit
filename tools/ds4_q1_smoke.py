"""CPU-only smoke helpers for DS4 Q1_0 routed expert planning.

No model payloads are read here.  The helpers validate the Q1_0 type-41 block
accounting, deterministic synthetic pack/depack, dot indexing against DS4's
Q8_K-sized activation blocks, and a sparse residual index that points back to
the authoritative IQ2 tensors without keeping a full hot copy in RAM.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
from dataclasses import asdict, dataclass
from typing import Any, Iterable

GIB = 1024**3
MIB = 1024**2

DS4_N_LAYER = 43
DS4_ROUTED_LAYER_FIRST = 3
DS4_ROUTED_LAYER_COUNT = 40
DS4_N_EMBD = 4096
DS4_N_FF_EXP = 2048
DS4_N_EXPERT = 256

Q1_TYPE_ID = 41
Q1_BLOCK_WEIGHTS = 128
Q1_BLOCK_BYTES = 18
Q8K_BLOCK_WEIGHTS = 256

IQ2_XXS_BLOCK_BYTES = 66
Q2_K_BLOCK_BYTES = 84


@dataclass(frozen=True)
class Q1Block:
    """Synthetic block_q1_0: f16 scale plus 128 sign bits."""

    d: float
    bits: int

    def pack(self) -> bytes:
        return struct.pack("<e", self.d) + int(self.bits).to_bytes(16, "little")

    @staticmethod
    def unpack(payload: bytes) -> "Q1Block":
        if len(payload) != Q1_BLOCK_BYTES:
            raise ValueError(f"Q1_0 block must be {Q1_BLOCK_BYTES} bytes")
        d = struct.unpack("<e", payload[:2])[0]
        bits = int.from_bytes(payload[2:], "little")
        return Q1Block(float(d), bits)

    def signs(self) -> list[int]:
        return [1 if (self.bits >> i) & 1 else -1 for i in range(Q1_BLOCK_WEIGHTS)]

    def dequantize(self) -> list[float]:
        return [self.d * s for s in self.signs()]


@dataclass(frozen=True)
class Q8KBlock:
    """Small CPU representation of the activation layout needed for dot tests."""

    d: float
    qs: tuple[int, ...]
    bsums: tuple[int, ...]

    @staticmethod
    def from_values(values: Iterable[float]) -> "Q8KBlock":
        vals = list(values)
        if len(vals) != Q8K_BLOCK_WEIGHTS:
            raise ValueError("Q8_K synthetic block needs 256 values")
        amax = max(abs(v) for v in vals)
        scale = amax / 127.0 if amax else 1.0
        qs = tuple(max(-128, min(127, int(round(v / scale)))) for v in vals)
        bsums = tuple(sum(qs[i : i + 16]) for i in range(0, Q8K_BLOCK_WEIGHTS, 16))
        return Q8KBlock(scale, qs, bsums)


@dataclass(frozen=True)
class ExpertOffsets:
    layer: int
    expert: int
    q1_gate: int
    q1_up: int
    q1_down: int
    iq2_gate: int
    iq2_up: int
    iq2_down: int


@dataclass(frozen=True)
class ResidualEntry:
    layer: int
    expert: int
    tensor: str
    block_first: int
    block_count: int
    q1_offset: int
    iq2_offset: int
    residual_offset: int
    residual_bytes: int


def deterministic_values(n: int, seed: int = 17) -> list[float]:
    state = seed & 0xFFFFFFFF
    out: list[float] = []
    for i in range(n):
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        centered = (state % 2001) - 1000
        out.append(centered / 997.0 + 0.01 * math.sin(i * 0.37))
    return out


def quantize_q1_0(values: Iterable[float]) -> Q1Block:
    vals = list(values)
    if len(vals) != Q1_BLOCK_WEIGHTS:
        raise ValueError("Q1_0 synthetic quantizer expects 128 values")
    mean_abs = sum(abs(v) for v in vals) / Q1_BLOCK_WEIGHTS
    d = mean_abs if mean_abs > 0 else 1.0
    bits = 0
    for i, v in enumerate(vals):
        if v >= 0:
            bits |= 1 << i
    return Q1Block(d, bits)


def dot_q1_pair_against_q8k(low: Q1Block, high: Q1Block, x: Q8KBlock) -> float:
    """Dot two 128-weight Q1 blocks against one 256-value Q8_K block."""

    acc = 0.0
    for block_index, block in enumerate((low, high)):
        base = block_index * Q1_BLOCK_WEIGHTS
        signed_sum = 0
        sum_all = sum(x.bsums[block_index * 8 : block_index * 8 + 8])
        positive_sum = 0
        for i in range(Q1_BLOCK_WEIGHTS):
            if (block.bits >> i) & 1:
                positive_sum += x.qs[base + i]
        signed_sum = 2 * positive_sum - sum_all
        acc += block.d * x.d * signed_sum
    return acc


def reference_dot(q1_blocks: tuple[Q1Block, Q1Block], x: Q8KBlock) -> float:
    weights = q1_blocks[0].dequantize() + q1_blocks[1].dequantize()
    activations = [x.d * q for q in x.qs]
    return sum(w * a for w, a in zip(weights, activations))


def q1_row_bytes(input_dim: int) -> int:
    if input_dim % Q1_BLOCK_WEIGHTS != 0:
        raise ValueError("Q1_0 rows must be divisible by 128")
    return input_dim // Q1_BLOCK_WEIGHTS * Q1_BLOCK_BYTES


def q1_expert_bytes(input_dim: int, output_dim: int) -> int:
    return output_dim * q1_row_bytes(input_dim)


def current_iq2_row_bytes(input_dim: int, block_bytes: int) -> int:
    if input_dim % 256 != 0:
        raise ValueError("current DS4 rows must be divisible by 256")
    return input_dim // 256 * block_bytes


def current_expert_bytes(input_dim: int, output_dim: int, block_bytes: int) -> int:
    return output_dim * current_iq2_row_bytes(input_dim, block_bytes)


def routed_sizes() -> dict[str, Any]:
    q1_gate = q1_expert_bytes(DS4_N_EMBD, DS4_N_FF_EXP)
    q1_down = q1_expert_bytes(DS4_N_FF_EXP, DS4_N_EMBD)
    q1_expert = 2 * q1_gate + q1_down
    iq2_gate = current_expert_bytes(DS4_N_EMBD, DS4_N_FF_EXP, IQ2_XXS_BLOCK_BYTES)
    iq2_down = current_expert_bytes(DS4_N_FF_EXP, DS4_N_EMBD, Q2_K_BLOCK_BYTES)
    iq2_expert = 2 * iq2_gate + iq2_down
    return {
        "q1_type_id": Q1_TYPE_ID,
        "q1_block_weights": Q1_BLOCK_WEIGHTS,
        "q1_block_bytes": Q1_BLOCK_BYTES,
        "q1_bpw_effective": Q1_BLOCK_BYTES * 8 / Q1_BLOCK_WEIGHTS,
        "q1_gate_or_up_expert_bytes": q1_gate,
        "q1_down_expert_bytes": q1_down,
        "q1_expert_bytes": q1_expert,
        "q1_expert_mib": q1_expert / MIB,
        "q1_all_routed_gib": q1_expert * DS4_N_EXPERT * DS4_ROUTED_LAYER_COUNT / GIB,
        "current_iq2_expert_bytes": iq2_expert,
        "current_iq2_expert_mib": iq2_expert / MIB,
    }


def expert_offsets(layer: int, expert: int, q1_base: int = 0, iq2_base: int = 0) -> ExpertOffsets:
    if not (DS4_ROUTED_LAYER_FIRST <= layer < DS4_ROUTED_LAYER_FIRST + DS4_ROUTED_LAYER_COUNT):
        raise ValueError("only routed layers 3..42 are indexed")
    if not (0 <= expert < DS4_N_EXPERT):
        raise ValueError("expert must be in 0..255")
    sizes = routed_sizes()
    q1_gate = sizes["q1_gate_or_up_expert_bytes"]
    q1_down = sizes["q1_down_expert_bytes"]
    iq2_gate = current_expert_bytes(DS4_N_EMBD, DS4_N_FF_EXP, IQ2_XXS_BLOCK_BYTES)
    iq2_down = current_expert_bytes(DS4_N_FF_EXP, DS4_N_EMBD, Q2_K_BLOCK_BYTES)
    layer_slot = layer - DS4_ROUTED_LAYER_FIRST
    q1_layer_span = DS4_N_EXPERT * (2 * q1_gate + q1_down)
    iq2_layer_span = DS4_N_EXPERT * (2 * iq2_gate + iq2_down)
    q1_expert_base = q1_base + layer_slot * q1_layer_span + expert * (2 * q1_gate + q1_down)
    iq2_expert_base = iq2_base + layer_slot * iq2_layer_span + expert * (2 * iq2_gate + iq2_down)
    return ExpertOffsets(
        layer=layer,
        expert=expert,
        q1_gate=q1_expert_base,
        q1_up=q1_expert_base + q1_gate,
        q1_down=q1_expert_base + 2 * q1_gate,
        iq2_gate=iq2_expert_base,
        iq2_up=iq2_expert_base + iq2_gate,
        iq2_down=iq2_expert_base + 2 * iq2_gate,
    )


def residual_entry(
    layer: int,
    expert: int,
    tensor: str,
    block_first: int,
    block_count: int,
    residual_offset: int,
    residual_bytes_per_block: int = 2,
) -> ResidualEntry:
    offsets = expert_offsets(layer, expert)
    if tensor not in {"gate", "up", "down"}:
        raise ValueError("tensor must be gate, up, or down")
    q1_tensor_offset = getattr(offsets, f"q1_{tensor}")
    iq2_tensor_offset = getattr(offsets, f"iq2_{tensor}")
    return ResidualEntry(
        layer=layer,
        expert=expert,
        tensor=tensor,
        block_first=block_first,
        block_count=block_count,
        q1_offset=q1_tensor_offset + block_first * Q1_BLOCK_BYTES,
        iq2_offset=iq2_tensor_offset,
        residual_offset=residual_offset,
        residual_bytes=block_count * residual_bytes_per_block,
    )


def smoke_report() -> dict[str, Any]:
    values = deterministic_values(Q8K_BLOCK_WEIGHTS)
    q1_low = quantize_q1_0(values[:Q1_BLOCK_WEIGHTS])
    q1_high = quantize_q1_0(values[Q1_BLOCK_WEIGHTS:])
    q8 = Q8KBlock.from_values(values)
    packed = q1_low.pack() + q1_high.pack()
    unpacked = (Q1Block.unpack(packed[:Q1_BLOCK_BYTES]), Q1Block.unpack(packed[Q1_BLOCK_BYTES:]))
    fast_dot = dot_q1_pair_against_q8k(unpacked[0], unpacked[1], q8)
    ref_dot = reference_dot(unpacked, q8)
    res = residual_entry(layer=3, expert=7, tensor="gate", block_first=5, block_count=9, residual_offset=4096)
    return {
        "schema": "ds4_q1_0_cpu_smoke_v1",
        "sources": {
            "upstream_layout": "ggml-org/llama.cpp ggml/src/ggml-common.h: block_q1_0 = ggml_half d + qs[QK1_0/8], QK1_0=128",
            "local_metadata": "ds4-win-work/gguf-tools/quants.h: DS4Q_TYPE_Q1_0=41; quants.c: q1_0 block_size=128 type_size=18",
        },
        "sizes": routed_sizes(),
        "synthetic_block": {
            "packed_pair_bytes": len(packed),
            "roundtrip_equal": packed == unpacked[0].pack() + unpacked[1].pack(),
            "dot_fast": fast_dot,
            "dot_reference": ref_dot,
            "dot_abs_error": abs(fast_dot - ref_dot),
            "dot_pass": abs(fast_dot - ref_dot) <= 1e-5,
        },
        "residual_index_sample": asdict(res),
        "dual_representation_policy": {
            "resident_base": "Q1_0 sidecar for all cold routed experts, 33.75 GiB ideal routed payload.",
            "authoritative_hot": "Existing IQ2 GGUF remains authoritative on SSD/main runtime path.",
            "no_full_hot_duplicate": "Promotion stores sparse residual/index entries and may reuse existing IQ2 streaming cache; it does not preload a second full hot IQ2 host tier.",
            "selection_invariant": "Router-selected expert ids are unchanged; representation resolver only chooses bytes for an already-selected expert.",
        },
        "runtime_port_plan": [
            "Add DS4_TENSOR_Q1_0=41 to ds4.c type enum/table and tensor_expect_layout for a Q1 sidecar.",
            "Add cuda_block_q1_0 { uint16_t d; uint8_t qs[16]; } and static_assert sizeof==18.",
            "For gate/up rows, use q1_row_bytes(4096)=576 bytes; for down rows q1_row_bytes(2048)=288 bytes.",
            "Implement dev_dot_q1_0_pair_q8_K_block over two 128-weight Q1 blocks per 256-value Q8_K block.",
            "Use Q8_K bsums to compute signed sums: signed_sum = 2*sum(q8 where q1 bit=1) - sum_all_128.",
            "Wire Q1 kernels beside existing IQ1_S gate/up/down qwarp kernels; keep IQ1_S path untouched.",
            "Gate under a new env flag and fail closed on unknown type/shape; first runtime smoke must be n>=3 with L0-L3 grading.",
        ],
        "limits": [
            "Synthetic quantizer is deterministic layout smoke only, not an accuracy claim.",
            "Bit convention must be confirmed against the exact upstream Q1_0 CUDA/CPU kernel before runtime adoption.",
            "No GGUF payload, GPU, or DS4 runtime was used.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    payload = json.dumps(smoke_report(), indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload + "\n")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
