# DS4 low-bit recovery probes, 2026-07-20

This directory freezes the CPU-only tools and receipts used to distinguish
weight-only Q1/ternary conversion from activation-aware recovery.

## Contents

- `ternary_b_microprobe/`: exact local GGUF offset/range probes, Q1 binary
  re-fit comparison, ternary fixed-budget probe and immutable JSON receipts.
- `activation_aware_trainer/`: fail-closed activation reader, bounded streaming
  binary/ternary recovery scaffold and synthetic unit tests.

## Verified conclusions

- Current Q1_0 and a fresh sign plus L2-scale g128 re-fit are numerically
  equivalent for block 3 expert 0.
- Q1 versus IQ2 teacher: cosine 0.811377, NMSE 0.341667.
- Ternary 1.296875 bpw weight-only: cosine 0.758266, NMSE 0.425033.
- Another weight-only converter is not the next discriminant.
- Real activation traces and exact-IQ2 teacher reconstruction are required
  before any recovery-quality claim.

## Scope limits

No GPU, DS4 server, model write, download or end-to-end quality run was used.
The trainer tests are synthetic. These files do not establish model quality,
throughput, n>=3 evidence or SOTA status.

Run the synthetic trainer checks from `activation_aware_trainer`:

```powershell
python -m unittest test_activation_trainer.py -v
python -m py_compile activation_reader.py activation_trainer.py test_activation_trainer.py
```
