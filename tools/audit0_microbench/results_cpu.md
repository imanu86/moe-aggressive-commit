# Audit #0 CPU results

**CPU leg: PASS. CPU/GPU decision: pending the deliberately unexecuted GPU
leg.**

The fastest eligible result is **294.4 µs/expert at 4 threads**. On this
8-physical-core host, four threads leave four physical cores free. Therefore:

```text
CPU wins iff 294.4 µs < GPU base_iq2_xxs_q2_k e2e_median_us
```

## Timings

Each row is the median of 101 individually timed complete expert FFNs after 32
warmups. The run cycles 32 GPTQ-backed experts in a 113,246,208-byte warm
working set.

| Threads | Leaves >=4 physical cores | Median µs | P10 µs | P90 µs | Min µs | Max µs | Mean µs |
|---:|:---:|---:|---:|---:|---:|---:|---:|
| 1 | yes | 1,050.4 | 1,032.2 | 1,131.3 | 1,019.9 | 1,268.0 | 1,064.333 |
| 4 | **yes** | **294.4** | 278.3 | 489.0 | 272.0 | 753.0 | 348.841 |
| 8 | no | 293.7 | 282.0 | 306.1 | 251.3 | 363.3 | 294.631 |
| 12 | no | 232.6 | 219.6 | 269.8 | 215.3 | 310.4 | 238.391 |

All four rows produced the same output checksum, `44.144`.

## Host and CPUID

- CPU: AMD Ryzen 7 5800X 8-Core Processor
- Topology reported by Windows: 8 physical cores, 16 logical processors
- CPUID plus XGETBV OS state: AVX available
- CPUID AVX2: true
- CPUID FMA: true
- CPUID F16C: true; used for fp16 scale conversion
- CPUID AVX-512F/DQ/BW/VL: all false
- Build flags: MSVC Release, `/O2 /arch:AVX2`
- OS registry identity: Windows 10 Pro, display version 25H2, build
  26200.8875
- Collection time: 2026-07-23 11:08 UTC

No thread affinity or elevated process priority was applied. The reported
median is the gate; the wider four-thread P90/maximum show normal Windows host
jitter and explain why the mean is not used.

## Input identity and validation

- Sidecar:
  `D:\ds4_work\q1_pilot_data\sidecar_L15_prod.gguf`
- File bytes: `909,526,048`
- SHA-256:
  `7124ede9ae9bfcff471df09f044de5f384904a2ce088b891f813dd426fef111a`
- GGUF version/data start/alignment: `3` / `9,248` / `32`
- Layer: `15`
- Tensor types: gate/up/down are all type `41`
- Tensor dimensions:
  - gate: `[4096,2048,256]`
  - up: `[4096,2048,256]`
  - down: `[2048,4096,256]`
- Bytes per matrix per expert: `1,179,648`
- Bytes per complete Q1 expert: `3,538,944`
- Total payload loaded into RAM: `113,246,208`
- GPTQ campaign expert IDs:
  `1,2,4,5,6,8,9,10,11,12,13,17,18,19,22,24,25,27,28,31,33,34,36,37,39,40,42,43,45,46,49,53`

The campaign provenance list came from
`D:\ds4_work\q1_pilot_data\gptq_campaign\results.tsv`, which contains 161
expert result rows. The benchmark selected only IDs present in that list, not
naive-filled sidecar slots.

Before timing, the AVX2 Q1_0 dot for the first real gate row was compared with
the scalar little-endian/little-bit-order decoder:

```text
scalar             1.23972917
AVX2               1.23972845
absolute error     7.15255737e-7
allowed tolerance  2.47945833e-4
```

Validation passed.

## Exact command

```powershell
.\tools\audit0_microbench\build\audit0_cpu.exe `
  --reps=101 --warmups=32
```

The sidecar path, layer 15, campaign TSV, 32-expert count, and thread set
`{1,4,8,12}` are executable defaults. The CPU process used approximately
108 MiB for encoded expert payloads, far below the 4 GiB audit cap. Nothing
was written to `D:`.
