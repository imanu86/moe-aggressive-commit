# DS4 Q1_0 converter step 6: reference dequant helper

Scope:

- Adds a CPU-only helper in `tools/ds4_q1_ref.h`, `tools/ds4_q1_ref.c`,
  and `tools/ds4_q1_ref_tool.c`.
- Ports the minimal upstream reference path needed by the single-layer runtime
  sidecar converter:
  - `IQ2_XXS` type 16 dequant row.
  - `Q2_K` type 10 dequant row.
  - `Q1_0` type 41 quant/dequant row.
  - row/chunk conversion API: real payload row(s) -> float -> Q1_0 bytes.
- Keeps the helper in the knowledge repo only; no ds4-win runtime files are
  changed.

Primary source / license provenance:

- Upstream: `ggml-org/llama.cpp`
- Commit: `635cdd5fcc5bdeb8ec2e108bb2a40acf62d9039b`
- License: MIT
- Files/functions:
  - `ggml/src/ggml-common.h`: `block_q1_0`, `block_q2_K`,
    `block_iq2_xxs`, `kmask_iq2xs`, `ksigns_iq2xs`, `iq2xxs_grid`.
  - `ggml/src/ggml-quants.c`: `dequantize_row_iq2_xxs`,
    `dequantize_row_q2_K`, `quantize_row_q1_0_ref`,
    `dequantize_row_q1_0`, `quantize_q1_0`.

Generated local table:

- `tools/ds4_q1_ref_tables.inc`
- Generated from the exact upstream `ggml-common.h` commit above.
- Byte format verified as UTF-8/ASCII without BOM; first bytes are `2F 2A`.

Converter integration:

- `tools/ds4_q1_sidecar_converter.py` still fails closed for real type16/type10
  payloads unless `DS4_Q1_REF_TOOL` points at a built helper executable.
- With `DS4_Q1_REF_TOOL` set, `convert-runtime-single-layer` converts each
  selected tensor by rows using `dims[0]` as `ncols`:
  - type16 -> `iq2_xxs` dequant -> float -> Q1_0.
  - type10 -> `q2_k` dequant -> float -> Q1_0.
- Fixture conversion remains available without the helper only for the
  synthetic int16 fixture path.

Build/test:

```powershell
python -m pytest tests\test_ds4_q1_ref_helper.py tests\test_ds4_q1_sidecar_converter.py tests\test_ds4_q1_runtime_step3_patch.py tests\test_ds4_q1_blocker_patch.py tests\test_ds4_patch_chain_apply.py tests\test_ds4_q1_runtime_patch.py tests\test_ds4_q1_runtime_step2_patch.py tests\test_ds4_q1_smoke.py -q
```

Result:

- `44 passed`
- The helper is compiled by pytest using MSVC `vcvars64.bat` + `cl`.
- Golden vectors:
  - Q2_K block with independent Python dequant formula and Q1_0 packing.
  - IQ2_XXS all-zero block, independently expected as all `+1.0` after
    dequant at `d=1.0`.
  - Runtime sidecar fixture with type16 gate/up and type10 down accepted only
    when `DS4_Q1_REF_TOOL` is explicitly set.

Real-model estimate, still no payload conversion:

```powershell
python tools\ds4_q1_sidecar_converter.py estimate-runtime C:\ds4-models\ds4-2bit.gguf C:\ds4-models\ds4-q1-layer42-derived.gguf C:\ds4-models\ds4-q1-layer42-derived.manifest.json --layer 42
```

- Estimated selected payload read: `1813389312` bytes (`1.689 GiB`).
- Estimated sidecar payload before GGUF header/alignment: `907419648` bytes
  (`865.383 MiB`).
- Target layer: `42`.
- Converted tensors if authorized: `blk.42.ffn_gate_exps.weight`,
  `blk.42.ffn_up_exps.weight`, `blk.42.ffn_down_exps.weight`.
- Copied byte-identical tensors: `blk.0..42.{attn_norm,ffn_norm}.weight` and
  `blk.3..42.exp_probs_b.bias`.

Command prepared for the first real conversion after explicit coordination:

```powershell
$env:DS4_Q1_REF_TOOL = "<built>\ds4_q1_ref_tool.exe"
python tools\ds4_q1_sidecar_converter.py convert-runtime-single-layer C:\ds4-models\ds4-2bit.gguf C:\ds4-models\ds4-q1-layer42-derived.gguf C:\ds4-models\ds4-q1-layer42-derived.manifest.json --layer 42
python tools\ds4_q1_sidecar_converter.py validate-runtime C:\ds4-models\ds4-2bit.gguf C:\ds4-models\ds4-q1-layer42-derived.gguf C:\ds4-models\ds4-q1-layer42-derived.manifest.json
```

Do not run the conversion command until the main task explicitly authorizes
reading the selected ~1.69 GiB payload from `C:\ds4-models\ds4-2bit.gguf`.

Limits:

- This produces an IQ2-derived deterministic sidecar, not a quality-optimal
  sidecar. Manifest marks `derived_from_IQ2=true` and
  `not_quality_optimal=true`.
- No quality or speed claim is made.
- No DS4 launch, GPU run, large model payload read, full-model hash, or
  full-model copy was performed in this step.
