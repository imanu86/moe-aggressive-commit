# Design 0013 — drafter MTP su CPU+RAM (env `DS4_MTP_CPU_DRAFTER=1`)

> Stato: PROGETTATO E BENCHMARCATO, in attesa di go (SPEX-main + utente).
> Bench: `runs/dspark/20260706_cpu_drafter_bench/` — testa LM Q8 43.5ms (bandwidth-bound
> 13.7GB/s, satura a 8 thread), draft completo stimato ~47ms = +2-3% del ciclo streaming
> a draft-2, contro +30-60% di expert-cache sbloccata (M8). Mappa sorgente: agente
> esplorativo 2026-07-06 su worktree `/root/ds4-dspark` (bee9eb3+0009-0011).

## Perché
Nel regime consumer la GPU è IO-starved e la CPU oziosa. Spostando il drafter su CPU:
la VRAM del drafter torna INTERA all'expert cache; spariscono 0011, 0012 e il bug di
accounting WSL2 (il drafter non tocca più CUDA) → stack piattaforma-indifferente.
Rischio correttezza nullo per costruzione: il target verifica ogni draft.

## La mappa (verificata sul sorgente, riusabilità 34/36 componenti)
Call-site da sostituire (worktree, righe attuali):
- `metal_graph_eval_mtp_draft()` → ds4.c:27810 (produce mtp_logits 129280f, mtp_top,
  aggiorna g->mtp_state_hc)
- `metal_graph_eval_mtp_draft_from_hc()` → ds4.c:27941 (idem, HC da prev_hc, ping-pong
  state_hc/next_hc)

Componenti CPU esistenti da riusare DIRETTI (file ds4.c, righe indicative):
- Q8_0 matvec (e_proj/h_proj/OUTPUT): `matvec_q8_0*` 5292-5318, prequant 5101/5128 —
  usare le varianti `_decode_scratch` (niente malloc nel hot path)
- Q4_K expert MoE: `matvec_q4_k_experts_mid_prequant` 5993 + `_accum_prequant` 6065
- F16 matvec (hc fn): `matvec_f16*` 4557-4584
- Attention raw SWA (ring 128): `layer_attention_raw_swa_one` 9220 + `kv_cache_init` 8484
  (pipeline interna completa: norm, q-lora, kv, rope, fp8-kv, push, softmax, out, hc_post)
- Hyper-connections: `hc_split_sinkhorn_one` 6332, `hc_weighted_sum_one` 6413,
  `hc_pre_from_state_one[_scratch]` 6464/6503, `hc_post_one` 6518
- Router+topk: `layer_router_probs_one` 7328, `layer_topk_selected_experts*` 7393/7405
- Testa LM: `output_logits_one_decode_scratch` 10209 + `argmax_f32` 10260
- Accesso pesi: `tensor_data()` 2326 (mmap diretto, dequant on-the-fly — IDENTICO per
  entrambi i modelli, zero copie)
- Threading: `ds4_parallel_for`

## Da scrivere ex novo (~300-500 righe)
1. `cpu_mtp_draft_forward()` e `cpu_mtp_draft_from_hc()`: orchestrazione della pipeline
   (embed anchor → e_proj/h_proj mix con enorm/hnorm → 1 blocco MTP: hc_pre → attn SWA →
   hc_post → hc_pre → MoE 6/256 → hc_post → collapse hc_head → norm → GEMV output →
   argmax). NB: i tensori sono `mtp.0.*` (ds4_mtp_weights, bind a ds4.c:4436 su pin).
2. Struct stato CPU: `float *mtp_raw_cache` (128×512f), `mtp_state_hc/next_hc`
   (2×16384f), contatore n_raw — sostituisce i campi ds4_gpu_graph.
3. Handoff GPU→CPU: `ds4_gpu_tensor_read` dell'HC del target (16384 float = 64KB) per
   ciclo — API esistente.
4. Dispatch env-gated ai due call-site (pattern identico alle nostre 0009-0011).

## Formato HC (verificato)
Stato = 4 teste × 4096 = 16384 float row-major (64KB). Split Sinkhorn: 24 float
(4 pre-w, 4 post-w, matrice 4×4 normalizzata, 20 iter).

## Piano (al go)
Sessione 1: wrapper + parity test vs drafter GPU su input identici (stesso anchor/HC →
confronto top-id e correlazione logits; NON bit-exact, basta acceptance comparabile).
Sessione 2: integrazione + smoke 3060 (M8-QUATER: spec2+cache CON drafter CPU — il
numero finale della tesi) + coppia eval di conferma. Eventuale s.3: perf (overlap
draft/verify su thread, kernel testa più furbo se serve).

## Sinergie upstream
PR #508 (SSD streaming expert su backend CPU, pread+LRU) — macchinario affine se mai
servisse il drafter CPU con pesi non in RAM. Nessun conflitto con #504 (solo CUDA).
