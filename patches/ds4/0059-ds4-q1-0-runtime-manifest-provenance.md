# DS4 Q1_0 runtime manifest provenance fix

Scope:

- Fixes stale runtime manifest provenance before the first real payload
  conversion.
- Does not run DS4, GPU, or real conversion.
- Does not read/hash/copy large model payloads.

Manifest changes:

- `quality_note` is now:
  `production IQ2_XXS/Q2_K -> float -> Q1_0 reference conversion for real payloads; not quality-optimal`
- `conversion_source` records the primary upstream source:
  `ggml-org/llama.cpp` commit
  `635cdd5fcc5bdeb8ec2e108bb2a40acf62d9039b`,
  `ggml/src/ggml-quants.c`, and `ggml/src/ggml-common.h`.
- The stale `blocked_real_dequant_source` field is no longer emitted and is
  rejected by the runtime manifest validator.
- `helper` records the explicit `DS4_Q1_REF_TOOL` helper path, size, and
  streaming SHA-256 when the helper is available. Fixture-only conversion
  without a helper records `helper: null`.
- `output.sha256` is now computed with streaming file hashing, not
  `read_bytes()`, so the ~865 MiB sidecar path is safe.
- Metadata records include `key`, `value_type`, decoded `value`, and
  `raw_sha256`.

Validator hardening:

- Verifies runtime `quality_note`, `conversion_source`, and absence of the
  stale blocked field.
- Verifies output full-file SHA-256 via streaming hash.
- Verifies helper path/size/SHA when `DS4_Q1_REF_TOOL` is available or when the
  manifest helper path exists.
- Verifies metadata value/type/raw hash against parsed source metadata and
  sidecar metadata.
- Verifies complete and unique tensor records against expected runtime sidecar
  tensor names for the selected layer.

Tests:

```powershell
python -m pytest tests\test_ds4_q1_ref_helper.py tests\test_ds4_q1_sidecar_converter.py tests\test_ds4_q1_runtime_step3_patch.py tests\test_ds4_q1_blocker_patch.py tests\test_ds4_patch_chain_apply.py tests\test_ds4_q1_runtime_patch.py tests\test_ds4_q1_runtime_step2_patch.py tests\test_ds4_q1_smoke.py -q
```

Result:

- `47 passed`

Real-model estimate repeated, still header/directory only:

```powershell
python tools\ds4_q1_sidecar_converter.py estimate-runtime C:\ds4-models\ds4-2bit.gguf C:\ds4-models\ds4-q1-layer42-derived.gguf C:\ds4-models\ds4-q1-layer42-derived.manifest.json --layer 42
```

- Estimated selected payload read: `1813389312` bytes (`1.689 GiB`).
- Estimated sidecar payload before GGUF header/alignment: `907419648` bytes
  (`865.383 MiB`).
