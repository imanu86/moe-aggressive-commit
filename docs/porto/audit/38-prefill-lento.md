# 38 — PREFILL LENTO: il raggruppamento per esperto ESISTE e funziona; a ub 64 ammortizza solo ×1,9, e il prefill resta un decode che ha perso il grasso ma non i byte

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, working tree con
fusione HC. **Nessuna compilazione, nessun server avviato, nessuna misura nuova**:
codice letto riga per riga, log già in cassa (`D:\ds4_work\llama_run\kvd_B.server.log`
come corsa di riferimento, più `curve-ub*` e i 37 rapporti in `D:\llama-overlap\audit\`).
Marcatura: [MISURATO] = log/file, [CONTATO] = codice letto, [DEDOTTO] = aritmetica su
misure, [IPOTESI] = da falsificare con la misura indicata.

**Esito in tre righe.**
(1) La tua ipotesi meccanica è FALSA: il prefill raggruppa le posizioni per esperto
(sort+compattazione in `mmq.cu`, esperti vuoti saltati PRIMA di leggere i pesi) e ogni
esperto usato viene letto UNA volta per chiamata. Ma l'economia della tua ipotesi è
GIUSTA: a ub 64 i 384 estratti (64×6) cadono su ~130-205 esperti distinti per strato,
quindi ogni lettura serve **~1,9 posizioni invece di 64** — l'ammortamento è il
rapporto 6·ub/unione(ub), e a ub 64 vale 1,9.
(2) Il libro mastro chiude: dei 44,27 ms/token, **~37-40 ms sono trasporto PCIe
zero-copy dei pesi esperti** (81-90%), il resto sono densi in VRAM (~0,6-1), attenzione
(~1-1,5), compressione+quantize+lanci (~1-2,5). Il prompt da 6.510 token rilegge la
massa esperti (72,6 GiB) **~50-80 volte**. Per token, il prefill muove sul PCIe circa
gli STESSI byte del decode (~0,6-0,9 GiB contro ~0,65): il fattore due — e non cento —
è tutto qui.
(3) La leva è UNA e non costa una riga di codice: **alzare `-ub`**. L'unione satura a
256 esperti/strato, quindi i byte per ubatch hanno un TETTO (74.304 MiB = tutta la
massa, una volta) e il costo per token scende ~∝ 1/ub. Atteso: ub 256 → **40-62 t/s**
(×1,8-2,7), ub 512 → **55-90 t/s** (×2,4-4,0). Il compute buffer a ub 64 è 104 MiB con
1.225 MiB liberi: lo spazio c'è. Cancello a ub 128: **≥ 29 t/s**, sotto 26 il modello
è rotto e si misura l'unione prima di proseguire.

---

## 0. La corsa di riferimento e la configurazione VERIFICATA [MISURATO]

`D:\ds4_work\llama_run\kvd_B.server.log` (10/8, binario build 82 `0adb16c64`, fusione
HC attiva — righe 232-233):

    prompt 6.510 tk @ ctx 10.240:  288.223,51 ms → 44,27 ms/token → 22,59 t/s   (riga 593)
    decode stesso contesto:        93,86 ms/token → 10,65 t/s                    (riga 594)
    velocità piatta sul prompt: 23,04 / 21,62 / 22,58 / 22,58 / 22,61 t/s        (righe 502-576)
    target: n_ubatch 64, n_batch 2048 (righe 164-165); bozza: n_ubatch 16 (riga 390)
    CUDA0 densi 7.383,67 MiB | CUDA0_Mapped esperti 74.304,00 MiB "zero-copy, UVA SI" (152-157)
    compute buffer CUDA0 = 104,04 MiB (poi 112,97) | grafo bs=64: 11.195 nodi, 5 split
    grafo bs=1: 11.711 nodi, 45 split | VRAM libera: 3.715 MiB dopo il target,
    1.225 MiB dopo la bozza (righe 234-239, 462-465, 422)

Tre fatti di configurazione che i contatori stessi dimostrano:

- **La cache esperti NON tocca il prefill**: i dump a progresso 0,31 / 0,63 / 0,94
  mostrano contatori CONGELATI a `domanda 860, byte 2,33 GiB` (righe 470→505→540→551),
  cioè il valore del warmup. Zero traffico cache per tutto il prompt.
- **La lane CPU (K) NON tocca il prefill**: 5 split a bs=64 contro 45 a bs=1; la
  guardia è `n_tokens > LLAMA_OVERLAP_BATCH_MAX` (default 1) in
  `D:\llama-overlap\src\llama-graph.cpp:1847-1856` → a ub 64 `build_moe_ffn_overlap`
  ritorna `nullptr` e si va sul percorso classico.
- **La bozza NON lavora nel prefill**: `#calls(b)=1, dur(b)=0,386 ms` (riga 600); e le
  quattro corse `curve-ub{2,8,16,64}-long` — che variavano l'ubatch DELLA BOZZA, non
  del target (vedi §7) — danno prefill identico 21,07-21,34 t/s: il prefill è
  insensibile alla configurazione della bozza.

---

## 1. La domanda del mandato: come vengono raggruppate le posizioni per esperto [CONTATO]

Catena a ub 64 (`ne2 = 64 > 8 = get_mmvq_mmid_max_batch`), tutta letta:

1. **Dispatch** `D:\llama-overlap\ggml\src\ggml-cuda\ggml-cuda.cu:2360-2362`:
   `ggml_cuda_should_use_mmq(IQ2_XXS, cc=86, 64, 256)` → vero su Ampere
   (`turing_mma_available` → `return true`, `mmq.cu:307-309`; IQ2_XXS e Q2_K in lista
   a 288/283) → `ggml_cuda_mul_mat_q` con `ids`. Il ripiego catastrofico con sort su
   host e `cudaStreamSynchronize` per chiamata (righe 2371-2485) **non viene mai
   preso** per i nostri formati.
2. **Raggruppamento** `D:\llama-overlap\ggml\src\ggml-cuda\mmq.cu:172-184`:
   `ggml_cuda_launch_mm_ids_helper` costruisce `ids_src1`, `ids_dst` e
   `expert_bounds[257]` — le coppie (token, esperto) COMPATTATE per esperto, su
   device, senza sincronizzazioni. Poi la quantize q8_1 raccoglie le righe già
   ordinate (righe 194-207) e il kernel riceve `ne02 = 256` come dimensione z della
   griglia (righe 214-220).
3. **Esperti vuoti saltati PRIMA dei pesi**
   `D:\llama-overlap\ggml\src\ggml-cuda\mmq.cuh:3670-3686` (ramo stream-k, il nostro):
   `col_diff = expert_bounds[zt+1] - expert_bounds[zt]`; se il tile di colonne è oltre
   `col_diff`, `kbc += blocks_per_ne00; continue;` — il salto avviene prima di
   qualunque `load_tiles` di `x`. **I 256−U esperti non usati non costano byte.**
4. **Ogni esperto usato è letto UNA volta per chiamata**: i token per esperto sono in
   media 384/U ≈ 1,9 (max ~8-10), sempre dentro UN tile di colonne (mmq_x ≥ 8):
   nessuna rilettura dei pesi dentro la chiamata. Tre chiamate per strato
   (gate, up, down) = l'esperto intero, 6,75 MiB.

**Verdetto**: il meccanismo è quello giusto — è il MICRO-BATCH che è troppo piccolo
per un MoE a 256 esperti. L'ammortamento delle letture è

    A(ub) = (6·ub) / U(ub),   U(ub) = esperti distinti per strato nell'ubatch

e con routing quasi uniforme (nessun nucleo caldo — verdetto di casa):
U(2)=11,9 · U(8)=44,9 · U(16)=82,9 · **U(64)≈202** · U(128)≈245 · U(256)≈255 ·
U(512)≈256 [DEDOTTO, binomiale; il reale sta sotto per la località 39,7% a distanza 1,
stima U(64) ∈ 130-205]. Quindi:

    A(64) ≈ 1,9   |   A(128) ≈ 3,1   |   A(256) ≈ 6   |   A(512) ≈ 12   |   A(4096) ≈ 96

**Il "fattore cento" vive a ub ≈ 4.000. A ub 64 il batching compra un fattore 1,9 — ed
è esattamente il fattore due che misuri.**

---

## 2. Il libro mastro dei 44,27 ms/token

Per ubatch da 64 token (2.833 ms misurati):

| voce | per ubatch | per token | fonte |
|---|---|---|---|
| **esperti via PCIe zero-copy**: 43 strati × U × 6,75 MiB = 36,8-58,1 GiB | 2.360-2.600 ms | **36-41 ms** | [CONTATO §1 + DEDOTTO: chiude col misurato per (U, banda_eff) ∈ (130, ~15) ÷ (205, ~22,5 GiB/s) — vedi §5] |
| densi in VRAM, 7.383 MiB letti 1×/ubatch a 200-250 GB/s + compute q8_0 | 31-45 ms | 0,6-1,0 | [DEDOTTO, PAVIMENTO §2a] |
| attenzione (fattn mma, 2.688 celle CSA+raw; indexer+top-k ×21) | 55-90 ms | 0,9-1,5 | [DEDOTTO, flops] |
| chiusure CSA/LID/HCA + ring store + quantize q8_1 + mm_ids_helper | 20-60 ms | 0,3-1,0 | [DEDOTTO; grafo bs=64 = 11.195 nodi ≈ bs=1 → chiusure BATCHED, audit 30] |
| sottomissione WDDM (11.195 nodi, niente CUDA graph a bs>1) | 35-90 nominali, quasi tutti sovrapposti | 0,3-0,8 | [DEDOTTO da 95,5 ms/12-19k lanci; duty CPU ~2-3%] |
| bozza / speculativa | 0,4 ms totali sul prompt | ~0 | [MISURATO riga 600] |
| **somma** | | **38-45** | chiude su 44,27 ±10% |

Due controprove indipendenti:

- **La fusione HC non ha mosso il prefill**: −23.822 nodi e −13,1 ms/token sul decode
  (audit 30 §0b), ma il prefill è passato da ~21,2 (curve dell'8/8, pre-fusione) a
  22,6 t/s — ~1-2 ms/token, confronto fra giorni e prompt diversi [DEDOTTO, debole].
  Se il prefill fosse lanci-bound, 24k nodi in meno si sarebbero visti.
- **Insensibile a tutto ciò che non è trasporto**: piatta sul progresso (l'attenzione
  cresce col contesto e non si vede → è piccola), insensibile alla bozza (§0).

**Il confronto che spiega il titolo** [DEDOTTO dai contatori]: nel decode il PCIe
muove `buchi × 6,75 MiB` ≈ 660-780 MiB/token (miss ~57% a 6,5k, righe 580-588: 100
buchi/token nella finestra di decode osservata). Nel prefill muove 43·U·6,75/64 ≈
**590-930 MiB/token**. STESSI byte, stessa pipe da ~20 GiB/s. La differenza fra 93,9
e 44,3 ms/token è che il prefill ha già eliminato i costi NON di trasporto (67 ms di
MMVQ residente, HC, bozza, orchestrazione → 4-6 ms), non che muova meno byte. E c'è
una simmetria beffarda: la cache VRAM del decode (43-58% colpi) e il raggruppamento a
ub 64 (A=1,9) comprano ENTRAMBI lo stesso ×~2 di byte — per questo il rapporto è
esattamente ~2.

---

## 3. Le altre piste del mandato, una per una

- **"la cache esperti nel prefill è accesa o spenta?"** Spenta per cancello:
  `ids->ne[0]*ids->ne[1] <= 64 && ids->ne[1] <= 8` (`ggml-cuda.cu:2195-2197`); a
  ub 64 gli id sono 384. Che succede allora: MMQ legge la RAM mappata via UVA
  (`cudaHostAlloc(cudaHostAllocMapped)`, `ggml-cuda.cu:1356-1367`; il buffer si
  spaccia per CUDA condividendo `get_name`, commento di progetto a 1415-1427).
  Costo del bypass: TUTTO il trasporto di §2. Ammetterla sarebbe peggio: U per ubatch
  ≈ 130-205 × 43 strati su 339 slot = churn puro (misurato il 6/8: 9,2 → 6,47 t/s con
  colpi SALITI — commento storico a 2163-2175). La semina (`patch_seed_prefill.diff`)
  resta anti-economica: RACCOLTA lavoro 2.
- **"il ramo CPU dell'overlap nel prefill?"** Strutturalmente fuori (guardia batch_max
  1, §0). Nessun esperto va alla CPU negli ubatch da 64. (In decode la lane K=2 c'è
  ed è visibile nella firma dei contatori: ~172 domande/token, il ~(k_gpu/6)·258
  previsto dal commento `llama-graph.cpp:1879-1882`.)
- **"la compressione DSV4 quanto aggiunge?"** Quasi niente: le chiusure sono BATCHED
  nel grafo dell'ubatch (11.195 nodi a bs=64 contro 11.711 a bs=1 → **175 nodi/token
  contro 11.711**); il lavoro per token delle chiusure è invariante in ub e piccolo
  (compressori f16 in VRAM). Nota per la leva di §6: a ub ≥ 256 arrivano PIÙ chiusure
  HCA per ubatch (oggi max 1 ogni 2 ubatch) — mai esercitato, va nel cancello.
- **"GGML_OP_OFFLOAD_MIN_BATCH=32"**: per il TARGET non decide nulla nel prefill — i
  suoi esperti stanno in un buffer che si dichiara CUDA, quindi le op sono già
  assegnate alla GPU; `offload_op` (`ggml-cuda.cu:5928-5932`) è il pezzo del disegno
  "ibrido" (batch ≥ 32 → GPU) e riguarda i pesi in buffer CPU — cioè la bozza, che nel
  prefill non lavora. La riga 6 di audit 31 va letta così.
- **"quanti byte per micro-batch, quante riletture?"** 36,8-58,1 GiB per ubatch;
  ogni esperto ricompare in ~U/256 dei 102 ubatch → riletto **~52-82 volte** nel
  prompt. Totale prompt ≈ 3,7-5,8 TiB contro 72,6 GiB di massa: **×52-82**.

---

## 4. Quanto DOVREBBE andare: l'aritmetica richiesta

Con 6.510 token, 258 attivazioni/token (6 × 43 strati), esperto 6,75 MiB, ~25 GB/s:

| scenario | byte totali | tempo | t/s |
|---|---|---|---|
| nessun raggruppamento (decode ripetuto, 0 colpi) | 6.510 × 258 × 6,75 MiB = **10,8 TiB** | ~476 s | 13,7 |
| raggruppato per ubatch da 64 (il codice OGGI) | 43 × Σ U(ubatch) × 6,75 ≈ **3,7-5,8 TiB** | ~255 s di trasporto + fisso | **misurato 288 s / 22,6** ✓ |
| ubatch 512 (unione satura: tutta la massa 1×/ubatch) | 13 × 74.304 MiB ≈ **0,92 TiB** | ~45-55 s + fisso | 70-100 |
| ogni esperto letto UNA volta per prompt | **72,6 GiB** | ~3,1 s | (trasporto) |
| pavimento di CALCOLO della 3060 (esperti 84,5 + densi 96 + attn ≈ 190 TFLOP a 12-20 TOPS eff) | — | ~10-16 s | **400-650** |

**Non è intrinseco all'hardware**: la macchina ha un tetto di ~400-650 t/s di
prefill; ne facciamo 22,6 perché a ub 64 paghiamo 4,7-6 TiB di PCIe per un lavoro che
ne richiede 0,07. Il fattore mancante è interamente A(ub).

---

## 5. Ciò che il misurato NON separa: unione × banda [DEDOTTO]

Il trasporto misurato (~39 ms/token) fissa solo il PRODOTTO: U(64)/banda_eff ≈ 8,6
(esperti per GiB/s). Coppie compatibili: (U=205, 22,5 GiB/s), (U=170, 19), (U=130,
15). Le due letture divergono sulla leva secondaria:

- U ≈ 200 (routing ~uniforme) → la pipe zero-copy va già a ~22 GiB/s, vicino al tetto
  pratico: la SOLA leva è ub.
- U ≈ 130-150 (località reale) → la pipe effettiva fa 15-17 GiB/s: il pattern di load
  di MMQ su memoria mappata spreca transazioni PCIe, e una **staged-copy** (memcpy
  asincrona della sola unione in uno staging VRAM + MMQ da VRAM) varrebbe fino a
  ×1,5 DA SOLA, cumulabile con ub.

La separazione costa una sonda da ~10 righe (§8.2), in CONTATORI e non in ms.

---

## 6. LA LEVA: alzare `-ub`. Intervalli, costi, cancelli

**Perché è robusta**: i byte per ubatch hanno un tetto per costruzione —
43 × 256 × 6,75 MiB = 74.304 MiB, tutta la massa una volta — qualunque sia il routing.
Quindi trasporto/token ≤ 74.304 MiB / (banda × ub): il termine dominante scala ~1/ub
finché U non satura, e DOPO la saturazione scala esattamente 1/ub.

| braccio | atteso [intervallo, non un punto] | VRAM compute buffer (oggi 104 MiB @64, ~∝ ub) | costo |
|---|---|---|---|
| `-ub 128` | 26-37 t/s (+15-65%; l'estremo basso È l'angolo banda-15) | ~210 MiB ✓ | una corsa |
| `-ub 256` | **40-62 t/s (×1,8-2,7)** | ~420 MiB su 1.225 liberi ✓ | una corsa |
| `-ub 512` | 55-90 t/s (×2,4-4,0) | ~830 MiB — stretto; se OOM: `LLAMA_CACHE_ESPERTI_SLOT` 339→~250 per il braccio | una corsa |
| oltre | rendimenti calanti (resta il fisso ~4-6 ms + attn) | | |

`-b 2048` copre già ub fino a 2048; `-np 1` invariato; niente ricompilazione.

**Cancelli che la falsificano** (scritti PRIMA, in contatori dove possibile):

1. **Il cancello vero è a ub 256, non a 128**: il tetto di saturazione (74.304 MiB
   per ubatch, qualunque routing) dà un PAVIMENTO di ~40 t/s anche nell'angolo
   pessimistico (banda 15 GiB/s). ub 256 < **35 t/s** → il modello è rotto: fermarsi,
   sonda U (§8.2) e nsys su UN ubatch. ub 128 da solo NON discrimina: nell'angolo
   banda-bassa può dare +15-20% — ed è esattamente il "+18%" del ledger 6/8, che
   quindi non contraddice il modello: semmai indica banda zero-copy degradata, cioè
   la leva staged-copy di §5.
2. Correttezza (è la parte fork-specifica, non llama.cpp): a ub ≥ 256 le chiusure HCA
   diventano ≥ 2 per ubatch, mai esercitato. Cancello: `LLAMA_DSV4_COMPRESS_DEBUG=1`
   → chiusure contate = n_tokens/4 (CSA) e n_tokens/128 (HCA) ESATTE; accettazione
   0,86 e p1 invariati contro ub 64; `divergenze replay = 0`.
3. Lo SHA della generazione con ub diverso PUÒ divergere legittimamente (ordine delle
   somme nel prefill): il cancello SHA non si applica fra ub diversi — dichiararlo nel
   ledger, non inseguirlo (regola di casa: cancello-sha-quando-vale).
4. La velocità deve restare PIATTA sul progresso anche a ub 512 (se compare una rampa,
   è l'attenzione che emerge: informativo, non bloccante).

**A 105k** l'aritmetica cambia: il collo di memoria non è il compute degli esperti ma
i punteggi dell'indexer (~26.214 celle × 64 teste × ub × 4 B ≈ **6,7 MiB × ub** per
strato CSA): ub 64 ci sta (~430 MiB), ub 256 no (1,7 GiB) senza liberare la slab della
cache (2,3 GiB) per il solo passo di prefill. Con slab liberata: ub 384-512 → 105k in
~25-40 min invece di 82. La cura vera resta doppia: **slot save/restore** (audit 31
riga 1: il prefill si paga UNA volta) e, come cantiere, il tiling dei punteggi
dell'indexer per spezzare il legame ub×contesto.

---

## 7. Correzioni di provenienza (tre trappole trovate stanotte)

1. **`curve-ub{2,8,16,64}-*` NON sono una spazzata di ub del target**: il target è
   sempre a `n_ubatch=64`; a variare è la SECONDA `llama_context` (la bozza) — righe
   164-165 contro 381-382 dei rispettivi `.stderr.log`. Il nome inganna. (Bonus: la
   piattezza 21,07-21,34 t/s su bozza-ub 2→64 è la prova che la bozza non tocca il
   prefill.)
2. **Il "+18% con -np 1 -ub 128" del ledger** (resume 6/8) non documenta il baseline
   (np? ub? cache? contesto?): non usarlo per tarare la leva di §6 — la spazzata nuova
   lo sostituisce. Se il baseline era ub 64, il +18% cade nell'angolo banda-bassa del
   modello (§6 cancello 1) ed è un indizio PRO staged-copy, non contro la leva ub.
3. **I contatori a cavallo del confine prompt→decode mentono**: il dump dopo
   `init_sampler` (righe 579-589: domanda 13.284, 49,96 GiB) NON è prefill — è il
   warmup (860) più i primi ~72 token di decode, riconoscibili dalla firma della lane
   K=2 (172 domande/token) e dal miss 58%. Ci sono cascato per un'ora scrivendo questo
   rapporto; i dump DENTRO il prompt (congelati a 860) sono quelli che dicono la
   verità. È la trappola già a verbale il 9/8, in versione nuova.

---

## 8. Dati che si ottengono SOLO eseguendo (in ordine di resa, con cosa decidono)

1. **Spazzata `-ub 64/128/256/512`** (una corsa l'una, prompt ≥ 4k, stesso contenuto):
   decide la leva principale e, gratis, la forma di U(ub) via fit del modello
   `t = C + 43·U(ub)·6,75 MiB/(banda·ub)`. Predizioni a verbale: §6. Se ub 512 regge
   l'intervallo, il fronte "prefill 10-100×" si chiude a metà strada senza una riga di
   codice.
2. **Sonda U** (~10 righe env-gated in `mmq.cu` dopo `mm_ids_helper`: copia di
   `expert_bounds[257]` a host 1 chiamata su 1000, conteggio dei gap non vuoti).
   Predizione: U(64) ∈ 130-205. Decide la ripartizione unione/banda di §5 → se
   banda_eff < 17 GiB/s, apre la leva staged-copy (×1,3-1,5 aggiuntivo, patch media).
3. **`GGML_SCHED_DEBUG=2` su UN ubatch di prefill** (gratis): identità dei 5 split a
   bs=64 [oggi IPOTESI: embedding su host + testa/coda] e conferma che nessuna op MoE
   finisce sulla CPU.
4. **nsys su 3-4 ubatch** (M1 di PAVIMENTO, mai eseguita): quota vera del kernel MMQ
   contro i buchi di sottomissione; serve SOLO se il cancello 1 fallisce.
5. **Braccio `-fa off` a ub grande** (audit 31 riga 2): prezzo/beneficio della FA nel
   prefill quando l'attenzione smette di essere l'1% — informativo per il fronte 105k.
6. **A 105k**: `llama-fit-params`/una reserve con ub 256 e slab ridotta, per verificare
   l'aritmetica dell'indexer di §6 prima di investire nel tiling.

## 9. Sintesi in tre righe

Il prefill non è rotto: è un decode con gli stessi byte e meno grasso. A ub 64 ogni
lettura d'esperto serve 1,9 posizioni (6·64 estratti su ~130-205 esperti distinti per
strato), il prompt rilegge 72,6 GiB di esperti ~75-80 volte via PCIe zero-copy, e
37-40 dei 44,27 ms/token sono quel trasporto. Il raggruppamento per esperto nel kernel
c'è ed è fatto bene (compattazione + salto degli esperti vuoti prima dei pesi): la
leva non è scriverlo, è dargli un batch su cui ammortizzare — `-ub 256/512` vale
×1,8-4 con una corsa per punto e un cancello-pavimento a 35-40 t/s su ub 256; il
fattore cento vive a ub ~4.000, cioè fuori da questa VRAM: quello si compra solo con
la persistenza dello stato (slot save/restore), che è già a verbale.
