# GAPS AND FIXES — from hobby to serious work

> Actionable list distilled from the five adversarial critiques (statistica, confondenti, trasferibilità, novelty, riproducibilità), ranked by **(severity × cost)**: high-severity + low-cost first. Each gap: **what is missing → why it matters → exact fix (seeds/chunks/reps, which experiment, estimated pod/hours) → who** (SPEX-main / SPEX-track / user).
>
> **MUST-FIX** = without it the paper is not publishable / a reviewer sinks it. **SHOULD** = needed to be taken seriously. **NICE** = polish.
> Repo `moe-aggressive-commit @ 31c38f2`. All source paths verified on disk.

Roles: **SPEX-main** = the driving agent (coding, analysis, offline stats). **SPEX-track** = a spawned worker for a bounded experiment. **user** = physical 3060 runs, pod start/stop, KB source access, final calls on scope.

---

## MUST-FIX (blocking publication)

### M1 — Commit the gitignored `dominio_kb` prompts (BLOCKING artifact-eval, trivial cost)
- **Missing:** the 8 `dominio_kb` k00–k07 prompts are gitignored (`dominio_kb/*.txt`) and untracked; their source (`raft_eval.jsonl`, sha 94b9b7f1) is a private out-of-repo file. The *entire* domain branch — trace, REAP mask, biasmask eval (the headline 1.013×/1.365×) — descends from prompts a reviewer cannot obtain.
  <!-- src: runs/spex/2026-07-05_trace_prompts/.gitignore; git ls-files (only coding_en + generale_ita tracked) -->
- **Why:** any artifact evaluation fails at clone; the most original branch ("Segnali") is non-reproducible for anyone without the user's disk.
- **Fix:** remove `dominio_kb/*.txt` from `.gitignore` and commit the ~155 KB of k00–k07; OR commit the generator (`build_family_kb_block`) + a sanitized RAFT extract; add a README "reviewer alternative" procedure.
- **Cost:** ~15 min, zero GPU. **Who:** user (owns KB source / decides sanitization), then SPEX-main commits.

### M2 — Retire all simulator tok/s and RAM-emulation claims from the paper (zero cost, high credibility) — **RESOLVED**
- **RESOLVED (2026-07-05).** Audited the draft for every tokens/s figure: all are on-disk *measured* values (0.06–0.72 t/s on the 3060; 0.49/0.64 block-4/base from `spec4_r1.log`/`base_r1.log`; 1.52/24.23 RAM-hot 3090 from `trace_dominio/meta.json`, explicitly marked NOT transferable). **No simulated tok/s is presented as a claim.** The only sim projection (45–74 t/s "10 t/s CONFIRMED") now appears solely in §7.3 as the *discredited artifact* against the real 0.06–0.70. The one remaining sim-derived number (dynamic-STS 1.91×) is a *scheduler* simulation, labeled as such, never a throughput claim. §7.3 strengthened to state the retirement as done; the RAM-emulation correction ("emulation attempted, failed on RLIMIT_MEMLOCK; acceptance = argmax property, not measured under memory pressure") is already in §7.3. **Remaining (source docs, out of paper scope):** correct `SCOPE_DECISION_20260705.md:25` prose — tracked as a source-doc hygiene item, does not block the paper.
- **Missing:** the paper/notes carry sim projections (45–74 t/s, "10 t/s CONFIRMED") that are 60–1000× the real 0.06–0.70 t/s; and "streaming regime emulated" when `--simulate-used-memory` never ran (gated on `ulimit -l unlimited`, failed at 8192).
  <!-- src: src/msc/spex/spex_speed_sim.py:126,21-24; runs/dspark/20260705_mtp_acceptance_pod3090/out_v3/accept_memlock_code.log, env.txt; docs/dspark/SCOPE_DECISION_20260705.md:25 -->
- **Why:** a reviewer who runs the engine sees 0.70 t/s and the paper says 47; instant credibility loss. `PAPER_STATE.md:120` already recommends retiring sim tok/s — apply it.
- **Fix:** delete every sim tok/s from paper prose; keep only miss-rate as a sim primary, with the two optimistic assumptions (SSD-sequential + perfect overlap) stated next to the real 0.70. Correct SCOPE_DECISION:25 to "emulation attempted, failed on RLIMIT_MEMLOCK; acceptance = argmax property, not measured under memory pressure."
- **Cost:** ~30 min, zero GPU. **Who:** SPEX-main (done in PAPER_DRAFT §7.3; also fix source docs).

### M3 — Reframe the REAP near-lossless claim to the defensible contrast (zero cost) + report the pre-reg FAIL honestly
- **Missing:** "REAP K50 1.013× near-lossless / PASS" is **not significant** (paired t(3df)=1.32, mean-excess 0.0131 < stdev 0.0197, one chunk 0.987 below 1.0); and the random control's pre-registered threshold literally **FAILED** (`rand_dom 1.3645x ... -> FAIL`), relabeled "PARTIAL" post-hoc.
  <!-- src: runs/reap/2026-07-05_eval_biasmask/eval_summary.json (paired reap/dom [1.0332,0.9868,1.0112,1.0212]; verdict "FAIL") -->
- **Why:** HARKing (relaxing a pre-registered threshold because the data missed it) is exactly what the house "gold-from-the-questions" protocol forbids; a reviewer catches it in one line.
- **Fix (prose, zero-GPU):** claim only the *ordinal contrast* reap≪rand (rand t≈7.8, real); report "pre-registered threshold NOT met (1.36× < 1.5×); ordering holds; IQ2-redundancy attribution is a POST-HOC hypothesis to test on held-out K/seed."
- **Cost:** ~20 min. **Who:** SPEX-main (done in PAPER_DRAFT §5.3/§7.7).

### M4 — Bootstrap CIs on every ratio already on disk (low cost, zero GPU, fixes the "no statistics" attack)
- **Missing:** zero CI, zero bootstrap, zero significance test on disk for *any* number (1.013×, 1.365×, τ, 1.91×, 0.848).
- **Why:** every comparative claim is a naked point estimate; the whole statistical critique collapses onto this one omission.
- **Fix:** per-token / per-cycle bootstrap (≥10k resamples) on the existing CSVs: REAP per-chunk log-ratios, DSpark accept.csv per-cycle, Fase C committed-distribution (Wilson CI on 56/66), MTP-1 acceptance. Emit `*_bootstrap.json` next to each result. No new runs needed.
- **Cost:** ~2–3 h coding, zero GPU. **Who:** SPEX-main.

### M5 — Resolve the target-model / title drift to ONE regime (blocks the whole novelty map)
- **Missing:** `PAPER_STATE.md` says 158B general; `CONSOLIDATION.md` says 235B-A22B full-quality general. The regime decides which prior art preempts us and whether the domain-vs-general finding *helps or hurts*.
  <!-- src: docs/PAPER_STATE.md:1; docs/CONSOLIDATION.md:3,94 -->
- **Why:** under "general full-quality," the F3 domain-concentration ace reverses against us; two durable docs with incompatible theses = a reviewer cannot tell what is claimed.
- **Fix:** decide NOW — (a) 158B-Flash domain-specialized (REAP + concentration = help) OR (b) 235B general full-quality (concentration = obstacle). PAPER_DRAFT provisionally chose (a). Archive/retire the losing doc; re-read the novelty map under the chosen regime.
- **Cost:** ~1 h decision + doc surgery, zero GPU. **Who:** user (scope call), then SPEX-main.

### M6 — Re-derive axis-flip AND union-load on the multi-domain trace (both rest on one degenerate prompt)
- **Missing:** axis-flip (0.0245 / temporal 0.366) and the 49% union-load *both* come from the single "Conta da 1 a 200:" 65-token prompt, which the design doc marks "NOT a base." Counting maximizes temporal redundancy and minimizes cross-layer diversity → both headline numbers are on the most favorable prompt possible.
  <!-- src: runs/ds4_routing_trace_smoke/README.md; docs/REAP_DS4_design.md:207; docs/briefs/BRIEF_DSPARK_MTP_DS4.md:32 -->
- **Why:** on diverse prompts unique-experts/block rises (< 49% saved) and the temporal signal weakens; publishing either as a model property is over-generalization. The negative "L→L+1 dead" against Fate needs the same robustness as a positive.
- **Fix:** run the axis-flip + union metrics on the `2026-07-05_trace_dominio` trace (3155 tok, 20 prompts, ON DISK) and the 3-domain manifest, stratified by template (extract/explain/chat). Report window-k and 24.3/48 per domain with IQR. Mark [PENDING] until done.
- **Cost:** trace already on disk → ~2 h offline recompute (no pod) for the domain trace; the 3-domain trace needs a pod session (see M7). **Who:** SPEX-main (offline recompute) + SPEX-track (pod trace).

### M7 — Run the multi-domain SPEX trace + fit the hidden predictor on the TARGET (the D2 open number)
- **Missing:** the 3-domain trace manifest is input-only (no result CSV); the hidden-recall on DS4 (D2) is unmeasured; the Python→C `.spex` exporter does not exist; every wired predictor has hit-rate ~0.
  <!-- src: runs/spex/2026-07-05_trace_prompts/prompts_manifest.json (input only); docs/SPEX_INTEGRATION_PLAN.md:62,100; docs/EXPERIMENTS_LEDGER.md:260 -->
- **Why:** the SPEX contribution (predictive prefetch) has no target-model evidence; the "hidden beats markov" story is proxy-only. Without a predictor that predicts on DS4, §5.4 stays [PENDING].
- **Fix:** pod session — run patch-0007 hidden-dump on the 3-domain prompts (routing + weights + hidden, per-token top-N IDs+scores, ~0.5 GB/trace); fit hidden probe; measure recall@8/16/32 on DS4; implement `spex_loop.py --export-c` to emit a real `.spex`. Then wire the temporal-window predictor as the first *measured* live variant.
- **Cost:** ~$3–6 pod (3090, RAM-hot ok for trace), ~3–4 h + exporter coding ~½ day. **Who:** user starts/stops pod; SPEX-track runs dump; SPEX-main fits + writes exporter. **NOTE (memory protocol):** pod egress is throttled ~11 MB/s — offload the npz once (bucket/user server) and power the pod off immediately; pull from the bridge afterwards.

### M8 — Demonstrate (or formally leave OPEN) the 2× IO in a cache-active regime on the 3060
- **Missing:** Fase C ran with expert cache **disabled** the whole run (available 5.73 ≤ reserve 6.00, hit 0.0000) → union-load never monetized; block-4 is *slower* than baseline. The central thesis has no positive datapoint on any hardware.
  <!-- src: runs/dspark/20260705_fase_c_smoke_3060/out/spec2_r1.log:18-28, runtimes.csv -->
- **Why:** "−49% → ~2×" is presented as the track result but is untested in the regime where it could exist.
- **Fix:** re-run Fase C on the physical 3060 with reserve lowered (3–4 GiB) so the cache activates while model+MTP+ctx still fit; measure t/s cache-ON vs OFF, ≥5 prompts × ≥3 runs, `-n ≥256`, median wall ± IQR, Wilson CI on acceptance. If still flat, isolate the SSD tail and mark 2× [OPEN] everywhere until a cache-active-faster regime exists.
- **Cost:** physical 3060, ~½ day of runs (no pod $). **Who:** user (only the physical 3060 has the real NVMe+RAM regime); SPEX-main analyzes.

---

## SHOULD-FIX (needed to be taken seriously)

### S1 — Run `reap/gen` on the target (the biggest missing cell)
- **Missing:** REAP's domain-vs-general cost on DS4 is unknown; only random/gen (2.11×) is measured. Cannot claim REAP preserves the general.
  <!-- src: runs/reap/2026-07-05_eval_biasmask/README.md; eval_summary.json -->
- **Fix:** same setup as rand/gen (wiki-it corpus already used), teacher-forced ppl, ≥8 chunks. **Cost:** ~$0.7–0.9 pod, ~1 h. **Who:** SPEX-track + user (pod).

### S2 — Re-run the three REAP configs on identical GPUs; measure the noise floor
- **Missing:** full/reap on 3090, rand on 3090 **Ti**; the engine is non-bit-reproducible (71% row divergence); the "SE ~1e-2" is asserted in README, never measured. The chunk below full (0.987) is exactly what run-to-run noise produces.
  <!-- src: runs/reap/2026-07-05_eval_biasmask/meta.json (3090/3090/3090Ti); runs/reap/2026-07-05_trace_dominio/meta.json (1933/2720) -->
- **Fix:** re-run all three on the same GPU model (ideally same machine in sequence); repeat `full` 3× on one pod to get sd(ppl) per chunk; confirm 1.013× > noise. **Cost:** ~$1–2 pod, ~1.5 h. **Who:** SPEX-track + user (pod).

### S3 — Fit STS on the RIGHT drafter (native MTP-1, 2-bit, 3060) and measure the cost-model constants
- **Missing:** STS T=[0.85,1.07,0.71,1.01,1.44] is fitted on the *proxy* DSpark drafter (fp8/fp4, H200); t\_fix and δ are **assumed at 10%**; u(k) is fitted on 4 points from the degenerate trace.
  <!-- src: runs/dspark/20260705_fase_b_sts/sts_params.json (source_csv strada B); src/msc/dspark/sched_sim.py:31,33-34 -->
- **Fix:** log per-step margins/confidence of the native MTP-1 drafter on the 3060 (`DS4_MTP_CONF_LOG=1`, already present); refit STS on that; measure t\_fix and δ from Fase C timing (`DS4_MTP_TIMING=1`); refit u(k) on ≥6 k-values from the multi-domain trace with bootstrap CI; run a sensitivity sweep t\_fix,δ ∈ {5,10,20}%. **Cost:** physical 3060 logging (folds into M8) + ~2 h offline. **Who:** user (3060 logs) + SPEX-main (refit).

### S4 — Redo both cache sweeps with a correct protocol (one model, one FS, randomized order, N≥3)
- **Missing:** benches are single-shot, strictly A→B (order confounded with reserve via KEEP_MODEL_PAGES), 2-rep protocol not executed (s156 rep2 truncated), non-iso-workload (s740 8831 vs 7283 tok), and mix ext4/ds4-2bit with 9p/IQ2XXS.
  <!-- src: runs/ds4_bench_clean_ext4_20260705/run_A2.log (no gen line); runs/ds4_cache_sweep_9p_20260705/run_s156_2.log (truncated), run_s740_r1.log (total 8831) -->
- **Fix:** one sweep, same model + same native ext4/NVMe (no /mnt/d, no 9p), backing store logged (`findmnt`/`stat -f`); randomized/interleaved order (A,B,B,A,…); drop-caches or WSL restart between config blocks; N≥3 measured reps, `-n ≥256`, warmup discarded, median±IQR; measure `stall_ms_per_streamed_load` on the ext4 setup so "collo=SSD" is proven where claimed. **Cost:** physical 3060, ~½ day. **Who:** user (3060).

### S5 — Report N-per-position and Wilson CIs on DSpark conditional acceptance
- **Missing:** acceptance is conditioned on the accepted prefix → effective N collapses (chat survival 0.092 at pos5 → ~18 obs), but 0.500 at pos5 is reported with the same authority as pos1 (N=195); STS regresses at pos3.
  <!-- src: runs/dspark/20260705_fase_b_sts/STS_REPORT.md:27-31 (survival); RISULTATI.md:19 -->
- **Fix:** report N\_eff(domain,position) and a Wilson binomial CI per acceptance; state pos3 STS regression explicitly; k-fold (≥5) ECE with adaptive binning. For pos4-5 on chat, need ~10× cycles (≥2000 tok/domain). **Cost:** ~2 h offline (existing CSV) + a pod re-run for deeper N if wanted (~$4). **Who:** SPEX-main (offline) / SPEX-track (deeper N).

### S6 — Pin build provenance on every run (env header)
- **Missing:** no run uniformly pins ds4 commit, build flags, or GGUF sha; eval `build_pod.log` omits commit/patch series → "same binary across the paired comparison" is asserted, not evidenced.
  <!-- src: runs/reap/2026-07-05_eval_biasmask/*/build_pod.log (no commit); good-practice model runs/dspark/20260705_mtp_acceptance_pod3090/RISULTATI.md -->
- **Fix:** `env_capture.sh` at every run start logging `ds4_commit` (`git rev-parse HEAD`), `git log --oneline` of patches, `cuda_version`, `gguf_sha256`, `gpu`, `filesystem`, `env`; assert the three eval binaries' sha256 match (they should — mask is runtime bias). **Cost:** ~1 h scripting. **Who:** SPEX-main + user (pod).

### S7 — Compute the recency-vs-prediction decomposition as a number, or downgrade it
- **Missing:** the "half cache-warm, half prediction" decomposition (novelty-candidate #2) is a reading of three numbers (gaps are actually 60/40), not a computed quantity with a CI; the loop is a simulation with the strong hidden predictor *outside* it.
  <!-- src: docs/EXPERIMENTS_LEDGER.md:125-126; docs/CONSOLIDATION.md:114-115 -->
- **Fix:** produce `decomposition.json` quantifying recency-fraction vs prediction-fraction per regime with bootstrap CI; frame the contribution as *methodological* (the random control that nobody uses), citing ProMoE/MoE-Infinity for "proactive>reactive." OR downgrade to a qualitative observation. **Cost:** ~2 h offline. **Who:** SPEX-main.

### S8 — Pin the engine source (submodule or per-claim `git show`) for the anatomy section
- **Missing:** §3.2–3.3 line offsets come from an ephemeral out-of-repo copy, mixing commit 80ebbc3 (stock) with bee9eb3 (patched) without stating which tree each offset is on.
  <!-- src: docs/SPEX_INTEGRATION_PLAN.md:4-5,146; docs/dspark/RECON_MTP_DS4.md:4-5 -->
- **Fix:** add a git submodule pin, or cite `git show 80ebbc3:ds4_cuda.cu:NNNN` per claim (as the RECON doc already does); tag every offset stock vs patched. **Cost:** ~1 h. **Who:** SPEX-main.

---

## NICE-TO-HAVE (polish / hygiene)

### N1 — Evaluate REAP-K50 on an independent held-out domain (not raft-index-disjoint)
- calibration and eval both from the same self-curated `raft_eval.jsonl` → near-lossless is in-distribution. A second independent domain would make the transfer claim real. **Cost:** ~$1 pod. **Who:** user + SPEX-track.

### N2 — Commit the source trace CSV as a fixed artifact
- greedy temp0 non-determinism (71% divergence) + gitignored traces = the committed mask is not regenerable end-to-end. Commit the domain-trace CSV as the fixed source of truth. **Cost:** ~15 min (check size). **Who:** SPEX-main.

### N3 — Regenerate patches 0002–0006 with full `git format-patch` headers
- bare diffs (no `Subject:`) are fragile for a reviewer applying via `git am`. **Cost:** ~30 min. **Who:** SPEX-main.

### N4 — Promote the sub-expert 3-family negative to a headline negative; demote axis-flip
- the sub-expert weight-space redundancy=zero result (3 families, convergent numbers) is the corpus's most robust negative and is buried; axis-flip (n=1 degenerate) and regime-map (sim) are in the window. Reorder the contributions. **Cost:** prose only. **Who:** SPEX-main (done in PAPER_DRAFT §4.5).

### N5 — Add per-layer distribution (not just means) for saliency overlaps
- split-half mean 0.8295 hides min 0.7578 (layer 26); freq-vs-gonly mean 0.735 hides min 0.6016 — near the ~0.50 chance floor. Report per-layer, flag layers <0.75, ablate their ppl-sensitivity. **Cost:** ~1 h offline. **Who:** SPEX-main.

### N6 — Guard the four un-sourced numbers out of the paper
- gate-weights top1 27%/top3 63%; n\_eff@64tok 30–47; skip-mass 46%/29%; axis-flip "0.0203" have NO on-disk source (real min = 0.0245). Keep them [PENDING/unverified] until the producing trace is committed. **Cost:** none (already excluded in PAPER_DRAFT §7.10). **Who:** SPEX-main.

---

## Dependency / sequencing note
- **Do first, zero-GPU, high-leverage:** M1, M2, M3, M4, M5, S7, S8, N2–N6 (all offline or trivial commits).
- **Pod sessions (batch to save egress):** M6 (3-domain trace) + M7 (hidden dump) + S1 (reap/gen) + S2 (identical-GPU REAP) + N1 (held-out domain) — run in ONE pod window, offload npz once, power off immediately.
- **Physical 3060 only (no pod $):** M8 (2× IO cache-active), S3 (STS on native drafter), S4 (clean cache sweeps) — batch into one 3060 session.
- **Unblocks the thesis:** M8 is the single experiment that turns the central claim from OPEN to a result (or kills it honestly).
