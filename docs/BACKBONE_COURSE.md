# Backbone di ds4 — corso accelerato + anatomia VRAM + limatura (verificata)

> Output di un workflow multi-agente (3 grounding sul sorgente ds4 vero + 11 verifiche avversariali di candidati +
> sintesi, 2026-07-06, `wfx2rkunv`, 16 agenti). Ogni numero = byte-count reale dai gguf su /root/models o log
> on-device; ciò che non è verificato è marcato **(da misurare)**. Un verificatore su 16 è fallito (retry cap) —
> il suo candidato (cap della Q8→F16 device-cache) resta non concluso.

## Verdetto in una riga (⚠️ CORRETTO 2026-07-06 — era "PROMISING", è REFUTED)
**`static-Q4` sul backbone è CHIUSO: il backbone residente NON è limabile a Q4_K su questo motore.** Verificato con tre
fonti convergenti — sorgente (letto), misura gguf fresca, e la memoria del 04-07 (`project_ds4_realtest_inflight.md:23`).
`weights_validate_layout` (chiamata al load, ds4.c:4105) inchioda TUTTO il non-expert a Q8_0/F16/F32 con `exit(1)` sul
primo mismatch di tipo (ds4.c:3144-3151); l'unico tensore libero è il routed-expert (ds4.c:3626-3628). Esito a due facce,
**entrambe misurate**:
- `/root/models/ds4-staticQ4.gguf` (82GB, backbone Q4_K reale su 704 tensori) → **NON carica** (`token_embd` Q4_K vs pin F16 a ds4.c:3566 → `exit(1)`).
- `D:\models\ds4\ds4-staticQ4.gguf` (86.72GB, "riparato" 04-07) → **carica ma è un GEMELLO del 2-bit** (istogramma dtype identico, backbone F16/Q8_0, zero Q4_K; Δ 288 byte) → **0 GB device liberati**.
Non esiste una versione che *insieme* carichi E rimpicciolisca il backbone. Le leve storiche patch 0011 MTP-host e
reserve-tuning restano **REFUTED**.

## ✅ Dubbio-gating RISOLTO (2026-07-06) — non era aperto
Il "dubbio" sul caricamento era **già chiuso il 04-07**; la rilettura sorgente + misura fresca lo conferma:
- La `staticQ4.gguf` 82GB ha **token_embd = Q4_K** (misurato) → collide col pin F16 (ds4.c:3566) → `exit(1)`. Non carica.
- Non è "704 tensori falliti misteriosi": il quantizzatore ha **onorato** tutti i flag (`--attention/-shared/-embedding/-output q4_k`) → istogramma staticQ4 = **704 Q4_K** = esattamente i 359 F16 + 345 Q8_0 del 2-bit. È un Q4-backbone genuino, e per questo NON passa il validatore.
- La versione **riparata** (trapianto dei 704 tensori dal 2-bit buono, 04-07) è su `D:\models\ds4\ds4-staticQ4.gguf` (86.72GB), **carica**, ma ha il backbone di nuovo F16/Q8_0 → gemello del 2-bit, **0 GB liberati**.
La vecchia frase "nessun artefatto sostiene il fallimento" era un buco di questo doc, non della realtà: gli artefatti
erano nella memoria 04-07 e sul disco D:. Il backbone reale resta **7.64GB** (Q8_0 5.45 + F16 2.19), non limabile via
quant su questo engine.

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
| **static-Q4 backbone** | **REFUTED** (verificato 07-06, misura+sorgente) | **0** (motore-bloccato) | Impossibile su questo engine: `weights_validate_layout` pinna il backbone a Q8_0/F16 (ds4.c:3566,3577,3592-3599,3633-3635) → il Q4_K fa `exit(1)` al load; il file "riparato" è un gemello del 2-bit | — | servirebbe patch al validatore **+ kernel CUDA Q4_K per MLA/HC/compressor/indexer** (non verificati esistere); e comunque nutrirebbe un device-cache dal beneficio non dimostrato |
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

## Prossimo passo (aggiornato 2026-07-06 — l'ex "passo obbligato" è OBSOLETO)
Il vecchio "carica staticQ4 e misura" è **superato**: sappiamo già che non carica (82GB) o è un gemello (86.72GB). E
l'anello a monte — *un device-cache più grande alza i t/s?* — **è GIÀ MISURATO** (`runs/ds4_bench_clean_ext4_20260705/`,
verificato dai log): cache 31→~700 slot, **hit-rate 0%→44%**, ma **generation t/s 0.18→0.15 = PIATTO** (dentro il rumore).
Nel regime **28GB cold/SSD-bound** il collo è la **coda SSD**, non le copie H2D → il device-cache è irrilevante e
ingrandirlo liberando VRAM dal backbone sarebbe moot. La limatura vera è sull'asse **RAM** (leva-RAM 4.3× + REAP bias-mask
−72.6GiB + 64GB in arrivo). **Unico anello ancora aperto:** il device-cache *si accende* nel regime **64GB-warm**
(working-set in RAM, coda SSD sparita, l'H2D diventa il gate)? Da misurare **solo sul 3060** quando arriva il kit RAM —
**NON su pod** (t/s non trasferibili, POD_PLAYBOOK §4.3; una 3090 ha troppa RAM → regime sbagliato).
