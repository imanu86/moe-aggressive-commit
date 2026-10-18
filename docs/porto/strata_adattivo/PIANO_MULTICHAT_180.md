# Piano del multi-chat verso 180 t/s aggregati — 18 ottobre 2026

Analisi in sola lettura (nessuna GPU, nessuna build, nessun motore avviato). Fonti: `ROOFLINE_2026-10-12.md`,
`HANDOFF_STRATA_2026-10-13.md`, `Strata-wt\multichat45\docs\MULTICHAT.md` (uso reale del Daily 13-17/10, misure `mc2`
del 13/10 e del 18/10), `Strata-wt\upsync-main\docs\UPSYNC_MAIN.md`, `Strata-wt\shortpf\docs\SHORTPF.md`,
`Strata-wt\multichat45\docs\BATCHING.md` (upstream), i `res.json` e gli `engine.log` di
`corse_2080ti\20261018_multichat45\mc2_*` e `20261013_multichat\mc2_*`.

Convenzione: **M** = misurato (log del motore, `res.json`, nsys), **S** = stimato (byte dai tensori, banda nominale,
modelli). Hardware: 3060 12 GB (360 GB/s, Oculink x4, monitor 8K) = stadio 0, layer 0-15; 2080 Ti 22 GB (616 GB/s)
= stadio 1, layer 16-47 + testa + MTP; niente P2P; 5800X, 96 GB. Modello Qwen3.8-Flash-Next IQ3_XXS.

## 0. Verdetto

- **180 t/s aggregati con 3 agenti nel carico reale (tool result da 1-5k token ogni pochi secondi): no, su questo
  hardware.** Il tetto non è il decode ma il **prefill**: ogni agente legge ~10 token per ogni token che genera (banco
  `agents:4:P`: 19 639 letti / 2 082 generati, M; nel Daily il prefill è il 46% del tempo, M). L'aggregato in t/s
  generati è quindi ≤ (tok/s di prefill) ÷ (letti/generati). Oggi le letture corte girano a **380-450 tok/s** (M, 1,5-2k
  token con prefisso in cache) → tetto ~40-45 t/s, e misuriamo 28,6 (M). Con tutto il programma qui sotto (letture
  impacchettate, due stadi sovrapposti, hc16/BF16_TC, prefisso senza copia) il prefill delle code corte può arrivare a
  ~1 500-2 000 tok/s (S; il prompt lungo a 131k fa già 1 600-1 770 tok/s, M) → **tetto 100-120 t/s con 3 agenti (S)**,
  realisticamente **70-105**. Con 8 agenti le letture si impacchettano meglio: **120-150 (S)**.
- **180 t/s con 3 agenti in decode puro (nessuna lettura) è fisicamente ammissibile ma fuori dalla portata del motore
  attuale.** Roofline in serie 205 t/s senza MTP e ~250 con MTP (S, §1); a pipeline perfetta 355/380. Alla migliore
  efficienza mai osservata in questo motore (~60% della banda, 4090 D con tutto in VRAM) restano 123-149 in serie e
  **213-227 a pipeline** (S). Oggi il decode puro a 3-4 chat vale **~75-86** (M: `same:4` 84,7, `diff:4` 85,9) perché
  ogni riga in più costa **~7,4 ms** di kernel (M) contro ~0,5 ms di byte (S). Per 180 servono tutte e tre le cose:
  gruppi davvero in pipeline sulle due schede, MTP nei gruppi con la catena in batch, kernel batch al 60% della banda.
  Sono 6-10 settimane di lavoro con rischio alto; la tappa intermedia credibile è **110-140 (S)**.
- **Dove conviene puntare**: (1) prefill delle code corte (impacchettamento + sovrapposizione degli stadi + hc16):
  è il 64-83% del wall degli agenti (M); (2) MTP nei gruppi (1 token a riga oggi contro 1,71-1,97, M); (3) kernel
  batch per riga; (4) prefisso e ammissione senza copia (0,7-1,5 s a turno a 131k, M). Le prime tre tappe (§4) sono
  config + banco + misure pulite, fattibili stanotte da un agente Sonnet.

## 1. Roofline del multi-chat

### 1a. Byte per passo (S, dai tensori di `ROOFLINE_2026-10-12.md` §1a)

Per passo: densi letti una volta per stadio (stadio 0 1 133 MB; stadio 1 2 260 MB + testa 437 MB); esperti = unione dei
top-10 delle righe (blob medio 1,50 MB stadio 0, 1,87 MB stadio 1; unione di R righe indipendenti
U(R) = 512·(1 − (1 − 10/512)^R): 10, 19,8, 29,4, 38,8, 74,6 per R = 1, 2, 3, 4, 8; a T=2 nella stessa chat le righe sono
correlate: 16 misurati ≈ U(1,6)); per sessione: stato GDN letto e scritto (75 MB stadio 0, 151 stadio 1, fp32), chiavi
pooled dell'indexer QSA (a 80k di contesto medio: 41 / 82 MB; a 131k: 67 / 134), K/V int8 delle celle scelte
(8,4 / 16,8 MB per riga). Catena MTP per sessione: 7 passi × 210 MB sulla 2080 Ti (S, nsys: 7 passi a finestra); se
la catena è in batch, i densi del passo (q, o, fc, testa: ~132 MB) si leggono una volta e restano ~78 MB per sessione.

| N agenti, righe | U esperti/layer | stadio 0 GB · ms | stadio 1 GB · ms | catena ms | **serie** ms → t/s | **pipeline** ms → t/s | al 60%: serie / pipeline |
|---|---|---|---|---|---|---|---|
| 1, T=2 (riferimento, 1,8 tok) | 16 | 1,67 · 4,6 | 3,96 · 6,4 | 2,4 | 13,4 → 134 | 8,8 → 205 | 81 / 123 |
| 3, T=1 (3 tok) | 29,4 | 2,21 · 6,1 | 5,21 · 8,5 | — | 14,6 → **205** | 8,5 → 355 | **123 / 213** |
| 3, T=2 MTP (5,4 tok) | 46,2 | 2,64 · 7,3 | 6,26 · 10,2 | 4,2 | 21,7 → **249** | 14,3 → 378 | **149 / 227** |
| 4, T=1 (4 tok) | 38,8 | 2,56 · 7,1 | 6,02 · 9,8 | — | 16,9 → 237 | 9,8 → 409 | 142 / 246 |
| 4, T=2 MTP (7,2 tok) | 60,7 | 3,12 · 8,7 | 7,40 · 12,0 | 5,1 | 25,7 → 280 | 17,1 → 422 | 168 / 253 |
| 8, T=1 (8 tok) | 74,6 | 3,92 · 10,9 | 9,16 · 14,9 | — | 25,8 → 310 | 14,9 → 537 | **186 / 322** |
| 8, T=2 MTP (14,4 tok) | 114 | 4,94 · 13,7 | 11,7 · 18,9 | 8,6 | 41,2 → 350 | 27,5 → 524 | 210 / 314 |

Letture:
- Il roofline **cresce con N** (i densi si ammortizzano: a N=8 sono il 35% dei byte contro il 70% a N=1), ma la
  catena MTP per sessione lo erode: a N=8 la catena in batch vale 8,6 ms di 2080 Ti a finestra, quasi quanto gli
  esperti. **Sopra ~6 agenti l'MTP rende poco; a 3-4 è la leva che fa la differenza** (+22-30% di roofline).
- Il 60% è il tetto osservato dal motore in decode con tutti gli esperti in VRAM (4090 D, 170 t/s a 0,169 t/s per
  GB/s; ROOFLINE §4). Nessuno della community lo supera; a 2 stadi con esperti in RAM siamo oggi al 42% in singola
  chat e al **20-25% in batch** (S da M: 7,4 ms a riga contro 0,5 di byte).
- Con i **kernel di oggi** (M): finestra ≈ 26 ms + 7,4 ms per riga oltre la seconda (`--batch 4 --batch-mtp`, 6,93
  righe in 77,1 ms; righe della stessa chat 2,2 + 2,9 ms, di chat diverse ~3,7 ms a stadio). In serie: 3 righe 33 ms
  → 91 t/s; 4 → 83 (misurato `same:4` 84,7 M); 8 → 103 (misurato 70, perché 8 slot tolgono VRAM e gli esperti CPU
  salgono a 46 ms su 98, M). I gruppi in pipeline sulle due schede rendono quanto la serie a 4 righe (85-86 M): il
  tetto dei gruppi è lo stadio lungo (2080 Ti, ~20 ms a 2 righe + 7 ms di commit/emissione/adattivo, M).

### 1b. Il mix reale: il prefill è il tetto (M + S)

Per un turno di agente: lettura di R token (tool result), generazione di G token, pausa del tool. Banco `agents:4:P`:
R/G = 9,4 (M); Daily reale: 46% del tempo in prefill con decode a 55 t/s mediano (M) → stesso ordine.

| regime | prefill delle code corte, tok/s | aggregato massimo a R/G = 10, t/s | nota |
|---|---|---|---|
| oggi, letture una alla volta, 1,5-2k token su 35k in cache | 380-450 (M, `c-conc`: 1 456-2 102 token in 3,8-4,9 s) | ≤ 40-45 (S); misurato 28,6 | le letture sono l'83% del wall (60,1 s su 72,7, M) e nel frattempo gli slot decodificano 24-36 righe/s (M) |
| letture impacchettate (4 code in un pezzo) | 6,4k token in 8,5 s = 750 (M, `packdet`) | ≤ 75 | −41% del tempo di lettura a 4 agenti (M); a 8 segno instabile (M) |
| impacchettate + due stadi sovrapposti + hc16/BF16_TC + anello pinned | 1 200-1 800 (S; il 131k fa 1 600-1 770 M, +17% con BF16_TC M) | ≤ 120-180 | il fisso per pezzo (0,4-0,7 s a stadio, M) non scende: ~1 s di PCIe se un pezzo tocca tutti gli esperti non residenti (6,6 GB sull'Oculink a 6,5 GB/s, S); si ammortizza, non si elimina |
| + decode a 150+ t/s in parallelo alle letture | — | **100-120 con 3 agenti, 120-150 con 8** (S) | il decode non è gratis: condivide le schede con il pezzo |

Modello di un giro con 3 agenti, R = 2,5k, G = 250 (S da M): oggi 3 letture da ~6 s in serie e 750 righe a ~30
righe/s → giro ~25-28 s → 27-30 t/s (misurato 28,6, M). Con pacco da 7,5k (~9-10 s) e decode a 85 t/s nei buchi →
giro ~15 s → 45-50. Con MTP nei gruppi (decode 120-130) → ~13,5 s → 55. Con prefill a 1 500 tok/s → ~10,5 s → 70.
Con kernel batch e pacco sovrapposto al decode (stadi diversi) → giro ≈ max(prefill, decode) ≈ 7-8 s → **95-110**.
Con 8 agenti lo stesso giro legge 20k e genera 2 000 token: 13-15 s → **130-150**.

## 2. Dove si perde oggi (M, in ordine di peso sul carico agenti)

| # | perdita | misura | fonte |
|---|---|---|---|
| 1 | **Letture una alla volta** (`_take_control` del server) e lente: 380-450 tok/s per code da 1,5-2k | 83% del wall in `agents:4` (`c-conc`), 64% in `agents:8` del 13/10; TTFT medio 7,8 s a 4 agenti, 21 s a 8 | `mc2_c-conc/res.json`, MULTICHAT §3 |
| 2 | **Costo fisso per lettura** ~1-1,5 s: streaming/dequant degli esperti 41-48% del tempo fino a 1k token; "hc read" 190-230 ms fissi sullo stadio 1 anche a 6 token | TTFT 1,74 s a 120 token, 4,5 a 1k, 7,7 a 3k; `--short-read 64` manda sul percorso del prompt letture da 100-250 token che in finestre costerebbero 0,3-0,9 s meno | SHORTPF §2-3 |
| 3 | **Cache conversazioni del Daily** (2 posti / 6 GB): 23% delle richieste rileggono ~100k token = 83% del tempo di prefill (6,3 h su 7,9) | con 16 posti / 28 GB `diff:4` passa da 37 a 86 t/s, `agents:4` da 18 a 27 | MULTICHAT uso reale; seconda coda 13/10 |
| 4 | **Con i gruppi in pipeline una lettura ferma tutti** (`batch_read_piece` torna 0 se `piped`) salvo `STRATA_PIPED_CONCURRENT=1` | con la leva gli slot decodificano 24-36 righe/s durante la lettura; `agents:4` 26,7 → 28,6, `agents:8` 28,7 → 30,4 | `c-conc` engine.log |
| 5 | **`--batch` spegne la pipeline della chat singola** (`"not with --batch slots"`), la cache elastica, e gli slot tolgono VRAM agli esperti (−20% slot sulla 3060, −15% sulla 2080 Ti a 4 slot) | chat singola 64,5 → 56,2 (18/10) / 75 → 66-71 (13/10); `STRATA_BATCH_PIPELINE=1` 55,0 contro 56,2 (rumoroso) e 74,0 contro 70,7 (13/10): inconclusivo | `a-daily`/`b-g2cc`/`l-bpipe`, MULTICHAT §1 |
| 6 | **MTP spenta nei gruppi**: 1 token a riga contro 1,71-1,97 della chat singola | −42/−49% dei token per finestra; `STRATA_PIPED_MTP` (#2985) portato: `diff:2` 67,8 contro 54,2, `same:2` 51,6 contro 50,6, `solo` 50,2 contro 51,5 (stessa finestra rumorosa: indicativo) | `i-pmtp2`/`i0-b2` |
| 7 | **Esperti su CPU in batch**: a 4 chat 6,7 + 9,8 ms su 77 (21%); a 8 slot 17 + 29 su 98 (47%) | ogni slot costa 0,36 GiB (3060) + 0,66 GiB (2080 Ti) di VRAM = ~230 esperti in meno sulla 3060 per slot | `mc2_b4mtp-prof.out`, MULTICHAT §3 |
| 8 | **Ammissioni con copia**: `copy_to_slot` ~13 ms per 1k token (0,7-1,5 s a 131k, in entrambe le direzioni, ogni turno); park 65-180 ms + ripristino 70-110 ms + copia 210-250 ms a turno sui 35k | ~0,5 s a turno a 35k = 10% del turno; a 100k ~1,5-2 s = 15-20% | MULTICHAT L3, misure 12-13/10 |
| 9 | **Kernel batch a costo per riga**: +7,4 ms a riga (+3,7 a stadio fra chat diverse) contro ~0,5 ms di byte | il batch oggi è "per riga", non "per byte": 4 righe = 48 ms, 8 = 78 | ROOFLINE §1c (pendenza T), MULTICHAT §2 |
| 10 | **Gli stadi corrono in serie dentro la finestra batch** a un gruppo (`run_slot_rows`); con 2 gruppi si sovrappongono ma senza MTP, adattivo, elastica | ogni scheda calcola il 25-34% della finestra a un gruppo | MULTICHAT §2, §5 |
| 11 | Stalli e cancellazioni che perdono la cache: 5 blocchi del watchdog a 240 s, 13 cancellazioni (988 s) | | uso reale del Daily |
| 12 | Top-k QSA un CTA per riga (80-110 µs piatti × 12 layer QSA = ~1,1 ms per riga, in sequenza fra le righe) | a 8 righe ~9 ms a finestra su 2 SM di 68 (S da M) | ROOFLINE leva 8 |

## 3. Architettura proposta

Principio: **una lettura dei pesi per più sessioni, e le due schede sempre occupate da lavoro diverso**. Sei pezzi, in
ordine di resa per il carico agenti; le stime per passo sono S salvo indicazione.

### 3a. Scheduler a pacchi: prefill impacchettato di più sessioni, in pipeline fra gli stadi, con il decode accanto

- Il server manda avanti i prompt in attesa (`BHINT`, esiste in `lab/multichat45` come `STRATA_PACK_PREFILL=N`); il
  motore legge in **un pezzo** le code di tutte le sessioni in attesa (prefisso di ciascuna ripristinato nello slot di
  pacco), con i chunk consecutivi in pipeline fra stadio 0 e stadio 1 (`STRATA_PACK_CHUNK`, oggi neutro a 6,4k perché
  il pacco è dominato dal calcolo, M) e i gruppi di decode che continuano (`STRATA_PIPED_CONCURRENT=1`, oggi 24-36
  righe/s durante una lettura, M).
- Stima per pezzo: 3 code da 2,5k lette insieme = 7,5k token: ~9-10 s contro 3 × 6 = 18 in serie (M per 6,4k: 8,5 s);
  con hc16/BF16_TC sulla 2080 Ti −2,3 s su 16k (M, fase "hc read" −71%) e anello pinned, ~6-7 s. **−50/−60% del
  tempo di lettura** sul carico agenti.
- Variante Sarathi (righe di decode dentro il pezzo di prefill): qui rende poco (S: −2/−15% del tempo di prefill)
  perché il nostro prefill non è legato alla lettura dei pesi residenti ma al toccare tutti gli esperti per pezzo; il
  decode concorrente su thread (già in 0.1.45) ne prende la maggior parte. Si rimanda.
- Rischio: parità del testo (le richieste impacchettate divergono a metà testo anche senza MTP, M) e la regressione a
  8 agenti (M, −4/+3%). Vanno chiusi con confronto dei logit a cache fissa e con la correzione del fisso per pezzo.

### 3b. Due gruppi alternati sulle due schede, con le bozze MTP dentro e la catena in batch

- I gruppi in pipeline **ci sono già** (`--batch-groups 2`: stadio 0 sul gruppo B mentre lo stadio 1 fa il gruppo A,
  M). Quello che manca è l'MTP: oggi 1 token a riga. #2985 (`STRATA_PIPED_MTP`) porta le bozze nei gruppi con uno
  slot per gruppo; spec208 le porta a ondate di 2 slot con un secondo verificatore. La forma giusta per noi: finestra
  del gruppo con T=2 per slot (riga + bozza, `kVerifyMaxT = 8` → 4 slot per gruppo), **catena di draft in batch** (un
  passo per tutte le sessioni del gruppo: i densi del passo letti una volta) e corta (3-4 passi invece di 7, perché
  in batch ogni passo costa N × 78 MB in più).
- Stima per passo (S, kernel di oggi): finestra del gruppo a 2 slot × T=2 = 4 righe: stadio 1 ~20 + 2 × 3,3 = 27 ms,
  stadio 0 ~12 + 2 × 2,5 = 17; periodo della pipeline ~27 + 5 ms di commit = 32 ms per 2 slot × 1,8 tok = 3,6 token
  → **112 t/s a 4 chat** contro 85 oggi (+30%); con la catena in batch sulla 2080 Ti (+4 ms) → ~100. A 3 agenti
  (gruppi di 2 + 1): ~90-100.
- Rischio medio-alto: verify.cpp/generate.cpp/resident_slots.cpp; il fork ha misurato +14% a prompt corti e +6,6% a
  9,5k con tutti gli esperti in VRAM; da noi gli esperti CPU per riga pesano di più.

### 3c. Kernel batch "per byte" invece che "per riga"

- Esperti in VRAM lato pesi (tile di 16 righe in shared, load da 16 B; ROOFLINE leva 3): 34% → 60% della banda, e il
  costo per riga in più cala da ~1,3 ms a ~0,3 (S). Hyper-connection e MMVQ a righe multiple (SoA, prodotti Q8_1 per
  riga: oggi +0,48/+0,63 ms a riga, M). Top-k QSA multi-CTA e parallelo fra le righe (leva 8): da ~1,1 ms a riga a
  ~0,2 (S).
- Stima per passo: finestra a 8 righe da 78 ms (M) a **~40-45 ms** (S): 4 chat 85 → ~140, 8 chat 70 → ~170 senza
  MTP (S). È la leva che fa valere "più agenti = più t/s" ed è l'unica strada verso 180 in decode puro.
- Rischio alto: CUDA sm_75 e sm_86, vincolo bitwise (stesso albero di somma per riga), 3-6 settimane.

### 3d. Prefisso condiviso fra sotto-agenti senza copia, ammissione senza copia

- Il prefisso comune **funziona già** via checkpoint parcheggiato (`cached 33380` su 35k, M) ma viene **copiato** a
  ogni ammissione (K/V in RAM pinned → immagine → slot, su ogni stadio; 13 ms per 1k, M). Disegno: pagine K/V e
  chiavi dell'indexer **condivise fra slot in copy-on-write** (lo stato GDN si copia: 113 MB a sessione, S) e lettura
  che scrive direttamente nella sessione dello slot (oggi legge nella sessione principale e poi `copy_to_slot`).
- Stima: −0,5 s a turno a 35k, −1,5/−2 s a 100-131k (M per la copia) = +10-20% sull'aggregato agenti a contesti
  lunghi (S). Prerequisito per 8 agenti a 100k (oggi ogni turno copia 1,3 GB per stadio).
- Rischio medio: `resident_slots.cpp`, `session.cpp`; niente kernel.

### 3e. Cache conversazioni a più livelli

- **RAM** (config, oggi): 16 posti / 28 GiB bastano per ~8 agenti a 64k o 3-4 a 131k (3,5-4 GB l'uno, S). È la
  correzione del collo n. 3 (M: 2,3× su `diff:4`). Da mettere subito nelle sessioni con agenti.
- **Disco su D:** (`STRATA_CONV_DISK`, esiste in `lab/ttft43` e nella pila: immagine al confine di turno a motore
  fermo): serve per i riavvii e per più di 8 agenti, non per i t/s. Il riavvio da 277 s **non** viene dalla cache su
  disco (TTFT43 M). Politica: RAM = sessioni vive, D: = sessioni ferme da >10 s e prefissi di sistema.
- VRAM degli slot: ogni slot costa 0,36 + 0,66 GiB (M); con `--kv-resident 16384`, stato GDN fp16 e chiavi
  dell'indexer in streaming si dimezza (S) → 8 slot senza perdere il 25% degli esperti residenti.

### 3f. Prefill più veloce per pezzo

- Sulla 2080 Ti: `STRATA_HC16_SM75=1` o `STRATA_BF16_TC=1` (fase "hc read" −71%, prompt 131k +17%, M, non bitwise);
  caricamenti degli esperti pinned invece che pageable (11,4 GB/s pageable, M); `STRATA_PREFILL_CPU_SHARE=auto`
  (−12% a 1k, M); `--short-read 256` (M); `STRATA_SM75_PERF=1` prompt (+30% dichiarato upstream, D); PLE in RAM
  (`--ple-io ram`, 26,8 GB, non misurata).
- Stima: fisso per pezzo da 1-1,5 s a ~0,8-1 s, pendenza da 1,5-2,9 ms/token a ~1 (S): letture corte 2× più veloci.

### 3g. Stima cumulativa (S; agenti = aggregato nel mix reale a R/G ≈ 10)

| passo | 3 agenti | 8 agenti | decode puro 4 chat |
|---|---|---|---|
| oggi (G2 + 16 posti + CONCURRENT) | 29 (M) | 30 (M) | 85 (M) |
| + 3e RAM + 3f leve env | 33-38 | 35-40 | 85 |
| + 3a pacchi con decode accanto | 45-50 | 55-65 | 85 |
| + 3b MTP nei gruppi | 55-62 | 60-70 | 100-112 |
| + 3d senza copia | 60-70 | 70-85 | 100-112 |
| + 3c kernel batch + 3e slot leggeri | **85-105** | **120-150** | **140-180** |

## 4. Piano a tappe

Ogni tappa ha una misura di accettazione sul banco `agents` (B-A-B di notte, PC fermo, `bench.lock`, cache fissa per
i confronti di testo). "Sonnet stanotte" = config, harness, misure, porti opt-in già scritti; "con cura" = codice del
motore con parità da dimostrare (Opus o umano).

| # | tappa | misura di accettazione | t/s attesi (agenti 3 / 8) | giorni | rischio | chi |
|---|---|---|---|---|---|---|
| **0** | **Banco agenti reale**: scenario `agents:3:R` in `mc2.py` (prefisso comune 30k, storie 30-100k per agente, tool result 1-5k casuali, G 100-400, pausa tool 1-3 s, 6 turni; metriche: aggregato, quota prefill del wall, TTFT p50/p90, righe/s durante le letture, tok/s di lettura) + `bab_verdict` che scarta i bracci disturbati (stage L01 > 0,6 ms, PLE blocked > 300 ms) | il banco gira due volte con ±5% | — (strumento) | 0,5-1 | basso | **Sonnet stanotte** |
| **1** | **Config per le sessioni con agenti**: `--batch 4 --batch-groups 2 --conversation-cache-mib 28672 --conversation-cache-slots 16 --short-read 256`, `STRATA_PIPED_CONCURRENT=1`, `STRATA_PREFILL_CPU_SHARE=auto`, `STRATA_SLOT_EXPIRE_S`; bracci `--kv-resident 16384`, `STRATA_PIPED_READ_PIECE`, `STRATA_PREFILL_HELP=1` | B-A-B contro `c-conc` | 33-38 / 35-40 (S) | 0,5 | basso (solo config, non nel Daily: chat singola −10%) | **Sonnet stanotte** |
| **2** | **Rimisura pulita delle leve già portate** contaminate il 18/10: `STRATA_PACK_PREFILL=3`, `STRATA_BATCH_PIPELINE=1`, `STRATA_PIPED_MTP=1` (`--batch 2/4 --batch-mtp`), `STRATA_HC16_SM75=1` / `STRATA_BF16_TC=1` sul prefill delle code corte, `STRATA_SM75_PERF=1` | ogni leva con un controllo alternato, 2 corse per braccio | decide le tappe 3-5 | 1 (notte) | basso | **Sonnet stanotte** |
| 3 | **Prefill corto più veloce** (3f): leve env promosse dalla tappa 2 + caricamenti pinned sulla 2080 Ti + `STRATA_PREFILL_LAYER_TIMES` per i 200 ms di "hc read" fissi | TTFT a 1k da 4,5 s a ≤ 3,2; 3k da 7,7 a ≤ 5,5 | 40-48 / 45-55 (S) | 2-4 | medio (non bitwise sul prompt: KL da misurare) | Sonnet con revisione |
| 4 | **Pacchi con decode accanto** (3a): `STRATA_PACK_PREFILL` + `PIPED_CONCURRENT` insieme, chunk in pipeline fra gli stadi, hint per tutte le richieste in attesa, correzione della regressione a 8; parità dei logit a cache fissa contro letture separate | letture di 3-4 code: −45% (M oggi −41% a 4); `agents:8` non peggio di `agents:4` | 45-55 / 55-65 (S) | 3-5 | medio-alto (parità) | con cura |
| 5 | **MTP nei gruppi con catena in batch** (3b): partire da #2985 se la tappa 2 lo conferma; poi catena batched e corta | `same:4`/`diff:4` ≥ 105; `agents:3` +10-15% | 55-62 / 60-70 (S) | 7-12 | alto (verify/generate/resident_slots) | con cura |
| 6 | **Prefisso e ammissione senza copia** (3d): lettura nella sessione dello slot; K/V e chiavi in CoW fra slot | turno a 100k: −1,5 s; `copy_to_slot` sparisce dal log | 60-70 / 70-85 (S) | 7-10 | medio | con cura |
| 7 | **Slot leggeri + disco** (3e): `--kv-resident`, GDN fp16, indexer in streaming; `STRATA_CONV_DISK` su D: con avvio misurato | 8 slot con esperti residenti −10% invece di −25%; riavvio ≤ 90 s | abilita 8 agenti | 3-5 | medio | Sonnet (misure) + con cura (fp16) |
| 8 | **Kernel batch per byte** (3c): esperti lato pesi a tile, hc/MMVQ multi-riga, top-k multi-CTA fra righe | finestra a 8 righe ≤ 45 ms; bitwise a T=1 | 85-105 / 120-150; decode puro 4 chat 140-180 (S) | 20-30 | alto | con cura, un kernel alla volta con B-A-B |
| 9 | Sarathi (righe di decode nel pezzo di prefill) | solo se dopo la 4 il decode resta fermo durante i pacchi | +5-10% (S) | 15-20 | alto | rimandata |

Ordine: 0 → 1 → 2 (stanotte) → 3 → 4 → 5 → 6 → 7 → 8. Le tappe 3 e 4 sono il grosso del guadagno sul carico agenti
(prefill); 5 e 8 sono quelle del decode puro. Dopo la tappa 4 il banco dirà se il tetto reale è 50 o 70: se le letture
impacchettate non scendono sotto ~1 ms/token, la 8 non cambia il verdetto sugli agenti e va fatta solo per il decode
puro.

### Cosa resta fuori e perché

- Tensor-parallel al posto del layer split: ~96 scambi da ~50 KB per finestra sull'Oculink (~2 ms) e motore da
  riscrivere; verdetto PIPELINE2 §9: pari a oggi con MTP. Non cambia con il batch.
- Tutti gli esperti in VRAM: 42 GB di blob contro 34 GB di VRAM totale, di cui ~15 per densi, K/V e slot. Non si fa
  con questa coppia di schede.
- Cambio della 3060: escluso dall'owner.

## 5. Limiti di questa analisi

- Le unioni degli esperti per N righe sono dal modello uniforme (U(R)); la misura diretta per chat diverse non c'è
  (il log del batch conta i lookup, 78 per layer-finestra a 6,93 righe, non gli esperti distinti).
- Il costo della catena MTP in batch (132 + 78 MB per sessione a passo) è dedotto dalle taglie dei tensori del
  drafter; nessun kernel batched della catena esiste oggi.
- Le misure del 18/10 dopo le 18:22 sono contaminate (CPU al 100% per i `node` di Codex): `PIPED_MTP`, `BPIPE`,
  `PACK` vanno rimisurati (tappa 2) prima di promuoverli o bocciarli.
- R/G ≈ 10 viene dal banco e dall'uso reale del Daily (46% prefill): con risposte lunghe (report finali) il tetto
  del mix sale verso quello del decode puro.
- Le percentuali di banda usano i valori nominali (360/616 GB/s); quelle effettive sono ~85-90% → le "efficienze" vere
  sono ~10% più alte di come scritte.
