Fork main aligned to upstream **0.1.39** (`6f32ec0`), keeping the SM75
ports, the automatic two-zone elastic expert cache (fork-only), wide top-k (PR603) and the near-tail checkpoint
(PR614).  New in the fork since 0.1.38 (all off by default): next-layer PCIe prefetch, swappable elastic core,
WDDM budget / NVML figures in `STRATA_TRACE`, CPU and GPU expert format benches.

Validated on a modified **RTX 2080 Ti 22 GB**, Ryzen 5800X/AVX2, 96 GB RAM, Windows, CUDA 12.6, IQ3_XXS,
KV 262144/int8/resident 32768, the Daily's own configuration:

- Decode at 131k (Daily configuration): L01 51.4 / L02 44.2 tok/s against 38.7 / 38.0 for the 0.1.38 Daily; the port build without this fork's lab commits measured 46.4-43.4 / 41.3-41.8.  Prefill unchanged (123 vs 129 s for 131k).
- Teacher-forced fidelity against the 0.1.38 Daily on code/explain/ledger: KL 0.0004 / 0.0020 / 0.0001 (Daily A/A 0.0004 / 0.0005 / 0.0001), perplexity -0.16% / -2.10% / +1.07%: no systematic shift.
- Full SM75 build, 8/8 CTest parity checks, 64 real-GGUF CPU pool cases bitwise; 262 of 271 server tests pass, 7 skipped, the 2 errors are a locale issue of the test and one that fails identically on stock upstream.

General model quality, stock 11 GB cards and multi-GPU are not validated.
Executable SHA256: `dd82377ab682108bb6a8e2480727a27e211400df8dd01a4801144a0843270791`.

The ZIP holds the exact tested and installed shipping engine, MIT notices, provenance and validation.
Requires the CUDA 12.6 runtime/cuBLAS and the Microsoft VC++ x64 runtime; supply the weights separately.
Previous releases remain available for rollback.
