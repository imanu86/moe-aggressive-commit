# Audit #0: cold-expert CPU/GPU microbenchmark

This directory is a go/no-go gate for handling a non-VRAM-resident MoE expert
on the CPU. It compares one complete batch-1 expert FFN:

1. CPU: fused Q1_0 dequantization and GEMV for gate, up, SwiGLU, and down,
   reading a warm working set in ordinary RAM.
2. GPU: pinned-RAM H2D, a deliberately naive CUDA dequant-GEMV FFN, and the
   required 16 KiB output D2H.

The CPU leg was run on the target host. The GPU executable was compiled but,
as required for audit #0, was **not run**. The measured CPU gate is
**294.4 µs/expert at four threads**, the fastest measured setting that leaves
at least four of this host's eight physical cores free. The final CPU/GPU
choice is pending the authored GPU CLI's single run.

## Decision rule

Use the strict rule requested for this audit:

```text
CPU wins iff eligible_CPU_median_us < base2_GPU_e2e_median_us
```

On this host, compare `294.4` with `e2e_median_us` from:

```text
GPU_RESULT variant=base_iq2_xxs_q2_k ...
```

The eligible CPU thread count must leave at least four **physical** cores free.
Eight and twelve benchmark threads are reported for scaling information but
are ineligible on the 8-core Ryzen 7 5800X. A tie does not pass the strict
CPU-wins rule.

## Verified formats and dimensions

The benchmark parses the GGUF header itself and fails closed on a tensor type,
rank, dimension, range, or Q1 block-alignment mismatch. The measured sidecar
reported:

| Matrix | GGUF dimensions | Type | Row bytes | Bytes/expert |
|---|---:|---:|---:|---:|
| gate | `[4096, 2048, 256]` | 41 | 576 | 1,179,648 |
| up | `[4096, 2048, 256]` | 41 | 576 | 1,179,648 |
| down | `[2048, 4096, 256]` | 41 | 288 | 1,179,648 |
| total | 25,165,824 weights | Q1_0 | — | **3,538,944** |

Q1_0 is 128 weights in 18 bytes: a little-endian fp16 scale followed by 16
sign bytes, with bit 0 describing the first weight in each byte. A set bit is
`+scale`; a clear bit is `-scale`. This is `18 * 8 / 128 = 1.125 bpw`.

The encoder reference is `tools/gptq_to_sidecar.py` (type table and
`_dequant_q1_block`). The read-only runtime reference at commit
`259c5b626058f8a553de9ea7cca00bae69fe1699` is:

- `D:/ds4_work/wt-g73-open/ds4.c`: `block_q1_0`, type 41, sidecar tensor
  validation, and routed expert byte geometry.
- `D:/ds4_work/wt-g73-open/ds4_cuda.cu`: Q1_0 bit polarity, Q1_0/Q8_K dot,
  and the gate/up/down qwarp kernels.

The CPU implementation uses fp32 activations and fused on-the-fly Q1_0
dequantization. It does not materialize fp32 weights.

### Actual base 2-bit footprint

Audit inspection of `C:/ds4-models/ds4-2bit.gguf` layer 15 confirmed the
current base representation rather than leaving the requested 7.6 MB figure
as an assumption:

| Matrix | Type | Block | Bytes/expert |
|---|---|---:|---:|
| gate | IQ2_XXS (16) | 66 B / 256 | 2,162,688 |
| up | IQ2_XXS (16) | 66 B / 256 | 2,162,688 |
| down | Q2_K (10) | 84 B / 256 | 2,752,512 |
| total | mixed base 2-bit | — | **7,077,888 B = 6.75 MiB = 7.078 MB** |

The GPU CLI still defaults to the explicitly requested **7.6 MB** H2D arm.
That is 522,112 bytes of transport padding beyond the confirmed encoded base
expert. For a source-exact footprint sensitivity run, pass
`--q2-copy-mb=7.077888`.

The requested 5.6 MB Q1 H2D arm likewise contains transport padding: the real
three-matrix Q1_0 payload is 3,538,944 bytes (3.375 MiB). The kernel consumes
the encoded prefix while `cudaMemcpyAsync` copies the full requested payload.

## Build

The paths below were taken from
`D:/ds4_work/wt-g73-open/build/CMakeCache.txt`:

- CUDA 12.6:
  `C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.6/bin/nvcc.exe`
- MSVC:
  `C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/cl.exe`
- Ninja:
  `C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe`

From the repository root:

```powershell
# CPU only
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\audit0_microbench\build.ps1 -CpuOnly

# CPU + authored CUDA target; compilation does not launch a CUDA workload
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\audit0_microbench\build.ps1
```

The CUDA target is compiled for `sm_86`. Both targets compiled successfully on
the audit host, so CUDA compilation is not blocked.

## Reproduce the CPU leg

```powershell
.\tools\audit0_microbench\build\audit0_cpu.exe `
  --sidecar=D:\ds4_work\q1_pilot_data\sidecar_L15_prod.gguf `
  --real-experts-tsv=D:\ds4_work\q1_pilot_data\gptq_campaign\results.tsv `
  --layer=15 --expert-count=32 --warmups=32 --reps=101
```

The TSV supplies IDs for 161 GPTQ-produced experts. The default run takes its
first 32 IDs, loads all three matrices for every selected expert into owned
RAM (113,246,208 bytes), pre-touches the entire set, and cycles the experts.
That working set exceeds the 5800X's 32 MiB L3, preventing a one-expert
cache-resident measurement while keeping every page warm. A persistent worker
pool avoids per-repetition thread creation. `QueryPerformanceCounter` brackets
each complete expert FFN.

The executable verifies AVX/AVX2 OS state with CPUID/XGETBV, reports FMA/F16C
and AVX-512 feature bits, and refuses to run without AVX2. It is compiled with
`/arch:AVX2`; no AVX-512 code is assumed or emitted. Before timing, one real
Q1_0 row is checked against a scalar decoder.

See [results_cpu.md](results_cpu.md) for the captured host result.

## Run the authored GPU leg once

Do not use this command during CPU-only collection. When GPU execution is
authorized, one invocation runs both requested transfer variants:

```powershell
.\tools\audit0_microbench\build\audit0_gpu.exe `
  --variant=all --warmups=10 --reps=101 `
  --q1-copy-mb=5.6 --q2-copy-mb=7.6
```

For each variant, one nonblocking CUDA stream performs:

```text
cudaMemcpyAsync(pinned host -> device, requested payload)
  -> naive gate/up dequant-GEMV
  -> SwiGLU
  -> naive down dequant-GEMV
  -> cudaMemcpyAsync(device -> pinned host, 16 KiB)
```

CUDA events produce a per-expert end-to-end median over 101 repetitions. A
separate event pair measures pure pinned H2D latency and GiB/s. Allocations,
payload initialization, activation upload, and warmups are outside the timed
samples.

The Q1 arm implements type 41 directly. The base arm implements the confirmed
IQ2_XXS gate/up and Q2_K down semantics, including the runtime's IQ2 grids and
sign table copied into this isolated directory. It intentionally uses a naive
fp32-activation kernel, as requested, rather than the runtime's optimized
Q8_K/qwarp kernel.

## Scope and interpretation

The CPU number includes all three GEMVs, SwiGLU, persistent-pool dispatch, and
the dependency barrier between the first two matrices and down. It excludes
routing, output integration, and any later 16 KiB CPU-to-GPU handoff.

The GPU end-to-end number includes the requested input transport and 16 KiB
output return, but excludes routing and allocation. The standalone GPU kernel
is intentionally a microbenchmark, not a call into the production runtime;
use its base2 end-to-end median only for this audit's stated gate.

Decode activates 6 experts across 40 routed layers (240 expert activations per
token), but no token-level extrapolation is used in the decision. Only the
cold subset would take the CPU path, so the deliverable and rule remain
per-expert.
