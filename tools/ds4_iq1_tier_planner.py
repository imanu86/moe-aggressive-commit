"""CPU-only DS4 routed-expert quantization size planner.

This tool is intentionally arithmetic-only: it does not start DS4, touch CUDA,
hash GGUF payloads, or read model contents. Optional file paths are stat'ed for
provenance bytes only.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

GIB = 1024**3
MIB = 1024**2

DS4_N_LAYER = 43
DS4_ROUTED_LAYER_FIRST = 3
DS4_ROUTED_LAYER_COUNT = 40
DS4_N_EMBD = 4096
DS4_N_FF_EXP = 2048
DS4_N_EXPERT = 256

BLOCK_WEIGHTS = 256

BLOCK_BYTES: dict[str, int] = {
    "IQ2_XXS": 66,
    "Q2_K": 84,
    "IQ1_S": 50,
    # Q1_0 g128 uses 18 bytes per 128 weights, normalized here to 36 bytes
    # per 256-weight DS4 accounting unit. DS4 gguf-tools has type 41 metadata;
    # ds4.c routed execution does not yet accept this tensor type.
    "Q1_0_G128": 36,
    "SUB1_32B": 32,
    "SUB1_34B": 34,
    "SUB1_36B": 36,
    "SUB1_40B": 40,
}

PROVENANCE = {
    "ds4_runtime": {
        "repo": r"C:\Users\imanu\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\ds4-win-work",
        "branch": "feature/iq1-probation-promotion",
        "files": [
            "ds4.c:104-120 DS4 geometry",
            "ds4.c:180-196 block_iq1_s/block_iq2_xxs sizes",
            "ds4.c:920-941 GGUF type id 19 = iq1_s",
            "ds4.c:3179-3243 IQ1_S sidecar binding and down Q2_K[0..2]",
            "ds4_cuda.cu:2025-2232 IQ1_S RAM cache/preload path",
            "gguf-tools/quants.h:52 and quants.c:73 Q1_0 type 41 metadata only",
            "ds4_iq1_s_bench.cu:1-8 upstream llama.cpp provenance",
        ],
    },
    "upstream_primary": {
        "repo": "ggml-org/llama.cpp",
        "commit_cited_by_ds4_bench": "b15ca938ad00aa6b3ee6c2edda7363fd02826b18",
        "files": [
            "ggml/src/ggml-common.h block_iq1_s",
            "ggml/src/ggml-cuda/vecdotq.cuh IQ1_S dot/dequant math",
            "PR #5453 1.5 bit quantization",
        ],
    },
}


@dataclass(frozen=True)
class ExpertLayout:
    name: str
    gate_type: str
    up_type: str
    down_type: str

    @property
    def gate_row_bytes(self) -> int:
        return DS4_N_EMBD // BLOCK_WEIGHTS * BLOCK_BYTES[self.gate_type]

    @property
    def up_row_bytes(self) -> int:
        return DS4_N_EMBD // BLOCK_WEIGHTS * BLOCK_BYTES[self.up_type]

    @property
    def down_row_bytes(self) -> int:
        return DS4_N_FF_EXP // BLOCK_WEIGHTS * BLOCK_BYTES[self.down_type]

    @property
    def gate_expert_bytes(self) -> int:
        return DS4_N_FF_EXP * self.gate_row_bytes

    @property
    def up_expert_bytes(self) -> int:
        return DS4_N_FF_EXP * self.up_row_bytes

    @property
    def down_expert_bytes(self) -> int:
        return DS4_N_EMBD * self.down_row_bytes

    @property
    def expert_bytes(self) -> int:
        return self.gate_expert_bytes + self.up_expert_bytes + self.down_expert_bytes

    @property
    def all_routed_bytes(self) -> int:
        return self.expert_bytes * DS4_N_EXPERT * DS4_ROUTED_LAYER_COUNT

    def to_record(self) -> dict[str, Any]:
        data = asdict(self)
        data.update(
            {
                "gate_row_bytes": self.gate_row_bytes,
                "up_row_bytes": self.up_row_bytes,
                "down_row_bytes": self.down_row_bytes,
                "gate_expert_mib": self.gate_expert_bytes / MIB,
                "up_expert_mib": self.up_expert_bytes / MIB,
                "down_expert_mib": self.down_expert_bytes / MIB,
                "expert_bytes": self.expert_bytes,
                "expert_mib": self.expert_bytes / MIB,
                "all_routed_gib": self.all_routed_bytes / GIB,
            }
        )
        return data


CURRENT_IQ2 = ExpertLayout("current_iq2xxs_gate_up_q2k_down", "IQ2_XXS", "IQ2_XXS", "Q2_K")
IQ1_ALL = ExpertLayout("iq1_s_gate_up_down", "IQ1_S", "IQ1_S", "IQ1_S")


def file_record(path_text: str | None) -> dict[str, Any] | None:
    if not path_text:
        return None
    path = Path(path_text)
    return {
        "path": str(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else None,
        "gib": path.stat().st_size / GIB if path.exists() else None,
    }


def mixed_hot_iq2_warm_iq1(hot_per_layer: int) -> dict[str, Any]:
    if hot_per_layer < 0 or hot_per_layer > DS4_N_EXPERT:
        raise ValueError("hot_per_layer must be in 0..256")
    warm_per_layer = DS4_N_EXPERT - hot_per_layer
    total = DS4_ROUTED_LAYER_COUNT * (
        hot_per_layer * CURRENT_IQ2.expert_bytes + warm_per_layer * IQ1_ALL.expert_bytes
    )
    return {
        "name": f"hot_iq2_{hot_per_layer}_per_layer_warm_iq1_rest",
        "hot_iq2_per_layer": hot_per_layer,
        "warm_iq1_per_layer": warm_per_layer,
        "all_routed_bytes": total,
        "all_routed_gib": total / GIB,
        "note": "This is larger than all-IQ1 whenever hot_iq2_per_layer > 0.",
    }


def ideal_bpw_layout(bpw: float) -> dict[str, Any]:
    elems_per_expert = 3 * DS4_N_EMBD * DS4_N_FF_EXP
    expert_bytes = elems_per_expert * bpw / 8.0
    all_bytes = expert_bytes * DS4_N_EXPERT * DS4_ROUTED_LAYER_COUNT
    return {
        "name": f"ideal_uniform_{bpw:g}_bpw",
        "bpw": bpw,
        "expert_mib": expert_bytes / MIB,
        "all_routed_gib": all_bytes / GIB,
        "note": "Ideal payload model; real GGUF block scales/metadata may add overhead.",
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    layouts = [
        CURRENT_IQ2,
        IQ1_ALL,
        ExpertLayout("q1_0_g128_candidate", "Q1_0_G128", "Q1_0_G128", "Q1_0_G128"),
        ExpertLayout("iq1_s_gate_up_q2k_down", "IQ1_S", "IQ1_S", "Q2_K"),
        ExpertLayout("sub1_1p000bpw_uniform_32B", "SUB1_32B", "SUB1_32B", "SUB1_32B"),
        ExpertLayout("sub1_1p0625bpw_uniform_34B", "SUB1_34B", "SUB1_34B", "SUB1_34B"),
        ExpertLayout("sub1_1p125bpw_uniform_36B", "SUB1_36B", "SUB1_36B", "SUB1_36B"),
        ExpertLayout("sub1_1p250bpw_uniform_40B", "SUB1_40B", "SUB1_40B", "SUB1_40B"),
    ]
    physical_ram_gib = args.physical_ram_gib
    os_runtime_reserve_gib = args.os_runtime_reserve_gib
    practical_cold_budget_gib = max(0.0, physical_ram_gib - os_runtime_reserve_gib)
    return {
        "schema": "ds4_iq1_tier_planner_v1",
        "geometry": {
            "n_layer": DS4_N_LAYER,
            "routed_layer_first": DS4_ROUTED_LAYER_FIRST,
            "routed_layer_count": DS4_ROUTED_LAYER_COUNT,
            "n_embd": DS4_N_EMBD,
            "n_ff_exp": DS4_N_FF_EXP,
            "n_expert": DS4_N_EXPERT,
            "block_weights": BLOCK_WEIGHTS,
        },
        "block_formats": {
            name: {"bytes_per_256": bytes_, "bpw_effective": bytes_ * 8 / BLOCK_WEIGHTS}
            for name, bytes_ in BLOCK_BYTES.items()
        },
        "model_files": {
            "main_iq2": file_record(args.main_iq2),
            "iq1_sidecar": file_record(args.iq1_sidecar),
        },
        "expert_layouts": [layout.to_record() for layout in layouts],
        "mixed_tiers": [mixed_hot_iq2_warm_iq1(hot) for hot in args.hot_iq2_per_layer],
        "ideal_subbit": [ideal_bpw_layout(bpw) for bpw in args.ideal_bpw],
        "ram_budget": {
            "physical_ram_gib": physical_ram_gib,
            "os_runtime_reserve_gib": os_runtime_reserve_gib,
            "practical_cold_budget_gib": practical_cold_budget_gib,
            "iq1_all_routed_fits_practical_cold_budget": IQ1_ALL.all_routed_bytes / GIB
            <= practical_cold_budget_gib,
        },
        "negative_results_to_preserve": [
            {
                "id": "G103",
                "finding": "Per-token SSD reads for IQ1_S cold experts regressed throughput.",
                "measured_decode_tps": 2.70,
                "control_decode_tps": 5.04,
                "claim_scope": "Do not use SSD->token path as a promotion strategy.",
            },
            {
                "id": "G105",
                "finding": "Full routed IQ1_S residency requires 46.875 GiB and paged on 64GB Windows with DS4 IQ2 runtime.",
                "all_iq1_routed_gib": IQ1_ALL.all_routed_bytes / GIB,
                "claim_scope": "Use smaller resident tiers or tighter ultracold format.",
            },
        ],
        "fork_survey": [
            {
                "name": "PrismML Bonsai / upstream llama.cpp Q1_0",
                "status": "primary reusable lead",
                "finding": "Bonsai 1-bit GGUF uses Q1_0-style blocks; public demo says Q1_0 is merged upstream for CPU, Metal, CUDA, and Vulkan.",
                "ds4_gap": "DS4 runtime routed tensors still accept IQ1_S, not Q1_0 type 41.",
            },
            {
                "name": "llama.cpp-1-bit-turbo",
                "status": "fork lead",
                "finding": "ROCm-focused fork remaps GGUF type 41 to Q1_0_g128 and claims GPU dot/dequant kernels.",
                "ds4_gap": "AMD/ROCm target; useful layout/kernel reference, not drop-in for RTX 3060 DS4 CUDA.",
            },
            {
                "name": "LittleBit",
                "status": "research lead",
                "finding": "Sub-1-bit latent factorization supports 1.0 down to 0.1 bpw, but requires QAT/factorized layers.",
                "ds4_gap": "Not GGUF block-compatible and not prompt-free post-training conversion.",
            },
            {
                "name": "BTC-LLM / UltraSketchLLM",
                "status": "research lead",
                "finding": "Sub-1-bit papers/code exist, but integration is custom and not directly DS4/ggml routed-expert compatible.",
                "ds4_gap": "Treat as algorithmic inspiration, not immediate runtime patch.",
            },
        ],
        "recommended_next_smoke": {
            "kind": "cpu_only_structural",
            "steps": [
                "Generate synthetic tiny IQ1_S and residual blocks.",
                "Verify deterministic pack/depack and dimension ledger.",
                "No DS4 launch, no GPU, no full GGUF hashing or copying.",
            ],
        },
        "provenance": PROVENANCE,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-iq2", default=None, help="Optional main GGUF path for size provenance.")
    parser.add_argument("--iq1-sidecar", default=None, help="Optional IQ1_S GGUF path for size provenance.")
    parser.add_argument("--physical-ram-gib", type=float, default=64.0)
    parser.add_argument(
        "--os-runtime-reserve-gib",
        type=float,
        default=22.0,
        help="Conservative RAM left for OS + IQ2 runtime + caches.",
    )
    parser.add_argument(
        "--hot-iq2-per-layer",
        type=int,
        nargs="*",
        default=[0, 4, 8, 16, 32, 64, 96, 128],
    )
    parser.add_argument(
        "--ideal-bpw",
        type=float,
        nargs="*",
        default=[0.75, 0.875, 1.0, 1.125, 1.25, 1.5],
    )
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    payload = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
