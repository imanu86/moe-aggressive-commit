# DS4 Q1_0 converter step 6 gate: IQ2_XXS golden hardening

Scope:

- Adds a non-trivial IQ2_XXS golden test before any real DS4 payload
  conversion is authorized.
- Hardens `tools/ds4_q1_ref_tool.c` and `tools/ds4_q1_ref.c` against size
  overflow and non-exact stdin payloads.
- Does not touch ds4-win runtime files.

New IQ2_XXS golden:

- Test: `test_ref_tool_converts_iq2_xxs_nontrivial_two_rows_two_blocks_golden`
  in `tests/test_ds4_q1_ref_helper.py`.
- Shape: `2` rows, `512` columns, therefore `2` IQ2_XXS blocks per row and
  `4` IQ2_XXS blocks total.
- Exercises:
  - multiple grid indices, including values such as `1`, `42`, `73`, `170`,
    `201`, `230`, and `255`;
  - multiple sign-index patterns;
  - nonzero scale nibbles for every 32-value group;
  - different half scales per block.
- Expected output is built independently in Python by unpacking the IQ2_XXS
  fields, applying the sign parity rule, computing float values, then packing
  Q1_0 bytes. The test compares Q1 output byte-for-byte.

Tool hardening:

- `ds4_q1_ref_row_size()` now checks row-size multiplication before returning
  `blocks * block_bytes`.
- `ds4_q1_ref_convert_rows_to_q1_0()` now checks:
  - `nrows * src_row`;
  - `nrows * dst_row`;
  - `ncols * sizeof(float)`;
  - exact `src_size` and `dst_size`, not just "large enough".
- `ds4_q1_ref_tool.c` now checks:
  - `src_row * nrows` overflow;
  - `dst_row * nrows` overflow;
  - stdin too short;
  - stdin too long;
  - exact stdout write length.

Tests:

```powershell
python -m pytest tests\test_ds4_q1_ref_helper.py tests\test_ds4_q1_sidecar_converter.py tests\test_ds4_q1_runtime_step3_patch.py tests\test_ds4_q1_blocker_patch.py tests\test_ds4_patch_chain_apply.py tests\test_ds4_q1_runtime_patch.py tests\test_ds4_q1_runtime_step2_patch.py tests\test_ds4_q1_smoke.py -q
```

Result:

- `46 passed`
- CPU-only helper build via MSVC `vcvars64.bat` + `cl`.

Status:

- No DS4 launch.
- No GPU run.
- No real conversion.
- No large model payload read/hash/copy.
- The prepared real conversion command remains gated on explicit coordination.
