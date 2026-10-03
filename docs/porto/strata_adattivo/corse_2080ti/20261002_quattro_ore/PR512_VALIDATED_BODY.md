With `--max-context 262144`, QSA score rows have a stride of 65538 blocks. A prefill batch at 131K actual context fits the register top-k kernel's 33792-block limit, but CUDA dispatch currently tests the allocated capacity and selects the reference kernel.

This enables the already supplied `active_blocks` bound **only on sm_75**. It keeps the score-row stride, selection arithmetic and kernel bodies unchanged. Other CUDA architectures retain the capacity rule, including the RTX 5070 case documented in the current source as a 1–3% regression. HIP retains its existing policy. Decode omits the bound, so captured graphs keep the capacity rule as their context grows. Invalid bounds and contexts beyond the register limit fall back to the existing dispatch. Presence of `STRATA_TOPK_CAPACITY_GUARD` restores the CUDA capacity rule for A/B runs.

The change reuses upstream's existing API and prefill caller rather than importing the separate API from our 0.1.31 fork. A CUDA parity target covers 16 cases with stride 65538: partial tails, zero/tied scores, batch sizes 1/8/255/256/257, invalid bounds, and both sides of the 33792-block limit.

### Retained measurements on our previous daily

Modified RTX 2080 Ti 22 GB, Ryzen 7 5800X, 96 GB RAM, Windows, CUDA 12.6, IQ3_XXS, KV262144/int8/resident32768, automatic elastic expert cache and MTP. Same-executable capacity/active/capacity A/B/A, two 1024-token outputs per arm; fresh prompt131248, second prompt131239 with131072 reused.

| Dispatch | Fresh prefill tok/s | TTFT seconds | Aggregate decode tok/s |
|---|---:|---:|---:|
| Capacity A1 | 831.20 | 158.509 | 38.251 |
| Active B | 886.38 | 148.664 | 39.272 |
| Capacity A2 | 828.26 | 159.092 | 39.293 |

Prefill **+6.83%** relative to the mean reference; reference spread0.35%. TTFT saves10.14s. **No decode gain attributed to this change.** The kernel fixture passed16 bitwise selected-ID cases. At8192 context the register kernel was slower in the microbenchmark; no universal short-prompt improvement is claimed. Elastic slots and MTP output varied, and whole-model logits were not bitwise even between the reference arms.

[Full measurement record, fixture cases and limitations](https://github.com/imanu86/moe-aggressive-commit/blob/research/ds4-iq1-subbit-tier-planner/docs/porto/strata_adattivo/RISULTATI_TOPK_2_OTTOBRE.md).

### Isolated validation against upstream 0.1.37

Built a plain upstream `db4f91a1171d697928b0d2e1f50ef95e25559d4c` source export with **only this PR's four-file delta** (published head `42131caf08c5f45329a97341590655e01664790a`). No other fork optimizations were present. The full CMake engine and `qsa_topk_active_parity` built with CUDA12.6, MSVC14.44, Release, sm75. All16 selected-ID parity cases passed bitwise again.

Same modified22GB RTX2080Ti / Ryzen5800X /96GB RAM, IQ3_XXS. Same executable capacity/active/capacity, KV262144/int8/resident32768, PCIe0.28, prefillauto, spec4 with default lookup3, two1024-token outputs per arm. Fresh prompt131248 tokens; follow-up131239 with131072 reused. Fixed5357 actual expert slots (requested budget4000), adaptation settings unchanged, no elasticity and no artificial pressure. Initial freeVRAM2222/2222/2197MiB. An earlier fixed6167-slot attempt was stopped before sending any prompt because887MiB free was below the test's1000MiB margin; it is excluded from this completed comparison.

| Dispatch | Fresh prefill tok/s | TTFT seconds | Aggregate decode tok/s |
|---|---:|---:|---:|
| Capacity A1 | 457.26 | 287.638 | 39.338 |
| Active B | 521.45 | 252.304 | 40.568 |
| Capacity A2 | 774.41 | 170.082 | 40.597 |

The measured active rate is **-15.33%** relative to the mean reference, but the two references themselves differ by **51.50%**. The performance comparison is **inconclusive**: no reliable speed gain or regression can be attributed to this patch from this run. No decode gain is attributed to this prefill dispatch change. This is an isolated upstream laboratory run, not a new record for our separate Turing fork, whose cache and projection paths differ. The16-case selected-ID oracle verifies the changed kernel selection; these bounded generation timings are not a general model-quality benchmark or a whole-model logits parity claim. Keep this PR **draft** until a stable isolated model comparison has been repeated; preserve all three arms rather than selecting only the favorable first pair.

Engine SHA256: `9933918a7f1e6dee2e55b41552df068e654169834c7d6e7679710330469b5207`. Head branch retains its0.1.36 merge history; this validates applying the unchanged PR delta to0.1.37. Score-row stride, arithmetic and captured-decode dispatch remain unchanged. No installer, workflow, elastic-cache patch or other fork optimization is included.
