# GPTQ teacher extraction on Linux

## What changed

`tools/make_teacher_outputs.py` is a compatible copy of the existing teacher
driver with one additional selector:

- `--backend auto` (the default) selects `msvc` on Windows and `gcc` elsewhere.
- `--backend msvc` keeps the existing behavior: it extracts the teacher-only
  main from `ste_backend.cpp`, calls `vcvars64.bat`, and links the Windows
  libraries.
- `--backend gcc` builds `tools/teacher_backend_portable.cpp` with `g++`. It
  does not read the legacy trainer tree and does not inspect `--vcvars64`.

All original command-line arguments remain accepted. The extra `--build-only`
mode lets the campaign compile once before starting parallel workers.

The portable helper uses the existing tracked `tools/ds4_q1_ref.c` directly.
It does not contain a second IQ2_XXS or Q2_K implementation. Its GGUF tensor
geometry, expert addressing, output matrix layout, SwiGLU, and scalar reference
forward follow the Windows `ste_backend.cpp` code.

The GCC build deliberately uses `-ffp-contract=off -fno-fast-math`. This keeps
the reference forward scalar and prevents contraction/reassociation. Weight
dequantization is independent of the forward and is the same
`ds4_q1_ref_dequant_row()` call on both paths.

## Equivalence evidence

The checked-in reference was also compared to the read-only runtime source
`D:/ds4_work/wt-g73-open/ds4.c`:

- GGUF type IDs match: Q2_K = 10 and IQ2_XXS = 16.
- Block sizes match: Q2_K = 84 bytes and IQ2_XXS = 66 bytes for QK_K = 256.
- All three IQ2 tables match value-for-value: `kmask_iq2xs` (8 values),
  `ksigns_iq2xs` (128 values), and `iq2xxs_grid` (256 values).
- The CUDA copies of the 128 sign values and 256 grid values also match the
  checked-in reference exactly; `ds4_cuda.cu` uses the same 84-byte Q2_K and
  66-byte IQ2_XXS layouts and equivalent integer dot-product equations.
- The Q2_K scale/min unpacking and IQ2_XXS grid/sign/scale equations in
  `ds4_q1_ref.c` are the scalar dequant forms corresponding to the runtime dot
  kernels.

The portable source was built locally with MSVC `/O2 /fp:strict` and run on
model `C:/ds4-models/ds4-2bit.gguf`, layer 15, expert 176, using the 256-row
`L15_e176` trace. Its raw matrix payloads were compared with
`D:/ds4_work/q1_pilot_data/abl_176_clean_lora0/weights.npz`, produced by the
legacy Windows helper. All float32 bit patterns matched:

| Matrix | Raw bytes | SHA-256 |
|---|---:|---|
| gate | 33,554,432 | `6082c1bd81f533fcbffdf889adf31b91db20c25a84b739aabe40b2970c007681` |
| up | 33,554,432 | `550bedad2c8110958a94632f1695a25849366b346fd2e755bc8d1dc073d463eb` |
| down | 33,554,432 | `b6d928922ab48c46ca320c24bfc7451401812ea4af929cfaf43d17c87d2a4c61` |

There is no GCC or Linux runtime installed on this workstation, so the final
cross-compiler assertion must be run on the pod. `compare_teacher_weights.py`
compares the uncompressed array payloads, dtype, and shape byte-for-byte; it
does not mistake ZIP compression/timestamps for weight differences.

Produce the Windows baseline:

```powershell
python tools/make_teacher_outputs.py `
  --backend msvc `
  --trace D:\ds4_work\q1_pilot_data\e176_n256\L15_e176.manifest.json `
  --teacher C:\ds4-models\ds4-2bit.gguf `
  --layer 15 --expert 176 `
  --out D:\teacher_equiv\msvc_teacher.npz `
  --weights-out D:\teacher_equiv\msvc_weights.npz
```

Copy `msvc_weights.npz` and the same trace triplet
(`manifest.json`, `vectors.f32le`, `samples.jsonl`) to the pod, then run:

```bash
python3 tools/make_teacher_outputs.py \
  --backend gcc \
  --trace /workspace/equiv/L15_e176.manifest.json \
  --teacher /workspace/ds4-2bit.gguf \
  --layer 15 --expert 176 \
  --out /workspace/equiv/gcc_teacher.npz \
  --weights-out /workspace/equiv/gcc_weights.npz

python3 tools/compare_teacher_weights.py \
  /workspace/equiv/msvc_weights.npz \
  /workspace/equiv/gcc_weights.npz
```

Success ends with `"exact": true` and reports a SHA-256 for each raw matrix.

## Measured cost

For the same L15/e176 case, with `OMP_NUM_THREADS=16`, the portable helper
reported:

| Operation | Time |
|---|---:|
| Dequantize one complete expert (gate + up + down, 25,165,824 float32 weights) | 0.240753 s |
| Reference forward, 256 captured inputs | 0.326087 s |
| Decode + forward | 0.566839 s |
| Helper wall time including trace/model/raw I/O | 0.650189 s |

This is a measured Windows/MSVC run of the portable source, not an estimate.
The Linux helper writes `decode_seconds`, `forward_seconds`, and
`decode_forward_seconds` into every `teacher_y.meta.json`, so the first pod
expert gives the directly comparable GCC number. Forward cost scales with the
deduped sample count; the constant per-expert dequant cost is the 0.241 s row
above. NPZ compression happens in the Python wrapper and is not included in
the helper timing.

## Full campaign

The campaign discovers every `*.L{3..42}.manifest.json`. For each layer it
counts deduped `(request_epoch, call_tick, token_index)` keys per expert,
matching `extract_expert_shard.py --dedup`, and retains experts with at least
200 rows. Every prefix found for a layer is passed to the extractor as a
separate repeated `--trace`.

Recommended command on the 256-vCPU pod:

```bash
cd /workspace/moe-aggressive-commit

bash tools/run_gptq_campaign_linux.sh /workspace/captures \
  --teacher /workspace/ds4-2bit.gguf \
  --bonsai-dir /workspace/c7_bonsai \
  --out /workspace/gptq_full_model \
  -P 40
```

Use `-P 32` to reduce concurrent memory pressure or `-P 48` for more
throughput. The script assigns `floor(nproc / P)` OpenMP/BLAS threads to each
worker, compiles the GCC helper once, and then uses GNU `xargs -P`.

Outputs are:

```text
/workspace/gptq_full_model/
  tasks.tsv
  results.tsv                         # expert, layer, n_samples, cosine
  L03/e000/q1/{gate,up,down}.q1.npz
  L03/e000/q1/manifest.json
  L03/e000/result.tsv
  L03/e000/campaign.log
  ...
```

A task is complete only when its Q1 manifest and all three Q1 NPZs exist.
Completed tasks are skipped on rerun. Failed tasks keep their intermediate
files and resume from the last completed extraction/teacher stage. After a
successful solve the default cleanup retains the Q1 NPZs, manifest, log, and
result fragment while removing the much larger shard, calibration, teacher
output, and float32 weights. Pass `--keep-work` to retain those intermediates.

To inspect eligibility without building or launching any expert jobs:

```bash
bash tools/run_gptq_campaign_linux.sh /workspace/captures \
  --out /workspace/gptq_full_model \
  --plan-only
```

## Focused validation

The focused tests cover backend selection, the strict GCC build command,
absence of Windows API dependencies, trace hash validation, bitwise NPZ
comparison, actual `g++` compilation when available, and campaign invariants:

```bash
python3 -m pytest -q tests/test_make_teacher_outputs_linux.py
bash -n tools/run_gptq_campaign_linux.sh
```

The campaign itself is intentionally not part of the tests and was not run.
