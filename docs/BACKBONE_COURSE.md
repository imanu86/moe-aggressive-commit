# Backbone di ds4 — corso accelerato + anatomia VRAM + limatura (verificata)

> Output di un workflow multi-agente (3 grounding sul sorgente ds4 vero + 11 verifiche avversariali di candidati +
> sintesi, 2026-07-06, `wfx2rkunv`, 16 agenti). Ogni numero = byte-count reale dai gguf su /root/models o log
> on-device; ciò che non è verificato è marcato **(da misurare)**. Un verificatore su 16 è fallito (retry cap) —
> il suo candidato (cap della Q8→F16 device-cache) resta non concluso.

## Verdetto in una riga
**Sì, si può limare — e il candidato è UNO solo: `static-Q4` sul backbone.** Porta il blocco statico residente da
**7.64 GB → 3.50 GB** (byte-count), liberando **~3.5 GB device** sul 3060 (scontato il token_embd). **NON i ~5 GB**
di HANDOFF_7:149 (gonfiato). Il gguf è **già costruito** (`/root/models/ds4-staticQ4.gguf`, 82GB, Jul 4) ma **MAI
misurato**. Le altre due leve storiche (patch 0011 MTP-host, reserve-tuning) sono **REFUTED**.

## ⚠️ Scoperta che corregge la memoria (da risolvere col caricamento)
Due cose che credevo vere NON sono nel repo / sono contraddette dai byte-count:
- **"static-Q4 è FALLITO su 704 tensori / è un redundant twin del 2-bit"** → nessun artefatto nel repo lo sostiene.
  Il byte-count del file dice **backbone genuinamente Q4_K** (statico 3.50GB, metà del 2-bit) = un **vero static-Q4**,
  non un twin. **MA** il grounding sul sorgente ha trovato un **assert HARD F16 su `token_embd`** (`ds4.c:3566`
  `tensor_expect_layout(..., DS4_TENSOR_F16, ...)`). Quindi resta UN dubbio aperto e gating: **la staticQ4.gguf
  carica davvero?** O la build ha tenuto token_embd in F16 (→ carica, win reale ~3.5GB), o l'ha portato a Q4_K
  (→ l'assert spara, non carica — possibile ORIGINE della storia "fallito"). **Solo caricarla lo decide.** Non
  fidarsi di nessuna delle due narrazioni finché non si carica.
- **"backbone ~5.8GB, ~6.2GB liberi"** (mio brief) → contraddetto: backbone reale **7.64GB**, e la cache già a
  7.86GiB device senza MTP.

## Convergenza con la traccia memoria
Lo studio confidence-cascade è arrivato alla **stessa conclusione da un altro angolo**: il muro dei 12GB **non** è
la KV (MLA la comprime già) né gli expert (streammati) — è il **peso RESIDENTE del backbone**. `static-Q4` è la sola
leva che lo tocca. Le due tracce si confermano a vicenda.

---

## Anatomia VRAM del backbone sul RTX 3060 12GB
Il "backbone" = tutto ciò che NON sono gli expert instradati: calcolato a OGNI token → DEVE stare in VRAM (gli expert
invece streammano da SSD). È lui che occupa lo spazio che vorremmo dare alla cache-expert.

| Componente | Ruolo | Precisione (2-bit daily) | GB | Fonte | Limabile? |
|---|---|---|---|---|---|
| **Attention MLA** (Q/K/V + o_proj, 43 layer) | calcolata ogni token | Q8_0 | (parte dei 7.64) | HANDOFF_7:144,149 | Sì → Q4_K (rischio ALTO) |
| **Shared-expert** (sempre-attivo) | expert su ogni token, salta il router | Q8_0 | (parte dei 7.64) | HANDOFF_7:149 | Sì → Q4_K |
| **HC / Compressor / Indexer** (blocchi DwarfStar) | compressione proprietaria V4; la quota F16 più pesante | **F16** | dominante dei 2.19 F16 | HANDOFF_7:149 | Sì → Q4_K (grosso del delta) |
| **Embedding + LM head + dense** | token embed, proiezione vocab 129280 | Q8_0 / token_embd F16 (assert!) | token_embd ~1.06GB F16 | ds4.c:3566 (F16 assert) | token_embd host-side → NON libera device |
| **Router** (ffn_gate_inp + exp_probs_b) | gate → logit per-expert; exp_probs_b = leva bias-mask REAP | F16/F32 | ~90 MiB su 43 layer | REAP_DS4_design:34-36 | **NO** (già minuscolo) |
| **KV cache** (ctx 6144) | cache K/V del contesto | attivazioni | ~151MB @6144 **(da misurare)** | HANDOFF_2:53 | indiretta |
| **Statics MTP** (ds4-mtp.gguf) | mini-transformer, solo sotto --mtp/spec-dec | misto | file 3.55GiB su disco; **device reale ~0.34GiB** | runs/dspark/…m8_* | NON è backbone (opzionale) |
| — Expert instradati (256/layer, 6 attivi) — NON backbone | streammati da SSD, cache LRU | IQ2_XXS+Q2_K | 6.75 MiB/exp; 72.56 GiB NON in VRAM | REAP_DS4_design:31-38 | — (bersaglio, non leva) |

**Blocco statico reale = 7.64 GB** (Q8_0 5.45 + F16 2.19). I doc dicono "~10GB" (PAPER_DRAFT:114) o "8.2GB"
(BRIEF_REAP:10) → arrotondati per eccesso.

**Il gate che trasforma i GB in velocità (o niente):** `ds4_cuda.cu:1591` reserve default 16GB → clamp `total/2`=6GiB
(:1643) → se `free_bytes <= reserve` **cache DISABILITATA** (:1646) → altrimenti `slots=(free-reserve)/6.75MiB` (:1658).
Su 12GB con backbone 7.64GB la libera (~5.9GiB) è SOTTO i 6GiB reserve → **cache a 0 slot di default**. Ecco perché
serve `--prefill-chunk 512` (HANDOFF_7:116). **Liberare VRAM dal backbone è l'UNICA leva strutturale.**

## Candidati di limatura — verificati avversarialmente
| Leva | Verdetto | GB reali device | Fattibilità | Rischio | Dove si tocca |
|---|---|---|---|---|---|
| **static-Q4 backbone** | **PROMISING** | **~3.5** (7.64→3.50, meno token_embd ~0.30 host) | Gguf GIÀ costruito (82GB, 1328 tensori). Nessuna patch. **Ma: carica? vedi assert F16** | **ALTO, non misurato**: attn→Q4_K si somma al -20pt coding 2-bit; zero eval_gold | build offline deepseek4-quantize (HANDOFF_7:138-146); runtime auto ds4_cuda.cu:1658 |
| **REAP bias-mask K50/K67** | **SOLID** (ma altro asse) | ~0 sul backbone | fatto | basso | libera **RAM/disco** (72.56GiB expert), non VRAM device. Utile per la % in RAM, non per la cache |
| **cap context length** (6144→4096) | **MARGINAL** | ~0.75 (32768→4096; da 6144 molto meno) | runtime | perde contesto | kv_cache_init ds4.c:8491-8516 |
| **quant token_embd/LM head → Q6/Q5** | **REFUTED** | tetto ~0.9 ma bloccato | token_embd F16 OBBLIGATA (assert ds4.c:3566) | — | non fattibile senza toccare l'assert |
| **reserve-tuning** (6→1) | **REFUTED** (per limatura) | 0 di backbone | fatto | nessuno | sblocca cache che non accelera nel regime testato = VRAM-utile 0 |
| **patch 0011 MTP-host** | **REFUTED** | **~0.34** (non 3.5-3.9; il "3.55GiB" è mmap HOST, errore di categoria) | fatto | nessuno | ds4.c:26605-26630; non risolve M8, spec-dec resta più lento |

---

## Syllabus (6 moduli, ordine pedagogico)
Vive nella chat-tutor aperta a parte; sintesi dei check pratici:
- **M0** residente-vs-streammato → leggi `REAP_DS4_design.md:31-38` (6.75 MiB/expert).
- **M1** anatomia → `ls -la /root/models/*.gguf` (i 3 file che incarnano il corso).
- **M2** il gate cache → `ds4_cuda.cu:1641-1667` riga per riga (le 26 righe che spiegano tutto).
- **M3** static-Q4 → `HANDOFF_7:138-146` (i flag `--attention q4_k` decidono cosa scende).
- **M4** il rischio → `HANDOFF_7:167-170` (baseline eval_gold: MATH 100 / KNOWLEDGE 85 / CODING 55 che static-Q4 deve pareggiare).
- **M5** le finte-leve → la riga "cache disabled" in `runs/dspark/20260706_night_validation_m8/out/eval_on.log`.
- **M6** decisione → `HANDOFF_7:188-194` (roadmap: static-Q4 test PRIMA del temperature-per-expert).

## Prossimo passo obbligato (HANDOFF_7:189)
Caricare `ds4-staticQ4.gguf` sul 3060 col comando server + env leva-RAM e **misurare due cose**: (1) **carica?** (assert
F16 su token_embd) → risolve la storia "fallito/twin"; (2) se sì, **t/s** (cache più grande?) e **qualità** (eval_gold:
l'attention-Q4 rompe il task Segnali?). Solo allora il ~3.5GB diventa un win adottabile.
