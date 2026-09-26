# Opt-in Q4_K fused-MMVQ occupancy experiment

**Closed: REJECTED for promotion.** See `FINAL_RESULT.md`: scoped correctness and actual activation passed, but clean OFF/ON/OFF runtime performance did not improve. This document preserves the experiment design/build history; no further variant is authorized.

## Evidence and rationale

Parent profile: `D:\ds4_work\qwen4b_campaign\nsys_original\capture.nsys-rep`, original runtime, warmed decode, no MTP, graph tracing at node granularity. Child ran CPU-only nsys stats/export and SQLite grouping. Full geometry/register grouping: `D:\ds4_work\qwen4b_kernel_lab\evidence\profile-kernel-groups.json`.

- Q4_K fused MMVQ accounts for 35.7% of summed GPU kernel time.
- Main fused shape: grid `(9216,1,1)`, block `(32,4,1)`, **53 registers/thread**, 768 bytes shared memory. 41,968 launches; 5,114,845,376 ns summed (~28.1% of total kernel time).
- Q5_K and Q6_K nonfused MMVQ use 40 registers/thread; these are not targets for this experiment.
- On sm86, 53 registers round to 56 per thread at warp allocation granularity. The register ceiling allows 9 x 128-thread blocks = 1152/1536 threads, 75% theoretical occupancy. This is a capacity bound, **not a measured achieved occupancy or proof of memory latency limitation**.

The experimental instantiation requests a minimum of 12 blocks per SM using the existing `min_blocks` template argument. This may force fewer registers, potentially improving latency hiding, or introduce spills and make it slower. Only a controlled micro/full-model A/B can decide. Node-trace timing includes profiler overhead and is not a throughput benchmark.

## Patch and precise limits

Only source file changed: `D:\ds4_work\qwen4b_kernel_lab\source\ggml\src\ggml-cuda\mmvq.cu`.

Patch: `evidence\occ12.patch`. Feature flag: **`GGML_CUDA_QWEN4B_Q4K_OCC12=1`**. Default OFF; values other than exactly `1` are OFF. Cached on first eligible dispatch, so set before launching the process.

New dispatch requires ALL of:

- Q4_K, one-column decode, neither small-K nor GB10 halve-iters path;
- physical device compute capability 860;
- dense operation (no expert IDs), K=2560 and output rows=9216;
- one channel and one sample on all operands;
- fused gate with SwiGLU, no bias or scale operands.

It invokes the **existing kernel and reduction**, with the same `(32,4,1)` block and grid; only `min_blocks` changes from 1 to 12. No graph/model/context change, quantization change, approximation or modified arithmetic expression. This does **not** prove bitwise preservation after compilation: the standalone validator and parent model tests must check it.

Original live runtime remains untouched. The unmodified rebuilt DLL is frozen separately at `evidence\unmodified-rebuild\ggml-cuda.dll`, SHA256 `0559091498F5D9704F51FE7649AB1C264820FF8B0EAF1F268B6BA400DA27E25D`. Its original `mmvq.cu` is beside it. Do not confuse a patched candidate with this prior source/binary drift baseline.

## Standalone validation design

- `make_occ12_unit.py` extracts the actual constexpr helpers and MMVQ kernel from the current source, appends `unit_occ12_driver.cu`, writes `evidence\unit_occ12.cu` and a source hash manifest. It does not compile or execute.
- `build-occ12-unit.cmd` compiles only, with CUDA12.6/sm86, original fast-math/Release settings. It never executes the binary.
- `evidence\unit_occ12.exe` (once built) is **GPU work for the parent to schedule**, not a CPU test.

The validator instantiates the exact Q4_K fused SwiGLU kernel at min_blocks=1 and 12. It tests 3 seeds x 4 input patterns (including zero weights and small scales), at the production 9216x2560 shape. It requires bitwise-identical finite output and intact output canaries. It reports registers, local memory, active blocks/SM and informational CUDA-event timings. Failure exits nonzero. Fixtures are valid packed quant blocks, not whole-model logits; dispatch correctness and full-model behavior remain separate parent tests.

When running the validator, parent must set PATH so that the **frozen live ggml-base.dll** resolves (e.g. prepend lab `bin-baseline` and CUDA12.6 bin). The import library comes from the identical-source rebuilt base; never replace the frozen runtime's base DLL.

## Acceptance gates

1. Compile backend and validator; record ptxas register/spill data. Preserve flag-OFF path.
2. Parent runs standalone validator; reject bitwise mismatch, NaN/Inf, canary overwrite or launch errors.
3. Parent confirms new dispatch actually fires, e.g. kernel name containing final `min_blocks=12` in a profile; lack of activation is not a performance success.
4. Parent compares patched flag OFF against unmodified rebuild, then ON against OFF, using deterministic full-model and tool cases. Include full-logit/tolerance checks if available; text equality alone is narrower evidence.
5. Evaluate unprofiled warmed decode and end-to-end latency, plus regressions with parent MTP settings and long context. If no repeatable gain, leave OFF/revert experiment. No promotion from profiler times alone.

## Build result (2026-09-26)

Backend and standalone validator compiled successfully. All jobs collected; no GPU execution by this lane. Static ABI gate PASS: same 11 exports and complete import sets, frozen base/consumer imports resolve. Candidate CUDA SHA256: `1798A55BB05FA852F8734F4F4C51E472A21D79536E29AEF1A1D93BB07B335253`. Validator SHA256: `7BBB65EE94AA2D53030C5F46C0522AE8D9DEB198F94A7C13A5604FA98186EC7D`.

ptxas for standalone exact template: baseline **53 registers**, OCC12 **40 registers**; both **0 stack bytes, 0 spill stores/loads, 768 shared bytes**. This supports the occupancy hypothesis but does not establish speed or numerical correctness.

Initial validator compile needed CUDA union `.data` field access in fixtures; fixed in the standalone driver only. Its link was changed to `--cudart shared` to match production and eliminate LIBCMT/CRT conflict. Remaining warnings come from existing common.cuh floating-point constants, not new math.

Evidence: `occ12-build.log`, `occ12-unit-build.log`, `occ12-abi-review.json`, `occ12-runtime-sha256.csv`, `unit-occ12-source-manifest.json` under lab `evidence`. Live runtime unchanged; only candidate ggml-cuda.dll differs. Parent now owns GPU validator, flag OFF/ON full-model A/B and activation profiling. No performance claim yet.
