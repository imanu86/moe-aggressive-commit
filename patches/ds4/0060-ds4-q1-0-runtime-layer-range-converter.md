# DS4 Q1_0 runtime layer-range converter

Scope:

- Adds runtime Q1_0 sidecar conversion for a layer range `3..N`.
- Keeps the existing `convert-runtime-single-layer` command unchanged.
- Does not run DS4 or use the GPU. The first real layer `3..42` conversion is
  tracked separately from the runtime benchmark and remains an IQ2-derived
  transport experiment, not a quality claim.

New commands:

```powershell
python tools\ds4_q1_sidecar_converter.py estimate-runtime-layer-range SOURCE.gguf OUT.gguf OUT.manifest.json --layer-first 3 --layer-last 42
python tools\ds4_q1_sidecar_converter.py convert-runtime-layer-range SOURCE.gguf OUT.gguf OUT.manifest.json --layer-first 3 --layer-last 42
```

Behavior:

- Copies shared runtime tensors once: `attn_norm`, `ffn_norm`, and
  `exp_probs_b.bias`.
- Copies one router identity tensor, `ffn_gate_inp.weight`, for every selected
  layer.
- Converts `ffn_gate_exps`, `ffn_up_exps`, and `ffn_down_exps` to Q1_0 for
  every selected layer.
- Emits manifest fields `layers`, `layer_first`, and `layer_last` while keeping
  `layer` as the first selected layer for compatibility.
- Validator accepts both legacy single-layer manifests and new layer-range
  manifests, and keeps streaming full-file SHA checks.
- Real conversion writes to PID-scoped `.partial` files and atomically
  publishes the sidecar and manifest only after validation.
- Copy tensors are streamed in 8 MiB chunks. Routed tensors are converted in
  bounded three-tensor batches; `DS4_Q1_CONVERTER_WORKERS=1..3` controls CPU
  parallelism.
- Helper provenance fails closed when the recorded executable is unavailable.

Measured plan for the canonical DS4 IQ2 model, layers `3..42`:

- selected source bytes read: `72,562,909,184`
- expected Q1 sidecar bytes: `36,324,122,624` (`33.83 GiB`)
- source model SHA-256 is bound by the verified-file receipt used by G111.

Tests:

```powershell
python -m pytest tests\test_ds4_q1_ref_helper.py tests\test_ds4_q1_sidecar_converter.py -q
```

Current result: `13 passed`.

## Incremental extension from an existing Q1 base

Follow-up scope:

- Adds an explicit `extend-runtime-layer-range` command.
- Input 1 is the authoritative primary IQ2 GGUF.
- Input 2 is an existing runtime Q1 sidecar, expected by default to contain
  layers `3..42`.
- Output is a new runtime Q1 sidecar covering the reused base tensors plus the
  missing converted prefix layers.
- The real intended use is:

```powershell
python tools\ds4_q1_sidecar_converter.py estimate-extend-runtime-layer-range `
  C:\ds4-models\ds4-2bit.gguf `
  C:\ds4-models\ds4-q1-layers3-42-derived.gguf `
  C:\ds4-models\ds4-q1-layers0-42-derived.gguf `
  C:\ds4-models\ds4-q1-layers0-42-derived.manifest.json

python tools\ds4_q1_sidecar_converter.py extend-runtime-layer-range `
  C:\ds4-models\ds4-2bit.gguf `
  C:\ds4-models\ds4-q1-layers3-42-derived.gguf `
  C:\ds4-models\ds4-q1-layers0-42-derived.gguf `
  C:\ds4-models\ds4-q1-layers0-42-derived.manifest.json
```

The command was implemented but the real large conversion was not run here.

Fail-closed guarantees:

- Output and manifest are PID-scoped `.partial.*` files until full validation
  passes, then are published with `os.replace`.
- Manifest records streaming SHA-256 for the primary IQ2, base Q1 sidecar, and
  final output.
- Base tensors are reused byte-identically and carry
  `reuse_q1_byte_identical_from_base`.
- Prefix layer tensors copied from the primary carry
  `copy_primary_byte_identical`.
- Prefix routed tensors converted from the primary carry
  `convert_primary_iq2_or_q2_to_q1_0`.
- Validator rejects stale primary/base/output hashes, missing tensors,
  duplicate tensors, metadata mismatches, non-Q1 reused routed tensors, and
  byte-identical copy hash mismatches.
- Conversion remains bounded: base tensors are streamed in 8 MiB chunks and
  missing prefix routed tensors are converted one tensor at a time.

Synthetic coverage:

- Builds a tiny primary fixture with layers `0..5`.
- Builds a tiny base sidecar for layers `3..5`.
- Extends it with converted layers `0..2`.
- Verifies the final sidecar contains Q1 routed tensors for `0..5`, that
  reused base tensors are byte-identical, and that stale base hashes fail.
