# 41 — I 5,8 ms/token del prefill: il libro mastro chiude a metà, la "costante" C non è costante (pendenza misurata +0,10÷0,15 ms ogni 1.000 token di contesto), e il non-spiegato ha due soli indiziati che una corsa di profilo separa

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, build dei log: 82
(`0adb16c64`), fusione HC attiva. **Nessuna compilazione, nessun server avviato,
nessuna misura nuova**: log già in cassa (`D:\ds4_work\llama_run\ub{064,128,256,512}.server.log`,
`kvd_A`, `kvd_B`) e codice letto. Rapporti a monte: 38, 40, 30 (+31 per la FA).
Marcatura: [MISURATO] = log; [CONTATO] = codice letto; [DEDOTTO] = aritmetica su
misure; [IPOTESI] = da falsificare con la misura indicata.

**Esito in quattro righe.**
(1) **C non è costante nel contesto**: dentro le corse a ub 512 la pendenza è
+0,10÷0,15 ms/token ogni 1.000 token di contesto [MISURATO, §2] — a ≤10k è
un +1÷3% e **il piano del follow-up da 10.000 token sta in piedi**; a 105k il
termine C **raddoppia o triplica** e la legge va riscritta (§2c).
(2) Il fit non poteva vederlo per costruzione: i quattro punti della spazzata usano
lo STESSO prompt, quindi qualunque dipendenza dal contesto si somma uguale in tutti
e finisce dentro C. La risposta stava nei **timestamp dei segmenti dentro ogni
corsa**, non fra le corse.
(3) Il libro mastro di C = 5,5±0,3 (rifinito, §1): **GEMM densi 1,5-2,4** (il
calcolo delle proiezioni MLA, non i loro byte), **attenzione 0,5-1,0** (di cui la
parte che cresce), **chiusure DSV4 0,2-0,5**, spiccioli ≤0,3. Somma dura:
**2,5-4,2**. Il resto — **1,5-3,0 ms, il 30-50%** — sta in UNO di due posti:
la coda di calcolo MoE non nascosta sotto il PCIe, o i GEMM densi sotto il
calibrato. Un profilo per-kernel di 2-3 ubatch li separa (§5.1).
(4) I lanci sono esclusi con un contatore (21,9 nodi/token a ub 512 → ≤0,05 ms), i
byte densi stanno in K come previsto, e la piatta-sul-progresso di audit 38 era
vera solo perché a ub 64 il trasporto (39 ms) seppelliva la rampa (0,3-0,8).

---

## 0. Da dove vengono i numeri: i segmenti coi timestamp [MISURATO]

I log del server marcano ogni confine di chunk (`cached n_tokens = X`) con
timestamp a microsecondo. Il prompt da 6.510 token viene processato in chunk:
1 token (checkpoint), poi 2048, 2048, …, e la coda è sempre `ub+4` (i 4 sono il
margine di rollback dell'anello). Dentro ogni chunk, ubatch pieni da `ub`.
Questo dà **tempi per segmento** dentro ogni corsa, a contesto crescente, con la
stessa configurazione — lo strumento che il fit non aveva.

Riproducibilità dello strumento: `ub064` e `kvd_A` sono due corse identiche
(stesso prompt, stesso binario, ub 64) fatte a un'ora di distanza. Segmenti:

    S1 (tk 1-2049)     ub064 88,490 s   kvd_A 88,457 s   (0,04%)
    S2 (tk 2049-4097)  ub064 100,595    kvd_A 100,599    (0,004%)
    S3 (tk 4097-6145)  ub064 82,629     kvd_A 82,604     (0,03%)

**Il rumore per segmento è ≤0,05%**: tutto ciò che segue e supera lo 0,1% è
struttura, non rumore.

### 0a. C rifinito con l'inventario vero delle passate

La corsa ub 512 non fa 13 passate: ne fa **15** (13 piene + la passata da 1 token
del checkpoint + la coda da 4). Le due piccole hanno K piccolo (unione non satura:
K(1)≈0,09 s, K(4)≈0,37 s [DEDOTTO, binomiale]). Rifacendo il conto:

    C = (89,273 − 13·4,045 − 0,092 − 0,374) / 6.510 = 5,56 ms/token   (banda 18,4)
    C = 5,36 ms/token                                                  (banda 17,5)

e l'angolo banda-17,5 esiste perché il fit assume U(256)=U(512): se a ub 256
l'unione reale è ~250 invece di 255 (località), K sale a ~4,15 e C scende.
**C ∈ [5,4; 5,8]; centrale 5,5.** Il 5,8 del mandato è l'angolo alto del fit a due
punti. Niente di quanto segue cambia fra i due angoli.

---

## 1. IL LIBRO MASTRO: di cosa sono fatti i ~5,5 ms/token

Prima la riattribuzione che rimette in ordine le piste del mandato: nel prefill i
**byte** dei pesi densi (7.383,67 MiB in VRAM) si leggono **una volta per
passata** — 14,4 MiB/token a ub 512, ~0,06 ms, dentro K e invisibili accanto ai
4.045 ms del trasporto esperti. Quello che sta in C è il loro **calcolo**, che è
per token. Il modello a due parametri non aveva niente che non tornasse: la voce
"densi" andava solo spaccata in byte (K) e FLOP (C).

L'inventario FLOP per token, contato dai tensori del log (n_embd 4096, 43 strati,
64 teste da 512, o_lora 1024 in 8 gruppi, shexp ffn 2048, indexer 64×128 su 21
strati) [CONTATO]:

| famiglia | MAC/strato | GFLOP/token (×43) |
|---|---|---|
| proiezioni MLA: wq_a 4096×1024, wq_b 1024×32768, wkv 4096×512, wo_a 8×4096×1024, wo_b 8192×4096 | 106,95 M | 9,20 |
| esperto condiviso (3×4096×2048) | 25,17 M | 2,16 |
| router (4096×256) | 1,05 M | 0,09 |
| indexer q_b+k (solo 21 strati, media) | 4,35 M | 0,37 |
| **GEMM densi, totale** | 137,5 M | **11,83** |
| esperti instradati 6×3×4096×2048 | 151,0 M | **12,99** |
| FA+punteggi indexer a contesto L | — | 0,774·L/1000 (→ 2,52 a L=3.255 medio) |
| attn fissa: raw SWA 128 + intra-ubatch + rope/de-rope | — | ~0,9 |
| chiusure CSA/LID (ogni 4) + HCA (ogni 128) | — | ~0,8-1,5 |
| **totale a 6,5k medio** | | **≈ 29,4** |

(controprova: audit 38 §4 dava ~190 TFLOP per l'intero prompt = 29,2 GFLOP/token —
chiude allo 0,7%).

Il libro mastro, con le efficienze dichiarate:

| voce | ms/token | fonte |
|---|---|---|
| **GEMM densi** (11,83 GFLOP; MMQ int8-mma, confermato il dispatch: `mmq.cu:307-309` ritorna true su Ampere a ogni batch, `ggml-cuda.cu:2078`) | **1,5-2,4** | [DEDOTTO: 3060 su MMQ pp512 rende ~6-8 TFLOPS-eq, calibrazione esterna su modelli densi 7-8B] |
| **attenzione, parte che cresce** (FA sulle celle CSA correnti + punteggi indexer) | **0,31-0,50** a 3,3k medio | [MISURATO via pendenza §2 — non stimato] |
| **attenzione, parte fissa** (SWA 128, intra-ubatch, rope, de-rope, maschera top-k, argsort) | 0,2-0,5 | [DEDOTTO] |
| **chiusure DSV4** (compressori a stato: le chiusure sono BATCHED — nodi 11.195 a bs=64 **e** a bs=512, è la prova) | 0,2-0,5 | [CONTATO+DEDOTTO] |
| **coda di calcolo MoE oltre il trasporto** (12,99 GFLOP: dequant iq2_xxs/q2_K + mma a ~12 token/esperto) | **0 ÷ 2,6** | [IPOTESI — vedi sotto, è IL buco] |
| quantize q8_1 + mm_ids_helper + softmax router | 0,05-0,1 | [DEDOTTO] |
| eltwise/HC/norme (~20-30 MB/token r+w in VRAM) | 0,08-0,15 | [DEDOTTO] |
| lanci: 11.207 nodi/passata ÷ 512 = **21,9 nodi/token** × 0,73-1,1 µs | 0,02-0,05 | [CONTATO×fattore 0b di audit 30] |
| host per passata (maschere+embedding = 27,3 MiB CUDA_Host, 5 split) | ≤0,05 | [MISURATO buffer, DEDOTTO costo] |
| **somma spiegata "dura"** | **2,5-4,2** | |
| **misurato** | **5,5±0,3** | |

**Quanto ammetto di non spiegare: 1,5-3,0 ms/token (il 30-50%)**, e ha due soli
indiziati perché tutto il resto è inchiodato da contatori:

- **Indiziato A — la coda MoE.** Il fit NON separa dove vive il calcolo degli
  esperti: K = massa/banda è il termine per-passata, ma se il kernel MMQ su
  memoria mappata serializza (caricamento tile via PCIe → syncthreads → mma →
  tile successivo, pipeline corta), una parte ∝ token si somma SOPRA il trasporto
  e cade in C. 12,99 GFLOP a ~5-10 TFLOPS-eq = 1,3-2,6 ms. Se invece i warp
  coprono le latenze (bastano ~28 KB in volo per saturare 18,4 GiB/s), la coda è
  ~0.
- **Indiziato B — i densi sotto il calibrato.** Le forme nostre sono sfavorevoli:
  wq_b ha K=1024 (GEMM "magro" in K), wo_a è un batched a 8 gruppi da
  [4096×1024]; su queste MMQ può rendere 3-5 TFLOPS-eq invece di 6-8 → densi da
  soli 2,4-4 ms e il libro chiude senza coda MoE.

Le due letture sono indistinguibili dai dati in cassa e **la distinzione decide la
leva** (§4). Una corsa con nsys su 2-3 ubatch le separa: la somma dei kernel
`mul_mat_q` con ids per passata è ~4,0-4,3 s (coda≈0, indiziato B) oppure
≥5,2 s (coda ≥1,5 ms/token, indiziato A).

---

## 2. C È COSTANTE NEL CONTESTO? No — e la spazzata non poteva dirlo

### 2a. Perché il fit era cieco per costruzione

Le quattro corse della spazzata processano lo STESSO prompt da 6.510 token: ogni
termine che dipende dal contesto (attenzione, indexer) contribuisce **identico**
in tutte e quattro e viene assorbito in C·6.510. La spazzata misura solo la
dipendenza da `ub`. La domanda "C(L)?" si risponde **dentro** una corsa, coi
segmenti di §0.

### 2b. La misura [MISURATO]

ms/token per segmento (spanne comuni: A = token 1-2049, B = 2049-4097,
C = 4097-6145; a ub 512 il terzo segmento è 4097-5994):

| corsa | A | B | C | coda | B−A | C−A |
|---|---|---|---|---|---|---|
| ub064 | 43,21 | 49,12 | 40,35 | 44,2 / 39,6 | **+5,91** | −2,86 |
| kvd_A | 43,19 | 49,12 | 40,33 | — | **+5,93** | −2,86 |
| ub128 | 33,28 | 36,47 | 30,72 | 33,5 / 29,1 | **+3,19** | −2,56 |
| ub256 | 21,54 | 22,29 | 20,23 | 35,2ᵃ / 19,8 | **+0,75** | −1,31 |
| ub512 | 13,37 | 13,67 | 13,96 | 12,95 | **+0,30** | **+0,59** |

ᵃ chunk da 105 token: una passata quasi piena di K su pochi token, non
informativo su C.

Due fatti, uno per colonna:

1. **B−A si sgonfia ~1/ub** (5,91 → 3,19 → 0,75 → 0,30): il grosso del divario
   fra i blocchi di contenuto è TRASPORTO — il blocco B tocca più esperti
   distinti. A ub 64 il divario vale ΔU ≈ **+23 esperti/strato/passata**
   [DEDOTTO: 5,6 ms/token × 64 = 359 ms/passata × 18,84 MiB/ms ÷ (43·6,75)].
   L'unione per passata dipende dal CONTENUTO, non solo da ub — a ub 64 K oscilla
   del ±10% fra blocchi dello stesso prompt. (È anche il motivo per cui il punto
   ub 128 "cadeva male" nel fit di audit 40.)
2. **A ub 512 il residuo cambia segno e resta positivo**: B−A = +0,30 su +2.048
   di contesto, C−A = +0,59 su +4.020. Se fosse ancora unione dovrebbe seguire il
   segno di ub 64-256 (negativo su C−A: il blocco C è PIÙ leggero di trasporto).
   Invece è positivo e **le due pendenze coincidono: 0,146 e 0,147 ms per 1.000
   token di contesto**.

Controprova aritmetica indipendente: FA+indexer crescono di
21·(4·64·512 + 2·64·128)/4 = **774 kFLOP per token per token di contesto**
[CONTATO dalle forme]; a 5-8 TFLOPS effettivi = **0,10-0,15 ms/1.000 tk** —
esattamente la pendenza misurata. E il codice conferma che DEVE crescere: la FA
poda solo la frontiera (`flash_attn_mask_to_KV_max`, `fattn-common.cuh:666-718`,
scandisce la maschera dal fondo e si ferma al primo blocco non interamente
mascherato; i **buchi interni della maschera top-512 NON si saltano**,
`fattn-mma-f16.cuh:1827/1873` limita solo `kb0_stop`) → il costo FA è ∝ celle
correnti (L/4), non ∝ 512 scelte.

Avvertenza dichiarata: il residuo-unione a ub 512 non è esattamente zero (la coda
del prompt, blocco D, dà −0,42 apparente — contenuto ripetitivo, unione magra
anche a 512: lo stesso blocco è leggero a TUTTI gli ub, firma di contenuto e non
di contesto). Perciò la pendenza onesta è **s ∈ [0,05; 0,15], centrale 0,10-0,15**.

### 2c. La legge riscritta, e cosa cambia

    tempo = Σ_passate K(U(contenuto, ub)) + Σ_token C(L)
    C(L) = C₀ + s·L        C₀ ≈ 5,0-5,2 ms   s ≈ 0,10-0,15 ms / 1.000 token
    (misurata su 0-6,5k; K satura a ~74.304 MiB/banda per ub ≥ ~256)

| bersaglio | col C "costante" | con la legge riscritta | verdetto |
|---|---|---|---|
| follow-up 10k, ub 7700 | 67 s (58,0 di C) | C medio = C₀+s·5k ≈ 5,6-5,9 → **56-59 s di C, ~67-70 s totali** | **il piano STA IN PIEDI** (C₀ più basso compensa la rampa) |
| tetto asintotico a ≤10k | 137-172 t/s | **170-190 t/s** (1/C con C 5,3-5,8) | invariato in pratica |
| prefill 105k | ~610 s di C | C medio ≈ C₀+s·52,5k = **10-13 ms** → 1.000-1.300 s di C, PIÙ l'aritmetica indexer di audit 38 §6 (punteggi 6,7 MiB×ub per strato) | **il termine C raddoppia**: l'estrapolazione piatta a 105k è FALSA, va rimisurata sul posto (§5.2) |

**La risposta alla domanda più importante del mandato**: sì, C cresce col
contesto; no, non rompe il cantiere — a 10k la correzione sta dentro il ±3%,
cioè sotto il rumore di una singola corsa. Rompe solo l'estrapolazione a 105k,
che era già in sospetto (audit 38 §6) e ora ha un numero.

---

## 3. Le piste del mandato, una per una

- **Attenzione**: non è quadratica-visibile, è lineare-piccola: a 6,5k pesa
  0,3-0,5 ms medi (5-9% di C), a fine prompt ~0,7-1,0. La "piatta sul progresso"
  di audit 38 era vera a ub 64 perché 39 ms di trasporto coprivano una rampa da
  0,5: coi segmenti a ub 512 la rampa si vede e si misura. FA attiva, mma f16,
  un lancio per strato (audit 30 §6) — il costo cresce perché le celle crescono,
  non perché il kernel degrada.
- **Pesi densi**: i byte stanno in K (0,06 ms/token a ub 512), il calcolo in C
  (1,5-2,4). Nessuna contraddizione nel modello: la voce era da spaccare.
- **Compressione DSV4**: 0,2-0,5 ms/token. Le chiusure sono batched nel grafo
  dell'ubatch (nodi identici 11.195 a bs 64 e 512 [MISURATO]); il lavoro è ∝
  token (~1 GFLOP + ring store). La fusione HC di ieri notte ha tolto NODI, che
  nel prefill sono per-passata e già ammortizzati: per il prefill era quasi
  neutra, come infatti misurato (audit 38 §2, controprova).
- **Lanci**: 11.207 nodi per PASSATA (non per token) — 21,9/token a ub 512,
  0,02-0,05 ms. **Escluso con un contatore.** (A ub 64: 175/token → 0,13-0,19 ms,
  comunque piccolo.)
- **La voce che il mandato non elencava**: i 13 GFLOP/token di calcolo MoE, che
  il fit non sa collocare (K o C) — è l'indiziato A del non-spiegato, e da solo
  può valere metà di C.

---

## 4. LA LEVA PIÙ GROSSA, col suo cancello

**Leva zero (il discriminatore, prima di ogni patch)** — profilo per-kernel di
2-3 ubatch a ub 512 (nsys, zero righe di codice, una corsa). Predizioni a
verbale, in numeri di kernel e non in ms stimati:
somma kernel MMQ-ids per passata ≤4,3 s → coda MoE ≈ 0, il buco è nei densi;
≥5,2 s → coda ≥1,5 ms/token. In più chiude il libro mastro all'unità (densi,
FA, chiusure, ciascuno col suo tempo).

**Se vince l'indiziato A (coda MoE) — la leva è la staged-copy col motore di
copia**, già schedata (audit 38 §5, RACCOLTA lavoro 2) ma con un motivo NUOVO:
non è solo banda. `cudaMemcpyAsync` della massa strato-per-strato su uno staging
VRAM (doppio buffer) + MMQ da VRAM fa tre cose: (i) elimina la coda (MMQ da
VRAM a ~360 GB/s), (ii) sposta il trasporto sul copy engine, che gira IN
PARALLELO agli SM → **la legge cambia da somma a max**:
`tempo/passata = max(massa/banda_DMA, C'·ub)` invece di `K + C·ub`;
(iii) rende il trasporto insensibile al pattern di load di MMQ (l'angolo
banda-degradata di audit 38 §5). Numeri attesi sul piano 10k (banda DMA misurata
11-14 GB/s → trasporto/passata ~6,2 s): con C' = C−coda ≈ 3,2-4,5:
**10k in ~40-55 s contro 67** — e a ub 512 il prompt da 6,5k in ~65-75 s contro
89. Intervallo largo perché dipende dalla coda vera: per questo la leva zero
viene prima. Costo: cantiere (patch media). Cancelli: (a) nsys mostra la coda,
altrimenti la leva scende a ×1,1-1,2 (solo overlap del trasporto); (b) a patch
fatta, tempo/passata ≤ max(massa/banda_DMA, somma kernel di calcolo)+10% e il
contatore `dma` del dump cache-esperti > 0; (c) SHA: cambia il percorso
aritmetico degli esperti (VRAM vs mapped) — il cancello SHA fra le due
configurazioni NON si applica, dichiararlo nel ledger.

**Se vince l'indiziato B (densi lenti)** — env-gate da ~10 righe che forza il
percorso dequant+cuBLAS per i SOLI `mul_mat` densi (NON globale:
`GGML_CUDA_FORCE_CUBLAS` è compile-time e avvelenerebbe il percorso ids col
ripiego catastrofico di `ggml-cuda.cu:2371-2485`). Dequant f16 dei 5,6 GiB q8_0
una volta per passata ≈ 60 ms (in K, trascurabile), GEMM a 15-20 TFLOPS →
densi da 2,4-4 a ~0,8-1,2 ms. Atteso su C: **−0,5÷−1,5 ms/token**
(prefill ub 512: +5-12%). Costo: una ricompilazione. Cancello: prefill ≥+5% a
ub 512 su n≥3; sotto +2% l'indiziato B è assolto e si torna alla A.

**Se C è incomprimibile** (nsys dice: niente coda, densi già al tetto MMQ):
l'aritmetica del tetto è questa e vale la pena scriverla — pavimento duro di C =
densi 1,5 + attn fissa 0,3 + chiusure 0,25 + spiccioli 0,2 ≈ **2,3-2,6 ms** più
l'attenzione che cresce: il tetto macchina a ≤10k è **380-430 t/s** SE tutto il
non-spiegato fosse eliminabile, **170-190 t/s** se non lo è. Con la staged-copy
che manda K sotto C, il prefill diventa PURO C: ogni ms tolto a C vale 10 s sul
follow-up da 10k; ogni ms lasciato è un s/1000-token per sempre.

---

## 5. Dati che si ottengono SOLO eseguendo (in ordine di resa, con cosa decidono)

1. **nsys su 2-3 ubatch a ub 512** (una corsa, zero codice). Decide A contro B
   (§1) e quindi QUALE leva; chiude il libro mastro all'unità. È il prerequisito
   dichiarato della staged-copy: senza, l'intervallo atteso resta ×1,1-×1,7.
2. **Un prompt da 20-30k a ub 512** (una corsa; i segmenti dai timestamp fanno il
   resto). Misura s su 4× l'intervallo, fuori dal rumore-unione; con blocchi di
   contenuto RIPETUTI (stesso testo ×N) l'unione per blocco è identica e la
   pendenza residua è pura attenzione. Decide il tetto vero a 105k e se il tiling
   dei punteggi indexer (audit 38 §6) è urgente o rinviabile.
3. **Sonda U** (~10 righe env-gated, già disegnata in audit 38 §8.2). Toglie
   l'ambiguità unione/banda che tiene C in [5,4; 5,8] e spiega il ±10% di K sul
   contenuto (§2b): dopo, ogni previsione di questo rapporto si stringe del
   10-15%.
4. **Env-gate cuBLAS-densi** (una ricompilazione, ~10 righe). Prezza l'indiziato
   B anche senza nsys — è l'A/B più economico se nsys non è installabile sulla
   macchina di misura.
5. **`GGML_SCHED_PROFILO=1` su una passata** (gratis, già nel fork,
   `ggml-backend.cpp:1766-1790`): costo dei confini fra i 5 split. Atteso ≤2
   ms/passata; se è di più c'è un sync non contato nel libro mastro.
6. **`LLAMA_DSV4_COMPRESS_DEBUG=1` a ub 512** (gratis): chiusure = n/4 e n/128
   esatte — è il cancello di correttezza già a verbale (audit 38 §6, 40 §6) e
   qui pesa anche la voce "chiusure" del libro mastro.

## 6. Sintesi in tre righe

C = 5,5±0,3 ms/token e non è una costante: è C₀ ≈ 5,1 più 0,10-0,15 ms ogni
1.000 token di contesto (misurato nei segmenti, confermato dall'aritmetica
FA+indexer, invisibile alla spazzata per costruzione) — il piano 10k regge, il
tetto 105k no. Dentro: GEMM densi 1,5-2,4, attenzione 0,5-1,0, chiusure 0,2-0,5,
lanci e byte esclusi con contatori; restano 1,5-3,0 ms che sono O la coda del
kernel MoE sopra il trasporto O i densi sotto il calibrato — una corsa di nsys li
separa e sceglie la leva: staged-copy col copy engine (che cambia la legge da
K+C·ub a max, atteso 10k in 40-55 s) oppure cuBLAS sui densi (−0,5÷−1,5 su C).
Se nessuna delle due paga, il tetto vero della macchina è 170-190 t/s ed è
scritto qui coi suoi numeri.
