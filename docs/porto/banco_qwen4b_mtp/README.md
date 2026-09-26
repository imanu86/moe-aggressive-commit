# Private lab — standalone Qwen3.5-4B MTP, CPU extraction

## Delivered artifact

`D:\models\qwen35-4b\Qwen3.5-4B-MTP-Q8_0-head-original-Q6_K-embedding.gguf`

- Size: **660,602,592 bytes**.
- SHA256: `4e1dfbc30b1c1d8b2861be93fb14e5ae0f2481df347f4484df763c347cea26e7`.
- 17 tensors: **15 preconverted MTP tensors** (Q8_0 matrices, F32 norms), plus **byte-identical original Q6_K token embedding and F32 output norm**.
- `general.architecture=qwen35`; `qwen35.block_count=33`; `qwen35.nextn_predict_layers=1`.
- Tied output: **no `output.weight`**. Standalone head is NOT a replacement trunk.
- All original tokenizer metadata, including the chat template, copied byte-for-byte.
- Payload includes ~521 MB of original embedding. This is deliberate: dense embedding sharing is NOT patched or assumed.

Original target (untouched):

`D:\models\qwen35-4b\Qwen3.5-4B-Q4_K_M.gguf`

SHA256 `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4`, checked in full before/after extraction and by independent verifier. Original tensor count is 426; no MTP tensors are inserted in it.

## Provenance and download safety

Third-party **preconverted** donor:

- Repo: https://huggingface.co/unsloth/Qwen3.5-4B-MTP-GGUF
- Pinned revision: `86835bf9949e4d14d6860f7910b1340ad4f271a9`
- Donor file: `Qwen3.5-4B-Q8_0.gguf`, 4,610,580,800 bytes.
- LFS SHA256 reference: `4f40ff26e3b6e23888e520e9c33d9a309d919b940cd1375b421710c6cb6cc8dd`.
- Only **139,710,464 bytes** downloaded: header plus 15 head tensors. The full donor was **not downloaded, and its full SHA was not independently verified**.
- Every HTTP tensor/header request requires status **206**, exact `Content-Range`, identity encoding, matching length, bounded read (`requested+1` at most); HTTP 200 is rejected **before reading the body**. Header bounded to 32 MiB, individual ranges to 32 MiB.
- Each cached range has SHA256 and transport proof in `D:\ds4_work\qwen4b_mtp_lab\ranges`.
- Manifest (all ranges, tensor geometries, offsets and hashes): `D:\ds4_work\qwen4b_mtp_lab\manifest.json`.
- Donor LFS metadata: `D:\ds4_work\qwen4b_mtp_lab\donor-file-metadata.json`.

The head is copied without conversion/quantization. Thus no hand-written +1 RMS conversion or transposition was performed. **It has not been independently numerically compared to the official BF16 MTP tensors.** Provenance trust remains in pinned Unsloth conversion. Segment hashes establish reproducibility/integrity of captured bytes, not independent authenticity of the upstream conversion.

## Exact CPU checks

- Original trunk complete SHA before and after extraction.
- Exact set of 15 `blk.32.*` tensor names; all runtime geometry/type constraints checked explicitly.
- All 17 structural `qwen35.*` metadata fields match donor/trunk except intentionally different block count/NextN count.
- Vocabulary/tokenizer checked against donor (template difference allowed); output keeps original template regardless.
- Written file reparsed; every tensor SHA rechecked, offsets in bounds and non-overlapping, tied output asserted.
- **Independent installed gguf-py reader**: 17 tensors, byte-identical original embedding/output norm, **8 tokenizer fields** byte-identical; complete trunk and output hashes checked again.
- Independent reader checks all F32 norm values and Q8_0/Q6_K block scales for finite values.
- **15/15 CPU unit tests passed**, including HTTP200 rejection, mismatched Content-Range/length, oversized/short response, cache tampering, bounded header/ranges, unsupported quantization and unaligned rows.
- Readable evidence (UTF-8 without BOM): `D:\ds4_work\qwen4b_mtp_lab\cpu-unit-tests.utf8.txt`, `independent-readback.utf8.json`, and `cpu-verification-summary.json`. The earlier unsuffixed Tee-Object outputs are legacy UTF-16; use these UTF-8 versions.
- No GPU, server, quantizer, build, commit, push, branch/worktree change, runtime/source patch or live configuration modification.

## Reproduce (CPU only)

From this directory, using Python 3.12 and installed `gguf`/NumPy for independent readback:

```powershell
python -B -m unittest -v test_extract_mtp
python -B verify_sidecar.py D:\ds4_work\qwen4b_mtp_lab\manifest.json
```

Extraction command used:

```powershell
python -B extract_mtp.py `
  --trunk D:\models\qwen35-4b\Qwen3.5-4B-Q4_K_M.gguf `
  --lab D:\ds4_work\qwen4b_mtp_lab `
  --output D:\models\qwen35-4b\Qwen3.5-4B-MTP-Q8_0-head-original-Q6_K-embedding.gguf
```

Extraction deliberately refuses existing output. For a repeat use a **new output filename** and optionally a new lab directory; reuse the existing range cache only after its recorded hash checks. Do not delete/replace any live artifact. Scripts use only Python stdlib for extraction; independent verification uses installed gguf-py/NumPy.

## Invocation contract — NOT executed here

Keep target `-m` pointing at the original Q4_K_M trunk, then add:

```text
-md D:\models\qwen35-4b\Qwen3.5-4B-MTP-Q8_0-head-original-Q6_K-embedding.gguf
--spec-type draft-mtp
-ngld 99
-ctkd q8_0 -ctvd q8_0
--spec-draft-n-max N
--spec-draft-n-min 1
--spec-draft-p-min 0
```

Test N=1,2,3 individually. Target context/cache remain `-c 131072 -np 1 -ctk q8_0 -ctv q8_0` as requested by parent. Keep all other baseline parameters identical. This is a **flag fragment, not an auto-start script**; parent owns runtime binary selection, port, GPU scheduling and actual tests.

Source inspected read-only:

`C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920\source`

- `src/models/qwen35.cpp:36`: standalone detected by missing `blk.0.attn_norm.weight`, with NextN count >0; trunk tensors optional.
- `src/models/qwen35.cpp:93-115`: required MTP tensor geometry, optional head embedding/output overrides.
- `src/models/qwen35.cpp:484-635`: dense MTP graph, fallback to model embedding/tied output.
- `common/arg.cpp:4179,4189,4236`: max/min/probability flags exist.
- `common/common.h:394-399` + `common/common.cpp:1724`: target `n_rs_seq` auto-set to draft max N for MTP (rollback capacity).
- `common/speculative.cpp:2580`: draft context copies target context; `2592` draft recurrent rollback slots=0 (dense head is full attention).
- `common/speculative.cpp:2523,2583`: **leave `LLAMA_MTP_LIGHT` unset/0 for first correctness baseline**; light mode changes batch16 and defaults draft context to8192 with eviction. It is a separate experiment, not equivalent setup.
- Never use `--spec-synth-*` in correctness/acceptance results: those fabricate acceptance for benchmarking.

### Telemetry without patches

- Add `--metrics`; read private server `/metrics` before and after each isolated request:
  - `llamacpp:spec_decode_num_draft_tokens_total`
  - `llamacpp:spec_decode_num_accepted_tokens_total`
  - `llamacpp:spec_decode_num_drafts_total`
  - `llamacpp:spec_decode_num_accepted_tokens_per_pos_total{position="..."}`
- Rejected proposals = delta drafted minus delta accepted. Acceptance = delta accepted / delta drafted; mean accepted span including target = 1 + delta accepted / delta verification steps.
- Response `timings.draft_n`, `timings.draft_n_accepted` (only present when draft tokens >0), plus `predicted_n/ms/per_second`.
- `-lv 3` prints acceptance and mean length in completed-slot timing logs.
- `LLAMA_SPEC_PROFILE=1` prints phase timings every 64 speculative verification steps (`server-context.cpp:42-64`).

## Parent-reported runtime smoke (not executed by extractor)

Parent reports a successful private GPU smoke using unchanged runtime, context131072, KVq8, draft1: head loaded and `tool_batch` emitted one correct Cockpit JSON call; predicted72, draft36, accepted36, approximately86.6 token/s. **Not a final benchmark:** short sample and concurrent compilation. Parent restored daily afterwards. Evidence directory: `D:\ds4_work\qwen4b_campaign\mtp1_smoke_contended`. These are parent-reported observations; this child performed no GPU/server action and did not independently audit those files.

## Outstanding risks / next gates

This child's delivery is **CPU-verified artifact integrity/layout**. Parent's successful runtime smoke establishes one loading/tool case, not general inference correctness. Parent must test private runtime load, target-vs-MTP greedy comparison, rejection rollback (including hybrid state), vocabulary/logits mapping, short+long context, output/tool integrity, acceptance, TTFT, end-to-end speed and VRAM. Quantized Q8 head can reduce acceptance; duplicate embedding and 128k head KV add memory. Source inspection does not establish that an arbitrary existing executable was built from exactly this source. No speedup or inference-equivalence claim is made here.
