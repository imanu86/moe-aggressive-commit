# DS4 Q1_0 runtime step 1 patch

Patch artifact: `patches/ds4/0052-ds4-q1-0-runtime-step1.patch`

Base checkout: `C:\Users\imanu\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\ds4-win-work`

Base commit: `d1505358f429128943cadd8424fcaf0f6911f931`

Base blob checks:

- `ds4.c`: `4cda897f489d42f131cf681447d4cb5919256c2b`
- `ds4_cuda.cu`: `590233ef127262177b18a794d963bf00ac88c735`

Patch encoding: ASCII/UTF-8 bytes, no BOM, no NUL, LF newlines. The first four bytes are `64 69 66 66` (`diff`).

Status:

- Scope is intentionally fail-closed. It adds Q1_0 type/layout recognition, a Q1_0 sidecar env binder guard, CUDA block layout, Q1_0 dequant/dot helpers against Q8_K, and a routed-dispatch discriminator separate from IQ1_S.
- Q1_0 routed row sizing is type-aware: type 41 uses 128 elements per 18-byte block, while existing IQ/K routed experts keep `QK_K=256`.
- It does not enable full routed Q1_0 execution yet. `DS4_Q1_0_EXPERT_SIDECAR` exits during engine open and `gate_type=41` routed CUDA dispatch returns 0 with a diagnostic until selected-expert binding and kernels are wired.
- It preserves the existing IQ1_S env-off path: no `DS4_IQ1_S_EXPERT_SIDECAR` or `DS4_IQ1_S_MIXED_COLD_K` behavior is deleted or retargeted.
- Verification on 2026-07-17:
  - `python -m pytest tests\test_ds4_q1_runtime_patch.py tests\test_ds4_q1_smoke.py -q`: 11 passed.
  - `git apply --check` against clean DS4 commit `d1505358f429128943cadd8424fcaf0f6911f931`, without whitespace flags: passed.
  - Temporary source clone build: `cmake --build build --config Release --target ds4_cuda` with `DS4_CUDA_ARCHITECTURES=86`: passed. No GPU runtime, DS4 launch, or model file access was used.

Primary source checks:

- `ggml-org/llama.cpp` commit `635cdd5fcc5bdeb8ec2e108bb2a40acf62d9039b`, `ggml/src/ggml-common.h:180-185`: `QK1_0=128`, `block_q1_0` is `ggml_half d` plus `uint8_t qs[QK1_0 / 8]`, size 18 bytes.
- Same commit, `ggml/src/ggml-cuda/dequantize.cuh:17-22`: Q1_0 dequant polarity is bit `1 => +d`, bit `0 => -d`, formula `(2*bit - 1) * d`.
- Same commit, `ggml/src/ggml-cuda/vecdotq.cuh:675-722`: CUDA Q1_0 dot processes 128-element blocks as four 32-element Q8_1 chunks with one Q1_0 scale.
- Cross-check fork: `carlosfundora/llama.cpp-1-bit-turbo` commit `c6747ad7a5d5d7a9d115ff211ca819ff262dfe1f`, `ggml/src/ggml-cuda/vecdotq.cuh:744-786`: `Q1_0_g128` uses one scale for 128 elements and unpacks each bit to `+1/-1` with the same positive-bit polarity.

Numbered next steps:

1. Apply-check and compile this fail-closed step against a clean worktree generated from DS4 commit `d1505358f429128943cadd8424fcaf0f6911f931`.
2. Add a Q1_0 selected-expert sidecar binder that validates only routed expert tensors (`gate/up` Q1_0, `down` Q1_0 or Q2_K), keeps IQ1_S sidecar state separate, and provides Q1_0 route pointers to CUDA without touching the authoritative IQ2 model.
3. Port qwarp32 gate/up and down kernels from IQ1_S shape to Q1_0, using two 128-weight Q1_0 blocks per 256-weight Q8_K block for dot.
4. Add CPU-only GGUF synthetic fixture tests for Q1_0 sidecar metadata and selected-route pointer offsets before any GPU smoke is proposed.
