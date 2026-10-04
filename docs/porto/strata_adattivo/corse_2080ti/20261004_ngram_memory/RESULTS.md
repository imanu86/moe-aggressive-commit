# N-gram-indexed expert-response memory, 4 October 2026

**Measured: n-grams provide some reusable local responses in the early layers,
but neither the frozen memory nor the fallback-updated memory passes the chosen
utility screen on all three texts. No production kernel, Daily or release change.**

This tests the proposed reuse of computations, including the hypothetical case
where model weights are already in VRAM. It is not another RAM/VRAM-placement
comparison and does not modify the model's existing learned PLE lookup table.

## Data and method

Modified 22 GB RTX 2080 Ti, Ryzen 5800X, 96 GiB RAM, Windows, CUDA 12.6/SM75;
Qwen3.8-Flash-Next GSQ-RCO IQ3_XXS. Three natural greedy continuations: Python LRU
code, Italian memory-hierarchy explanation, and inventory arithmetic. Prompts
86/85/102 tokens, 512 generated tokens each. The original answers are saved in
`capture-results.json`; some reach the generation cap before completing.

There are 1,536 accepted input positions and 61,440 routed expert calls over
layers 0, 1, 35 and 36. The first input is the last prompt token. Speculative
tails are discarded. Each text calibrates on the first 128 inputs and measures
the remaining 384: 1,152 distinct held-out inputs / 46,080 expert calls in total.
The 120 frozen and 36 adaptive conditions reuse these same three trajectories;
they are not 156 independent conversations.

Capture: KV capacity 262144, int8, resident 32768; spec/MTP 4; seven CPU workers;
5080 fixed expert slots / 8442 MiB; PCIe fraction 0.25; elasticity, swaps and
suffix drafting off. No synthetic saturation. This is a short-context pilot,
not a 250k-depth run. The raw trajectory is produced by the ordinary mixed
CPU/GPU model. Each recorded expert input is then replayed completely on the
same grouped GPU backend for both cached and reference outputs. This isolates
local approximation error; it is not a fully GPU-resident model generation.

Keys are `(layer, expert, token suffix)`, with one-, two-, three-token suffixes
and a no-suffix control. Keep at most 16 most recent exemplars per key. Compare:

- nearest current input -> its cached full expert output;
- affine combination of cached input/output pairs, using a ridge term of 0.001
  times the mean Gram diagonal, with coefficient L1 capped at 4.

For the affine method, a last-observation anchor gives
`x ≈ x0 + sum(c_i * (x_i-x0))` and
`y_hat = y0 + sum(c_i * (y_i-y0))`. Coefficients and residual use current x and
past x only. No current output is used by the guard. This is an approximation
to the **whole nonlinear expert**, not exact `Wb` reuse inside each gate/up/down
projection. FP64 analysis favors numerical stability; no FP32 online kernel is
implemented or timed.

Frozen policy: cache stays fixed after calibration; residual guards 1/3/5/10%
and an unguarded comparison. Adaptive exploratory stage was added after the
first frozen-code nearest results were inspected: on rejection or miss compute
the full expert and insert that exact response; on reuse do not insert the
current reference response. Guards are 10/20/30%. Only previously completed
positions are eligible. Global cache eviction/deduplication is not implemented;
the 16-entry limit is per key, not a total memory bound.

The prespecified local screen requires mean routed relative L2 <=3%, P99 <=10%,
and ideal routed-weight byte saving >=3%, separately on each text. This is an
engineering screen, not a guarantee about answer quality. Adaptive thresholds
are exploratory on the same data and have no independent model-quality holdout.

## Frozen memory: repeated words do not imply repeated computations

| Text | Held-out inputs whose bigram appeared in calibration | Trigram |
|---|---:|---:|
| Code | 56/384 | 23/384 |
| Explanation | 23/384 | 7/384 |
| Reasoning | 52/384 | 27/384 |

The same suffix may route to different experts, reducing usable coverage further.
Direct nearest-response reuse for matching **trigrams**, without an input guard:

| Text | Expert calls reused | Mean routed L2 | P99 routed L2 |
|---|---:|---:|---:|
| Code | 3.57% | 3.18% | 86.15% |
| Explanation | 1.09% | 1.04% | 52.85% |
| Reasoning | 4.04% | 3.06% | 88.52% |

A 10% input-residual guard rejects all frozen direct reuse in code and
explanation, and leaves 0.30% of reasoning calls. Affine interpolation helps
only slightly with this small calibration set. None of the 40 frozen policies
passes across all three texts, including the no-suffix control.

## Updating on fallback helps, but the saving is small and localized

Representative adaptive policy: **bigram + affine, input residual <=10%**.

| Text | Expert calls reused | Ideal skipped weight bytes | Net read-saving estimate | Mean routed L2 | P99 routed L2 | Max routed L2 |
|---|---:|---:|---:|---:|---:|---:|
| Code | 3.59% | 3.73% | 3.32% | 0.190% | 6.09% | 13.29% |
| Explanation | 0.88% | 0.93% | 0.73% | 0.061% | 0.22% | 10.14% |
| Reasoning | 3.85% | 3.89% | 3.51% | 0.291% | 8.56% | 12.78% |

The net estimate subtracts hypothetical FP32 input-bank, response and small-matrix
reads. It excludes hash/index overhead, writes/refresh, launches, solve arithmetic,
memory allocation and contention; it is not measured VRAM/PCIe bandwidth or t/s.
All byte fractions refer only to routed experts in the four measured layers,
which deliberately include two early layers; do not extrapolate them to all 48
layers or the whole decode step.

**Every reused call in this policy is in layer 0 or 1. Layers 35 and 36 reuse
none.** Layer-0 call reuse is 13.49% / 3.52% / 13.05%; layer 1 is
0.86% / 0% / 2.37% for code/explanation/reasoning. The representative policy
passes the local screen in code and reasoning, but fails utility in explanation.
None of the 12 adaptive policies passes the screen on all three texts.

Small aggregate means include many exact-fallback rows. On the calls actually
reused, mean expert-output L2 is **8.53% / 10.41% / 10.14%**, with maxima
20.77% / 24.53% / 22.04%. Neither these numbers nor routed L2 are percentages of
incorrect answers. A low overall P99 can also hide rarer outliers: all maxima
are retained. No approximate output was fed into subsequent model layers or
future token inputs, so accumulated generation error is unmeasured.

With the 20% adaptive affine guard, reuse rises to 8.76% / 5.21% / 9.88%, but P99
routed error rises to 20.23% / 22.02% / 21.70%. The looser 30% variants also fail
the error screen. Simply accepting more matches does not solve the problem.

The representative cache ends with 19,929 / 20,345 / 19,888 exemplars. Direct
FP32 x+y storage is 389.24 / 397.36 / 388.44 MiB for just the four layers,
before keys and Gram matrices. Inputs can be shared across experts and entries
can be filtered/evicted, so this is the tested representation's estimate, not
a lower bound. It does not demonstrate a package as small as three experts.

## Controls and provenance

- Accepted positions and input IDs match the generated token stream; no rejected
  speculative tails enter calibration or evaluation.
- Trace splitting reconstructs every recorded accepted x, route, weight, output
  and tier exactly; original replay limits remain unchanged.
- GPU replay covers all four GU/down pairs: 17/20, 16/42, 18/20 and 18/42.
- An identical physical GPU replay of **4360 expert calls** matches the full SNR
  output bitwise, including all eight recorded output variants and h.
- Twelve independent nearest/affine calculations and routed reductions reproduce
  the frozen summaries. Adaptive n=2, guard=20% checks both methods with an
  independent matrix solve on every candidate query in all three texts.
- Corrupting all held-out reference outputs leaves the calibration memories
  unchanged; exact duplicate-input/anchor, rank-deficiency, context-collision,
  known affine-map and FIFO-cap controls pass.
- First attempted capture failed before measurements because its relative trace
  path was interpreted from the engine's working directory. The runner now
  resolves the output path. `initial-failed-start.json` preserves the failure;
  successful measurements come exclusively from the second capture directory.

Engine SHA256 `dd92a8980567c403be5f3ae31e24bbc97850c30b06f3f164e8afbb80d7e90a3a`;
corrected diagnostic replayer SHA256
`64b55b1bef1b4ef4528ab8be9d7cc7f4465ed878e40ddf3b60bd00667d7a970c`.
The immutable trace engine comes from the earlier probe build; differences from
current fork source are recorded explicitly. No new CUDA build was required.
The local same-backend reference avoids conflating expert-response approximation
with normal CPU/GPU backend differences, which are separately recorded.

Evidence: `protocol.json`, `capture-results.json`, `frozen-measurements.json`,
`adaptive-measurements.json`, `verification.json`, and `final-state.json`.
Runners: `capture.py`, `trace_io.py`, `analyze.py`, `adaptive.py`, `verify.py` and
`publish_evidence.py`. Capture uses the existing local capture/tokenizer helpers
whose exact paths and hashes are recorded; it is a workstation harness, not a
portable installer. CPU analysis requires NumPy and the matching raw SNT/SNR
inputs. Large captures, replays and scalar audit NPZ files remain in local
`.codex_runs/20261004_ngram_*` directories and are not included in this report.
Source/evidence hashes refer to the measured bytes; Windows checkout newline
conversion may require comparing the Git blob rather than the worktree copy.

Daily executable, config, launcher and public ZIP were not changed. All test
engines and replayers exited. This pilot supports further study of compact
context-dependent responses in early layers; it provides no validated online
speedup or new SOTA, and does not reject trained conditional memory, larger
calibration corpora, or separate linear-projection response bases.
