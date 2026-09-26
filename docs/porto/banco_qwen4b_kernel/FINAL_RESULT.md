# Kernel lane final result: OCC12 REJECTED for promotion

**Verdict: do not enable OCC12 in the daily runtime.** The experiment compiled, passed the scoped numerical/output checks and was demonstrably active, but did not improve end-to-end performance in the clean OFF/ON/OFF campaign. No kernel optimization success is claimed.

## Scope completed

- Frozen original runtime and source copy; isolated unmodified rebuild and static ABI gate.
- Parent unmodified rebuild A/B passed the initial 15 text-output cases and speed parity (not full-logit equivalence).
- One profile-supported, default-OFF patch: Q4_K fused SwiGLU MMVQ, sm86, dense 9216x2560 shape only, existing arithmetic/reduction/geometry, min_blocks=12 instead of 1.
- All donor/live files preserved. No child server starts/stops or GPU execution. GPU tests and captures below were performed by the parent.
- No min_blocks=10 variant, further kernel build, commit or push performed by this lane.

## Correctness evidence and limits

Parent GPU standalone test: `D:\ds4_work\qwen4b_campaign\kernel-unit.txt`.

- **12/12 fixtures bit-identical**, max absolute difference 0; finite outputs and canaries passed.
- Baseline: 53 registers, 9 active blocks/SM; OCC12: 40 registers, 12 active blocks/SM.
- Both: zero local memory reported; ptxas zero stack/spill stores/spill loads.
- The validator directly invokes both exact kernel templates on valid packed synthetic tensors at the production shape. It does not validate the runtime dispatch predicate, actual model weights, arbitrary strides, state rollback or complete model logits.

Parent full-runtime OFF/ON/OFF: **15/15 generated text outputs identical** (five cases, three repetitions) in each ON-vs-OFF comparison; tool validity checks passed. This is text/output equivalence for these cases, **not full-logit or broad numerical equivalence**.

## Clean runtime performance: no win

Decode medians in tokens/second (unprofiled parent runs):

| Case | OFF A | ON | OFF B |
|---|---:|---:|---:|
| prose | 68.640 | 68.652 | 71.402 |
| result | 73.889 | 66.964 | 73.693 |
| tool_batch | 73.690 | 68.212 | 72.392 |
| tool_describe | 74.975 | 68.056 | 73.065 |
| tool_retry | 73.139 | 67.909 | 74.098 |

Tool-batch median latency was **1.335 s ON vs 1.247/1.245 s OFF**. Result latency was **0.820 s ON vs 0.747/0.742 s OFF**. Prose was approximately tied against OFF A, worse against OFF B. Variance exists; the supported conclusion is **no repeatable net gain, with observed tool-case regressions**, not a universal slowdown theorem.

Evidence:
- `D:\ds4_work\qwen4b_campaign\kernel_on-vs-kernel_off_a.json`
- `D:\ds4_work\qwen4b_campaign\kernel_on-vs-kernel_off_b.json`

## Actual dispatch independently confirmed

Parent ON trace: `D:\ds4_work\qwen4b_campaign\nsys_occ12_on\capture.nsys-rep`. CPU-only child export/query produced the archived `occ12-profile-activation.json`.

| Diagnostic | Original capture | OCC12 ON capture |
|---|---:|---:|
| Template final min_blocks | 1 | **12** |
| Matching actual launches | 41,968 | **18,374** |
| Grid / block | 9216x1x1 / 32x4x1 | same |
| Registers/thread | 53 | **40** |
| Shared bytes / local bytes | 768 / 0 | same |
| Instrumented kernel median | 96.990 us | 89.374 us |

The ON capture contains the actual `mul_mat_vec_q<... (int)12>` launches, so this is not an inactive-flag test. The lower instrumented hotspot median (~7.9%) **does not override the failed clean runtime performance gate**: capture windows differ, CUDA graph node tracing adds overhead, and a local kernel diagnostic is not end-to-end throughput.

## Final state and reproducibility

- Original live CUDA SHA256: `A8E6D2A95C1FCAA14D28914CEE1657E7E492A9B788AFAAF5430D8019E667886E`.
- Frozen unmodified rebuilt CUDA: `D:\ds4_work\qwen4b_kernel_lab\evidence\unmodified-rebuild\ggml-cuda.dll`, SHA256 `0559091498F5D9704F51FE7649AB1C264820FF8B0EAF1F268B6BA400DA27E25D`.
- Rejected opt-in candidate: `D:\ds4_work\qwen4b_kernel_lab\bin-candidate\ggml-cuda.dll`, SHA256 `1798A55BB05FA852F8734F4F4C51E472A21D79536E29AEF1A1D93BB07B335253`.
- Experimental flag remains **default OFF**: `GGML_CUDA_QWEN4B_Q4K_OCC12=1` would opt in. Do not add it to daily launchers.
- `occ12.patch` is a relative-path patch against the frozen donor; `git apply --check --reverse` was verified against the current lab source without modifying it.
- Build recipe, validator driver/generator, profiler-comparison script, source hash manifest and compact ABI/activation evidence are archived in this dossier for parent-owned explicit-path integration. No DLLs or profiler databases are committed by this lane.

The experiment answers a narrow question: reducing register allocation raised theoretical/measured occupancy, but **occupancy alone was not a reliable predictor of application speed**. Do not spend another build on min_blocks=10 without new authorization and a specific measurement plan.
