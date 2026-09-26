# Qwen3.5-4B kernel lane: isolated unmodified-backend gate

**Final status: OCC12 rejected for promotion.** Read `FINAL_RESULT.md` for the completed experiment: 12/12 kernel fixtures and 15/15 runtime text outputs matched, activation was proven, but clean runtime speed did not improve. Daily runtime was not modified by this lane. The sections below record the initial phase-1 isolation/build plan; current lab `bin-candidate` contains the rejected default-OFF OCC12 experiment, while its prior unmodified rebuild is preserved under `evidence\unmodified-rebuild`.

## Scope and safety

User-approved branch: `research/ds4-iq1-subbit-tier-planner`. No commits, pushes, branches, worktrees or upstream PRs in this lane. Existing untracked research files are untouched.

Lab: `D:\ds4_work\qwen4b_kernel_lab`.

- `source`: plain frozen copy of `C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920\source`, excluding `.git` and generated build/cache directories.
- `build`: fresh isolated CMake/Ninja build.
- `bin-baseline`: byte-identical copy of `D:\ds4_work\bin_q36m3`, never replace its DLLs.
- `bin-candidate`: initially identical copy; only its `ggml-cuda.dll` may later be replaced with the unmodified rebuild after the static ABI gate.
- `evidence`: copy manifests, logs, ABI records and future parent-owned profiling output.

Donor and live runtime are read-only inputs. Kernel ownership is limited to local `source\ggml\src\ggml-cuda`. No graph/context/model-source changes. Phase 1 makes NO kernel patches. No server starts/stops or GPU inference/benchmarks are performed by this lane. Parent owns GPU scheduling and runtime tests.

## Frozen evidence

- `evidence\runtime-initial-sha256.csv`: all live, baseline and initial candidate file hashes.
- `evidence\source-initial-sha256.csv`: every copied source-file hash.
- `evidence\source-copy-verification.json`: copied files compared against donor.
- `evidence\donor-CMakeCache.txt`: original build configuration, copied unchanged.
- Existing provenance: `D:\ds4_work\elastico_q36_m3\evidence\q36m3-build-manifest.json`.

The frozen live CUDA DLL SHA256 is `A8E6D2A95C1FCAA14D28914CEE1657E7E492A9B788AFAAF5430D8019E667886E`.

## Build recipe

Run `D:\ds4_work\qwen4b_kernel_lab\configure-build.cmd`.

Matched settings: Visual Studio 2022 Community, MSVC 14.44.35207 (compiler 19.44.35227), CUDA 12.6, Ninja, Release, sm86, shared backend, backend DL OFF, CUDA graphs ON, flash attention ON, FA_ALL_QUANTS OFF, forced MMQ/CUBLAS OFF, compression=size, VMM ON and peer-copy ON.

CMake disables common/server/tools/tests/examples/MTMD/UI/app. Only target `ggml-cuda` is built, with its required `ggml-base` dependency. **The rebuilt ggml-base.dll is NOT installed into either runtime copy.** Actual C/C++ and CUDA Release flags are checked against the original cache.

`verify-abi.ps1` compares exported symbols and imported dependencies; checks that the rebuilt CUDA DLL's ggml-base imports exist in the frozen live ggml-base; and checks that frozen runtime consumers can resolve their CUDA imports. This is a static symbol gate, not proof of internal-struct ABI or numerical equivalence. No LoadLibrary or runtime execution is part of it.

Status/results will be recorded in `PHASE1_RESULT.md` after compilation settles.

## Parent-only source/binary drift gate

Before any kernel patch, compare frozen `bin-baseline` against `bin-candidate` containing only the unmodified CUDA rebuild. Keep identical model, prompt, sampling, context, env, KV types, batching and checkpoint settings. Check output/token equivalence under deterministic settings, prompt/decode timings, memory footprint and errors. A nonidentical DLL hash by itself is not a failure (new path, linker timestamps, build metadata); a semantic/performance regression must be explained before proceeding.

No patched candidate is authorized until the parent supplies the baseline profile.

## Proposed Nsight Systems command (NOT executed)

Installed executable:
`C:\Program Files\NVIDIA Corporation\Nsight Systems 2024.5.1\target-windows-x64\nsys.exe`

Example CMD command for an isolated frozen baseline server, to be scheduled/run by the parent only. Port 8114 is illustrative: verify it is free. Set `LLAMA_API_KEY` privately in the parent environment (do not write a credential into this document). Restore the same workload/env options used for the corresponding unprofiled run.

```bat
set GGML_SCHED_ASYNC_INPUTS=1
set GGML_CUDA_GRAPH_COMPAT_CACHE=1
set GGML_CUDA_MMVQ_OCCUPANCY=1
"C:\Program Files\NVIDIA Corporation\Nsight Systems 2024.5.1\target-windows-x64\nsys.exe" profile ^
  --trace=cuda,nvtx --cuda-graph-trace=node --sample=none --cpuctxsw=none ^
  --delay=30 --duration=45 --kill=false --force-overwrite=false ^
  --output=D:\ds4_work\qwen4b_kernel_lab\evidence\baseline-node-profile ^
  D:\ds4_work\qwen4b_kernel_lab\bin-baseline\llama-server.exe ^
  -m D:\models\qwen35-4b\Qwen3.5-4B-Q4_K_M.gguf ^
  --alias qwen3.5-4b-kernel-baseline --host 127.0.0.1 --port 8114 ^
  -ngl 99 -fit off -fa on --no-mmap -ctk q8_0 -ctv q8_0 ^
  -b 2048 -ub 512 -t 16 -c 131072 -np 1 ^
  --jinja --reasoning on --no-reasoning-preserve ^
  --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repeat-penalty 1 ^
  --no-context-shift --cache-ram 0 -ctxcp 8
```

Parent warms up through HTTP before the 30-second delay ends, then issues a controlled decode during capture. Adjust delay/window to actual cold-prefill duration. For useful measurements, separate prefill and steady decode (short prompt first, then a distinct long-context experiment). Parent stops its profiling server after capture: `--kill=false` intentionally leaves it alive. Never overlap another GPU workload.

Node-level CUDA graph tracing can impose **significant overhead** (installed help lines 88-107). Use it for attribution/kernel counts, not final throughput claims. Use unprofiled repeats for performance verdicts. Count actually launched kernels, not graph nodes alone; inspect launch gaps, synchronization, MMVQ/MMQ, recurrent GDN and attention kernels. Only then choose a local CUDA patch.

Audit leads, not preselected changes: RMS+weight+SiLU gate; ADD+SOFTPLUS+MUL; existing fusion coverage; Q4_K/Q6_K matrix-vector bandwidth. `GGML_CUDA_MMVQ_OCCUPANCY` only affects IQ2_S/IQ4_NL in this donor, so toggling it is not a Q4_K optimization.
