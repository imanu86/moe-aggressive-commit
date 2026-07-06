# Design 0013 — drafter MTP su CPU+RAM (env `DS4_MTP_CPU_DRAFTER=1`)

> **STATO: NO-GO (probe 2026-07-06, `runs/dspark/20260706_probe_0013/`).**
> Probe decisionale (mandato SPEX-main, soglia <10%): (a) meccanismo NO — nella config
> daily (cache a conteggio, reserve default) il gate `available=0.00` non scatta MAI,
> con o senza registrazioni host della mappa MTP (isolate entrambe con la diagnostica
> `DS4_MTP_NO_REGISTER`, patch 0012): l'accounting mordeva solo le config a budget-GB
> di M8. (b) delta reg-vs-noreg a parità di --mtp: ~5% sulle mediane (0.42 vs 0.44),
> dentro un rumore intra-lato di ±50% (0.27-0.59 su config identiche). (c) NO-GO.
> Il beneficio ipotizzato era un artefatto di configurazione. Il design resta agli atti
> (mappa componenti valida) se il quadro cambia — es. target di produzione con config
> a budget-GB, o drafter DSpark-vero con footprint device reale.
> Nota metodologica: la varianza ±50% tra run identici sul 3060 daily impone mediane
> di ≥3 run a stato controllato per QUALSIASI claim t/s futuro su questa macchina.
> Bench: `runs/dspark/20260706_cpu_drafter_bench/` — testa LM Q8 43.5ms (bandwidth-bound
> 13.7GB/s, satura a 8 thread), draft completo stimato ~47ms = +2-3% del ciclo streaming
> a draft-2, contro +30-60% di expert-cache sbloccata (M8). Mappa sorgente: agente
> esplorativo 2026-07-06 su worktree `/root/ds4-dspark` (bee9eb3+0009-0011).

## Perché — FRAMING CORRETTO (correzioni SPEX-main 2026-07-06, incassate)
⚠️ Tre errori del framing iniziale, corretti:
1. **Host ≠ device**: i "3.55GB" sono mmap HOST; il footprint DEVICE delle statics MTP
   è ~0.34GB. Il blocco della cache su WSL2 NON è VRAM recuperabile: è il bug di
   accounting `cudaHostRegisterMapped` (`cudaMemGetInfo available=0.00`) — M8-BIS/TRIS
   lo provano (statics tolte via 0011, cache ancora negata).
2. **Il "+30-60%" era un confronto a DUE variabili** (base senza --mtp E con
   RESERVE_GB=1 vs spec con --mtp): NON è il beneficio attribuibile alla cache. Il
   numero pulito (cache-on vs cache-off a parità di --mtp) è l'oggetto del PROBE sotto.
3. Il bench 47ms era su GEMV sintetico: il costo drafter-CPU va rimisurato sul path
   ds4-CPU reale prima di qualsiasi build.

**Beneficio VERO ipotizzato dalla 0013**: il drafter CPU non richiede NESSUNA
registrazione host-mapped → l'accounting si sblocca → l'expert cache può abilitarsi
con --mtp su WSL2. Da PROVARE col probe (sotto), non da inferire.
Rischio correttezza nullo per costruzione: il target verifica ogni draft.

## PROBE decisionale (mandato SPEX-main, PRIMA di ogni build — soglia: delta <10% = NO-GO)
(a) meccanismo: `available` riportato con vs senza registrazione host del support model
    (env diagnostica `DS4_MTP_NO_REGISTER=1`, patch measurement-only nel worktree);
(b) numero pulito: cache-on vs cache-off **a parità di --mtp** (draft-1 inerte su
    entrambi i lati: mappa caricata, drafting spento, path identico — l'unica variabile
    è registrazione→cache). Sul 3060 daily, MAI pod (regime cache/warm non trasferisce).

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
