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
`abstained −0.003 · correct −0.000 · wrong −0.011` — **all ≈ 0**. Greedy-decoding token
logprob measures "is the next-token distribution peaked", not "does the model know the
answer"; the model is peaked on its refusal. So AUROC collapses to ≈0.5 and a logprob
gate never fires. This is the spec's **risk #5 realized**, and it is regime-dependent:
the very sensor that passed Gate #1 is inert here. The usable low-confidence signal
becomes the **verbalized abstention** itself (self-knowledge / Self-RAG-family), so the
controller escalates on `abstention OR logprob<theta`. (Consequence: theta is inert in
this regime; the cascade is effectively abstention-gated, a single operating point.)

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

## Boundary conditions (stated as caveats, not re-run to fish a positive)
The negative is specific to: (a) **uniform fact-distance** (adversarial to buffer-scoped
cheap rungs) — under **recency-skewed access** (most references recent, realistic for
conversation) cheap rungs would hit far more; (b) **cheap in-memory retrieval** — if
full-RAG were expensive (large KB, embeddings, rerank, network) avoiding it would pay;
(c) here 20% resolve natively — a more valuable native context shifts the trade-off.
These would each be pre-registered hypotheses for any follow-up, not post-hoc rescue.

## Net
- Novel narrow claim (turn-level rung-0 re-boost + heterogeneous cost cascade with
  early-exit) is **not supported** on a GQA model with cheap retrieval and uniform access.
- Two transferable results stand on their own: **(F1)** logprob confidence is
  regime-fragile and collapses under verbalized abstention; **(F2)** a cost cascade needs
  cheap rungs with a high hit rate or it is dominated by always-retrieve. Both are the
  kind of honest negative the measurement spec was built to produce.
- MLA/ds4 substrate (pre-registered inert) was not needed — the concept already fails to
  dominate on the *positive* substrate, so the MLA run is moot for the novelty claim.
