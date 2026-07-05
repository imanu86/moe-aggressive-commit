# Extending Expert-Offload Engines Down the Memory Ladder: A Measured Anatomy and a Stack of Composable Levers on a Real Deployment Model

> **Draft status.** Systems-paper draft, post-pivot. Every quantitative claim carries an on-disk source path in an HTML comment `<!-- src: ... -->`. Claims that depend on data not yet on disk (the multi-domain trace in flight) are explicitly marked **[PENDING]**. Claims whose mechanism has run but whose *thesis-level payoff* is not yet demonstrated are marked **[OPEN]**. Repo at `5b25576` (branch `main`) before this editorial pass; the pass adds the bootstrap-CI artifact (`scripts/paper_ci.py`, `runs/paper_ci_results.json`) and resolves gaps M1/M2/M3/M5 (see `GAPS_AND_FIXES.md`).
> <!-- src: git rev-parse HEAD = 5b25576924d694159e7cce4db3e3f8df5ccf1e50 before editorial pass; git branch --show-current = main -->

---

## Abstract

Expert-offload inference engines (Mixtral-offloading, PowerInfer-2, HOBBIT, and the DwarfStar/ds4 engine we build on) let a Mixture-of-Experts (MoE) model run on hardware that cannot hold all experts in VRAM. This paper asks a narrower, more honest question than "can we run a giant model on a small GPU": **what actually happens, and where the levers are, when you push one such engine down the memory ladder to a genuine consumer target** — a DeepSeek-V4-Flash-class MoE (E=256 experts/layer, 6 active, 40 MoE layers, IQ2\_XXS 2-bit) on an RTX 3060 (12 GB VRAM) with 28 GB of system RAM.

We contribute: **(1) a measured anatomy** of the engine on the target, showing the compute pipeline stalls behind a blocking device-sync, there is no compute stream to hide copies behind, and — counter-intuitively — every configuration in which the expert cache is *active* is slower than the cache-disabled baseline, because on 12 GB the static working set (attention + shared) crowds out the expert cache and the bottleneck moves to the SSD tail. **(2) A set of routing-structure findings** on the deployment model — most importantly that the naive next-layer expert-ID carry-over is random (0.0245 top-6, indistinguishable from chance), while a hidden-state cross-layer probe recovers ~0.99 recall on a proxy model; we are careful *not* to overclaim these on a single degenerate prompt. **(3) A stack of composable levers** — expert-cache sizing (including a clean *negative* result), block speculative decoding with union-load (−49% expert-IO arithmetic at block-8), runtime REAP bias-masking for domain pruning (near-identity on-domain, random control fails cleanly), predictive hidden-state prefetch (**[PENDING]**), and skip-on-miss with a REAP loop — each measured with honest controls and each with its own failure mode documented. **(4) An unusually large Threats-to-Validity section** that we consider the paper's real contribution: the central product thesis ("usable speed on 12 GB") currently has *no positive datapoint on the target hardware*, and we say so.

We frame this not as "we shipped a 235B model on a 3060" but as *a rigorous engineering study of the gap between the offload literature (measured on RAM-hot data-center hardware and idealized simulators) and a real SSD-bound consumer deployment*, with a stack of levers that are individually validated and a clear, costed list of what remains before any speed claim is defensible.

---

## 1. Introduction

### 1.1 The north star and the gap

The target is concrete: run a DeepSeek-V4-Flash-class MoE — 158B parameters, 256 experts per MoE layer, 6 active, 40 MoE layers, quantized to IQ2\_XXS (~2-bit, GGUF 86.72 GB on disk) — on an RTX 3060 with **12 GB VRAM and 28 GB system RAM** (soon 64 GB).
<!-- src: model geometry: runs/reap/2026-07-05_trace_dominio/meta.json (40 layer routed 3..42, E=256, expert_weights_scale 1.5); gguf size runs/reap/gguf_flash_expert_geometry.txt (86,720,111,488 B) -->
The model does not fit in VRAM, does not fit in RAM, and is served by streaming experts from SSD on demand. The engine we extend, DwarfStar/ds4 (antirez), already does reactive per-expert streaming with an LRU expert cache and a native MTP-1 speculative decoder.

The **gap versus DwarfStar** we set out to close is fivefold, following our positioning document:
predictive (not reactive) expert fetch; saliency-guided (not frequency-guided) retention; dynamic/STS confidence scheduling (not static imatrix); MTP repurposed from token- to expert-scheduling; and — the through-line of this paper — **every one of these measured with honest controls (random, mass, reactive) on the model we actually deploy**, not on a proxy.
<!-- src: docs/CONSOLIDATION.md:5 (five substitutions vs DwarfStar); docs/PRIOR_ART.md -->

### 1.2 What this paper is, and is not

This paper is **not** a demonstration that the target runs at usable speed. On the contrary, one of our headline anatomy findings (§3.1) is that *we have not yet made it fast*, and we are explicit about which numbers are simulation, which are worst-case, and which are non-transferable data-center measurements. It is a **measured anatomy plus a lever stack**: each lever is individually validated (or shown to fail) with a control, and the composition into an end-to-end fast system is left as clearly-scoped future work with costs attached (see companion `GAPS_AND_FIXES.md`).

### 1.3 A note on target scope (unresolved, flagged)

Our two durable positioning documents currently disagree on the target: `PAPER_STATE.md` (marked pre-pivot) titles a **158B general** model on a 12 GB GPU; `CONSOLIDATION.md` titles a **235B-A22B full-quality general** model.
<!-- src: docs/PAPER_STATE.md:1 ("158B general MoE ... 12GB"); docs/CONSOLIDATION.md:3 ("235B-A22B ... qualità piena ... uso generale") -->
This is not cosmetic: the regime determines which prior art preempts us and *whether our domain-vs-general finding helps or hurts* (§7.4). **This draft targets the 158B DeepSeek-V4-Flash model** — the model we actually run on the 3060 — and treats all 235B/Qwen numbers as **cross-scale evidence from a proxy model**, never as evidence on the target. Resolving the two documents to one target is a MUST-FIX (see `GAPS_AND_FIXES.md`, G-STRUCT-1).

---

## 2. Background and Related Work

### 2.1 Expert offloading and caching

Streaming experts from slower memory is well established: Mixtral-offloading [2312.17238], PowerInfer-2 [2406.06282] (smartphone), HOBBIT [2411.01433], MoE-Infinity [2401.14361] (sparsity-aware cache), and ProMoE [2410.22134] (proactive caching). ProMoE and MoE-Infinity *already* argue that proactive prefetch beats reactive caching at a fixed budget. Our contribution here is therefore **not** the qualitative conclusion "predictive beats reactive" — that is theirs — but a **measurement protocol**: a random-eviction floor + reactive-LRU + adaptive at matched VRAM that isolates how much of the gain is recency versus prediction. Honest caveat: that decomposition is currently a reading of three numbers, not a computed quantity with a confidence interval (§7.5, and `GAPS_AND_FIXES.md` S-DECOMP).
<!-- src: docs/PRIOR_ART.md:13,21; docs/CONSOLIDATION.md:16; decomposition source docs/EXPERIMENTS_LEDGER.md:125-126 -->

### 2.2 Expert prediction / prefetch

Fate [2502.12224] predicts next-layer experts from the hidden state at ~99% hit rate; Pre-gated MoE [2308.12066], SiDA [2310.18859], and ExpertFlow [2410.17954] similarly exploit a cross-layer signal. **Crucially, these predict from the hidden state, not from the previous layer's expert identities.** Our axis-flip finding (§4.1) is often mis-stated as "cross-layer is random here"; the honest statement is narrower and does *not* contradict Fate (§4.1, §7.6).

### 2.3 Expert pruning and saliency

REAP [2510.13999] prunes experts one-shot by saliency `mean(g·‖f‖)`; EASY-EP [2504.06792], PreMoE [2505.17639], NAEE [2402.14800] (expert skipping), and "How to Score Experts" [2606.15716] are adjacent. Domain pruning ~50% near-lossless is **already known** (we replicate it), per EASY-EP/PreMoE/REAP.
<!-- src: docs/EXPERIMENTS_LEDGER.md:133 (G1: F1 near-lossless GIÀ-NOTO) -->
Our delta is engineering (a runtime bias-mask actuator on a stock 2-bit engine) plus an *admitted downgrade* (g-only saliency, without ‖f‖, forced by what the trace exposes) — not a better selection criterion (§4/§5.3, §7.7).

### 2.4 Speculative decoding for expert-IO

DSpark (confidence-scheduled verification) schedules speculative blocks to save *tokens*; DwarfStar has union-load but only in the prefill batch path. Our candidate contribution is putting the **expert-IO term** into the block-length optimum: at block-k the verifier streams the *unique* experts of the block (union-load), not 6·k. This is the most genuinely new piece, and also the least demonstrated (§5.2, §7.8).
<!-- src: docs/dspark/DESIGN_DSPARK_DS4.md:66; docs/briefs/BRIEF_DSPARK_MTP_DS4.md:32 -->

### 2.5 Honest novelty verdicts

| Our finding | Verdict | Nearest prior art |
|---|---|---|
| ~50% experts prunable near-lossless on-domain | **KNOWN** (we replicate) | EASY-EP, PreMoE, REAP, NAEE |
| FT-router disperses; domain concentrates | **NOVELTY-CANDIDATE #1** | counter-case ReMoE [2412.14711]; ESFT, ST-MoE |
| Domain-vs-general gap grows with scale | **KNOWN** (we quantify) | EASY-EP Tab.4, PreMoE, Less-is-MoE |
| Cross-layer hidden prediction + adaptive loop | **NOVELTY-CANDIDATE #2** (robustness/transfer) | Fate, Pre-gated, SiDA, ExpertFlow |
| Offload 158–235B on 12 GB | **MECHANISMS KNOWN**, extreme regime | ProMoE, MoE-Infinity, PowerInfer-2, HOBBIT |
| Mass < random at scale (control exposes it) | **NOVELTY-CANDIDATE** (confound-limited) | How-to-Score, DeepSeekMoE, REAP |
| Sub-expert weight-space redundancy = zero (3 families) | **NOVEL and ROBUST** (see §4.5) | — |
<!-- src: docs/EXPERIMENTS_LEDGER.md:133-139 (G1-G7 verdicts); docs/CONSOLIDATION.md:15-19; sub-expert docs/EXPERIMENTS_LEDGER.md:55-56 -->

---

## 3. System Anatomy

All numbers in this section are measured on the target-class hardware (RTX 3060, 12 GB, WSL2) unless a proxy pod is named.

### 3.1 The central negative: activating the expert cache is always slower on the target

Across the entire committed corpus, **there is no run on the 3060 where enabling the expert cache improves tokens/s.** The best observed speed (0.70–0.72 t/s) is always with the cache *disabled*; every cache-active run is flat-to-slower:

| Config | Cache | hit-rate | gen t/s | source |
|---|---|---|---|---|
| event-on smoke | OFF (hit=0) | 0.0000 | **0.70–0.72** | <!-- src: runs/ds4_selected_upload_event_smoke/ ; HANDOFF.md:56-57,68 --> |
| Fase C spec2 | OFF (disabled 5.73≤6.00) | 0.0000 | 0.70 | <!-- src: runs/dspark/20260705_fase_c_smoke_3060/out/spec2_r1.log:18-28 (cache disabled), runtimes.csv --> |
| ext4 bench B (reserve 1 GB) | ON | 0.44 | **0.15** (4.6× slower) | <!-- src: runs/ds4_bench_clean_ext4_20260705/run_B1.log (hit_rate=0.4396, generation 0.15 t/s) --> |
| 9p sweep s740 (reserve 1) | ON | 0.38 | 0.11 (~6× slower) | <!-- src: runs/ds4_cache_sweep_9p_20260705/run_s740_r1.log:35-36 (hit 0.3791, gen 0.11) --> |

The mechanism-of-cure is thus, as measured, **anti-correlated** with the mechanism-of-thesis on this hardware. §3.2–3.5 explain why.

### 3.2 No compute stream: copies cannot hide behind compute

All MoE kernels launch on the CUDA default stream (0): `ds4_cuda.cu:12424-12599` launch `<<<grid,block>>>` with no 4th argument, and `cublasSetStream` has **zero** occurrences. The three non-default streams that exist are all host→device I/O. There is therefore no GPU pipelining of expert copy under compute; `cudaStreamWaitEvent` has **zero** occurrences in the whole engine — the primitive needed to order compute↔copy is simply absent.
<!-- src: docs/SPEX_INTEGRATION_PLAN.md:148-152 (default stream, cublasSetStream=0); :143-167 (cudaStreamWaitEvent ZERO). Line offsets valid for the analysis copy of ds4 at commit 80ebbc3; see §7.9 threat. -->

### 3.3 The stall floor: a blocking device-sync serializes everything

Safety today is guaranteed only by a double blocking barrier: `cudaDeviceSynchronize` at `ds4_gpu_end_commands` (:14286) framing every step, plus `cudaStreamSynchronize(upload_stream)` at `:2237` inside every copy. To prefetch layer L+1 you must predict its experts *before* that upstream sync — this is the central node of any async design, not a detail.
<!-- src: docs/SPEX_INTEGRATION_PLAN.md:143-182 (double barrier; 3 deeper nodes: upstream sync, shared upload stream, single-buffer destination cache g_stream_selected_cache.gate_ptr) -->

### 3.4 The SSD tail is the bottleneck, not the experts

On the 9p sweep the per-streamed-load stall is ~15–16 ms **regardless of cache setting** (s156 15.03 ms, s740 15.02 ms, smax 16.03 ms) — the signature of random per-expert SSD reads (6.75 MiB/expert), not sequential bandwidth. More cache raises hit-rate (0→0.38) but t/s stays tapped at 0.10–0.11 because the tail dominates.
<!-- src: runs/ds4_cache_sweep_9p_20260705/run_s156_1.log:33 (stall_ms_per_streamed_load=15.03), run_s740_r1.log:36 (15.02), run_smax_r0.log:34 (16.03) -->
**Caveat (do not overstate):** this SSD-tail signature is measured on the 9p mount (`DeepSeek-V4-Flash-IQ2XXS-imatrix.gguf` on /mnt/d, drvfs) — a filesystem with translation overhead — whereas the ext4 bench uses a *different model* (`ds4-2bit.gguf`) and does not emit the `streamed_loads`/`stall` metric. Attributing the ext4 flat-t/s to "SSD tail" is inference by analogy across two different setups (§7.2).

### 3.5 The VRAM ceiling disables the cache by default

With the default 6 GB reserve, available VRAM (5.73–5.96 GiB) is *below* the reserve, so the engine disables the expert cache entirely: model + MTP + context saturate the 12 GB budget. The cache only activates when the reserve is lowered to ~1 GB — at which point §3.1 shows it does not help. The static working set (attention + shared, ~10 GB) is the constraint; the expert cache (~1–2 GB) is what gets squeezed. This is the anatomical reason the offload literature's "optimize expert IO" framing does not transfer: **on 12 GB the static component is the ceiling, not the expert stream.**
<!-- src: runs/ds4_bench_clean_ext4_20260705/run_A1.log:16 (available 5.96 ≤ reserve 6.00 → disabled); runs/dspark/20260705_fase_c_smoke_3060/out/spec2_r1.log:18 (5.73 ≤ 6.00); docs/PAPER_STATE.md:11 (I4/I5) -->

### 3.6 Per-token expert demand

At 6 active experts × 40 MoE layers = 240 expert reads per token; at 6.75 MiB/expert (2-bit) that is ~1.6 GiB of expert weight touched per token if nothing is cached — the raw driver of the SSD tail.
<!-- src: expert geometry 6.750 MiB/expert, 1.6875 GiB/layer — runs/reap/gguf_flash_expert_geometry.txt; runs/reap/reap_mask_ds4_domain.json (geometry). 240 = 6 active × 40 routed layers per meta.json -->

---

## 4. Routing Structure Findings

### 4.1 Axis-flip: naive expert-ID carry-over is random; the hidden-state axis is not

On the target model, predicting a token's layer-L+1 experts from its **layer-L expert identities** is random: same-token prev-layer top-6 = **0.0245**, prev-token prev-layer top-6 = **0.0251** — both at chance. The signal that survives is *temporal, same-layer*: prev-token same-layer top-6 = **0.2623**, window-4 same-layer top-6/12 = **0.342/0.507**, window-8 = **0.366/0.550**.
<!-- src: runs/ds4_routing_trace_smoke/routing_trace_count64_summary.json (same_token_prev_layer_top6=0.024523, prev_token_prev_layer_top6=0.025107, prev_token_same_layer_top6=0.262305, window4_same_layer_top6=0.341992/top12=0.506836, window8_same_layer_top6=0.365560/top12=0.549544) -->

**Critical framing correction (this is not a contradiction of Fate).** What is dead is the *expert-ID carry-over* — a strawman prefetcher nobody proposes. Fate and our own hidden-state predictor predict L+1 from the **hidden state** `h_L`, and on a proxy (Qwen-30B) that axis achieves recall **0.9316/0.9906/0.9978** @8/16/32 (25% budget ≈ 0.986–0.998), essentially Fate's ~99%.
<!-- src: docs/EXPERIMENTS_LEDGER.md:116 (E8 hidden .9316/.9906/.9978 dom); :218-220 (hidden @25% ≈ 98.6-99.8% ≈ Fate); :136 (G4: static recall @25% hidden .986/markov .865/rnd .25) -->
The defensible statement is: *on a real deployment model, the cheap ID-only predictor must be temporal-same-layer, not cross-layer-ID; the strong cross-layer signal requires computing the hidden state.* And the temporal signal is **weak in absolute terms** (0.37) versus markov (0.865) and hidden (0.986) — it is a zero-cost fallback, not a discovery.
<!-- src: docs/EXPERIMENTS_LEDGER.md:216-220 -->

**[PENDING] — degenerate prompt.** All axis-flip metrics come from a **single degenerate prompt** ("Conta da 1 a 200:", 65 tokens, 2600 rows, 3 positions). Our own design doc states this smoke "is NOT a base." A counting stream is quasi-periodic, which *inflates* the temporal signal and *depresses* the cross-layer signal — the most redundancy-favorable prompt possible. These metrics must be re-derived on the multi-domain trace before any claim (§7.6).
<!-- src: runs/ds4_routing_trace_smoke/README.md (prompt "Conta da 1 a 200:"); docs/REAP_DS4_design.md:207 ("NON è una base") -->

### 4.2 Temporal-window redundancy

Window-8 adds little over window-4 (top-12 0.507→0.550), suggesting a short recency window captures most of the temporal signal.
<!-- src: runs/ds4_routing_trace_smoke/routing_trace_count64_summary.json (window4_same_layer_top12=0.506836, window8_same_layer_top12=0.549544) -->

### 4.3 Cross-model replications (proxy Qwen, value doubled by transfer)

The routing structure replicates across models on the *sign*, not always the *magnitude*:
- **Static-cache recall dominated by concentration in-distribution:** Qwen-30B gate @25% static .693 (general) / .744 (domain), markov +.10/+.13 cross-layer.
<!-- src: docs/EXPERIMENTS_LEDGER.md:111-112 (E3/E4) -->
- **Static prediction does NOT transfer cross-distribution** (static @25% collapses ~.75→.44), while markov holds its margin — a pro-SPEX argument under workload shift.
<!-- src: docs/EXPERIMENTS_LEDGER.md:113 (E5) -->
- **Scale-invariant routing concentration:** n\_eff 49.9/128 at 30B ≈ 49.9/128 at 235B.
<!-- src: docs/EXPERIMENTS_LEDGER.md:69 (C1: 235B n_eff 49.918/128); :222-230 -->

### 4.4 Extract-vs-explain: the "domain" in a trace is partly the template

Template matters: extract vs explain prompts yield different routing concentration, so "domain" signal in a trace is partly JSON-template artifact, not pure semantics — a stratification requirement for any routing claim.
<!-- src: runs/reap/2026-07-05_trace_dominio/meta.json (16 extract -n320 + 4 explain -n512); docs/CONSOLIDATION.md -->

### 4.5 The robust negative: sub-expert weight-space redundancy is zero across 3 families

The strongest *negative* in the corpus, and under-promoted: sub-expert per-neuron fusion buys nothing on three model families (Qwen-30B, DS2-Lite, V4-Flash) — neurons are diffuse, n\_eff/I ≈ 0.885 (base) / 0.890 (FT), and fine-tuning does **not** compact neurons (683 vs 679).
<!-- src: docs/EXPERIMENTS_LEDGER.md:55-56 (A25 n_eff 679.5/768=0.885; A26 683.3/768=0.890, FT NON compatta); docs/PAPER_STATE.md:14 -->
This falsifies a reasonable intuition ("fuse the sub-experts") on multiple families — a genuinely publishable negative that should be the *headline* negative, above axis-flip (§7.6).

---

## 5. The Lever Stack

Each lever is stated with its control and its failure mode.

### 5.1 Cache sizing (including a clean negative on ext4)

More cache → more hits, but t/s does not follow. On ext4 (reserve default→1 GB): hit-rate 0→0.44 while generation t/s goes 0.18→0.15 (i.e. *worse*).
<!-- src: runs/ds4_bench_clean_ext4_20260705/run_A1.log (cache disabled, gen 0.18); run_B1.log (hit 0.4396, gen 0.15); run_B2.log (hit 0.4143, gen 0.15) -->
On 9p, across reserve 5→0: hit-rate 0→0.35–0.38, t/s pinned 0.06→0.11.
<!-- src: runs/ds4_cache_sweep_9p_20260705/run_s156_1.log (hit 0, gen 0.06), run_s440_r3.log (hit 0.2507, gen 0.10), run_s740_r1.log (hit 0.3791, gen 0.11), run_smax_r0.log (hit 0.3472, gen 0.10) -->
**This is a clean negative result** (the bottleneck is downstream of hit-rate, §3.4), but see §7.1–7.3: the runs are single-shot, non-randomized in order, use different models/filesystems, and are not iso-workload — so the *magnitude* is not defensible even though the *direction* is.

### 5.2 Block speculative decoding (union-load; Fase C unlock)

**Union-load arithmetic (transfers; TRUE).** At block-8 the verifier's unique experts per layer = **24.3 vs 48** (6×8) = **−49% expert-IO**; block-4 = 16.4 (−32%), block-2 = 10.6 (−12%). In the prefill batch the same mechanism gives mean **163.0 unique/layer** (min 132, max 191) vs 4020 slots = 95.9% avoided.
<!-- src: docs/briefs/BRIEF_DSPARK_MTP_DS4.md:30-32 (10.6/12%, 16.4/32%, 24.3/49%); runs/dspark/20260705_mtp_acceptance_pod3090/out_v3/unionload_compact_counts.log (43 prefill rows slots=4020, mean 163.0; decode rows slots=6 compact=6 must be filtered — see §7.1) -->

**Fase C unlock (mechanism runs on the 3060).** `--mtp` + `--ssd-streaming` was forbidden by the engine (`ds4.c:25685`); patches 0009 (one-liner from upstream PR #497) + 0010 (durable secondary MTP model-map registration) unlock it. The block verifier completes 100 tokens with no crash; spec2 acceptance = **56 committed=2 / 66 cycles = 0.848**; wall time base 186/181 s vs spec2 168/166 s = **~10% faster**.
<!-- src: runs/dspark/20260705_fase_c_smoke_3060/out/spec2_r1.log (56 committed=2 / 66 conf cycles); runtimes.csv (base 186/181, spec2 168/166, spec4 229); patches/ds4/0009,0010 -->

**[OPEN] — the 2× IO payoff is NOT demonstrated.** Fase C ran with the **expert cache disabled** the entire run (available 5.73 ≤ reserve 6.00, hit-rate 0.0000, ~190–270 GiB copied from SSD for 100 tokens), so union-load could not be monetized: block-4 is *slower* than baseline (0.49 vs 0.64 t/s). The tested regime is the worst case, not the thesis. "−49% → ~2×" remains **[OPEN]** on all hardware.
<!-- src: runs/dspark/20260705_fase_c_smoke_3060/out/spec2_r1.log:18-28 (cache disabled), runtimes.csv (spec4_r1=229s) -->

**DSpark drafter acceptance (proxy: 2×H200, fp8/fp4).** The trained DSpark drafter's conditional acceptance decays slowly on code/math and crashes on chat: code pos1–5 = 0.979/0.948/0.928/0.899/0.821 (τ=5.18/6), math 0.959→0.863 (τ=5.00/6), chat 0.713→0.500 (τ=2.70/6).
<!-- src: runs/dspark/20260705_dspark_b_v4flash_2xh200/RISULTATI.md:17-19 (acceptance + τ); :4 (fp8/fp4 167GB 2×H200) -->
**Caveat (§7.3):** this is a *different model* (DeepSeek-V4-Flash-DSpark), *different precision* (fp8/fp4 vs IQ2 2-bit), *different hardware* (H200 vs 3060), and *different drafter* (trained DSpark-5 vs native MTP-1). The native MTP-1 baseline on 2-bit is 0.872/0.846/0.604 (code/math/chat). The domain *ordering* (code>math>chat) transfers; the τ *magnitude* fp8→IQ2 does not, and must not be composed into a single speedup.
<!-- src: runs/dspark/20260705_mtp_acceptance_pod3090/RISULTATI.md:17-19 (MTP-1 130/149=0.872, 126/149=0.846, 90/149=0.604) -->

**STS + scheduler (offline, proxy drafter).** STS temperatures T=[0.85, 1.07, 0.71, 1.01, 1.44] calibrate the DSpark drafter's confidence; holdout ECE improves on 3–4 of 5 positions (pos1 0.058→0.039) but **regresses at pos3** (0.037→0.052). A dynamic-STS scheduler reaches 97–99% of oracle (all-domains 1.91× vs oracle 1.96×), and a fixed block on chat *destroys* the gain (fixed-5 = 0.92×, i.e. slower than plain decode).
<!-- src: runs/dspark/20260705_fase_b_sts/sts_params.json (T=[0.8499,1.0730,0.7136,1.0122,1.4359]); STS_REPORT.md (pos3 0.037→0.052 regress); SCHED_SIM.md (fixed-5 1.46× all / 0.92× chat; dynamic-STS 1.91×; oracle 1.96×) -->
**Caveat (§7.3):** the STS is fitted on the *proxy* drafter's logits (`source_csv` = strada B accept.csv), and the cost-model constants t\_fix and δ are **assumed at 10%**, never measured — u(k)=6.30·k^0.668 is fitted on **4 points** from the degenerate 65-token trace. The whole scheduler table is a composition of three regimes.
<!-- src: runs/dspark/20260705_fase_b_sts/sts_params.json (source_csv strada B); src/msc/dspark/sched_sim.py:31 (TRACE_POINTS 4 pts), :33-34 (T_FIX_FRAC=0.10, DELTA_DRAFT=0.10) -->

### 5.3 REAP bias-mask domain pruning

**Actuator (system contribution).** Domain pruning is actuated at runtime by writing `-1e9` into the selection bias (`exp_probs_b`) — exactly equivalent to physical pruning given the ds4 router math (independent per-expert probs + renorm over top-6), at ~zero cost, no surgery, on the stock 2-bit engine. Verified on the field: `selections checked=11280 violations=0` — with the mask active the router *never* selected a pruned expert.
<!-- src: docs/REAP_DS4_design.md:48-60 (router math); runs/reap/2026-07-05_eval_biasmask/reap/biasmask.log (V0_OK, 11280 checks, 0 violations) -->

**Result — the claim is the ordinal contrast, not a near-lossless point.** REAP K50 on-domain ppl = 3.8604 vs full 3.8111 = **1.013× [CI 0.995–1.028]** (bootstrap 95%, geomean of 4 paired per-chunk ppl ratios, 10k resamples, seed 42); random control = 5.2001 = **1.365× [CI 1.280–1.455]**. The REAP CI **crosses 1.0** — REAP-K50 is statistically indistinguishable from the full model on-domain at N=4 chunks — while the random CI does not and sits far above it. **The defensible claim is therefore the contrast reap ≪ rand (the two CIs do not overlap), not "1.013× near-lossless."** REAP degrades ~27× less than random *as a point estimate*, but that ratio too is CI-unquantified at N=4.
<!-- src: runs/reap/2026-07-05_eval_biasmask/eval_summary.json (reap/dom 1.0129, rand/dom 1.3645, rand/gen 2.1149); CIs runs/paper_ci_results.json (reap_over_full_dom ci95 [0.9953,1.0277] crosses 1.0; rand_over_full_dom ci95 [1.2797,1.4549]) -->

**Three honest problems (see §7.7, §6.2):**
1. **The near-lossless point is not statistically significant.** Paired per-chunk reap/dom = [1.0332, 0.9868, 1.0112, 1.0212]; one chunk (0.9868) shows pruning *improving* ppl; mean-excess 0.0131 < its own cross-chunk stdev 0.0197 → paired t(3df) ≈ 1.32 < t\_crit 3.18, and the bootstrap CI [0.995–1.028] crosses 1.0. The defensible claim is the *contrast* reap≪rand (rand t≈7.8, CI [1.280–1.455] clear of 1.0), not "1.013× near-lossless."
<!-- src: runs/reap/2026-07-05_eval_biasmask/eval_summary.json (paired_per_chunk reap/dom [1.0332,0.9868,1.0112,1.0212]); runs/paper_ci_results.json (reap ci95 crosses 1.0) -->
2. **The pre-registered random threshold FAILED — no post-hoc rescue.** The verdict file literally reads `rand_dom 1.3645x (>=1.5 e >reap) -> FAIL`. The run README relabels this "PARTIAL" and attributes the shortfall to IQ2 redundancy; **we reject that relabeling as HARKing.** The pre-registered criterion was `rand_dom ≥ 1.5×`; the measured 1.365× (CI [1.280–1.455], upper bound below 1.5) **does not meet it — this is a FAIL, full stop.** What *is* defensible is the ordering (rand ≫ reap, non-overlapping CIs); what the threshold miss *does not* license is a claim that 1.5× "would have been met on cleaner data." We record three candidate explanations for why random is less catastrophic here than the 30B-bf16 prior (2.5×) suggested — **as discussion to be tested on held-out K/seed, not as a relaxation of the threshold**: (i) **granularity** — at K50 of E=256 the surviving 128 experts leave more per-token routing redundancy than at the coarser 30B geometry, so a random 50% cut is cushioned; (ii) **shared-expert floor** — the always-on shared/attention path carries load the router cut cannot touch, bounding the damage of *any* expert removal; (iii) **2-bit floor** — at IQ2\_XXS the per-expert precision is already so low that swapping experts costs less relative ppl than at bf16. All three are *hypotheses that predict a lower random-damage ratio*; the honest test is to re-run random at a more aggressive K (e.g. K25) where even IQ2 should degrade, so the control bites, and multi-seed to separate the hypotheses from noise (§7.7). **[PENDING] — a multi-seed / multi-chunk (≥8 chunks, ≥3 seeds) re-eval on identical GPUs is in progress; until it lands, the near-lossless and threshold results stand as N=4, single-run, and the only claim carried forward is the ordinal contrast.**
<!-- src: runs/reap/2026-07-05_eval_biasmask/eval_summary.json (verdict_preregistrato: "rand_dom 1.3645x ... -> FAIL"); runs/reap/2026-07-05_eval_biasmask/README.md:23-27 (the "PARTIAL"+IQ2 relabel we reject); GAPS_AND_FIXES.md S1/S2/N1 (held-out K, identical-GPU, multi-seed pending) -->
3. **reap/gen was never run** — the domain-vs-general cost of REAP on the target is unknown; only random/gen (2.11×) is measured. We cannot claim REAP preserves the general.
<!-- src: runs/reap/2026-07-05_eval_biasmask/README.md (reap/gen not executed); eval_summary.json (only rand/gen present) -->

**Saliency is g-only (admitted downgrade).** ‖f‖ is not extractable from the trace, so we use g-only conditional-mean; validated at retention 0.902@K32 / 0.762@K64 on a *proxy* (Qwen-30B), not on the target. Footprint at K50 = 46.98 GiB (centered in the 64 GB budget). Split-half drop-set overlap mean 0.8295 (min 0.7578).
<!-- src: runs/reap/reap_mask_ds4_domain.json (method gonly_conditional_mean, est_file_gib 46.98); runs/reap/gonly_vs_eq9_30b.json (retention@32 0.8969, retention@64 0.7619 for base row); runs/reap/mask_stability_splithalf.json (mean 0.8295, min 0.7578) -->
Note: the headline "0.902" is retention@32 for the base row; retention@64 is 0.762. We report both to avoid the cherry-pick (§7.7).

### 5.4 SPEX hidden-state prefetch [PENDING-D2]

The strong predictor (hidden-state probe) is not yet self-contained: it needs a per-token probe dump from the pod, and the Python→C `.spex` exporter **does not exist** (`spex_loop.py` only saves miss-rate/ECE). Expected hidden recall 0.93–0.99 vs markov 0.51–0.89 on the proxy; **recall on the target (DS4) is the open number D2**, not yet measured. The 3-domain trace manifest is on disk (input only, no result CSV).
<!-- src: docs/SPEX_INTEGRATION_PLAN.md:62 (exporter missing), :100 (hidden not self-contained, recall 0.93-0.99 vs markov 0.51-0.89); runs/spex/2026-07-05_trace_prompts/prompts_manifest.json (input only); docs/EXPERIMENTS_LEDGER.md:260 (per-token re-dump needed) -->
Every wired predictor to date has hit-rate ~0: naive L→L+1 prefetch (hit 0.0000, t/s 0.70→0.43), synthetic markov loader (hit 0.0037). **A predictor that actually predicts on the target does not yet exist** (§7.5).
<!-- src: runs/ds4_stage1_prefetch_smoke/prefetch_l1_decode.log (hit 0, gen 0.43); HANDOFF.md:84-85 (markov synthetic hit 0.0037, gen 0.44) -->

### 5.5 Skip-on-miss + REAP loop (design + verified actuator)

The idea: dropping a *low-impact* mispredicted/missing expert costs little (plateau ~1.3× ppl on the proxy hidden-drop), whereas indiscriminate markov-drop is catastrophic (59× @block-8). The runtime actuator exists and runs: margin-gated skip (`margin-skip drafted=2 committed=1`) fires in Fase C. The REAP loop's sensor is the g-only conditional saliency from the trace; the loop itself is DSpark-faithful in `spex_loop.py` but **not run end-to-end** (markov-only + STS-on-hit-labels locally).
<!-- src: docs/PAPER_STATE.md:9 (hidden-drop plateau 1.3× vs markov 59×); docs/EXPERIMENTS_LEDGER.md:290 (H5 hidden-drop C8 8.7× vs markov 59×, plateau 1.3×); runs/dspark/20260705_fase_c_smoke_3060/out/spec2_m3.log (margin-skip); docs/EXPERIMENTS_LEDGER.md:125,260 (spex_loop.py not run end-to-end) -->

---

## 6. Evaluation

Every number carries its source. Sections marked **[PENDING]** await the multi-domain trace in flight; **[OPEN]** marks a mechanism that runs but whose thesis payoff is undemonstrated.

### 6.1 Speed on target (the honest table)

| Regime | Cache | hit | gen t/s | Note |
|---|---|---|---|---|
| event-on / spec2 (3060) | OFF | 0.000 | 0.70–0.72 | best observed; cache off <!-- src: runs/ds4_selected_upload_event_smoke/; runs/dspark/20260705_fase_c_smoke_3060/out/spec2_r1.log --> |
| ext4 reserve-1 (3060) | ON | 0.44 | 0.15 | 4.6× slower <!-- src: runs/ds4_bench_clean_ext4_20260705/run_B1.log --> |
| 9p reserve-1 (3060) | ON | 0.38 | 0.11 | ~6× slower <!-- src: runs/ds4_cache_sweep_9p_20260705/run_s740_r1.log --> |
| RAM-hot trace (3090 pod) | — | — | 1.52 (gen), 24.23 (prefill) | **NOT transferable** to 3060 <!-- src: runs/reap/2026-07-05_trace_dominio/meta.json --> |

**Thesis verdict: "usable speed on 12 GB" has no positive datapoint on target. [OPEN].**

### 6.2 REAP domain pruning (paired, N=4 chunks)

| Config | ppl | ratio vs full [boot 95% CI] | paired per-chunk | source |
|---|---|---|---|---|
| full/dom | 3.8111 | 1.000 | — | <!-- src: runs/reap/2026-07-05_eval_biasmask/eval_summary.json --> |
| reap/dom | 3.8604 | **1.013× [0.995–1.028]** (CI crosses 1.0) | [1.033, 0.987, 1.011, 1.021] | <!-- src: eval_summary.json paired_per_chunk; runs/paper_ci_results.json --> |
| rand/dom | 5.2001 | 1.365× [1.280–1.455] (**pre-reg FAIL: <1.5×**) | [1.265, 1.295, 1.505, 1.406] | <!-- src: eval_summary.json verdict_preregistrato; runs/paper_ci_results.json -->|
| rand/gen | 11.3014 | 2.115× [2.104–2.126] (N=2, CI insuff.) | [2.126, 2.104] | <!-- src: eval_summary.json; runs/paper_ci_results.json (n=2 flagged) --> |

Statistics (bootstrap 10k, seed 42, `scripts/paper_ci.py`): reap/dom paired t(3df)≈1.32 (**not significant**; CI [0.995–1.028] crosses 1.0); rand/dom t≈7.8 (significant; CI [1.280–1.455] clear of 1.0 but below the 1.5× pre-reg threshold → FAIL). rand/gen CI is at N=2 chunks and flagged insufficient. Defensible claim = ordinal contrast reap ≪ rand only. reap/gen **missing**.

### 6.3 Speculative decoding

| Metric | Value | Regime | source |
|---|---|---|---|
| MTP-1 acceptance (code/math/chat) | 0.872/0.846/0.604 | 3090, 2-bit, N=1 prompt/domain | <!-- src: runs/dspark/20260705_mtp_acceptance_pod3090/RISULTATI.md:17-19 --> |
| DSpark drafter τ | 5.18/5.00/2.70 | **H200, fp8/fp4** (proxy) | <!-- src: runs/dspark/20260705_dspark_b_v4flash_2xh200/RISULTATI.md:17-19 --> |
| Union-load @block-8 | 24.3/48 = −49% | arithmetic (transfers) | <!-- src: docs/briefs/BRIEF_DSPARK_MTP_DS4.md:32 --> |
| Union prefill | 163.0 unique/layer (95.9% avoided) | prefill rows only | <!-- src: runs/dspark/20260705_mtp_acceptance_pod3090/out_v3/unionload_compact_counts.log --> |
| Fase C spec2 acceptance | 0.848 (56/66) | 3060, cache **disabled** | <!-- src: runs/dspark/20260705_fase_c_smoke_3060/out/spec2_r1.log --> |
| Fase C spec2 wall | ~10% faster (183.5→167 s) | 3060, N=2, 1 prompt | <!-- src: runtimes.csv --> |
| Scheduler dynamic-STS | 1.91× (oracle 1.96×) | **simulation**, proxy drafter | <!-- src: runs/dspark/20260705_fase_b_sts/SCHED_SIM.md --> |
| 2× IO payoff | **[OPEN]** — undemonstrated | — | — |

### 6.4 Routing structure

| Metric | Value | source |
|---|---|---|
| Axis-flip same-token prev-layer top6 | 0.0245 (random) **[PENDING multi-domain]** | <!-- src: runs/ds4_routing_trace_smoke/routing_trace_count64_summary.json --> |
| Temporal window-8 same-layer top6/12 | 0.366/0.550 **[PENDING]** | <!-- src: same file --> |
| Hidden recall @25% (proxy 30B) | 0.986 | <!-- src: docs/EXPERIMENTS_LEDGER.md:218 --> |
| Sub-expert n\_eff/I (3 families) | 0.885/0.890 (redundancy zero) | <!-- src: docs/EXPERIMENTS_LEDGER.md:55-56 --> |
| Split-half drop-set overlap | 0.8295 (min 0.7578) | <!-- src: runs/reap/mask_stability_splithalf.json --> |

### 6.5 SPEX hidden prefetch

**[PENDING-D2].** No target-model recall on disk. All wired predictors hit-rate ~0. Exporter not implemented.

---

## 7. Limitations and Threats to Validity

This section is the paper's real contribution: it separates the honest engineering study from a hobby demo. We incorporate the five adversarial critiques directly.

### 7.1 Statistics: point estimates without confidence intervals

Every ratio in the paper (1.013×, 1.365×, τ 5.18/5.00/2.70, 1.91×, 0.848) is a **naked point estimate**: zero bootstrap, zero significance test, zero standard error is computed on disk. The one headline (REAP 1.013× near-lossless) is **not significant** (paired t(3df)=1.32); the scheduler speedups rest on u(k) fitted to **4 points** from a 65-token degenerate prompt with 1 residual degree of freedom. Single-shot runs pervade: ext4 config A is N=1 (A2 truncated, no generation line); the 9p sweep is non-iso-workload (s740 generated 8831 tokens vs 7283 for the others, s156 rep2 truncated). MTP-1 baseline and union-load are single-prompt/single-shot. **Minimum fix (zero-GPU): bootstrap per-token/per-cycle on the CSVs already on disk before any comparative claim.**
<!-- src: runs/ds4_bench_clean_ext4_20260705/run_A2.log (no generation line); runs/ds4_cache_sweep_9p_20260705/run_s740_r1.log (total 8831); src/msc/dspark/sched_sim.py:31 (4 points) -->

### 7.2 Confounds: order, filesystem, model, and hardware are entangled

The cache benches run strictly A→B back-to-back, non-randomized, with `KEEP_MODEL_PAGES=1` deliberately warming the page cache — so page-cache/thermal warming is perfectly confounded with the reserve setting. The two-rep protocol was **not executed** (s156 rep2 truncated; other configs N=1). The "SSD-tail" thesis stitches two experiments with *both* a different model *and* a different filesystem (ds4-2bit/ext4 vs IQ2XXS-imatrix/9p), and the stall signature exists *only* in the 9p logs. The REAP paired eval runs full/reap on RTX 3090 but rand on RTX **3090 Ti** — a hardware axis mixed into a ratio on an engine that is *not bit-reproducible at temp0* (repeat p00 diverges on 1933/2720 rows = 71%). **Fix: randomized/interleaved order with drop-caches; one sweep, one model, one filesystem, backing store logged; re-run the three REAP configs on identical GPUs (ideally same machine in sequence).**
<!-- src: runs/reap/2026-07-05_eval_biasmask/meta.json (full/reap 3090, rand 3090Ti); runs/reap/2026-07-05_trace_dominio/meta.json (DETERMINISM_DIFF 1933/2720) -->

### 7.3 Transferability: three tacit regime substitutions

The paper repeatedly measures in one regime and applies in another: **(1) model** (Qwen proxy → V4-Flash target — recall 0.986, miss 0.117, mass<random, hidden-drop 1.3× are ALL on Qwen); **(2) precision** (bf16/fp8 → IQ2 2-bit — the DSpark τ and STS are fp8/fp4); **(3) hardware/regime** (RAM-hot pods + idealized sim → SSD-bound 3060). **We have retired every simulated tokens/s figure from this paper's claims** (`spex_speed_sim.py` projected 45–74 t/s, tagged "10 t/s CONFIRMED", under two optimistic assumptions — SSD 5 GB/s *sequential* and *perfect* compute↔copy overlap); the real engine does 0.06–0.70 t/s (a 60–1000× gap) because the SSD serves 15 ms *random* reads and there is no compute stream to overlap. The projection is cited here only as the discredited artifact, never as a speed. The one remaining simulation-derived number in the paper — the dynamic-STS scheduler at 1.91× (§5.2, §6.3) — is a *scheduler* simulation over accepted-length draws, explicitly labeled "simulation, proxy drafter", not a throughput measurement, and is never composed into a tokens/s claim. Every acceptance number is tagged with {model, precision, drafter, GPU}. Only the sim *miss-rate* is retained as a primary (§5.4).
<!-- src: src/msc/spex/spex_speed_sim.py:126 (overlap assumption), :21-24 (SSD seq); docs/PAPER_STATE.md:120 (retire sim tok/s); runs/dspark/20260705_dspark_b_v4flash_2xh200/RISULTATI.md:49-51 (precision caveat); dynamic-STS 1.91x = runs/dspark/20260705_fase_b_sts/SCHED_SIM.md (scheduler sim, not tok/s) -->
Additionally, the RAM-starvation emulation (`--simulate-used-memory`) **never ran**: it is gated on `ulimit -l unlimited`, which failed (`ulimit -l = 8192`), so the acceptance was measured RAM-hot, not under memory pressure. The claim "streaming regime emulated" must be corrected to "emulation attempted, failed on RLIMIT\_MEMLOCK; acceptance validated as an argmax property, not under memory pressure."
<!-- src: runs/dspark/20260705_mtp_acceptance_pod3090/out_v3/accept_memlock_code.log ("ulimit memlock non alzabile: skip"), env.txt (ulimit -l 8192); docs/dspark/SCOPE_DECISION_20260705.md:25 -->

### 7.4 The central thesis is undemonstrated on target

"Usable speed on 12 GB" has **no positive datapoint** (§3.1, §6.1). The 2× IO payoff was tested in the one regime where the mechanism is *off* (cache disabled, §5.2). The two results that *seem* to support the thesis live on different hardware/precision (H200 fp8) or on a degenerate smoke. We state plainly: **this is an anatomy + lever study, and the product claim is OPEN.**

### 7.5 Two "novelty candidates" are not yet computed as numbers

The recency-vs-prediction decomposition ("half cache-warm, half prediction") is a *reading of three numbers* (`ledger:125`), not a computed quantity with a CI — and the two gaps are 60/40, not 50/50. It is a *simulation* in which the strong hidden predictor sits **outside** the loop (recall 0.986 static; loop runs at 0.117 with cheaper predictors); our own doc flags "verify the gap survives paying the hidden-compute cost early enough to hide load latency" as a **BLOCKING** step. And a predictor that actually predicts on the target does not yet exist (all wired predictors hit ~0). **Fix: compute `decomposition.json` with bootstrap CI, or downgrade to a qualitative observation; frame C2 as a *methodological* contribution (the random control), not a result — "proactive > reactive" is already ProMoE/MoE-Infinity.**
<!-- src: docs/EXPERIMENTS_LEDGER.md:125-126; docs/CONSOLIDATION.md:114-115 (BLOCKING step, hidden outside loop); docs/SPEX_INTEGRATION_PLAN.md:150-152 (no compute stream) -->

### 7.6 Two headline findings rest on a single degenerate prompt

Both the axis-flip ("temporal signal strong / L→L+1 dead") *and* the 49% union-load derive from the **same** "Conta da 1 a 200:" counting prompt (65 tokens, single prompt), which our own design doc marks "NOT a base." A counting task maximizes temporal redundancy (inflating both the temporal signal and the union-load saving) and minimizes cross-layer diversity. On diverse prompts, unique-experts/block rises → less than 49% saved, and the temporal window signal likely weakens. **Fix: re-derive both on the multi-domain trace (3155 tokens, 20 prompts, on disk) and the 3-domain manifest, stratified by template; mark [PENDING] until replicated.** Symmetrically, the *negative* "L→L+1 dead" must not be over-generalized: publishing a negative against Fate requires the same robustness as a positive.

### 7.7 REAP: framing and downgrades

The bias-mask actuator is a property of the ds4/DeepSeek router (mask ≡ logical pruning), not an invention — REAP/NAEE/EASY-EP define pruning as removal from the active set, indifferent to physical vs masked. The real delta versus REAP is **g-only without ‖f‖**, which is a *downgrade* (retention 0.762@K64, not 1.0), forced by the trace, validated only on the *proxy* (Qwen-30B). The pre-registered random threshold **failed** (`rand_dom 1.365× < 1.5×`, §5.3); we do **not** relabel it "PARTIAL" and we treat the three candidate explanations (granularity, shared-expert floor, 2-bit floor) strictly as **discussion to be tested, never as an ex-post relaxation of the criterion**. The near-lossless point's bootstrap CI [0.995–1.028] crosses 1.0, so only the ordinal contrast survives. reap/gen is missing. **Fix: sell the engineering (runtime bias-mask on a stock 2-bit engine) as a systems contribution; declare g-only as a lower-bound approximation, not a better criterion; run reap/gen; re-run random at more aggressive K (K25) where even IQ2 degrades, so the control bites; multi-seed/multi-chunk re-eval [PENDING].**
<!-- src: docs/REAP_DS4_design.md:48-60; runs/reap/gonly_vs_eq9_30b.json (retention@64 0.7619); runs/reap/2026-07-05_eval_biasmask/eval_summary.json (FAIL); runs/paper_ci_results.json (reap ci crosses 1.0) -->

### 7.8 The most novel piece (union-IO term) is arithmetic, not a measured gain

The −49% is *arithmetic* (unique experts/block, a model property that transfers), not a measured t/s gain. The "−49% → ~2×" leap assumes expert-IO ≈ 90% of wall-clock, never isolated on the 3060 with cache active. **Fix: separate "−49% union-load (arithmetic, TRUE)" from "monetizes to ~2× (OPEN)" everywhere; recompute the union rate on the multi-domain trace, per code/math/chat, and expect it lower than 49%.**

### 7.9 Reproducibility gaps (artifact evaluation)

1. **The 8 `dominio_kb` prompts — the core of the "Segnali" domain study — are gitignored and untracked** (`dominio_kb/*.txt`), and their source (`raft_eval.jsonl`, sha 94b9b7f1) is a private out-of-repo file. The entire domain branch (trace, mask, biasmask eval — the headline 1.013×/1.365×) descends from prompts a reviewer cannot obtain. **MUST-FIX (trivial): commit the ~155 KB of k00–k07, or the generator + a sanitized source.**
<!-- src: runs/spex/2026-07-05_trace_prompts/.gitignore (dominio_kb/*.txt); git ls-files confirms only coding_en + generale_ita tracked -->
2. **The "disjoint" corpus is index-disjoint, not distribution-disjoint** — calibration and eval both derive from the same self-curated `raft_eval.jsonl`, so the near-lossless claim is in-distribution. **Fix: evaluate REAP-K50 on an independent held-out domain.**
3. **The engine source is an ephemeral out-of-repo copy**; line offsets (§3.2–3.3) are not checkable by a cloner, and the plan mixes commit `80ebbc3` (stock) with `bee9eb3` (patched) without stating which tree each offset refers to. **Fix: pin the commit and cite `git show 80ebbc3:file:NNNN` per claim, as the RECON doc already does.**
<!-- src: docs/SPEX_INTEGRATION_PLAN.md:4-5,146; docs/dspark/RECON_MTP_DS4.md:4-5 (good-practice model) -->
4. **No run pins the ds4 binary commit, build flags, or GGUF sha uniformly**; the eval `build_pod.log` files do not record the commit or patch series, so "same binary across the paired comparison" is asserted, not evidenced. **Fix: an `env_capture.sh` header (ds4\_commit, cuda\_version, gguf\_sha256, gpu, filesystem) on every run.**
5. **Traces are not bit-reproducible** (greedy temp0 non-determinism, 71% row divergence) and live out-of-repo; the committed mask is not regenerable end-to-end from a clone. **Fix: commit the source trace CSV as a fixed artifact.**
6. **Patches 0002–0006 are bare diffs** (no `Subject:`); regenerate with `git format-patch` for `git am`.

### 7.10 Numbers cited in briefing that are NOT on disk

The following appear in project notes but have **no on-disk source** and are **excluded** from this paper until committed: gate-weights top1 27%/top3 63%; n\_eff@64tok 30–47; skip-mass 46%/29%; axis-flip "0.0203" (the real minimum on disk is **0.0245**). Three independent inventories concur these come from an uncommitted trace or memory. Per house protocol ("verify agents' measurements"), they are marked **[PENDING/unverified]**.
<!-- src: absence confirmed via grep over docs/ and runs/; real min axis-flip runs/ds4_routing_trace_smoke/routing_trace_count64_summary.json (0.024523) -->

### 7.11 The est-file footprint minor discrepancy

The mask JSON reports 46.98 GiB; the design geometry reports 47.01 GiB (~0.03 GiB, GiB/GB rounding). We use the mask-measured 46.98; the difference does not affect any conclusion.
<!-- src: runs/reap/reap_mask_ds4_domain.json (est_file_gib 46.98); runs/reap/gguf_flash_expert_geometry.txt (47.01) -->

---

## 8. Conclusion and Artifacts

We set out to run a 158B MoE on a 12 GB consumer GPU by extending an expert-offload engine down the memory ladder. The honest state: the **mechanisms** are validated (bias-mask ≡ pruning with 0 violations, union-load arithmetic, structural acceptance, async plumbing that runs without crashing, a robust 3-family negative on sub-expert fusion), and the **routing structure** transfers on sign across models. But the **product thesis — usable speed on 12 GB — has no positive datapoint on the target**, because on 12 GB the static working set is the ceiling, the SSD tail is the floor, there is no compute stream to hide copies behind, and every cache-active run is slower than cache-off. The lever stack is composable in principle; its end-to-end payoff (the 2× IO) is OPEN, waiting on a cache-active-and-faster regime, a predictor that predicts on the target, and the STS fitted on the right drafter.

We consider the value of this paper to be the *measured gap* between the offload literature and a real SSD-bound deployment, plus a costed roadmap (`GAPS_AND_FIXES.md`) of exactly what turns each OPEN/PENDING into a claim.

**Artifacts (repo `moe-aggressive-commit @ 31c38f2`):**
- `docs/EXPERIMENTS_LEDGER.md` (~100 experiments F1–F6, anti-repetition ledger)
- `docs/REAP_DS4_{design,eval_plan}.md`, `runs/reap/2026-07-05_eval_biasmask/` (biasmask eval, mask, split-half)
- `runs/dspark/{20260705_dspark_b_v4flash_2xh200, 20260705_fase_b_sts, 20260705_mtp_acceptance_pod3090, 20260705_fase_c_smoke_3060}/`
- `runs/ds4_{routing_trace_smoke, bench_clean_ext4_20260705, cache_sweep_9p_20260705}/`
- `patches/ds4/0001-0010`, `src/msc/dspark/{sts_fit.py, sched_sim.py}`, `src/msc/spex/spex_loop.py`
- **[PENDING to commit]** `runs/spex/2026-07-05_trace_prompts/dominio_kb/` (gitignored — MUST-FIX)

<!-- src (durable positioning): docs/CONSOLIDATION.md, docs/PRIOR_ART.md, docs/PAPER_STATE.md (pre-pivot), docs/SPEX_INTEGRATION_PLAN.md, docs/HANDOFF*.md -->
