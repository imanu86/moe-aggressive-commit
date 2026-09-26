# MTP2/3 greedy divergence — CPU analysis and proposed probes

## Observed, not inferred

Inputs: completed `D:\ds4_work\qwen4b_campaign\clean_*\bench\results.jsonl`. Analysis command: `python -B analyze_divergence.py`; result `D:\ds4_work\qwen4b_mtp_lab\divergence-analysis.json`.

Against `original_b`:

| Variant | Same output hashes | Divergence |
|---|---:|---|
| original_a | 15/15 | none |
| rebuild | 15/15 | none |
| mtp1 | 15/15 | none |
| mtp2 | 12/15 | prose, all 3 repetitions |
| mtp3 | 12/15 | prose, all 3 repetitions |

Requests have identical SHA256 within each matched case/repetition. This establishes repeatability for these prompts, **not universal equivalence for MTP1**.

First text divergence (Unicode character index, zero-based; NOT a token index):

- **MTP2 at997**: common tail `...non produca allucinazioni o errori logici, specialmente in `; baseline continues `domini critici come la medicina o la giurisprudenza`, MTP2 `contesti critici come la sanità o la finanza`. Baseline349 generated tokens, MTP2342; proposed336, accepted175 in repetition0.
- **MTP3 at1363**: common tail `...i risultati potrebbero essere distorti da fattori `; baseline `esterni o anomalie temporanee`, MTP3 `di rumore o condizioni ambientali specifiche`. Both349 generated tokens, but texts/hashes differ. Proposed477, accepted192 in repetition0.

Tool cases and result summary match baseline in all tested repetitions. This includes **the same incorrect extra login argument** in `tool_retry`: identical does not mean correct. Do not report 3/3 tool semantic success or lossless MTP2/3.

## What the source proves, and what it does not

Source root read-only: `C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920\source`.

1. `common/sampling.cpp:678-705`: each proposed token is compared with a token sampled from **target logits** at the matching batch row; processing stops on first mismatch. With greedy sampling, a divergent accepted token means target verification logits/state or row selection changed (unless logging/token reconstruction is wrong); low draft quality alone should reduce acceptance, not override target choices.
2. `tools/server/README.md:589` explicitly warns that logits need not be bit-identical across batch sizes. Scalar decode vs verification over N+1 tokens can legitimately change floating-point reduction. **This warning does not prove these particular differences are harmless.**
3. `ggml/src/ggml-cuda/ggml-cuda.cu:2173-2185`: matmul dispatch depends on shape. `mmvq.cu:290-385` has architecture-dependent thresholds; Ampere falls back to `MMVQ_MAX_BATCH_SIZE`. Do not automatically claim MTP2 switches to MMQ: N+1 small-column MMVQ specializations can still differ.
4. `common/common.h:394-399` sets target recurrent rollback capacity to draft max N. `llama-memory-recurrent.cpp:193-199` selects per-token snapshot on partial removal; pending rollback is single-use. `models/delta-net-base.cpp:499-502` requires trailing N+1 tokens to remain in one ubatch. `llama-memory-hybrid.cpp:85-89` asks splitter to preserve this suffix.
5. `tools/server/server-context.cpp:3963-3995` chooses checkpoint restore/replay only if context needs full removal or rollback exceeds recurrent capacity. Otherwise `common_speculative_accept` and `slot.mem.seq_rm` handle partial acceptance (`4003`, `4040`). With n_rs_seq=N and draft<=N, normal rejection usually uses snapshot rollback, not whole-checkpoint fallback. Thus increasing ctxcp alone is **not a demonstrated fix**.
6. `server-context.cpp:4047-4049` sets speculative emitted token probability to1 and leaves `TODO: set result.probs`. **Speculative logprobs may be absent/placeholder**, not valid evidence of target verifier confidence.
7. `server-context.cpp:513-527`: remaining output budget limits speculation to `n_remaining()-1`. Native `n_predict:1` therefore forces no draft. Cold one-token top probabilities on an MTP-enabled server are meaningful target results, but **not the internal multi-token verifier state**.

## Prioritized diagnosis

A. **Localize exact generated token divergence**, not only text position. Obtain native `/completion` raw token IDs with the same rendered prompt and greedy request. Confirm the native generated text matches the existing chat case before using its index.

B. **Cold teacher-forced prefix probe**: force the exact original generated token prefix up to divergence, then sample one token with top10 probabilities. Compare original vs MTP-enabled target at positions j-2..j+2. Use no reused cache. Inspect logp gap between baseline/alternate token. Nearly equal candidates with small coherent logp changes support floating-point sensitivity, but cannot exclude accumulated state error. Large differences or corruption demand state/row investigation.

C. **Batch-only control, no speculative rejection** (requires a native helper, not exposed by current HTTP API): on the same original target, feed canonical token IDs teacher-forced through scalar llama_decode and through N+1-token batches with logits requested for every row. Compare complete target logits at the same prefix, top1/2 margins, max-abs and RMS deltas. Matching observed alternate at the same position without any wrong draft/rollback strongly supports batch numerical effects. Keep context, KV type, offload, graph options and prompt segmentation fixed.

D. **Rollback control** (native helper): checkpoint one canonical prefix, evaluate controlled N-token proposals with a known wrong suffix, remove unaccepted positions using `llama_memory_seq_rm`, replay the accepted canonical prefix and query next logits. Compare with a clean context evaluated using **identical batch segmentation**. Cover rejection lengths1..N and consecutive rejection events. Large persistent deltas only after rollback implicate snapshots/state indexing. Compare recurrent/conv and attention KV state separately; do not let different prefill chunking confound it.

For source instrumentation, capture position, `slot.spec_i_batch`, target top2 logits before `common_sampler_sample_and_accept_n`, proposed/accepted IDs, `n_rollback`, actual `llama_n_rs_seq`, snapshot index and checkpoint/replay flag. No patch is made by this CPU analysis. Native server cannot supply raw internal logits or force a particular rejected draft through the public completion API.

## Minimal HTTP probe commands (PARENT ONLY; child did not execute)

`native_prefix_probe.py` is opt-in and refuses daily ports8100/8104. Use the private server sequentially, never alongside another GPU campaign. It reads optional `QWEN_BENCH_API_KEY` from environment and writes no key.

1. With baseline private server on8114:

```powershell
python -B native_prefix_probe.py capture --allow-inference --url http://127.0.0.1:8114 --out D:\ds4_work\qwen4b_mtp_lab\baseline-native.json
```

2. With MTP2 private server on the same private port:

```powershell
python -B native_prefix_probe.py capture --allow-inference --url http://127.0.0.1:8114 --out D:\ds4_work\qwen4b_mtp_lab\mtp2-native.json
```

3. CPU-only token comparison:

```powershell
python -B native_prefix_probe.py compare --reference D:\ds4_work\qwen4b_mtp_lab\baseline-native.json --variant D:\ds4_work\qwen4b_mtp_lab\mtp2-native.json --out D:\ds4_work\qwen4b_mtp_lab\native-first-diff.json
```

4. Substitute returned token index J. Run once with original private server and once with MTP private server, different output paths:

```powershell
python -B native_prefix_probe.py prefix --allow-inference --url http://127.0.0.1:8114 --reference D:\ds4_work\qwen4b_mtp_lab\baseline-native.json --position J --out D:\ds4_work\qwen4b_mtp_lab\prefix-J-original.json
```

Actual HTTP sequence: `/apply-template` with original messages and `chat_template_kwargs.enable_thinking=false`; `/tokenize` with `add_special=true,parse_special=true`; `/completion` takes **token IDs** (no assistant-message reformat). Prefix request:

```json
{"prompt":["ACTUAL_INTEGER_TOKEN_IDS"],"n_predict":1,"stream":false,"return_tokens":true,"temperature":-1,"samplers":["temperature"],"n_probs":10,"post_sampling_probs":false,"seed":42,"cache_prompt":false,"repeat_penalty":1,"id_slot":0}
```

Replace the illustrative string with integer IDs; script does this automatically. Negative temperature is documented greedy selection with simple softmax probabilities; raw-logit differences are not directly returned. The script rejects a response with nonzero `timings.draft_n`. A one-token cold replay alone cannot decide rollback correctness; warm-cache reuse is not a substitute unless exact reused prefix/state is verified.

## Larger draft safety and next quality probes

- No static hard cap at3 or5 was found in generic Qwen35 recurrent path. N4/6/8 -> K5/7/9 snapshot planes. `gated_delta_net.cu:146-155` writes slots with dynamic `target_slot<K`.
- `K<=5` is only optional tiled GDN fast-path (`187-195`), also requiring H48 and n_tokens>=16. Qwen4B H32 does not match, so it uses generic fallback regardless. Keep N+1<=ubatch (512 easily satisfies9), watch increased VRAM, verify logged n_rs_seq=N and rejection paths.
- First finish short deterministic **tool_batch** N3/4/6/8 for speed/valid JSON. Then test all three tool cases, especially retry recovery, and real-result summaries with simulated responses.
- Thinking-on short test should precede100k: compare tool correctness, time-to-tool, total time and reasoning length. Thinking is not expected to preserve output hash across sampler changes; compare like-for-like settings.
- For100k, start baseline + selected conservative MTP (N1 unless larger-draft correctness is established), one tool case first with capped output and identical100k synthetic prompt tokens. Record actual prompt count, cold prefill/TTFT, peak VRAM and acceptance. This is a capacity/latency smoke, **not broad100k instruction-following validation**. Do not combine large-draft+thinking-on+100k changes in the first test.
