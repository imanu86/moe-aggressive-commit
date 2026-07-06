# Pre-registration — Confidence-Cascade Memory (frozen BEFORE results)

Frozen 2026-07-06, before any measurement was run, on branch `cascade-memory/harness`.
Source of truth: `docs/CONFIDENCE_CASCADE_MEASUREMENT_SPEC.md §4`. This file exists so
the go/no-go thresholds and the sensor cannot be chosen post-hoc to fit the numbers.

## Frozen choices
- **Primary confidence sensor**: `mean_logprob` = mean per-token log-probability of the
  generated answer span (higher = more confident). `min_logprob`, `mean_prob`,
  schema/format fallback are **exploratory only** and MUST NOT drive any gate.
- **Primary cost axis**: total LLM tokens `prefill + decode` from API `usage`
  (deterministic). Call-count surcharges default to 0 and must be disclosed if ever
  set non-zero. Wall-clock is secondary.
- **Denominator**: `N_total_items` for every average. Failures and abstentions stay in.
- **Scorer**: exact-match / token-containment of the fictitious gold. Abstention scored
  as a **separate** metric, never as correct, never folded into recovery cost.
- **Dataset**: fictitious-universe synthetic, distance grid `{5,20,40,60,80}`,
  categories `{single_fact, distractor_dense(, updated_fact)}`, N ≥ 200–500/cell,
  seeded. Leak-control twin (plant removed) must score ~chance (≤ 0.05 acc).

## Expected substrate (directional, pre-registered)
- Positive on **MHA/GQA** (dense KV = real cost).
- Null/negative on **MLA (ds4)** — the negative is a deliverable, not a failure.

## Gate #1 — post Step 1 (sensor separability), THIS step
- **GO** if `AUROC(confidence, correctness) ≥ 0.65` on the baseline arm (B0).
- **NO-GO** if `AUROC < 0.60` → STOP; report the honest negative (an early-exit gate on
  a non-discriminative sensor is just noise). Do **not** build the cascade.
- `[0.60, 0.65)` → grey; needs more data / a better sensor before deciding.

## Gate #2 — post cascade + ablation (Step 2, only if Gate #1 GO)
GO-novelty only if ALL hold:
1. B4 (cascade) **dominates the Pareto frontier** of both B3 (RANDOM at equal budget)
   and B1 (always-RAG); `Δcost@matched-accuracy < 0` with a bootstrap CI95 excluding 0.
2. rung-0 (turn-level text re-boost) resolves **≥ 10%** of successfully-recovered items
   **and** ablation B5 (cascade minus rung-0) significantly worsens the frontier.
3. `P(stop-too-early ∧ high-confidence ∧ wrong) < 5%`.
Otherwise: honest negative (complexity > gain).

## Gate #3 — post realistic (Step 3–4, only if Gate #2 GO)
Confirm the gain reappears on **RULER** and **LongMemEval_s** with consistent sign;
abstention must not degrade.

## Anti-gaming, fixed
Denominator always `N_total`; primary cost = tokens+calls; no metric chosen post-hoc;
RANDOM-at-equal-budget control (B3) is mandatory in Step 2 — if the cascade cannot beat
a random rung at equal budget, the gain was the budget, not the gate.
