# DS4 Q1_0 Type-41 CPU Smoke And Port Design

Date: 2026-07-17

Scope: CPU-only structural smoke for `Q1_0` type 41 and a precise runtime port
plan for DS4 Flash routed experts. This does not launch DS4, use GPU, read GGUF
payloads, or make quality claims.

## Source Facts

- Upstream `ggml-org/llama.cpp` `ggml/src/ggml-common.h` defines `QK1_0=128`
  and `block_q1_0` as:
  - `ggml_half d`
  - `uint8_t qs[QK1_0 / 8]`
  - `sizeof(block_q1_0) == 18`
- Local DS4 `gguf-tools` already carries metadata:
  - `gguf-tools/quants.h:52`: `DS4Q_TYPE_Q1_0 = 41`
  - `gguf-tools/quants.c:73`: `{ "q1_0", 128, 18, false, false }`
- Local DS4 runtime `ds4.c` does not yet expose `DS4_TENSOR_Q1_0` in its
  routed execution binder. Current sidecar runtime support is IQ1_S type 19.

## Size Ledger

`Q1_0` is 18 bytes per 128 weights, so 1.125 bpw effective.

For one DS4 routed expert:

- Gate: input 4096, output 2048.
  - row bytes = `4096 / 128 * 18 = 576`
  - expert bytes = `2048 * 576 = 1,179,648`
- Up: same as gate = 1,179,648 bytes.
- Down: input 2048, output 4096.
  - row bytes = `2048 / 128 * 18 = 288`
  - expert bytes = `4096 * 288 = 1,179,648`
- Total expert = 3,538,944 bytes = 3.375 MiB.
- All routed layers 3..42 = `3,538,944 * 256 * 40` = 33.75 GiB.

This is materially smaller than all-IQ1_S routed residency at 46.875 GiB, while
remaining a concrete GGUF block format instead of a new custom format.

## CPU Smoke

Implemented in:

- `tools/ds4_q1_smoke.py`
- `tests/test_ds4_q1_smoke.py`

What it verifies:

- Q1_0 type/layout constants: type 41, 128 weights/block, 18 bytes/block.
- DS4 expert size accounting: 3.375 MiB/expert, 33.75 GiB for routed layers
  3..42.
- Deterministic synthetic pack/unpack for `d:f16 + qs[16]`.
- CPU dot identity for two 128-weight Q1 blocks against one 256-value Q8_K
  activation block:
  - reference path dequantizes signs then dots.
  - fast path uses Q8_K sums:
    `signed_sum = 2 * sum(q8 where q1 bit=1) - sum_all_128`.
- Expert/layer offset indexing.
- Sparse residual entry indexing from Q1 base offsets to authoritative IQ2
  tensor offsets.

The synthetic quantizer uses sign bits and mean-absolute scale only to exercise
layout and indexing. It is not a quantization-quality result.

## Runtime Port Plan

Do this as an isolated DS4 patch only after coordination with the main task.

1. Add runtime type support.
   - In `ds4.c`, extend `gguf_types[]` with `[41] = {"q1_0", 128, 18}` if not
     already present in that runtime table.
   - Add `DS4_TENSOR_Q1_0 = 41`.
   - Add a `block_q1_0` layout:
     `uint16_t d; uint8_t qs[16];`
   - Add static assert `sizeof(block_q1_0) == 18`.

2. Add sidecar binding mode.
   - Keep current IQ1_S sidecar untouched.
   - Add a separate Q1 sidecar env, for example `DS4_Q1_0_EXPERT_SIDECAR`.
   - Validate gate/up/down routed tensors as Q1_0 for layers 3..42 only at
     first; leave layers 0..2 out unless a real sidecar proves matching layout.
   - Preserve existing checkpoint identity checks for non-routed controls.

3. Add CUDA layout and dot helper.
   - In `ds4_cuda.cu`, add:
     `struct cuda_block_q1_0 { uint16_t d; uint8_t qs[16]; };`
   - Add `dev_dot_q1_0_pair_q8_K_block(const cuda_block_q1_0 *w2,
     const cuda_block_q8_K *x)`.
   - Each Q8_K block covers 256 activations; consume two consecutive Q1 blocks.
   - For each 128 half:
     - compute `sum_all_128` from 8 Q8_K `bsums`.
     - compute `positive_sum` by scanning set bits in the corresponding 16
       bytes and adding matching `x->qs`.
     - `signed_sum = 2 * positive_sum - sum_all_128`.
     - accumulate `q1.d * q8.d * signed_sum`.
   - Confirm bit polarity against upstream Q1_0 CPU/CUDA before enabling by
     default. The smoke assumes bit 1 = positive, bit 0 = negative.

4. Add kernels parallel to IQ1_S.
   - Mirror the existing IQ1_S qwarp path:
     - gate/up: Q1_0 rows dot `ffn_norm` Q8_K blocks.
     - down: Q1_0 rows dot quantized routed mid Q8_K blocks.
   - Do not rewrite the IQ1_S path.
   - Gate behind explicit env flags and fail closed on shape/type mismatch.

5. Add telemetry.
   - Counters should mirror IQ1_S:
     - sidecar installed bytes.
     - selected loads.
     - Q1 RAM cache hits/misses/evictions if a cache is added.
     - residual hits/misses.
     - fallback-to-IQ2 counts.

## Dual Representation: Q1 Base + Authoritative IQ2 Residual

Goal: avoid a second full hot IQ2 host copy.

Representation:

- Resident cold base: Q1_0 sidecar for routed experts.
- Authoritative high-quality source: existing IQ2 GGUF and existing DS4 IQ2
  streaming/cache path.
- Sparse residual index: per `(layer, expert, tensor, block_range)` entry:
  - Q1 base offset.
  - authoritative IQ2 tensor offset.
  - residual payload offset if an explicit residual is materialized.
  - residual byte count and version/provenance.

Execution policy:

- Default selected expert uses Q1_0 base when cold.
- Promotion does not allocate a full duplicate IQ2 tier in host RAM.
- For a promoted expert, resolver chooses one of:
  - existing IQ2 path for that selected expert, using the authoritative main
    model and current streaming cache;
  - Q1 base plus sparse residual payload if a residual format is present;
  - Q1 base only if neither promotion nor residual is resident.
- Router selection is invariant. The resolver changes only the representation
  bytes used for an already-selected expert.

Promotion gates:

- minimum touches;
- minimum route weight/mass;
- SPEX or repeated-window evidence;
- request/window budget;
- exact provenance and sidecar identity checks.

## Limits

- No quality claim from this smoke.
- No runtime speed claim.
- No claim that Q1_0 is acceptable for DS4 Flash coding quality.
- The bit polarity and exact scale semantics must be confirmed against the
  upstream Q1_0 runtime kernel before a DS4 runtime patch is promoted.
- Any runtime adoption needs n>=3, L0-L3 grading, exactness/provenance, and
  negative-result preservation for G103/G105.
