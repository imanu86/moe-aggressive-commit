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

### Validation status of this upstream port

Updated against upstream `36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca` (0.1.36), preserving the new sm_90+ cluster dispatch. The branch contains a merge of upstream main without rewriting its published history. The CUDA port and harness compile with CUDA 12.6 for sm_75, and all 16 selected-ID parity cases pass bitwise on the modified RTX 2080 Ti. The full SM75 fork engine build and its CMake-built top-k harness now pass; the fork contains additional changes and its model timings are not attributed to this narrow PR. The harness also passes MSVC C++17 syntax-only compilation; the existing-file diffs pass the whitespace check. The measurements above belong to the separately validated 0.1.31 daily, not this rebased tree. Keep this PR draft until an isolated full-engine model A/B/A has been repeated on this upstream base. No installer, workflow, elastic-cache patch or other fork optimization is included.
