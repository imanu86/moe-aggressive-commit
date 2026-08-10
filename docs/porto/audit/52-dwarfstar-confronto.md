# 52 — DwarfStar (antirez/ds4): i loro numeri, la loro configurazione, il confronto onesto (10 agosto 2026)

**Verdetto in tre righe.** (1) La premessa va corretta: il "~25 t/s su M3 Ultra" era in realtà **26,68 t/s su MacBook Pro M3 *Max*** al lancio (7/5); l'M3 Ultra faceva **36,86** (prompt corto) e **27,39** (prompt 11.709 tk), e oggi la testata è **39,35 su M5 Max**. (2) **Tutti i loro numeri di punta sono a modello interamente residente** in memoria unificata (273–1.792 GB/s verso i pesi): nessuno è nel nostro regime. (3) Il confronto a parità di *specie* di metrica regge (il loro `generation` è decode-only come il nostro), e nei due punti dove il regime si avvicina al nostro — il loro streaming su Mac (12,16 t/s con cache 32 GB su banda 546 GB/s) e la loro via CUDA su 12 GB VRAM (0,66–2,60 t/s) — **il nostro 13,23 sta sopra o alla pari con 1/27–1/40 della banda**. Il divario vero, tutto a loro favore, è il **prefill** (826 t/s perfino a 273 GB/s, contro il nostro 20).

Metodo: regola [[external-posts-read-their-config]] — per ogni numero, la LORO configurazione letta per intero. Marcature: **[loro]** = loro-riportato testuale; **[dedotto]** = mio calcolo/deduzione; **[utente]** = dichiarato dall'utente nel mandato; **[mancante]** = non trovato. Meccanismi e cosa portare: già coperti dall'audit `DWARFSTAR.md` (9/8) — qui solo numeri, configurazioni e confrontabilità.

---

## 1. Cos'è e da dove veniamo

`github.com/antirez/ds4` ("DwarfStar 4"), motore di inferenza in C di Salvatore Sanfilippo, pubblicato il **7 maggio 2026**, dedicato a **DeepSeek V4 Flash** (284B MoE, ~13B attivi **[loro]**) con supporto PRO e GLM 5.2. Metal è la piattaforma primaria; CUDA e ROCm sono porte successive. Il nostro repo è un fork al commit zero (`d997b56`, 7/5): il nostro backend CUDA/Windows e il loro sono **due porte indipendenti** dello stesso motore Metal (verificato nell'audit DWARFSTAR §1). Oggi il nostro banco è llama.cpp con op custom, quindi anche la base di misura è diversa.

## 2. Il modello è LO STESSO file: l'àncora di parità più forte

Il loro "q2" **è il nostro GGUF**: routed experts gate/up in **IQ2_XXS**, down in **Q2_K**, attention/shared/output in **Q8**, imatrix — **80,76 GiB** [loro, tre fonti indipendenti: README ("2-bit … already 81GB"), issue #437 ("q2: 80.76 GiB"), articolo RTX PRO 6000 ("model tensor cache 80.76 GiB")]. Coincide col nostro 80,76 GiB a 2,44 bpw **[utente]**. Quindi: **stessa qualità di modello, stessi byte da muovere per token** — ogni differenza di t/s è ferro + runtime, non modello.

## 3. I loro numeri, ciascuno con la SUA configurazione

### 3.1 Tabella di lancio (README al commit di fork `d997b56`, 7/5 — letta sul clone locale `D:\ds4_work\promo0033_clone`, testuale)

Configurazione dichiarata **[loro]**: *"single-run Metal CLI numbers with the q2 GGUF, `--ctx 32768`, `--nothink`, greedy decoding, and `-n 256`"*. Prompt corto = piccola storia italiana; prompt lungo = 11.709 token. **Una sola run** (contro il nostro protocollo n≥3). Modello interamente residente in memoria unificata. Speculazione: il README di lancio la dichiara sperimentale e *"at most a slight speedup, not a meaningful generation-speed win"* → **i numeri sono senza speculazione**.

| Macchina | Banda unificata | Prompt | Prefill | Generation |
|---|---|---|---:|---:|
| MacBook Pro M3 Max, 128 GB | 400 GB/s [dedotto, spec Apple] | corto | 58,52 | **26,68** |
| MacBook Pro M3 Max, 128 GB | 400 GB/s | 11.709 tk | 250,11 | 21,47 |
| Mac Studio M3 Ultra, 512 GB | 819 GB/s [dedotto, spec Apple] | corto | 84,43 | **36,86** |
| Mac Studio M3 Ultra, 512 GB | 819 GB/s | 11.709 tk | 468,03 | 27,39 |

**Correzione della premessa**: il ricordo "~25 su M3 Ultra" corrisponde al **26,68 dell'M3 Max** (il titolo di lancio era "26 t/s"); l'Ultra fa di più. Il divario onesto contro Apple residente è **2–3×**, non "meno del doppio" — ma vedi §6: il rapporto di banda resta 20–40× a loro favore.

### 3.2 Benchmark attuale (README `main`, aggiornato 5/8) — metodologia migliore della loro di lancio

Configurazione dichiarata **[loro]**: strumento `ds4-bench`, input *I Promessi Sposi*, prefill incrementale a passi di **2.048 token** (chunk 2048, contro il default 4096), **128 token greedy per frontiera**, misura **istantanea alla frontiera di contesto, non media cumulativa** (*"instead of reporting one whole-run average"*). Speculazione **spenta** (DSpark opt-in, non nei numeri). Modello q2 residente.

| Macchina | Backend | ctx | Prefill | Generation |
|---|---|---:|---:|---:|
| MacBook Pro M5 Max, 128 GB | Metal | 2.048 | 790,18 | **39,35** |
| MacBook Pro M5 Max, 128 GB | Metal | 16.384 | 572,53 | 36,14 |
| MacBook Pro M5 Max, 128 GB | Metal | 32.768 | 557,04 | 34,36 |
| MacBook Pro M5 Max, 128 GB | Metal | 65.536 | 398,50 | 27,64 |
| DGX Spark GB10, 128 GB | CUDA | 2.048 | 825,76 | **18,05** |
| DGX Spark GB10, 128 GB | CUDA | 16.384 | 872,44 | 15,10 |
| DGX Spark GB10, 128 GB | CUDA | 32.768 | 855,94 | 14,43 |
| DGX Spark GB10, 128 GB | CUDA | 65.536 | 822,98 | 13,84 |

Banda M5 Max: **[mancante]** — non verificata da me (M4 Max era 546 GB/s; M5 Max presumibilmente ≥). DGX Spark GB10: **273 GB/s** [loro: antirez su X dichiara "270GB/sec"; ai primi test privati faceva 12 t/s, oggi 18]. Nota di metodo: la loro misura "istantanea alla frontiera" è concettualmente la NOSTRA regola ([[misura-il-regime-non-la-media]]) — su questo sono arrivati dove siamo noi, e meglio di llama.cpp che riporta il cumulativo.

### 3.3 PRO (fuori parità: modello più grande)

Mac Studio M3 Ultra 512 GB, PRO q2, ctx 32.768: **138,82 prefill / 9,56 generation** [loro, tabella legacy]. Citato solo perché è la fonte probabile del "10–13 t/s del PRO" che gira negli articoli.

### 3.4 GPU discreta grande, tutto in VRAM (articolo community loftllc, RTX PRO 6000 Blackwell)

Configurazione dichiarata **[loro]**: RTX PRO 6000 Blackwell 96 GB GDDR7 (**1.792 GB/s**), host EPYC 755 GiB RAM, **modello interamente in VRAM** (picco 93,1/95,6 GiB), stesso GGUF q2 da 80,76 GiB, greedy, KV su disco attivo, niente speculazione, build `cuda-generic` dichiarata alfa.

| Condizione | t/s |
|---|---:|
| Generazione corta (~100 tk prompt) | 43,6 |
| ~400 tk generati | 41,7 |
| 4.058 tk generati (media) | 38,5 |
| ctx 20k / 33k / 50k | 36,3 / 35,3 / 31,4 |
| Prefill 13k–30k+ tk | 267 → 245 |

### 3.5 Il LORO streaming quando il modello NON è residente (issue #437, M4 Max 128 GB — la loro curva di capacità)

Configurazione dichiarata **[loro]**: Metal, Flash **q2 80,76 GiB** e q4 153,33 GiB, `--ssd-streaming-cache-experts` a 8/16/32/64/80 GB; "nommap" = miss letti davvero dall'SSD (senza aiuto della page cache). Banda unificata 546 GB/s [dedotto, spec Apple M4 Max].

| Config (q2) | Prefill | Generation |
|---|---:|---:|
| **Residente (non-streaming)** | 261,0 | **22,80** |
| Streaming mmap, cache 32 GB | 249,3 | 19,29 |
| Streaming nommap, cache 8 GB | 206,5 | 4,52 |
| Streaming nommap, cache 16 GB | 210,1 | 6,54 |
| Streaming nommap, cache 32 GB | 214,6 | **12,16** |
| Streaming nommap, cache 64 GB | 215,9 | 19,57 |
| Streaming nommap, cache 80 GB | 215,2 | 19,92 |

È la **stessa forma della nostra curva di capacità** ([[capacity-curve-vram-wall]]): la generazione scala con la cache, il prefill quasi no. E dà il prezzo che *loro* pagano quando escono dalla residenza: da 22,80 a 12,16 con cache 32 GB **pur avendo 546 GB/s e NVMe Apple**.

### 3.6 La LORO via su 12 GB di VRAM — il nostro regime, casa loro (issue #629 e #732)

Configurazione dichiarata **[loro]**: RTX 3500 Ada laptop **12 GB VRAM**, **31 GB RAM**, NVMe, CUDA 13, stesso GGUF IQ2_XXS 80 GB, ctx 256 e 2.048, greedy. Attenzione alla differenza di regime: con 31 GB di RAM il modello NON sta in RAM — i miss vanno all'**SSD**, non alla RAM come da noi.

| Config | Generation | Note |
|---|---:|---|
| Upstream baseline, ctx 256 | 0,84 | |
| Upstream baseline, ctx 2.048 | 0,66 | |
| Con cache esperti host proposta dall'autore, ctx 256 | 2,60 | hit 72–82% [loro] |
| Con cache, ctx 2.048 | 1,09 | |
| Prefill (ctx 2.048) | 9,28 | **più lento del nostro 20** |

E issue #732 (stessa classe di macchina, `--cuda --ssd-streaming`): il tier MMQ del prefill va **OOM su 12 GB** (`moe down mmq 1792 MiB`, contabilità "32 GiB cached" su una scheda da 12), workaround `DS4_CUDA_MMQ=0`. **La loro via CUDA a poca VRAM è immatura per loro stessa ammissione** (nessun numero ufficiale nel README sotto 48 GB di VRAM: [mancante]).

### 3.7 Speculazione (DSpark) — spenta nei loro numeri, e quanto rende dove è accesa

- **Upstream [loro]**: opt-in (`--mtp … --dspark`), bozza ~5,6 GiB, propone **fino a 5 token** (= il nostro block_size 5), confidenza default 0,6 Metal / 0,7 CUDA. Al lancio: *"at most a slight speedup"*. Con l'identità bit-esatta ripristinata via replay (issue #731): **−35% netto** — la correttezza si mangia tutto il guadagno.
- **Fork Entrpi `ds4-on-spark` (DGX Spark) [loro]**: DSpark fast-accept con guardia di break-even: suite 9 carichi, 512 tk × 3 run, wall clock: **20,1 → 27,7 t/s medio (1,38×)**, accettazione 58–91%, 2,18–4,00 token/passo; il creativo va a 0,96× (perde). Decode liscio senza speculazione: 20,0 t/s @2k.
- **Noi**: la speculazione rende **+8%** oggi ([[dspark-97-percento-esperti]]: 73 ms di bozza CPU a GPU ferma). Il loro 1,38× su Spark è la prova d'esistenza che il drafter può pagare — ma su macchina **residente**, dove la verifica non attraversa il confine MoE-CPU che è il nostro collo ([[dspark-collo-verifica-moe-cpu]]).

## 4. Come misurano loro, come misuriamo noi

| Aspetto | Loro | Noi | Confrontabile? |
|---|---|---|---|
| t/s decode | Decode-only: legacy = media su `-n 256`, 1 run; attuale = istantaneo alla frontiera, 128 tk greedy | Media escluso il prefill, n token dichiarato (es. 1.200) | **Sì in specie** — entrambi escludono il prefill |
| Prefill | Riportato a parte, per chunk incrementale 2.048 | Riportato a parte (20 t/s) | Sì |
| Campionamento | Greedy, `--nothink` | Da dichiarare accanto al nostro numero quando si pubblica | Da allineare |
| Numero di run | **Single-run dichiarato** (lancio); bench attuale non dichiara n | n≥3, mediana, QUIETE=300 | Loro sotto il nostro standard |
| Contesto | Dichiarato per riga (2k–65k) | Da dichiarare per il 13,23 | Da allineare |
| Contenuto | Promessi Sposi / storia italiana | Banco chat con template (dal 8/8) | Diverso ma entrambi dichiarati |
| Speculazione | **Spenta** in tutti i numeri ufficiali | Presente nel nostro stack (topk=1) | **Da dichiarare**: se il 13,23 include la speculazione, va detto accanto |

Conclusione di metodo: **il confronto è lecito in specie ma va fatto per riga di regime**, e accanto al nostro numero vanno dichiarati: contesto, n token, campionamento, speculazione on/off.

## 5. La tabella di confronto a parità dichiarata

Stesso GGUF (80,76 GiB IQ2_XXS/Q2_K/Q8) su tutte le righe. "Banda pesi" = banda del percorso che serve i pesi al motore di calcolo.

| Sistema | Banda pesi | Residenza | ctx | Spec | Decode t/s | Prefill t/s | Provenienza |
|---|---:|---|---:|---|---:|---:|---|
| **Noi: RTX 3060 12 GB + 96 GB RAM** | ~19,8 GB/s PCIe (+cache VRAM 360 GB/s) | NON residente: esperti in RAM bloccata, cache in VRAM | da dichiarare | nostro stack | **13,23** | 20 | [utente] |
| MacBook M3 Max 128 GB (lancio) | 400 GB/s | residente | 32.768 | no | 26,68 / 21,47 (corto/11,7k) | 58,5 / 250,1 | [loro] |
| Mac Studio M3 Ultra 512 GB (lancio) | 819 GB/s | residente | 32.768 | no | 36,86 / 27,39 | 84,4 / 468,0 | [loro] |
| MacBook M5 Max 128 GB (attuale) | [mancante] (≥546?) | residente | 2k→65k | no | 39,35 → 27,64 | 790 → 399 | [loro] |
| DGX Spark GB10 128 GB (attuale) | 273 GB/s | residente | 2k→65k | no | 18,05 → 13,84 | 826 → 823 | [loro] |
| DGX Spark, fork Entrpi | 273 GB/s | residente | 2k / 48k | no / DSpark | 20,0 / 17,7 · con spec 27,7 medio | ~960–1.010 | [loro] |
| RTX PRO 6000 96 GB (community) | 1.792 GB/s | residente in VRAM | corto→50k | no | 43,6 → 31,4 | 267 → 245 | [loro] |
| M4 Max 128 GB, streaming nommap cache 32 GB | 546 GB/s + SSD sui miss | NON residente | [non dich.] | no | **12,16** | 214,6 | [loro] |
| RTX 3500 Ada 12 GB + 31 GB RAM | PCIe + **SSD sui miss** | NON residente | 256 / 2.048 | no | 0,84–2,60 | 9,28 | [loro] |
| **Il nostro regime esatto (12 GB VRAM + modello tutto in RAM) da loro** | — | — | — | — | **[mancante]** | **[mancante]** | — |

Letture oneste della tabella **[dedotto]**:

1. **Contro Apple residente**: 13,23 vs 27,4–36,9 (M3 Ultra) = noi al **36–48%** del loro throughput con **1/40 della banda** verso i pesi. Contro M5 Max: al 34–48%. Il "meno del doppio" della premessa non regge sui numeri corretti (è 2–3×), ma l'argomento di fondo si rafforza: per unità di banda siamo un ordine di grandezza sopra.
2. **Contro DGX Spark residente (273 GB/s)**: 13,23 vs 13,84–18,05 = **73–96%, quasi parità** con una macchina a memoria unificata interamente residente da ~€4.000 [dedotto, listino ~$3.999].
3. **Contro il LORO streaming** (l'unica riga dove anche loro pagano i miss): 13,23 **batte** il loro 12,16 su M4 Max con cache 32 GB — noi con cache VRAM ~2,8 GiB [dedotto: ~371 slot × ~7,5 MiB] e miss a 19,8 GB/s, loro con cache 32 GiB e miss su SSD. I regimi non coincidono (i loro miss vanno a disco, i nostri in RAM), ma è il confronto più vicino che esista.
4. **Contro la loro via 12 GB VRAM**: 13,23 vs 0,66–2,60 = **5–20×** — con l'avvertenza che loro avevano 31 GB di RAM (SSD-bound). Resta il fatto: **upstream non ha alcun numero, né via matura, nel nostro regime** (12 GB VRAM + modello in RAM). Su quello siamo da soli, ed è coerente con la caccia esterna del 9/8 (nessuna cache MoE senza nucleo caldo allo stato dell'arte).
5. **Nessuno satura la banda** [dedotto]: ~13B attivi a ~3–3,5 bpw effettivi sul percorso attivo ≈ 5–5,7 GB/token → tetto teorico M3 Ultra ~150–160 t/s, fanno 27–37 (≈20%); Spark ~50–65, fanno 14–18 (≈25–30%). Anche loro sono orchestration-bound, non byte-bound — conferma esterna del nostro [[orchestration-bound-not-byte-bound]].

## 6. Il punto che vale più di tutti (regola 4 del mandato)

**I numeri su hardware a poca VRAM esistono ma sono i più deboli di tutto il loro corpus**: una issue community con 31 GB di RAM (0,84–2,60 t/s), una issue di OOM sul prefill tier, zero righe ufficiali nel README sotto 48 GB di VRAM. Il numero che varrebbe il confronto perfetto — **12 GB VRAM + 80,76 GiB interamente in RAM di sistema — da loro non esiste**. Chi vuole quel regime oggi passa da noi. (Corollario pratico: la issue #629 con la sua cache host a 2,60 t/s è anche il segno che la domanda esiste.)

## 7. Le tre cose che loro fanno e noi no — con quanto possono valere da noi

1. **Prefill per strato in streaming, kernel fusi** — loro **826 t/s perfino a 273 GB/s** (Spark) e 206–216 t/s *anche in streaming* su Mac; noi **20**. Il prefill non è questione di banda: è disegno (strato intero, N+1 caricato dietro il calcolo di N, cache mai sfrattata in prefill, chunk 2–4k). Valore da noi: è il bersaglio 10–100× dello studio prefill già deciso — con la taglia da rifare per 12 GB (il loro tier MMQ va OOM proprio lì, #732; aritmetica in audit DWARFSTAR §4.4). **La leva più grande di tutto il confronto.**
2. **KV su disco per hash del prefisso** (con logits nel checkpoint, riuso fra riavvii e fra quant 2/4 bit) — a 105k il nostro re-prefill costa **82 minuti a riavvio**; per un agente stile Claude Code (prompt iniziale ~25k, loro lo dicono esplicitamente) è la differenza fra usabile e no. Valore: enorme in pratica, zero sul t/s di targa. Da verificare se nel nostro porto è quasi-solo-configurazione (`--slot-save-path`, audit §4.3).
3. **Speculazione con guardia di break-even (fork Spark): 1,38× medio, 0,96× sul caso peggiore, auto-quench** — contro il nostro +8%. Il valore da noi è **condizionato**: il loro guadagno vive su macchina residente; il nostro collo è il costo bozza/verifica attraverso il confine CPU (73 ms a GPU ferma). Se la bozza passa su GPU con esperti mappati (cantiere già aperto) e si aggiunge la guardia adattiva, il margine teorico è la forbice fra +8% e +38%: **fino a ~3–4 t/s sul nostro 13,23** [dedotto, tetto ottimista — da simulare prima, regola [[simulatore-router-sceglie-le-leve]]].

(Quarta, minore ma quasi gratis: hotlist per dominio + seed della cache durante il prefill — già prima nell'ordine consigliato dell'audit DWARFSTAR §7.)

## 8. Cosa abbiamo noi che loro non hanno

1. **Il regime stesso**: modello non residente su GPU consumer 12 GB a 13,23 t/s — la loro via equivalente fa 0,66–2,60 t/s ed è dichiarata immatura. Cache esperti in VRAM con LRU+pin (45,2% di colpi), zero-copy dalla RAM bloccata, prefetch sul DMA.
2. **Il ramo CPU come motore di calcolo in overlap** (34% del nostro t/s): da loro la CPU trasporta, mai calcola. Su memoria unificata non serve; nel nostro regime è un terzo della velocità.
3. **Porta Windows nativa** (upstream: [mancante], nessun port ufficiale).
4. **Disciplina di misura**: n≥3 con mediana, QUIETE fra bracci, cancello SHA, banco col contenuto dichiarato — i loro numeri di targa sono dichiaratamente single-run. (La loro misura "istantanea alla frontiera" è invece un punto dove ci hanno raggiunto per via indipendente.)
5. **Bozza con visibilità stabile dei pesi** (esperti in RAM mappata): la loro bozza sotto streaming propone token sbagliati al 100% (issue #724).

## 9. Costo per token al secondo (indicativo)

| Sistema | Costo | Decode | €/(t/s) |
|---|---:|---:|---:|
| **Noi (3060 + 96 GB)** | ~€1.000–1.200 [utente] | 13,23 | **~83** |
| DGX Spark 128 GB | ~€4.000 [dedotto] | 18,05 | ~222 |
| MacBook M5 Max 128 GB | ~€5.500–7.000 [dedotto] | 39,35 | ~150–180 |
| Mac Studio M3 Ultra 512 GB | ~€11.000+ [dedotto] | 36,86 | ~300 |
| RTX PRO 6000 workstation | ~€12.000+ [dedotto] | 43,6 | ~275 |

A parità di modello e di specie di metrica, siamo il **miglior €/(t/s) del quadro, di un fattore 2–3,5** [dedotto; prezzi indicativi, non quotazioni].

## 10. Cosa dichiarare accanto al nostro 13,23 quando lo si confronta in pubblico

Contesto e n token della misura; campionamento; speculazione on/off (i loro numeri sono TUTTI senza); "media escluso il prefill" esplicitato; n run e mediana. Con queste sei righe il confronto con qualunque loro riga è onesto; senza, è il tipo di confronto da cui questa regola è nata.

---

**Fonti.** README upstream `main` (benchmark 5/8, metodologia ds4-bench, streaming, DSpark): github.com/antirez/ds4 · README al commit di fork `d997b56` letto sul clone locale `D:\ds4_work\promo0033_clone` (tabella di lancio testuale, "single-run… `-n 256`") · issue #437 (streaming M4 Max, curve per budget) · issue #629 (RTX 3500 Ada 12 GB, 0,84→2,60 t/s, hit 72–82%) · issue #732 (OOM MMQ su 12 GB) · issue #731 (replay −35%) · fork github.com/Entrpi/ds4-on-spark (DSpark 1,38×, decode 20 t/s @2k) · loftllc.dev "DwarfStar 4 × RTX PRO 6000" (43,6→31,4 t/s, 80,76 GiB in VRAM) · antirez.com/news/165 ("A few words on DS4") · x.com/antirez (Spark "270GB/sec", 12 t/s ramo privato) · HN item 48050842 (lancio, "26 t/s M3 Max") · dwarfstar.sh. Interne: `DWARFSTAR.md` (audit 9/8, meccanismi e piano di porto), memoria [[external-posts-read-their-config]], [[capacity-curve-vram-wall]], [[orchestration-bound-not-byte-bound]], [[dspark-97-percento-esperti]].
