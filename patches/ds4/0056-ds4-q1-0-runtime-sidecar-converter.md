# DS4 Q1_0 runtime sidecar converter step 5

Tool: `tools/ds4_q1_sidecar_converter.py`

Scope:

- Builds a runtime-shaped Q1_0 sidecar for one routed layer on synthetic fixtures.
- Preserves required DS4 metadata raw bytes, including `general.name`, shape/config keys, compression-ratio arrays, and SwiGLU clamp arrays.
- Copies `blk.*.attn_norm.weight`, `blk.*.ffn_norm.weight`, and `blk.3..42.exp_probs_b.bias` byte-identically.
- Converts only `blk.<layer>.ffn_gate_exps.weight`, `blk.<layer>.ffn_up_exps.weight`, and `blk.<layer>.ffn_down_exps.weight` to Q1_0 in the fixture path.
- Emits a manifest with per-tensor source/output offsets, sizes, hashes, `derived_from_IQ2=true`, and `not_quality_optimal=true`.

Real model estimate:

Command:

```powershell
python tools\ds4_q1_sidecar_converter.py estimate-runtime C:\ds4-models\ds4-2bit.gguf C:\ds4-models\ds4-q1-layer42-derived.gguf C:\ds4-models\ds4-q1-layer42-derived.manifest.json --layer 42
```

Result:

- Estimated selected payload read: `1813389312` bytes (`1.689 GiB`).
- Estimated output payload before GGUF header/alignment: `907419648` bytes (`865.383 MiB`).
- Target layer: `42`.
- Required routed tensors to convert: gate/up/down for layer 42.
- Required byte-identical copy tensors: attn/ffn norm for layers 0..42 and `exp_probs_b.bias` for layers 3..42.

Negative result / fail-closed boundary:

- The real-model path currently refuses to convert type 16/10 payloads until the exact IQ2_XXS and Q2_K dequantizers are ported into the converter.
- Local `gguf-tools/quants.c` is not sufficient as a production dequant source for this step: it can quantize IQ2_XXS/Q2_K from float, while Q1_0 is metadata-only (`can_quantize=false`), so it must not be used to manufacture real DS4 Q1_0 bytes.
- Real conversion is marked BLOCKED until the converter uses provenance-verified production dequantization for IQ2_XXS and Q2_K, a verified Q1_0 row quantizer, and block-level golden tests against an independent upstream implementation.
- This prevents producing a plausible-but-wrong sidecar and satisfies the no-zero-output requirement on the tested fixture path.
- Full-quality path remains: derive Q1_0 from a richer checkpoint/original precision weights, not from IQ2-derived values, before making any quality claim.

No DS4 runtime, GPU run, full-model hash, or full-model copy was used.
