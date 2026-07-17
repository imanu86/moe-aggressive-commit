# DS4 IQ1_S / Sub-1bit Routed Expert Roadmap

Date: 2026-07-17

Scope: DS4 Flash routed expert quantization research, starting from IQ1_S and
keeping it separate from static K60/K75 bakes.

## Ground Truth From Local Runtime

- DS4 geometry is fixed at 43 layers, 256 routed experts per layer, 4096 embed,
  2048 routed FFN, and top-6 active experts.
- The existing DS4 GGUF type table maps type 19 to `iq1_s` with 256 weights per
  block and 50 bytes per block.
- `block_iq1_s` is `d:u16`, `qs[32]`, `qh[8] as u16`, so its effective storage
  is `50 * 8 / 256 = 1.5625 bpw`.
- The IQ1_S sidecar binding requires gate/up to be IQ1_S for every layer. Down
  is Q2_K for layers 0..2 and IQ1_S for layers 3..42.
- The RAM cache full-preload path is a frozen full policy for 40 routed layers
  times 256 experts. It is useful as a negative result, not as the production
  target on 64GB Windows.

Primary local references:

- `ds4.c:104-120` fixed geometry.
- `ds4.c:180-196` quant block layouts.
- `ds4.c:920-941` GGUF type table and IQ1_S type id.
- `ds4.c:3179-3243` IQ1_S sidecar validation and layer layout.
- `ds4_cuda.cu:2025-2232` IQ1_S RAM cache preload/resolve path.
- `ds4_iq1_s_bench.cu:1-8` upstream provenance:
  `ggml-org/llama.cpp` commit `b15ca938ad00aa6b3ee6c2edda7363fd02826b18`,
  files `ggml/src/ggml-common.h` and `ggml/src/ggml-cuda/vecdotq.cuh`.
- `gguf-tools/quants.h:52` and `gguf-tools/quants.c:73` already know
  `Q1_0` as type 41, block size 128, 18 bytes per block. That is 1.125 bpw
  metadata in the tools, but the DS4 runtime `ds4.c` routed tensor binder does
  not yet accept Q1_0 for execution.

## Size Ledger

Per routed expert:

| Layout | Expert MiB | All routed layer 3..42 GiB |
| --- | ---: | ---: |
| Current IQ2_XXS gate/up + Q2_K down | 6.7500 | 67.5000 |
| IQ1_S gate/up/down | 4.6875 | 46.8750 |
| IQ1_S gate/up + Q2_K down | 5.7500 | 57.5000 |
| Q1_0 g128 candidate | 3.3750 | 33.7500 |
| Ideal uniform 1.25 bpw | 3.7500 | 37.5000 |
| Ideal uniform 1.125 bpw | 3.3750 | 33.7500 |
| Ideal uniform 1.0 bpw | 3.0000 | 30.0000 |

Important consequence: keeping hot experts in current IQ2 while storing the rest
as IQ1_S increases total host RAM above all-IQ1. For example, 8 hot IQ2 experts
per layer plus the rest IQ1_S is 47.5195 GiB; 32 hot per layer is 49.4531 GiB.
Promotion to IQ2 should therefore be sparse and residency-scored, not a blanket
second resident copy.

Observed file sizes on this host:

- `C:\ds4-models\ds4-2bit.gguf`: 86,720,111,488 bytes, 80.7644 GiB.
- `C:\ds4-models\DeepSeek-V4-Flash-IQ1_S-XL.gguf`: 61,540,805,344 bytes,
  57.3143 GiB.

## Negative Results To Preserve

- G103: per-token SSD reads for IQ1_S cold experts are the wrong transport path:
  2.70 decode t/s vs 5.04 control. Do not design cold promotion as SSD per token.
- G105: full routed IQ1_S residency needs 46.875 GiB and paged on the 64GB
  Windows setup alongside the IQ2 runtime. Do not claim full-IQ1 resident fit.

## Best Current Option

Use two authoritative SSD files only as backing stores:

1. Current IQ2 model remains the authoritative hot/high-quality representation.
2. IQ1_S or sub-1bit sidecar remains the cold/warm compressed representation.

RAM should hold a smaller resident tier:

- Hot: current IQ2, only for a small score-gated set.
- Warm: IQ1_S, bounded and resident only when demand/mass/SPEX justifies it.
- Ultracold: sub-1bit payload around 1.0..1.25 bpw, designed to keep a much
  larger low-quality fallback resident without paging.
- Residual: separate delta from ultracold or IQ1_S toward IQ2, loaded/promoted
  only after repeated evidence. Avoid direct SSD-to-VRAM for ephemeral cold hits.

## Implementation Roadmap

1. CPU-only structural tool.
   - Done here: `tools/ds4_iq1_tier_planner.py`.
   - Test: `tests/test_ds4_iq1_tier_planner.py`.
   - Purpose: lock geometry, sizes, and negative-result guardrails.

2. Synthetic sub-1bit pack/depack prototype.
   - Add tiny block formats only under `tools/`, e.g. 32B/34B/36B per 256
     weights.
   - Verify deterministic round-trip metadata and residual indexing on synthetic
     tensors.
   - No DS4 runtime, no GPU, no model reads.

3. GGUF metadata-only validator.
   - Read GGUF header/tensor directory only.
   - Confirm tensor names, types, dimensions, offsets, and per-expert row spans.
   - Refuse payload hashing or bulk copying by default.

4. Residual design.
   - Define residual as `authoritative_iq2 - cold_repr` at block/tensor scope.
   - Keep residual physically separate from cold payload, so promotion is
     additive or replaceable by tier policy.
   - Require exact provenance: source GGUF path, bytes, tensor identity metadata,
     block format version, and conversion script commit.

5. Runtime patch design only until coordinated.
   - Add a representation-neutral tier resolver: given `(layer, expert)`, choose
     resident IQ2, resident IQ1/subbit+residual, or existing fallback.
   - Selection must remain router-owned. The tier resolver can change only bytes
     used for the selected expert, not which expert is selected.
   - Gate with env flags and counters mirroring IQ1_S cache telemetry.

6. Coordinated smoke.
   - First smoke should be CPU-only: synthetic pack/depack plus size ledger.
   - First runtime smoke should be scheduled with the main task and require
     `n>=3`, L0-L3 grading, exactness/provenance, and no claim from repeat_flag
     or n=1.

## Quality Risk

Sub-1bit is a memory hypothesis, not a quality result. Bonsai or other 1-bit
schemes may be useful as prior art, but DS4 integration should start with
ggml-compatible block layouts and DS4 tensor geometry. Any quality claim needs
held-out prompts, n>=3, L0-L3 grading, and exact provenance.

## Fork / Prior-Art Survey Addendum

This was added after a targeted fork check.

- PrismML Bonsai / llama.cpp Q1_0 is the best immediate lead. The Bonsai demo
  reports 1-bit Bonsai GGUF availability and says Q1_0 is merged in upstream
  llama.cpp for CPU, Metal, CUDA, and Vulkan. For DS4, this maps naturally to a
  1.125 bpw accounting target if using 18 bytes per 128 weights, but DS4 runtime
  support still has to be implemented and tested.
- Mintplex/prism-ml-llama.cpp is an experimental bridge fork for Bonsai 1-bit
  models. It is useful for format archaeology, but the README itself says it is
  not production-ready.
- carlosfundora/llama.cpp-1-bit-turbo is a ROCm-focused fork that remaps GGUF
  type 41 to `Q1_0_g128` and claims HIP/CUDA/Metal dequant and dot-product
  kernels. It is useful as a kernel/layout reference, but not a drop-in RTX 3060
  DS4 patch.
- LittleBit is true sub-1-bit research, down to 0.1 bpw, but it relies on latent
  factorization/QAT and changes the layer representation. It is not a direct
  GGUF block quantizer for DS4 experts.
- BTC-LLM and UltraSketchLLM are relevant sub-1-bit algorithmic leads, but they
  are not immediately DS4/ggml routed-expert compatible. Treat them as research
  candidates after Q1_0 metadata-only and synthetic smoke tests.

Conclusion: for near-term DS4 work, Q1_0 g128/type 41 is more concrete than a
new homegrown sub-1bit block. The next smoke should validate metadata and
synthetic Q1_0 expert sizing first, then decide whether to port runtime
dot/dequant.
