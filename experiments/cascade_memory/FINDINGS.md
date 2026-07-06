# Confidence-Cascade Memory — Findings (Gate #1 GO, Gate #2 NEGATIVE)

Model-agnostic harness (OpenAI-compat), measured on **Qwen2.5-7B-Instruct (GQA)** via
vLLM on RunPod. Denominator always N_total; cost = deterministic token/call vector;
sensor and go/no-go **pre-registered** (PREREGISTRATION.md) before results. Two real
runs, ~$0.18 (Gate #1) + ~$0.33 (Gate #2) of pod time.

## Gate #1 — sensor separability: **GO** (full-window regime)
AUROC(mean_logprob, correctness) = **0.845**, CI95 [0.802, 0.883] on the baseline arm;
leak-control 0/400 (no leakage); P(high-conf ∧ wrong) = 0.007. The pre-registered
`mean_logprob` sensor discriminates right from wrong **when errors are hallucinated
values** (full window, abstention rate 1.7%).

## FINDING 1 — the sensor does NOT transfer to the small-window regime
When the native window is small, the model stops hallucinating and starts **abstaining**
("I don't know."). Measured mean_logprob by class in that regime:
`abstained −0.003 · correct −0.000 · wrong −0.011` — **all ≈ 0** in absolute terms.
As a SINGLE-threshold sensor over the whole population, `mean_logprob` AUROC drops from
0.845 (full window) to **0.685** here — NOT because logprob is information-free, but
because **abstentions (−0.003) sit between confident-correct (−0.000) and confident-wrong
(−0.011)**, so one threshold mislabels them. A single logprob gate therefore never fires
(all values ≈0 ≥ any theta), which is why theta is inert and the cascade collapses to an
abstention-gated single point. This is the spec's **risk #5 realized** — but see
**FINDING 3**, which corrects the too-strong reading "logprob is useless here": split the
population and the logprob is strong again (AUROC 0.937 conditioned on non-abstention).
The usable trigger is `abstention OR low-logprob-among-non-abstainers`.

## Gate #2 — does the cascade win? **NEGATIVE** (novelty not supported)
Small-native-window regime (native 6 / buffer 50 turns), 600 items, uniform fact-distance
{5,20,40,60,80} × {single_fact,distractor_dense} × {easy,hard}, k=3, abstention-gated.

| Arm | acc | mean tokens | rung_stop dist |
|---|---|---|---|
| B0_sw (no recovery) | 0.200 | 296 | native 1.00 |
| **B1 always-RAG** | **0.863** | **158** | — |
| B2 reactive (→ full-RAG) | 0.843 | 571 | native .29 / 2 .71 |
| B3 random (equal budget) | 0.887 | 705 | 0 .18 / 1 .12 / 2 .43 / native .27 |
| B4 cascade (cheap-first) | 0.885 | 793 | 0 .40 / 1 .01 / 2 .32 / native .27 |
| B5 cascade − rung-0 | 0.840 | 723 | 1 .35 / 2 .36 / native .29 |

Pre-registered criteria:
- **(i) FAIL** — B4 vs B1: `Δcost@matched-acc = +635 tok`, CI95 [600, 668] (needed < 0);
  the cascade is ~5× more expensive than always-RAG at matched accuracy. B4 vs B3:
  `Δ = +88`, CI95 [65, 109] — **cheap-first loses even to the random-order control at
  equal budget** → the ordering is not helping; it is hurting.
- **(ii) partial** — rung-0 resolves **54.5%** of recovered items (≥10% ✓) and its ablation
  B5 cannot reach B1's accuracy, so rung-0 does add value; insufficient to rescue (i).
- **(iii) FAIL** — stop-too-early (confident-yet-wrong native accepted) = **7%** (> 5%),
  the hallucination tail the logprob gate cannot catch.

**Verdict: NO-GO for the novelty claim at this regime.** Per the pre-registration this is
an honest negative; we do NOT proceed to Gate #3.

## FINDING 2 — why the cascade loses (mechanistic, robust)
1. **Always-RAG is a brutally strong cheap baseline here.** One in-memory BM25 retrieval
   with small top-k finds the fact ~86% of the time at ~158 tokens prefill. The cascade's
   "try native first, then escalate" adds a near-always-wasted LLM call (far facts abstain)
   before doing what B1 does directly.
2. **Cheap-first ordering backfires under uniform distance.** 60% of facts (dist 40/60/80)
   sit beyond the buffer, so buffer-scoped rung-0/rung-1 systematically FAIL and the cascade
   pays for them before reaching full-RAG (rung-2). Cost ranks B4 (793) > B3 (705) > B2
   (571): random order sometimes hits full-RAG first; reactive-binary skips straight to it.
   A cost cascade only wins when the CHEAP rungs have a good hit rate.

## FINDING 3 — the learned trigger works BLACK-BOX (corrects F1); white-box not needed (yet)
The interesting question was never the index ("where") but the trigger ("does the model
need memory?"). Offline probe (trigger_probe.py) on the already-collected runs, label =
"answered correctly WITHOUT recovery", features = ONLY inference-time black-box signals
(answer logprob stats + verbalized abstention), 5-fold CV, baselines = mean_logprob and
abstention-alone. Result (small-window regime, N=600):

| trigger | AUROC |
|---|---|
| mean_logprob alone (pre-reg sensor, whole population) | 0.685 |
| abstention alone (free signal) | 0.955 |
| **logprob among NON-abstainers only (the "confident-hallucination" residual, N=159)** | **0.937** |
| **full black-box [logprob stats + abstention]** | **0.984** |

Reading: two cheap black-box signals, split by role — (1) *abstained?* catches the 73%,
(2) *logprob among non-abstainers* catches the confident-hallucination residual — combine
to 0.984, beating both the raw logprob (0.685) and the free abstention signal (0.955).
This **corrects F1's over-strong "logprob is useless here"**: logprob is strong (0.937)
once applied to the right sub-population instead of thresholded over the whole mix. So the
model *does* know when it doesn't know — the signal was just being read wrong.
Consequence: on this task the **white-box hidden-state probe is NOT required** — a
two-signal black-box router suffices. (Full-window regime: logprob already 0.845; the
router adds nothing there — abstention is rare.)

CAVEATS (honest): all in-distribution on the synthetic fictitious universe, where answers
are exact tokens and abstention is clean; 0.984 will drop on realistic open-ended data
(LongMemEval) where hallucinations are subtler — that is where white-box probing might
re-earn its keep. The learned classifier's edge over abstention-alone (+0.029) is real but
modest; whether it converts into a better cost/accuracy frontier needs an ONLINE run
(apply the trigger live in the 2-tier memory, compare vs trigger=abstention-only) — a
clean pre-registered next experiment.

## Boundary conditions (stated as caveats, not re-run to fish a positive)
The negative is specific to: (a) **uniform fact-distance** (adversarial to buffer-scoped
cheap rungs) — under **recency-skewed access** (most references recent, realistic for
conversation) cheap rungs would hit far more; (b) **cheap in-memory retrieval** — if
full-RAG were expensive (large KB, embeddings, rerank, network) avoiding it would pay;
(c) here 20% resolve natively — a more valuable native context shifts the trade-off.
These would each be pre-registered hypotheses for any follow-up, not post-hoc rescue.

## Net
- **DEAD**: the many-level cost cascade (turn-level rung-0 + heterogeneous rungs with
  early-exit) is **not supported** on a GQA model with cheap retrieval and uniform access —
  it is dominated by a single direct RAG (F2). When retrieval is cheap, the intermediate
  rungs have no cost niche to occupy; the design collapses to a **2-tier** (small window +
  one RAG).
- **ALIVE**: the **learned trigger router** (F3). Deciding *when* to go back — via
  `abstained? + logprob-among-non-abstainers` — reaches AUROC 0.984 black-box, beating both
  the raw sensor and abstention-alone. The hard problem was the trigger, not the index, and
  a cheap two-signal router cracks it on this task.
- F1 (regime-fragility of a single-threshold logprob sensor) stands but is corrected by F3:
  the signal is there, it was being read over the wrong population.
- MLA/ds4 substrate (pre-registered inert) not needed for the cascade negative.
- **Next pre-registered experiment**: 2-tier memory (small window + RAG) with the *learned
  trigger* vs *abstention-only trigger*, on recency-skewed realistic access, measuring the
  amortized cost/accuracy frontier over a long conversation (not per-item). That is the
  honest test of the idea that actually survived.
