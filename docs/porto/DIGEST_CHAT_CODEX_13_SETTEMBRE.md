# Digest sessioni Codex CLI — 13 settembre 2026

Fonte: `C:\Users\imanu\.codex\sessions\2026\09\13\` (39 file `rollout-*.jsonl`, dalle 09:08 alle 20:31 locali, l'ultimo prosegue fino alle 06:40 del 14/9). Metodo: estrazione programmatica (Python, streaming riga per riga) dei soli messaggi `user`/`assistant` di tipo testo, scartando diff, output di strumenti e boilerplate di sistema (`<environment_context>`, `<skills_instructions>`, elenco plugin). Gli orari sono locali Europe/Rome (i nomi dei file rollout sono già in ora locale, verificato contro il timestamp UTC interno +2h).

## Come leggere questo digest — due tracce indipendenti

Le 39 sessioni appartengono a **due progetti diversi**, distinguibili dalla `cwd`/`workspace_roots` di ciascuna sessione:

- **Traccia A — DS4/DSpark** (`C:\Users\imanu\Documents\Codex\2026-08-26\dspark-20tps-replacement`): 34 delle 39 sessioni. È il filone "DeepSeek-V4 Flash + DSpark verso 20 t/s", **non** il repo `moe-aggressive-commit`. Sono quasi tutte sessioni di sub-agenti automatizzati di build/review (B56...B75) senza alcun turno umano reale: ogni sessione comincia con lo stesso rapporto upstream broadcast (identico testo ripetuto in più sessioni parallele) e procede da sola fino a un verdetto GO/NO-GO. Le riporto in forma sintetica perché il compito le include cronologicamente, ma **non contengono richieste dell'utente** né toccano i temi Qwen3.8/FreeToken richiesti.
- **Traccia B — Qwen3.8 / `moe-aggressive-commit`** (`C:\Users\imanu\Documents\Codex\2026-09-13\rip`, con permesso di scrittura esplicito anche su `C:\Users\imanu\source\repos\moe-aggressive-commit`): **5 sessioni** (10:45:42, 10:49:34, 10:49:42, 20:30:56, 20:31:47). È qui che vivono tutti i temi richiesti: divario cache 41%/75%, n-grammi/testa MTP, sparse FA, prototipo CPU/GPU FreeToken (`fused_cpu`), audit FreeToken/Bonsai, prefill 32k/131k, la strada verso 50 t/s/400 prefill. La sessione delle 10:45:42 è la "regia" con l'utente umano; le altre quattro sono sub-agenti economici delegati dalla regia stessa (vedi sotto "possibilmente usa agenti economici").

---

## Indice cronologico di tutte le 39 sessioni

| # | Ora locale | Dimensione | Traccia | Contenuto in una riga |
|---|---|---|---|---|
| 1 | 09:08:22 | 22,1 MB | A | Rapporto upstream 28/8–9/9 → freeze B56 (sparse FA+injection); poi audit B58 cache break-even (`h*` sconosciuto, gate Wilson LCB95>53,45%) |
| 2 | 09:08:29 | 22,9 MB | A | Stessi rapporti upstream (duplicato parallelo) → freeze B58.1 "causal staging" (build/test/review PASS, GO solo canary 128 token) |
| 3 | 09:08:34 | 4,4 MB | A | Freeze B56 + freeze B57 (radix TOP_K); banco bloccato da server Qwen esterno sulla porta GPU |
| 4 | 09:25:42 | 26,4 MB | A | Freeze B56 + catena di review indipendenti B58/B58.1/B58.2/B58.3 telemetry collector, **REVOKED più volte** per formule con falso PASS |
| 5 | 09:25:55 | 4,1 MB | A | Freeze B56 + audit statico B59 (PR ik_llama #2441 prefix pinning): **NO-DELTA** su P26/B52 |
| 6 | 09:37:38 | 11,8 MB | A | Audit ABA mailbox/staging-slot su `cache-esperti.cu`: difetto ABA trovato e corretto, poi nessun P0/P1 residuo |
| 7 | 10:44:51 | 3,8 MB | A | Freeze B56 + collector telemetria B58 congelato (screen-only, non un GO prestazionale) |
| **8** | **10:45:42** | **14,7 MB** | **B** | **Sessione principale/regia Qwen3.8 — vedi sezione dedicata** |
| **9** | **10:49:34** | **14,4 MB** | **B** | **Sub-agente economico: audit simulatore cache + ricerca esterna prefill/GDN/prefetch — vedi sezione dedicata** |
| **10** | **10:49:42** | **11,8 MB** | **B** | **Sub-agente economico: audit contatori CUDA/GGUF + matematica 50 t/s + protocollo A/B — vedi sezione dedicata** |
| 11 | 10:59:44 | 16,0 MB | A | Audit P0 genealogia B58.1 (NO-GO card); build B63 "DSpark draft context window": source/build PASS, runtime **NO-GO** |
| 12 | 10:59:47 | 3,2 MB | A | Audit P0 upstream PR #884 (correttezza CUDA su contesto lungo): **NO-DELTA 3/3** |
| 13 | 11:05:16 | 4,5 MB | A | Toolchain telemetria B58.2→B58.3: chiusi P0+5 P1, stato resta "re-review required / no bank" |
| 14 | 11:12:13 | 8,3 MB | A | Ricerca del file modello `DS4-0731-IQ2XXS.gguf` (SHA storico): **non trovato** nei percorsi locali, un candidato con stessa dimensione ma hash diverso escluso |
| 15 | 11:26:28 | 3,3 MB | A | Contratto B58.3 raccomandato (criteri di closure PDH/headroom, casi avversariali) |
| 16 | 11:31:04 | 8,0 MB | A | Continuazione B58.x/B63 (build/telemetria) |
| 17 | 11:49:19 | 8,7 MB | A | Continuazione B58.x/B63 (build/telemetria) |
| 18 | 12:03:52 | 4,3 MB | A | B65 "synthetic ceiling marker": **GO** con singolo fix P0 (marker visibile anche in `/slots` metrics-only) |
| 19 | 12:03:59 | 2,6 MB | A | Review indipendente B65: nessun blocker semantico |
| 20 | 12:05:52 | 35,6 MB | A | B64 "Codacus dual-chain" CPU/GPU: **source/build APPROVE, runtime NO-GO** |
| 21 | 12:19:47 | 35,8 MB | A | Review indipendenti multiple: B64 APPROVE source/build (P0=0,P1=0); B68 (multirow MoE fusion) rereview APPROVE con 1 P2 non bloccante |
| 22 | 12:23:02 | 3,3 MB | A | B66 "KV row ownership": porta PR upstream #27781 (MTP rileva KV condivisa via ownership celle), #27705 **NO-DELTA** |
| 23 | 12:42:19 | 1,5 MB | A | Review indipendente B66: APPROVE source/build, 1 P2 non bloccante |
| 24 | 12:48:41 | 2,6 MB | A | B67 = composizione B63+B65+B66: **PASS**, zero conflitti |
| 25 | 12:49:02 | 0,4 MB | A | Audit incrociato lineage/patch-id fra 4 worktree (B63-B66): coerente |
| 26 | 13:06:19 | 19,4 MB | A | B68 "multirow MoE fusion" (porta PR upstream batch 2/4/8): prima versione, poi corretta dopo review, infine congelata |
| 27 | 13:36:03 | 5,9 MB | A | Review indipendente B68 (prima versione): **CHANGES REQUIRED**, 4 P1 |
| 28 | 14:08:59 | 32,4 MB | A | B69 (composizione +B64) PASS; B70 (+B68) PASS; **B71 "NEGATIVE_ONE" NO-GO** (12 mismatch); B72 **GO**; B73 "CACHE_SLOTS" **NO-GO parziale**; B75 **NO-GO diagnostico** |
| 29 | 14:33:53 | 2,6 MB | A | Recap B69 + review indipendente B70: GO statico |
| 30 | 14:45:49 | 6,2 MB | A | Ispezione gate CUDA B70; diagnosi dei mismatch B71/B72: **non erano un bug**, l'oracolo confrontava kernel diversi (MMVF vs cuBLAS) |
| 31 | 15:07:49 | 2,4 MB | A | Conferma indipendente: i 12 mismatch B71 sono un difetto dell'oracolo di test, non del flag `NEGATIVE_ONE` |
| 32 | 15:21:41 | 6,8 MB | A | Piano B73 (`CACHE_SLOTS`) consegnato al thread principale, con oracolo corretto e ordine stop-first-fail |
| 33 | 15:34:08 | 13,1 MB | A | B74 (fixture CUDA reale multirow): **NO-GO GPU**, 3 P1 strutturali |
| 34 | 15:46:38 | 14,2 MB | A | Review indipendente B74: **NO-GO GPU** confermato (hash reachability non fail-closed, lineage non esatta) |
| 35 | 16:30:59 | 3,9 MB | A | Diagnosi B73/R4: il fallimento è una precondizione temporale della fixture, non un bug del percorso produttivo |
| 36 | 16:36:51 | 9,6 MB | A | Review B73→B75: **GO CUDA solo per il test diagnostico R4** (P0=0,P1=0) |
| 37 | 16:55:18 | 3,3 MB | A | Verifica finale ordine runtime R4: P0/P1/P2=0, "per questo perimetro CUDA autorizzabile" |
| **38** | **20:30:56** | **1,3 MB** | **B** | **Sub-agente: audit Bonsai (kernel CPU) — vedi sezione dedicata** |
| **39** | **20:31:47** | **10,1 MB** | **B** | **Sessione finale (ULTIMA): sub-agente audit FreeToken + review `fused_cpu` + gap review del piano — vedi sezione dedicata** |

Nota sulla Traccia A: nessuna delle 34 sessioni DSpark contiene un messaggio umano reale (solo il boilerplate automatico `<recommended_plugins>`); sono tutte orchestrate da un thread padre non incluso in questa cartella (`source_thread_id 01a0375e...`). Il filone produce artefatti in `C:\Users\imanu\Documents\Codex\2026-08-26\dspark-20tps-replacement\outputs\` (B56...B75), non nel repo `moe-aggressive-commit`, e riguarda DeepSeek-V4/DSpark, non Qwen3.8. Lo stato di chiusura a fine giornata: cache esperti CUDA (`CACHE_SLOTS`) resta **NO-GO** (B73/B75 falsificano solo la fixture, non abilitano la capability); dual-chain CPU/GPU (B64) resta **NO-GO runtime**; multirow MoE fusion (B68) e context-window DSpark (B63) restano **source/build APPROVE, runtime NOT RUN**. Nessuna dichiarazione di t/s in produzione su questa traccia nella giornata.

---

## Traccia B — le 5 sessioni Qwen3.8 / `moe-aggressive-commit` (dettaglio)

### Sessione 8 — 10:45:42, 14,7 MB — regia/orchestratore con l'utente

**1. Richieste dell'utente, in ordine:**

1. *(allegato `HANDOFF_13_SETTEMBRE.md`)* — **"ripartiamo da qua"**.
2. **"possibilmente usa agenti economici rimanendo il cervello dell'operazione"** — regola di metodo esplicita: Codex deve tenere diagnosi e decisioni, delegando le verifiche circoscritte a sub-agenti a basso costo (da qui nascono le sessioni 9 e 10).
3. **"ok bene! come portiamo questo modello verso i 50 t/s in generazione e prefill oltre i 400?"**
4. **"puoi consultare qualsiasi repo e fare ricerche! l'obiettivo è chiaro!"** — autorizzazione esplicita a cercare in repository esterni.
5. (alle 20:27) **"Quei 39 allora cosa sono se risposta libera mi da 25…? Ad ogni modo vediamo anche colibrì come sfrutta la cpu, potrebbe essere interessante"** — l'utente contesta l'ambiguità fra il numero 39 t/s (copia di codice) e i 25 t/s (prosa libera).
6. **"Ho sbagliato intendevo bonsai"** — correzione: non "Colibrì" ma **Bonsai**.
7. **"Anche freetoken sembra promettente su alcuni fronti"** — aggiunge FreeToken al confronto.
8. **"Sarebbe anche da verificare se il q4 vada più veloce del q3 per via della minor quantizzazione…almeno per la parte che resta in ram e viene usata su cpu"**
9. **"Potremmo usare un ibrido dove una parte è q4 e una parte q3 deciso durante il prefill per singolo turno, teniamo una parte di pesi attivati in q3 in vram e ram pinnata e una parte q4 ad uso esclusivo della cpu"** — proposta di riquantizzazione Q3→Q4 per la quota CPU.
10. **"No intendevo scaricare il q4"** — correzione: non riquantizzare, ma scaricare un GGUF Q4 già pubblicato.
11. **"Ma è un ipotesi, prima lavoriamo su freetoken e altre cose"** — decisione esplicita: **rinviare** l'ipotesi Q4/Q3 ibrido, dare priorità a FreeToken.
12. (alle 06:30 del 14/9) **"fai un piano fatto bene, tieni tutto documentato"**.

**2. Cosa ha fatto e concluso Codex:**

- **Divario cache 41% vs 75%**: prima verifica diretta (non stimata dal traffico PCIe) dà **75,6%** di colpi di cache; confronto completo su **36.913 piani GPU, zero differenze dal simulatore**; escludendo i primi 64 passi per cache, **75,55%**. Verdetto: **il 41% ricavato dal PCIe era una stima fuorviante**; ma **"resta da spiegare il traffico PCIe eccedente"** — punto lasciato esplicitamente aperto in questo messaggio (per la spiegazione trovata da un sub-agente parallelo, vedi Sessione 10). Due corse di riferimento: **24,68 e 24,85 t/s** (no MTP), testo identico byte per byte; poi replica con CUDA graph attivi confermata a **24,87–24,88 t/s**. Output: [`RIPRESA_CACHE_13_SETTEMBRE.md`](C:/Users/imanu/Documents/Codex/2026-09-13/rip/outputs/RIPRESA_CACHE_13_SETTEMBRE.md) + `cache_evidence.zip`.
- **Verso 50 t/s / 400 prefill**: target esplicito 50 t/s decode e >400 t/s prefill, con contesti corti, 32k e 250k per evitare risultati validi solo su un caso favorevole (250k **non è mai stato misurato** in questa sessione, resta obiettivo dichiarato).
  - Batch 4096: **410,48 t/s a 32.139 token** (78,36 s al primo token), contro **327,33 t/s** con batch 2048 (+25% circa); testo greedy diverso fra i due batch (qualità non riverificata).
  - Kernel DeltaNet (GDN) a blocchi: **~1,7× più veloce nel microbenchmark**, output/stati identici nei casi testati; integrato in binario sperimentale dietro flag.
  - **N-grammi accanto alla testa MTP**: trovato e corretto un bug nel draft n-gram (`ngram-simple` rifiutava bozze più corte della sequenza cercata; la config 12→2 non produceva mai bozza) — corretto passando a `ngram-map-k`. Con la correzione: **34,93 t/s** in copia di codice (676/684 token di bozza accettati, testo identico a MTP puro da 30,39 t/s); **33,85 t/s** in modifica di codice. Ma **sulla generazione libera la velocità scende da 27,3 a 22,8 t/s**: gli n-grammi non vengono adottati come impostazione generale, aiutano solo su compiti "a copia" (codice), non sul ragionamento libero.
  - Trasferimento asincrono degli esperti (overlap prefill/copy) + fix rollback n-gram (checkpoint da 2 stati invece di 1, +112,57 MiB VRAM): combinazione **39,19 t/s copia codice / 406,36 t/s prefill** (prima 34,93/342,19); **37,76 t/s** in modifica codice.
  - Prefill a contesto lungo con trasferimento asincrono: **414,83 t/s a 32k** (MTP attivo, cache vuota); **394 t/s a 84k** (~2 GiB VRAM liberi); **367 t/s a 120k**; **357,61 t/s a 131k completo**, con recupero **5/5** informazioni distribuite nel contesto (il riferimento storico a 131k era 294,95 t/s). Batch 8192 testato ma **fallito oltre 32k**: superava inizialmente 480 t/s poi crollava per esaurimento VRAM (riserva salita a 7,45 GiB) — sceso a batch 6144.
  - **Sulla risposta libera la nuova configurazione dà 25,08 t/s, sotto il riferimento 27,26 t/s**: i **50 t/s restano esplicitamente aperti**. Priorità indicata per avvicinarsi: verificare 4–6 token mantenendo il percorso CUDA veloce, migliorare riuso pesi Q6_K e accuratezza bozza; per >400 sul lungo, adattare il batch alla memoria disponibile.
  - Output: [`VERSO_50_TPS_400_PREFILL_13_SETTEMBRE.md`](C:/Users/imanu/Documents/Codex/2026-09-13/rip/outputs/VERSO_50_TPS_400_PREFILL_13_SETTEMBRE.md) + `speed_evidence.zip`.
- **FreeToken/Bonsai** (dopo la correzione utente "intendevo bonsai"): confronto — cooperazione CPU/GPU di FreeToken **funziona anche su Windows/RTX3060** (primitive di sincronizzazione verificate); cache: **replay a pari memoria dà 75,55% (nostra) contro 74,82% (LRU globale simulata)** — cambiare politica **non conviene**; compatibilità: **FreeToken non carica direttamente il Qwen GGUF** e non ha percorso CPU per IQ2_S/IQ4_NL (codice verificato: `cpu_executor.py#L71-L72`). Priorità individuata: **un esecutore CPU fuso per pochi esperti mancanti**, misurato mentre la GPU lavora, mantenendo la cache attuale. Output: [`FREETOKEN_BONSAI_13_SETTEMBRE.md`](C:/Users/imanu/Documents/Codex/2026-09-13/rip/outputs/FREETOKEN_BONSAI_13_SETTEMBRE.md).
- **Ipotesi Q4/Q3 ibrido**: l'utente propone prima una riquantizzazione Q3→Q4 (Codex nota che non recupera precisione e introduce errore), poi corregge in "scaricare un GGUF Q4 già pubblicato" — trovato **Unsloth UD-Q4_K_XL, ~111 GB**, percorso di salvataggio individuato (`C:\ds4-models\qwen38flashnext\UD-Q4_K_XL`) ma **download mai avviato**: l'utente chiede di rimandare e dare priorità a FreeToken. **Resta un'ipotesi aperta, non testata.**
- **Prototipo FreeToken CPU/GPU (`fused_cpu`)**: dopo il via libera utente ("Ok proviamo questa strada"), prototipo che riusa i kernel IQ2_S/IQ4_NL esistenti in un unico esecutore fuso. Primo confronto completo (copia pesi mancanti + calcolo esperti + trasferimento attivazione + somma) è **sfavorevole**: con 3 esperti mancanti, spostarne 1 sulla CPU porta il blocco da ~338 a 449 µs. Poi, usando **RAM pinnata mappata direttamente + callback** invece di copie esplicite: **2 esperti su CPU riducono un caso da ~263 a 184 µs**; risultato finale ripetuto: **con 3 esperti mancanti, 2 sulla CPU portano il blocco MoE da 337 a 242 µs (−28%)**. I blocchi con 1–4 miss sono **~62% del tratto caldo** nella traccia reale (dato confermato anche dal sub-agente, Sessione 10: istogramma miss/piano, miss 0-4 = 82,89% dei piani dopo warmup). Formati verificati: **47 dei 48 strati** (layer 2 ha gate/up IQ2_XS anziché IQ2_S). Il guadagno riguarda **solo il blocco MoE testato in isolamento**: serve ancora integrazione nel server + verifica con MTP per misurare l'effetto sui t/s reali. Output: [`FREETOKEN_IBRIDO_13_SETTEMBRE.md`](C:/Users/imanu/Documents/Codex/2026-09-13/rip/outputs/FREETOKEN_IBRIDO_13_SETTEMBRE.md) + `freetoken_ibrido_evidence.zip`.
- **Piano CPU/GPU per il 14/9**: 6 fasi — (1) congelare baseline e prompt; (2) correggere il contratto della cache (un esperto calcolato su CPU **non deve risultare residente in VROM/VRAM fittizia**); (3) integrare l'esecutore su un solo strato, senza MTP; (4) estendere al decode completo, calibrare core/esperti CPU; (5) aggiungere MTP, rollback, gestione errori; (6) verificare generazione libera/qualità/prefill, poi affrontare il divario residuo verso 50 t/s. Output: [`PIANO_CPU_GPU_14_SETTEMBRE.md`](C:/Users/imanu/Documents/Codex/2026-09-13/rip/outputs/PIANO_CPU_GPU_14_SETTEMBRE.md), [`PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md`](C:/Users/imanu/Documents/Codex/2026-09-13/rip/outputs/PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md), [`REGISTRO_CPU_GPU_14_SETTEMBRE.md`](C:/Users/imanu/Documents/Codex/2026-09-13/rip/outputs/REGISTRO_CPU_GPU_14_SETTEMBRE.md), pacchetto completo `piano_cpu_gpu_14settembre.zip`. **Stato dichiarato a fine sessione: "P0 da avviare; produzione invariata."**

---

### Sessione 9 — 10:49:34, 14,4 MB — sub-agente economico "coerenza del simulatore" (nessun utente umano)

Delegata dalla regia (Sessione 8) per l'audit del simulatore cache e per la ricerca esterna. Nessuna richiesta umana diretta; lavora su istruzioni ricevute dal thread padre.

**Cosa ha fatto e concluso:**

- **Audit codice simulatore vs CUDA**: `simula_cache.py:49-78` incrementa `step` prima di derivare l'epoca, mentre CUDA (`fork-moe-kernels.cuh:262-266`) usa il valore vecchio restituito da `atomicAdd` — uno scarto di un passo nel confine dell'epoca alla chiamata 64. **Quantificato**: epoca corretta **119.791 miss totali** (112.357 dopo step>64) contro epoca del vecchio simulatore **119.833 miss** (112.399 dopo step>64) — **differenza di 42 miss su 49.152 piani (~0,035%)**: **esclude** l'off-by-one come spiegazione del divario di 34 punti percentuali.
- **Sospetto principale identificato**: la qualità della traccia. `routes.bin` (49.152 record = 1.024 passi × 48 strati, `rows=1`) registra **solo decodifica greedy a un token**; la verifica MTP reale passa **fino a 3 righe** al planner CUDA (`moe-demand.cuh:163-190`), e quelle rotte a bozza sono **assenti dalla traccia**. I rifiuti possono alterare rotte successive ed evizioni. Confidenza: alta sui disallineamenti di codice, media che il solo mismatch di traccia spieghi tutti i 34 punti.
- **Audit prefill**: numeri Qwen registrati **337,21–337,92 t/s a 32k** e **294,95 t/s a 131k con sparse FA attiva** (sparse FA **inattiva/neutra a 32k**, fa risparmiare 80,4 s a 131k, **+18,1%** — attivazione risalente all'handoff, non rifatta in questa sessione). **400 t/s a 250k non è deducibile da questi dati** (la corsa sparse a 131k dura 445,1 s; 250k a 400 t/s durerebbe comunque 625 s). Tre esperimenti proposti in ordine: misurare Qwen reale a 250k con sparse FA on/off + `-ub 128/256/512`; profilare 2-3 ubatch a `ub512`; verificare/abilitare l'indexer fuso a contesto lungo.
- **Ricerca esterna** (autorizzata dall'utente): fork Strix Halo (`drluoto`) — row-id hoisting per 512 esperti (+19% a 8k, +16% a 32k) **non trasferibile**: CUDA locale ha già una compattazione di routing globale equivalente (`mmid.cu`). `thecodacus/fable5/prefetch-experts`: `GGML_CUDA_REGISTER_HOST=1` già presente localmente; `GGML_SCHED_PREFETCH_EXPERTS=1` (prefetch strato successivo su stream separato) **assente localmente**, ma non è drop-in per il workspace dinamico Qwen. Commit `964c6f2f0` (GDN a tile): idee trasferibili isolate (tile 16 token, staging condiviso q/k/v, riduzione shuffle) — preparato un probe CUDA standalone (compilazione riuscita solo dopo correzioni, mai eseguito su GPU). Fork `flashnext-hybrid`: il suo 50 t/s **dipende da un hybrid APU+RTX3090Ti**, non trasferibile 1:1; unico elemento utile isolato: PR upstream #28040 (lookup posizione ordinato invece di scan) — beneficio atteso piccolo a contesto corto.
- **Matematica dei 50 t/s** (in sessione 10, vedi sotto, ma coerente): decode attuale **~40 ms/token senza MTP (25 t/s)**, **~33,8 ms/token con MTP (~29,6 t/s)**; 50 t/s richiede **≤20 ms/token**, cioè **1,69× oltre il percorso MTP attuale o 2,0× oltre il no-MTP**.

---

### Sessione 10 — 10:49:42, 11,8 MB — sub-agente economico "affidabilità dei contatori" (nessun utente umano)

Seconda delega parallela della regia, per l'audit dei contatori CUDA/PCIe e per completare la ricerca esterna e il protocollo A/B finale.

**Cosa ha fatto e concluso:**

- **Audit contatori cache**: `plan->n_unique`/`plan->n_misses` (`fork-moe-kernels.cuh:428-435`) sono logicamente corretti. `LLAMA_MOE_HIT_REPORT` è basato su chiamate host e **durante il replay dei CUDA graph normali non avanza** (solo in warmup/capture/rebuild) — spiega perché il report non compariva dopo centinaia di token. Il `cudaMemcpy` sincrono dentro il report (`moe-demand.cuh:228-229`) è **pericoloso durante stream capture** (può generare `cudaErrorStreamCaptureUnsupported`).
- **Spiegazione quantitativa del traffico PCIe residuo** (il punto lasciato aperto dalla regia in Sessione 8): parsing solo-metadati dei tre shard GGUF conferma payload totale **76,3226 GiB**, esperti **45,2881 GiB**/144 tensori, `per_layer_token_embd` **26,8222 GiB** (spiega esattamente i 27.465,95 MiB CPU osservati, ma pesa solo ~1.440 B/token, non spiega centinaia di MB). Trasferimento esperti misurato **~232,5 MB/token**, coerente con i contatori diretti (~24,4% di miss, cioè **~75,6% di hit** — combacia con la Sessione 8). Il residuo di **~308 MB/token** è spiegato come lettura della **cache K/V mappata ad attenzione piena su contesto lungo**: 12 strati ad attenzione piena × 1.024 B/token/strato × ~26k contesto ≈ 305 MiB/token, **coerente con il residuo osservato**. Conclusione esplicita: **"il 300 MB/token gap è quantitativamente spiegato dalla storia di attenzione mappata a contesto lungo"** — ma questa spiegazione è un'analisi statica sui metadati GGUF/codice, **non una nuova misura empirica riconciliata con la stima PCIe originale**; è per questo che il documento `RIPRESA_CACHE_13_SETTEMBRE_CODEX.md` la riporta come **non confermata definitivamente**, mentre la sessione regia (8) l'aveva lasciata esplicitamente aperta.
- **Matematica 50 t/s**: confermata come sopra (serve ≤20 ms/token). Constraint hardware: RTX 3060 12 GB **non può contenere il modello** (45,29 GiB esperti + 26,82 GiB tensore PLE sono intrinseci); il 50 t/s **richiede vera accettazione/speculazione multi-token o un guadagno di kernel/posizionamento vicino a 2×**, nessuna prova che i soli contatori di cache lo diano.
- **Ricerca esterna aggiuntiva**: PR #28040 (posizione ordinata predecessori PLE) — misura upstream +4,9% a 71k, maggiore a 132k, **prefill invariato**; a contesto corto (867 token) **improbabile spieghi un 2× sul decode**. PR #28023 (QSA indexer senza `ggml_cont`) — solo prefill (+9% upstream), non decode. Gather probe e prefetch-experts branch analizzati: **rischio concreto identificato** — la rotazione globale degli slot di staging **è incompatibile con il replay dei CUDA graph** (un graph catturato può leggere lo slot 0 mentre la rotazione carica nello slot N); soluzione minima proposta: slot deterministico `split_id % 3`, sincronizzazione a inizio eval, rilascio esplicito al confine prefill→decode (costo stimato ~960-967,5 MiB per 3 slot).
- **Distribuzione dei miss nella traccia reale FreeToken** (per la Sessione 8): dopo warmup, **33.747 piani, tutti n_routes=10, rows=1**; media **2,445 miss/piano**; istogramma 0:7010, 1:6971, 2:6016, 3:4625, 4:3351, 5:2198, 6:1474, 7:1041, 8:580, 9:327, 10:154; **miss 1-4 = 62,12% dei piani**, miss 0-4 = **82,89%**.
- **Audit GGUF quant/layer**: 48/48 strati con banche esperti, tutti E=512; 47 strati gate/up **IQ2_S**, down **IQ4_NL**; **solo lo strato 2** ha gate/up IQ2_XS.
- **Protocollo A/B finale (14/9)** (scritto alle 06:31 locali del 14/9, dopo il via libera dell'utente al piano): microbench→server, matrice minima (decode a contesto 0/dopo prefill reale, prefill 32k/131k), metriche da registrare (predicted_per_second, prompt_per_second, draft_n_accepted, SHA testo, picco VRAM), criteri di successo: **decode +10% minimo su FreeToken baseline (25,08 t/s)**, **nessuna regressione oltre 5% sul prefill**, **accettazione MTP entro 2 punti percentuali**.

---

### Sessione 38 — 20:30:56, 1,3 MB — sub-agente "audit Bonsai" (nessun utente umano)

Delegata dopo la richiesta utente delle 18:28 ("intendevo bonsai").

**Cosa ha fatto e concluso** (letture codice sola-lettura, nessuna esecuzione):

1. **Q1_0 è già ottimizzato AVX2 localmente** (`quants.c:555`); copiare il kernel Q1 di Bonsai **non darebbe guadagno**.
2. I percorsi caldi del modello Qwen sono **formati quant diversi** (IQ2_S, IQ4_NL, Q6_K, ciascuno con già un percorso AVX2 dedicato); uno shortcut Q1/Q2 di Bonsai **non è applicabile** senza riscrivere unpacking/scale/codebook/rappresentazione GGUF.
3. **Bonsai Q2/PQ2 è un'opportunità di formato modello separata**, richiede pesi Q2/PQ2 che il Qwen attuale non ha.
4. **Lo speedup Q2 riportato (3-3,6×) è specifico VNNI** (AVX-VNNI/AVX-512-VNNI): il Ryzen 5800X ha solo AVX2/FMA/F16C, **senza AVX-VNNI** — quel guadagno **non è atteso** sul nostro hardware.
5. **Q4_K vs Q3_K**: entrambi hanno kernel AVX2 reali locali; la sola lettura del codice **non stabilisce quale sia più veloce** sul 5800X, e comunque il formato reale del modello (IQ4_NL) è diverso da entrambi.
6. **Il target di prefill va validato separatamente**: le funzioni dot di Bonsai assumono per lo più `nrc==1` (multi-riga `nrc==2` esplicitamente non finito nel PR Q1 upstream); un miglioramento del kernel di decode **non va estrapolato a prefill≈400 t/s**.

---

### Sessione 39 — 20:31:47, 10,1 MB — ULTIMA sessione: sub-agente "audit FreeToken profondo + review `fused_cpu`"

Sessione delegata in parallelo alla 38, focalizzata sul codice FreeToken al commit pinnato e sulla revisione statica del prototipo `fused_cpu` prodotto nella Sessione 8. Nessuna richiesta umana diretta al suo interno (sub-agente); è la sessione più recente della giornata e quindi porta le raccomandazioni finali.

**Cosa ha fatto e concluso:**

- **Blocco di applicabilità FreeToken confermato con riferimenti di riga esatti**: GGUF nudo riconosciuto solo per `general.architecture=="gemma4"`; Qwen3.8-Flash-Next è `Qwen4ExpForConditionalGeneration` (percorso FP8/NVFP4 esperti soltanto) — **il GGUF Qwen richiesto non può caricare direttamente**. `_cpu_moe` accetta solo `bf16, nvfp4, mxfp4_triton, ds_fp4, q4_0`: **nessun kernel CPU per IQ2_S/IQ4_NL/Q3_K/Q4_K/Q6_K**. Il supporto GPU (IQ2_S/IQ4_NL/Q6_K nel dispatcher CUDA) **non implica supporto CPU/ibrido**. Portabilità Windows/Ryzen: file CPU usa `__attribute__((target))`/`__builtin_cpu_supports` in stile GCC/Clang con flag Unix `-pthread/-O3` — **compilazione MSVC stock non verificata/improbabile**; affinità CPU disabilitata su Windows (rischio oversubscription SMT sul 5800X). Calibrazione banda: `benchbw` **esclude interamente `q4_0`** — con solo il dato PCIe misurato (25,7 GB/s) e nessun target CPU, **nessuna frazione ibrida difendibile può essere scelta** con lo strumento FreeToken così com'è.
- **Probe nativo Windows sulla sincronizzazione CUDA**: confermato che il driver RTX 3060/Windows accetta lo stesso percorso `cuStreamWriteValue64`/`cuStreamWaitValue64` mappato host-pointer usato da FreeToken; grafo seriale a 96 nodi host aggiunge **~66,9 µs per lancio (0,696 µs per nodo no-op)** rispetto al grafo vuoto — solo microcosto di dispatch, non latenza di modello.
- **Mappatura del "seam" più stretto nel codice Qwen** per inserire un percorso CPU: la cache LFU legacy (con `src[3]`) è il punto più piccolo per aggiungere esecuzione CPU dei miss, mantenendo la semantica LFU; il percorso "demand-GPU" (quello realmente usato) è **più invasivo** perché gli array di miss sono device-only. Vincoli MTP: `moe-demand.cuh:231-234` limita `1<=n_tokens<=3`; dispatch `MUL_MAT_ID` demand è **solo MMVQ con `ne2<=3`**.
- **Review statica del prototipo `fused_cpu.hpp`/`cpu_test.cpp`** (prodotto in Sessione 8) — **6 problemi trovati**:
  1. **Alto — `FusedCpu::run` non è concurrency-safe** (campi mutabili condivisi senza guardia in-flight).
  2. **Alto — distruzione durante un run può fare deadlock** (worker può uscire prima che il chiamante esca da `barrier.wait()`).
  3. **Medio — input non validi possono causare crash** (`active`/`route_weights` dereferenziati senza controllo null).
  4. **Medio — dipendenza da inizializzazione tabelle IQ2_S non garantita** (`ggml_quantize_init(GGML_TYPE_IQ2_S)` non chiamato) — **poi ritrattato**: non è un bug reale, perché il dot IQ2_S usa la griglia statica `iq2s_grid`, non le routine di inizializzazione quantizzazione.
  5. **Medio — il test copre solo un token, shape fissa**, non valida route ripetute, 2-3 token, stride non contigui.
  6. **Medio — il banco è sbilanciato a favore del percorso fuso** (il riferimento include `ggml_backend_tensor_set()` a ogni iterazione, il fuso no).
  Nota positiva: la partizione dei worker è **race-free per un singolo run serializzato**.
- **Review di `overlap_probe.cu`**: 2 problemi **P1 alti** (attesa CPU senza timeout che può bloccare indefinitamente lo stream; distruttore non sicuro sotto cancellazione), 4 **P2 medi** (indirizzo mappato driver-specific; route sintetiche non router reale; misura di throughput batched non di latenza singolo token; nessun test MTP/multi-token).
- **Gap review finale del `PIANO_CPU_GPU_14_SETTEMBRE.md`** (documento prodotto in Sessione 8) — **4 gap P1 concreti trovati con riferimenti di riga esatti**:
  1. La classificazione CPU-vs-GPU dei miss deve avvenire **prima** di `moe-demand::remap()`, altrimenti il gather copia comunque le banche anche per i miss destinati alla CPU (il peso GPU zero evita il contributo ma non il trasferimento).
  2. La cache demand non ha slot "fittizi": uno slot "già disponibile" dev'essere protetto dalla pianificazione corrente o essere una route GPU reale già inclusa, altrimenti il replay può sovrascriverlo.
  3. Le ammissioni differite (`MISS_EXPERTS/MISS_SLOTS`) devono restare nella contabilità di frequenza ma **sparire dagli array di ammissione e dal gather GPU** per le richieste CPU — il piano lo prescrive ma va reso requisito concreto dell'interfaccia P1.
  4. **Punto esatto del merge pesato**: per Qwen il peso va applicato a `experts` in `llama-graph.cpp:2366` **prima** della riduzione — il contributo CPU va sommato **dopo** quella moltiplicazione e **una sola volta**, prima del ritorno di `build_moe_ffn` e **prima** dell'aggiunta dello shared expert (`qwen4exp.cpp:1463`); sommarlo prima verrebbe pesato due volte.

**3. Ultime raccomandazioni di Codex (fine sessione, 06:39 locali del 14/9) — passo successivo proposto:**

Le "Scelte proposte per l'integrazione" (6 punti) sono il vero step successivo lasciato in sospeso a fine giornata:

1. **Definire il contratto del plan split**: distinguere esplicitamente `gpu_misses` da `cpu_misses`; solo i miss realmente trasferiti ricevono uno slot.
2. **Usare `remap()`/MMVQ come seam principale**: buffer persistente per route CPU, maschera GPU a forma fissa, output CPU `[n_embd,n_tokens]`; le route CPU devono produrre righe GPU nulle o essere escluse dal merge.
3. **Conservare tre banche coerenti** (gate/up IQ2 + down IQ4_NL): stesso esperto identificato su tutti e tre i bank; non modificare i dati host durante un trasferimento.
4. **Stabilire lifetime e cancellazione**: un solo job in volo per stream (o ring preallocato); distruzione deve prima sincronizzare/cancellare il grafo poi fermare il worker; serve un percorso di errore/cancel per l'attesa CPU (oggi può bloccare indefinitamente).
5. **Gestire MTP per token**: mantenere route/pesi per ogni colonna di `ids[n_expert_used,n_tokens]`; il limite demand a 3 token e la disabilitazione della cache in alcuni contesti MTP vanno rivisti esplicitamente.
6. **Validare prima di misurare throughput**: testare con router reale — 1/2/3 token, tutti i miss GPU, tutti CPU, split 1-2 miss, ID duplicati fra token, peso zero, cambio vittima LFU fra passi — confrontando output finale e stato cache dopo ogni replay, **prima** di qualunque banco di velocità.

A questi si sommano i 4 gap P1 sul piano (sopra) come blocker da chiudere esplicitamente nell'interfaccia prima di procedere alla Fase 1 (P0) del `PIANO_CPU_GPU_14_SETTEMBRE.md`.

---

## Stato delle piste al termine del 13/9

| Pista | Stato | Prova | Numero chiave | Dove sta il documento |
|---|---|---|---|---|
| Divario colpi cache 41% vs 75% | **Aperta/parzialmente falsificata** — il 41% (stima da traffico PCIe) è fuorviante; il 75% è misurato direttamente e confermato dal simulatore, ma la spiegazione del traffico PCIe residuo è solo analitica, non riverificata empiricamente | 36.913 piani GPU vs simulatore, zero differenze | **75,55%** hit reali (contro 74,82% LRU simulata); residuo PCIe spiegato per ~305 MiB/token da KV mappata ad attenzione piena, non confermato definitivamente | `docs/porto/RIPRESA_CACHE_13_SETTEMBRE_CODEX.md` (dichiara NON confermato) |
| N-grammi accanto alla testa MTP | **Falsificata come impostazione generale, utile solo su compiti "a copia"** | Bug `ngram-simple`→corretto in `ngram-map-k`; A/B su copia/modifica codice vs prosa libera | 34,93→39,19 t/s (copia codice) ma 27,3→22,8/25,08 t/s (prosa libera, peggiora) | `docs/porto/VERSO_50_TPS_400_PREFILL_13_SETTEMBRE_CODEX.md` |
| Sparse FA (DSV4/Qwen, teste 256) | **Confermata/preesistente** — non riattivata in questa giornata, solo riaudita | Audit numerico su handoff | 294,95 t/s a 131k con sparse FA (+18,1% vs 249,78 storico); neutra a 32k | Citata in `VERSO_50_TPS_400_PREFILL_13_SETTEMBRE_CODEX.md`, origine in `HANDOFF_13_SETTEMBRE.md` (13/9, sessione precedente non in questa cartella) |
| Prefill 32k | **Confermata, con qualità non riverificata** | Batch 4096 vs 2048 A/B | 410,48 t/s (batch 4096) vs 327,33 t/s (batch 2048); con MTP: 414,83 t/s | `VERSO_50_TPS_400_PREFILL_13_SETTEMBRE_CODEX.md` |
| Prefill 131k | **Confermata, sotto il target 400** | Corsa completa, recupero 5/5 informazioni | 357,61 t/s (in calo da 414 a 32k, 394 a 84k, 367 a 120k) | `VERSO_50_TPS_400_PREFILL_13_SETTEMBRE_CODEX.md` |
| Prefill 250k | **Proposta, mai misurata** | — | — (obiettivo dichiarato, non raggiunto in giornata) | non presente nelle chat come misura, solo come target |
| 50 t/s in generazione libera | **Aperta** | Best risultato libero misurato | 25,08 t/s (nuova config) contro 27,26 t/s (riferimento) — regressione, non progresso | `VERSO_50_TPS_400_PREFILL_13_SETTEMBRE_CODEX.md` |
| Prototipo CPU/GPU FreeToken (`fused_cpu`) | **Positivo a livello di microbenchmark isolato, non ancora integrato** | A/B sul blocco MoE, 3 esperti mancanti | 337→242 µs (−28%) con 2/3 esperti su CPU + RAM pinnata mappata + callback | `FREETOKEN_IBRIDO_13_SETTEMBRE.md`; review statica in Sessione 39 (6 problemi di concorrenza/robustezza, non ancora risolti) |
| Audit FreeToken (compatibilità) | **Falsificata come drop-in** | Lettura codice a commit pinnato `9535656` | Non carica GGUF Qwen; CPU solo per bf16/nvfp4/mxfp4/ds_fp4/q4_0, nessun kernel IQ2_S/IQ4_NL | `FREETOKEN_BONSAI_13_SETTEMBRE.md` + Sessione 39 |
| Audit Bonsai (kernel CPU) | **Falsificata come drop-in su questo hardware** | Lettura codice, confronto AVX2 vs AVX-VNNI | Speedup Q2 (3-3,6×) è VNNI-specifico; Ryzen 5800X non ha AVX-VNNI | Sessione 38 (nessun file `.md` di output dedicato nominato nella chat) |
| Ipotesi Q3/Q4 ibrido (pesi CPU) | **Proposta, rinviata dall'utente, mai testata** | — | Candidato: Unsloth UD-Q4_K_XL, ~111 GB (download mai avviato) | non presente come file di output |
| Cache LRU globale (alternativa alla politica attuale) | **Falsificata** | Replay a pari memoria | 74,82% (LRU) contro 75,55% (politica attuale) | Sessione 8, riportato in `FREETOKEN_BONSAI_13_SETTEMBRE.md` |
| Piano CPU/GPU per il 14/9 | **Proposta, con gap P1 aperti trovati dalla review finale** | Documento in 6 fasi + protocollo A/B | Stato dichiarato: "P0 da avviare; produzione invariata" | `PIANO_CPU_GPU_14_SETTEMBRE.md`, `PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md`, `REGISTRO_CPU_GPU_14_SETTEMBRE.md` |
| DS4/DSpark — cache esperti CUDA (`CACHE_SLOTS`) | **Chiusa NO-GO** (traccia A, fuori scope Qwen) | B73/B75: fixture falsificata, capability mai abilitata | 3 build NO-GO consecutive (B71, B73, B75 parziale) | outputs B71/B73/B75 in `dspark-20tps-replacement` (repo diverso) |
| DS4/DSpark — dual-chain CPU/GPU (B64) | **Chiusa NO-GO runtime** (traccia A) | Review statica P0=0/P1=0, ma CUDA mai eseguita | — | outputs B64 in `dspark-20tps-replacement` |

---

## Cose che Codex ha detto di NON rifare

- **Non riproiettare i guadagni di sparse FA misurati a 131k su 250k senza una misura reale**: "il 131k sparse run è 445,1 s; 250k a 400 t/s durerebbe comunque 625 s" — nessuna legge fittata, nessuna misura a 250k (Sessione 9).
- **Non adottare gli n-grammi come impostazione generale di decode**: aiutano solo sui compiti "a copia" (codice), peggiorano la prosa libera (Sessione 8).
- **Non copiare kernel esterni alla cieca senza verificarne il regime**: lo speedup Q2 di Bonsai (3-3,6×) è specifico AVX-VNNI/AVX-512-VNNI e il Ryzen 5800X non ha AVX-VNNI, quindi non va replicato aspettandosi lo stesso guadagno (Sessione 38).
- **Non fidarsi del traffico PCIe (`nvidia-smi`) come misura diretta dei byte trasferiti**: sulla macchina locale mostra ~40 GB/s anche per una copia CUDA standard misurata a 24,4 GB/s — non è una misura affidabile (Sessione 8).
- **Non estrapolare un guadagno di kernel di decode al target di prefill** (regola esplicita nell'audit Bonsai: "un miglioramento del kernel di decode non va estrapolato a prefill≈400 t/s", Sessione 38).
- **Non riquantizzare Q3→Q4 per la quota CPU** (l'utente stesso lo corregge: non recupera precisione e introduce errore aggiuntivo — poi chiarisce di voler scaricare un Q4 già pubblicato invece; Sessione 8).
- **Non sommare due volte il contributo CPU nel merge pesato**: va inserito dopo la moltiplicazione per il peso in `llama-graph.cpp:2366` e prima dello shared expert, mai prima della moltiplicazione (Sessione 39, gap P1 nel piano).
- **Non avviare il banco di velocità prima di validare la correttezza** con router reale su tutte le combinazioni (1/2/3 token, split CPU/GPU, ID duplicati, peso zero, cambio vittima LFU) — Sessione 39.
- Sul lato DS4/DSpark (fuori scope Qwen ma esplicito nelle sessioni): **non dichiarare GO CUDA basandosi su un oracolo di test che confronta kernel diversi** (MMVF contro cuBLAS) — la B71 era un falso NO-GO per questo motivo, corretto solo dopo riprogettazione dell'oracolo (Sessioni 28-31).

## Cose che l'utente ha chiesto esplicitamente

1. Ripartire dal punto lasciato nell'`HANDOFF_13_SETTEMBRE.md`.
2. **Usare agenti economici per le verifiche circoscritte**, mantenendo Codex "il cervello dell'operazione" (regola di delega esplicita).
3. Portare il modello verso **50 t/s in generazione e oltre 400 in prefill**.
4. **Autorizzazione esplicita a consultare qualsiasi repository e fare ricerche** esterne.
5. Chiarire la differenza fra il numero 39 t/s (citato senza contesto) e i 25 t/s reali in risposta libera.
6. Verificare **Bonsai** (non "Colibrì", correzione esplicita) per l'uso della CPU.
7. Verificare anche **FreeToken**.
8. Verificare se **Q4 sia più veloce di Q3** per la quota di pesi che resta in RAM/CPU.
9. Proporre un **ibrido Q3 (VRAM/RAM pinnata) + Q4 (uso esclusivo CPU)**, deciso per turno durante il prefill — poi chiarito: **scaricare un GGUF Q4 già pubblicato**, non riquantizzare.
10. **Rimandare** l'ipotesi Q3/Q4 e dare priorità a FreeToken.
11. Via libera esplicito a procedere con il prototipo CPU/GPU fuso ("Ok proviamo questa strada").
12. **Fare un piano fatto bene, con tutto documentato** per il proseguimento del 14/9.
