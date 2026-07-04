# Positioning — Prior-Art Verificato e Delta

> Verificato via web (arXiv, GitHub, model card) con doppio passaggio (ricerca + skeptic
> avversariale). Citazioni in fondo a ogni voce. Confidence alta salvo dove indicato.

---

## 1. Predizione expert pre-attention (~93–97 %) — CONFERMATO

**Fonte primaria.** Zhu, Bohl, Oester & Alonso (ETH Zürich), *"Pre-Attention Expert Prediction and
Prefetching for MoE LLMs"*, [arXiv:2511.10676](https://arxiv.org/abs/2511.10676) (nov 2025).

**Cosa fa.** Prende le hidden activations **prima** del blocco di attention (dopo la layernorm),
le passa per **2 funzioni lineari** (intermediate 2048) con loss ranking-aware (BCE pesata +
pairwise ranking), e predice quali expert il gate selezionerà → il prefetch si sovrappone al
compute di attention+expert, coprendo anche il primo layer.

**Numeri (exact-match).** 93.03 % DeepSeek-V2-Lite · 94.69 % Qwen3-30B · 97.62 % Phi-mini-MoE.
~15 % assoluto sopra SOTA (vs FATE 78.79 % su DeepSeek-V2-Lite).

**Relazione col delta.** Input **riusabile**: nella nostra policy il predittore serve al *prefetch*
(ammortizzare la latenza nei modi `fetch-lossless`/cascade). **Non lo miglioriamo** — non è il nostro
contributo. Altri predittori verificati: FATE (97.15 % con routing-weight enhancement), SiDA-MoE
(LSTM-as-hash offline, hit-rate ~99 %), ExpertFlow (routing-path predictor), Pre-gated MoE
(gate cross-layer, **non** pre-attention).

---

## 2. MoE-Infinity — ⚠️ CORREZIONE AL BRIEF (partially_confirmed)

**Fonte.** Xue, Fu, Lu, Sun, Mai, Marina (Univ. Edinburgh), [arXiv:2401.14361](https://arxiv.org/abs/2401.14361),
codice [EfficientMoE/MoE-Infinity](https://github.com/EfficientMoE/MoE-Infinity) (Apache-2.0).

> **Il brief dice:** *"MoE-Infinity = coarse-grained popularity caching = versione SEMPLICE della mia
> idea"*. **La verifica dice il contrario.**

MoE-Infinity **rifiuta esplicitamente** il caching per frequenza di attivazione globale, e cita
proprio BrainStorm come approccio insufficiente:
> *"A straightforward approach is to track expert activation frequency over time, as implemented in
> BrainStorm… we find this approach insufficient, as it fails to account for the sparse activation
> patterns of individual requests."*

Fa invece **matching di similarità per-sequenza**: l'Expert Activation Matrix (EAM, `L×E`) viene
tracciata a livello di iterazione (iEAM) → richiesta (rEAM) → collezione storica (EAMC, `P≪N`
rappresentanti via clustering); a runtime la richiesta in corso è matchata per **distanza coseno**
al rappresentante storico più simile, guidando prefetch ed eviction. È **lossless**: cambia solo il
*placement* degli expert, **mai** quali expert eseguono → accuratezza invariata. Gain: 3.1–16.7×
latenza per-token (v3) su macchine personali.

**Conseguenze per il nostro disegno (due correzioni):**
1. La **baseline `COARSE`** (top-K più frequenti globali) NON è "stile MoE-Infinity": è **stile
   BrainStorm** (popolarità globale). Rinominata di conseguenza in `00_architecture.md`.
2. **MoE-Infinity è il cugino *lossless* di AGGRESSIVE-COMMIT**, non la sua versione semplice. Stima
   già un working set per-sequenza in modo raffinato — ma non molla **mai** accuratezza.

---

## 3. I sistemi di eviction/miss-handling — nomi corretti (CONFERMATO il sospetto)

I nomi del brief sono in gran parte **misattribuiti**:

| Nome nel brief | Cos'è davvero | arXiv |
|---|---|---|
| **ST-MoE** | Training **stabile/transfer** di MoE sparsi (Zoph et al.). **NON** offloading. | [2202.08906](https://arxiv.org/abs/2202.08906) |
| **SP-MoE** | **Speculative decoding + prefetching** (TPOT 1.07–3.5×). NON eviction LRU. | [2510.10302](https://arxiv.org/abs/2510.10302) |
| **SpecMD** | **Benchmark di cache policy** + propone "Least-Stale" (feb 2026). | [2602.03921](https://arxiv.org/abs/2602.03921) |

I sistemi **reali** dietro le tecniche citate:
- **LRU eviction** → **Mixtral-offloading** (Eliseev & Mazur, [2312.17238](https://arxiv.org/abs/2312.17238)):
  cache LRU + mixed-quant HQQ + speculative prefetch; `k=2` su 12 GB, `k=4` su 16 GB.
- **Precision cascading** → **HOBBIT** (vedi §4).
- Altri verificati: Fiddler (CPU-GPU orchestration, ICLR'25), AdapMoE (gating sensitivity-based),
  MoE-SpeQ (speculative quantized decoding).

> 🎯 **Rilevante per noi:** **SpecMD** (feb 2026) benchmarka cache policy **su OLMoE**: hit-rate
> **>88 %** con cache di **~5 % / 0.6 GB**, fino a 85× meno collision-miss vs LRU. È evidenza
> esterna che **OLMoE ha alta località** → buona scelta come modello ad alta sparsità (vedi
> `02_models.md`).

---

## 4. HOBBIT — il prior-art PIÙ VICINO al nostro `precision-cascade` (CONFERMATO)

**Fonte.** Tang et al. (SJTU + CUHK), *"HOBBIT: A Mixed Precision Expert Offloading System"*,
[arXiv:2411.01433](https://arxiv.org/abs/2411.01433) (preprint nov 2024). ~8.000 righe su llama.cpp.

**Cosa fa.** Sui cache-miss, invece di caricare l'expert a piena precisione, lo **sostituisce con
una versione a bassa precisione**. Criterio = magnitudine del gating weight `‖G(x)‖` (proxy con
correlazione **0.99** col contributo reale). Regola **a due soglie** (per-token):
`s ≤ T1=0.6 → alta precisione` · `T1 < s ≤ T2=0.9 → bassa precisione` · `s > T2 → SKIP`.
Distribuzione su Mixtral: **67 % high / 30 % low / 3 % skip**. Precisioni: FP16→INT4 (RTX 4090),
INT8→INT2 (Jetson). Speedup decoding fino a **9.93×**.

**Numero chiave e SUO LIMITE.** Degrado accuratezza **≤ 1 %**… ma **solo su GSM8K e TruthfulQA**,
benchmark a **contesto corto**. ⟵ **Questo è esattamente il buco del Vincolo B.**

**Relazione col delta.** HOBBIT è la prova che il lato "lossy mixed-precision" funziona — ma:
- è **per-token dinamico**, non un **commit per-sessione** sul working set;
- riporta **un singolo numero** (≤1 %), **non** una superficie accuratezza-vs-VRAM-vs-sparsità;
- **non valida a contesto crescente** → non sa dirti se quel ≤1 % regge a 32k/64k.

La nostra soglia-importanza per `precision-cascade`/`hard-drop` può **riusare** lo stesso proxy
`‖G(x)‖` (validato a 0.99 da HOBBIT) — non lo reinventiamo.

---

## 5. imatrix + antirez/ds4 — quant importance-aware STATICA (CONFERMATO)

- **imatrix (llama.cpp).** Introdotta da ikawrakow, [PR #4861](https://github.com/ggml-org/llama.cpp/pull/4861)
  (gen 2024). Calcola **offline** su un corpus di calibrazione i termini diagonali `⟨a_i²⟩` (magnitudine
  quadra media per colonna), usati come **pesi in una RMSE pesata** per scegliere scale/rounding.
  **Non cambia il bit-budget** del tensore, solo ri-pesa l'errore. Effetto massimo a 2–4 bpw.
  → **statica/offline, non per-sessione.**
- **antirez/ds4.** Verificato via GitHub API: "DwarfStar", motore di inferenza C **from-scratch** per
  DeepSeek-V4 (Flash 43 layer/256 expert; Pro 61/384), di Salvatore Sanfilippo, 16.7k star, creato
  2026-05-06. Include tooling imatrix con dataset di calibrazione (~4.682 prompt, ~2.91M token, anche
  coding/agent/long-context). **NON** è un quant pubblicato su HF: è motore + calibrazione statica.

**Relazione col delta.** **Ortogonale.** imatrix decide l'importanza **una volta, offline, sui pesi**;
noi decidiamo la residenza **per-sessione, online, sull'uso**. Sono combinabili (es. gli expert
degradati in `precision-cascade` potrebbero usare quant imatrix-aware), non in competizione.

---

## 6. Il delta, riformulato e affilato

> **NON** è "stimare il working set per-sessione" — **MoE-Infinity lo fa già**, in modo persino più
> raffinato della popolarità globale, ma **lossless**.
>
> Il delta è la **congiunzione** di tre cose che nessun lavoro verificato fa insieme:
> 1. **Lossy deliberato sul complemento del working set** — non solo riposizionare (MoE-Infinity) ma
>    **degradare** (`precision-cascade` / `hard-drop`), committando **per-sessione** (non per-token
>    come HOBBIT).
> 2. **Misura della SUPERFICIE** accuratezza-vs-VRAM **in funzione di sparsità (strutturale +
>    concentrazione empirica) E lunghezza di contesto** — dove HOBBIT, il prior-art lossy più vicino,
>    riporta **un singolo ≤1 % su benchmark corti**.
> 3. **Protocollo di falsificazione a contesto crescente** (§12 di `00_architecture.md`): una regione
>    è promossa solo se regge < 2 % su **tutte** le lunghezze, non in media.

| Lavoro | Stima working set per-sessione? | Lossy? | Misura superficie vs sparsità+ctx? |
|---|---|---|---|
| Predittori pre-attention | no (predice il prossimo step) | no | no |
| BrainStorm (popolarità globale) | no (globale) | no | no |
| MoE-Infinity | **sì** (per-sequenza) | **no** | no |
| Mixtral-offloading | no (LRU) | quant statica | no |
| HOBBIT | no (per-token) | **sì** (mixed-prec) | no (≤1 %, ctx corto) |
| imatrix/ds4 | no (offline sui pesi) | sì (statica) | no |
| **AGGRESSIVE-COMMIT (noi)** | **sì** | **sì** | **sì** ← il delta |
