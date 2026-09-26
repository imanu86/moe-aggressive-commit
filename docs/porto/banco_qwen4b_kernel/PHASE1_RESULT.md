# Kernel lane phase 1 result

Completed 2026-09-26. **Fresh unmodified CUDA backend compiled; static ABI gate PASS. No kernel patch and no GPU execution by this lane.** Parent must run the runtime/numerical/performance drift gate, then supply a profile before patches.

## Artifacts

| Artifact | Path / result |
|---|---|
| Frozen live baseline | `D:\ds4_work\qwen4b_kernel_lab\bin-baseline` |
| Isolated candidate | `D:\ds4_work\qwen4b_kernel_lab\bin-candidate` |
| Rebuilt backend | `D:\ds4_work\qwen4b_kernel_lab\build\bin\ggml-cuda.dll` |
| Build recipe | `D:\ds4_work\qwen4b_kernel_lab\configure-build.cmd` |
| Build log (UTF8) | `D:\ds4_work\qwen4b_kernel_lab\evidence\configure-build-readable.log` |
| ABI evidence | `D:\ds4_work\qwen4b_kernel_lab\evidence\abi-review.json` |
| Build flags comparison | `D:\ds4_work\qwen4b_kernel_lab\evidence\build-command-comparison.json` |
| Runtime hashes | `D:\ds4_work\qwen4b_kernel_lab\evidence\runtime-final-sha256.csv` |
| PE sections | `D:\ds4_work\qwen4b_kernel_lab\evidence\pe-section-comparison.json` |

Candidate differs from frozen baseline in **ggml-cuda.dll only**. Frozen `ggml-base.dll`, all llama DLLs and executable remain unchanged. All nine live runtime file hashes still equal the frozen baseline.

### CUDA DLL hashes

- Live/frozen: `A8E6D2A95C1FCAA14D28914CEE1657E7E492A9B788AFAAF5430D8019E667886E`, 192,566,272 bytes.
- Rebuilt/candidate: `0559091498F5D9704F51FE7649AB1C264820FF8B0EAF1F268B6BA400DA27E25D`, 192,547,840 bytes.

All PE raw-section hashes differ. Root paths, layout and build metadata can alter binaries; **byte drift is not explained away as proven harmless**. This is why a parent-owned unmodified-rebuild A/B gate is required before optimization.

## What was verified

1. Branch was the explicitly authorized `research/ds4-iq1-subbit-tier-planner`. Existing untracked work preserved; no git operation changed history.
2. Plain donor source copy contains **3006 files, zero donor hash mismatches**. All SHA256 entries populated (LiteralPath used for Svelte `[id]` names). No `.git` or generated build cache copied.
3. Fresh CMake/Ninja configure with original MSVC 14.44.35207/CUDA 12.6/sm86 Release configuration.
4. **143 CUDA compile commands match the donor exactly after normalizing only source/build roots. All target commands, including dependency/link commands, also match.**
5. Build job `pwsh-70` completed exit 0, final log step `[154/154] Linking CUDA shared library bin\ggml-cuda.dll`. Warnings were emitted by unchanged code (notably nvcc #221-D); no failed command or compile error was found. Do not describe this build as warning-free.
6. Export sets match: **11 vs 11, no delta**. Imported DLL/symbol sets match completely. No missing ggml-base imports and no missing CUDA imports in frozen runtime consumers. Source backend API version is 2.
7. No `LoadLibrary`, server launch/stop, GPU inference, numerical test or benchmark was executed by this lane. Static symbol matching alone cannot establish layout or numerical ABI compatibility.

## Parent next step

Use the isolated candidate with the parent's HTTP benchmark runner, one GPU owner at a time. Keep settings identical to baseline and compare deterministic output, errors and timings before profiling/patches. No live-runtime replacement.

The Nsight Systems plan and exact installed Windows options are in `README.md`. Important details: `--cuda-graph-trace=node`, `--sample=none`, `--cpuctxsw=none`, `--delay`, `--duration`, and **`--kill=false` (not `none`)**. Parent launches server through nsys, uses a separate HTTP client, allows timed capture to finalize, and explicitly stops its server afterward. Node tracing can impose substantial overhead; final speed verdicts come from unprofiled runs.

**Waiting for parent profile before any CUDA source patch.**
