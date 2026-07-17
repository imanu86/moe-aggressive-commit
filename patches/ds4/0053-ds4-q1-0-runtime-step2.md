# DS4 Q1_0 runtime step 2 patch

Patch artifact: `patches/ds4/0053-ds4-q1-0-runtime-step2.patch`

Base: apply after `patches/ds4/0052-ds4-q1-0-runtime-step1.patch` on DS4 commit `d1505358f429128943cadd8424fcaf0f6911f931`.

Base blob checks before step1:

- `ds4.c`: `4cda897f489d42f131cf681447d4cb5919256c2b`
- `ds4_cuda.cu`: `590233ef127262177b18a794d963bf00ac88c735`
- `ds4_gpu.h`: `92609ec4fe17fbf36b548cff5b820a10aa0d8511`

Patch encoding: ASCII/UTF-8 bytes, no BOM, no NUL, LF newlines. The first four bytes are `64 69 66 66` (`diff`).

Status:

- Scope remains fail-closed. The patch adds metadata/offset binding for a Q1_0 routed-expert sidecar and compiles Q1_0 qwarp32 gate/up/down kernels, but does not dispatch them.
- `DS4_Q1_0_EXPERT_SIDECAR` now opens and validates a sidecar instead of immediately aborting. The sidecar state is `g_q1_0_sidecar`, separate from `g_iq1_s_sidecar`.
- Q1_0 routed source selection is separate from IQ1_S and has priority only when `g_q1_0_sidecar.ready` and the layer is inside `DS4_Q1_0_LAYER_FIRST..DS4_Q1_0_LAYER_LAST`.
- The Q1_0 binder is routed-only: defaults are layer `3..42`, env overrides outside `3..42` fail closed, and layers `0..2` remain outside this sidecar contract instead of inflating the Q1_0 payload.
- Type 41 acceptance is explicit to this sidecar binder through `tensor_expect_layout(... DS4_TENSOR_Q1_0 ...)`; the primary model's generic routed-expert validation still rejects Q1_0.
- `DS4_Q1_0_EXPERT_SIDECAR` plus `DS4_IQ1_S_MIXED_COLD_K=1` fails closed at engine open for this smoke, because the first runtime path does not yet support mixed IQ1_S and Q1_0 route ownership in the same open.
- Existing IQ1_S env-off behavior is preserved; the patch does not change `DS4_IQ1_S_EXPERT_SIDECAR`, `DS4_IQ1_S_MIXED_COLD_K`, or IQ1_S dispatch conditions.
- Verification on 2026-07-17:
  - `python -m pytest tests\test_ds4_q1_runtime_step2_patch.py tests\test_ds4_q1_runtime_patch.py tests\test_ds4_q1_smoke.py -q`: 17 passed.
  - `python tools\ds4_q1_smoke.py --write-fixture <work>\q1_0_type41_fixture.gguf --pretty`: wrote a 3-tensor type41 GGUF fixture with offsets `0,64,128`.
  - Apply sequence check: step1 then step2 applied cleanly to DS4 commit `d1505358f429128943cadd8424fcaf0f6911f931`, without whitespace flags.
  - Temporary source clone build: `cmake --build build --config Release --target ds4_cuda ds4` with `DS4_CUDA_ARCHITECTURES=86`: passed. No GPU runtime, DS4 launch, or real model file access was used.

Binder details:

- Validates `blk.%u.ffn_gate_exps.weight`, `blk.%u.ffn_up_exps.weight`, and `blk.%u.ffn_down_exps.weight` tensors as type 41/Q1_0 only for the active routed layer range.
- Gate/up layout: `[DS4_N_EMBD, DS4_N_FF_EXP, DS4_N_EXPERT]`.
- Down layout: `[DS4_N_FF_EXP, DS4_N_EMBD, DS4_N_EXPERT]`.
- Stores per-layer row/expert byte spans for gate/up/down using the step1 type-aware 128/18B row sizing.
- Bounds-checks routed expert spans against the sidecar file size.

Kernel details:

- Adds `moe_gate_up_mid_q1_0_qwarp32_kernel`.
- Adds `moe_down_q1_0_qwarp32_kernel`.
- Each Q8_K 256-value activation block maps to two Q1_0 128-value blocks via `dev_dot_q1_0_q8_K_pair`.
- Kernels accept existing selected-expert ids and optional route-pointer tables, matching the IQ1_S qwarp32 calling shape.

CPU-only fixture:

- `tools/ds4_q1_smoke.py --write-fixture <path>` writes a tiny GGUF v3 fixture with three routed tensors (`gate/up/down`) using type 41.
- `tests/test_ds4_q1_smoke.py` validates fixture type, dims, offsets, and payload bounds without reading any model file.

Next coordinated smoke for the Windows branch:

1. Apply step1 then step2 to a clean DS4 branch/worktree.
2. Build `ds4` and `ds4_cuda` only; do not run DS4.
3. Generate the tiny fixture with `python tools\ds4_q1_smoke.py --write-fixture <tmp>\q1_0_type41_fixture.gguf --pretty`.
4. Add a binder-only runtime smoke after coordination: set `DS4_Q1_0_EXPERT_SIDECAR` to a full synthetic DS4-shaped metadata fixture, verify binder diagnostics and fail-closed route, still with no model payload benchmark.
