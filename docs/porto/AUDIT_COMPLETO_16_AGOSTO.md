# AUDIT COMPLETO PORTO — 16 AGOSTO 2026

Documento di sintesi di un audit multi-agente. Non contiene misure nuove: raccoglie,
confronta e **verifica su disco** quanto affermato dai documenti di lavoro del periodo
13-16 agosto. Ogni numero porta un marcatore:

- **[misurato su disco: prova]** — esiste un artefatto (log, summary, CSV, hash, diff)
  che è stato aperto e confrontato durante la verifica.
- **[dichiarato, non verificato]** — l'affermazione compare solo nel testo di un
  documento, senza artefatto localizzato.

Fonti primarie di questo audit (campo *doc* citato ad ogni affermazione):

| doc | file |
|---|---|
| `ledger-porto-16` | `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\outputs\LEDGER_PORTO_16_AGOSTO_2026.md` (fuori repo, non versionato) |
| `handoff-porto-16` | `...\outputs\HANDOFF_PORTO_16_AGOSTO_2026.md` (fuori repo, non versionato) |
| `docs-repo-15ago` | `docs/porto/HANDOFF_15_AGOSTO.md`, `docs/porto/LEDGER_15_AGOSTO.md`, `docs/porto/dopo_il_riavvio.ps1` (nel repo, modifiche non committate) |
| `handoff-nuova-chat-15ago` | `docs/porto/HANDOFF_NUOVA_CHAT_15_AGOSTO.md` e `..._NOTTE.md` (nel repo, untracked) |

---

## 1. Stato dell'arte

### 1.1 Decode — i numeri che contano

| Grandezza | Valore | Marcatura | doc |
|---|---:|---|---|
| SOTA storica certificata (media 3 run B1200) | **16,0733 t/s** (16,04 / 16,11 / 16,07) | [misurato su disco: `D:\ds4_work\llama_run\mass2_copyall_stablelane_t473_d12_b1/b2/b3.server.log`, righe `eval time = 74804.71 / 74478.48 / 74661.80 ms`; `p1=.90025 (713/792)`; `copie=47906`; SHA output `4FDCFADF…` ricalcolato e identico] | `ledger-porto-16`, `handoff-porto-16`, `docs-repo-15ago` |
| Baseline B1200 corrente pulita (sonde spente) | **12,12 t/s** (R1) / **12,22 t/s** (R2) | [misurato su disco: `…\work\runs\current_clean_noprobes_b1200_r1_20260816.summary.json` = 12.12; `hotmask15_natural_full_b1200_r2_20260816.summary.json` = 12.12/12.22; entrambi `p1 0.90025`, SHA `3BAC3069…`] | `ledger-porto-16`, `handoff-porto-16` |
| Baseline B1200 corrente strumentata (profiler acceso) | **10,53 / 10,54 t/s** | [misurato su disco: `sota_k2_no_hot_profile_diag_b1200_r1_20260816.server.log:651` = 10,53; `sota_k2_no_hot_snapshot_b1200_r1_20260816.server.log` = 10,54, `p1=.90025` identica allo storico] | `handoff-porto-16`, `handoff-nuova-chat-15ago` |
| Reference B160 corrente pulita | **12,34 t/s** | [misurato su disco: `current_clean_noprobes_b160_r1_20260816.server.log`, `81.06 ms/token`, `p1 0.77670`, SHA `991AF3E1…`] | `handoff-porto-16` |
| Delta host localizzato (`calc altri` / `graph_compute_async`) | **4,080 → 22,318 ms/grafo (+18,238)** | [misurato su disco: righe `sched-profilo: 1951 grafi, 35.6 split/grafo …` nei due log; 18,238 × 1.951 = 35,58 s su 39,19 s di regressione totale = 90,8%] | `ledger-porto-16`, `handoff-porto-16` |
| Budget mancante per 20 t/s | **12,214 ms/token ≈ 0,284 ms/layer** su 43 layer | [misurato su disco: profilo `macro_v2_terna_mmvq_probe_k0_plan_graph_off_b160_r1_20260815.server.log:590` → `terna=1.925591 ms/layer mmvq=1.481610 contorno=0.443981`; aritmetica 62,215 → 50,000 ms/token esatta] | tutti e quattro |
| Ceiling del solo trasporto DMA | ~19,453 t/s | [dichiarato, non verificato — aritmetica derivata (39,9217 esperti/token × 6,75 MiB a 24,35 GiB/s), nessuna corsa a quella velocità esiste] | `handoff-nuova-chat-15ago`, `handoff-porto-16` |

**Il fatto centrale: la SOTA non è oggi riproducibile.** A parità di testo generato
(SHA del testo normalizzato identico bit a bit), di configurazione cache
(`cache-esperti: 473 slot … massa=2 … sfratto_par=1 …` identica carattere per carattere)
e di carico (`domanda 216737, colpi 168831 = 77,9%, buchi 47906`), il binario corrente
rende 12,12-12,22 t/s invece di 16,0733. [misurato su disco: confronto a tre assi fra
`mass2_copyall_stablelane_t473_d12_b1.server.log` e i tag `*_20260816`]. `ledger-porto-16`,
`handoff-porto-16`, `handoff-nuova-chat-15ago` concordano.

Avvertenza di metodo emersa dalla verifica: **il confronto 16,04 vs 12,12 non è a pari
strumentazione** — il log del record ha `GGML_SCHED_PROFILO=1(E)` acceso, la baseline
"pulita" no. Il confronto omogeneo è 16,04 contro 10,53 = −34,4%; il rapporto
12,12/10,53 = +15,1% citato nel ledger è esatto.

### 1.2 Prefill — i numeri che contano

| Grandezza | Valore | Marcatura | doc |
|---|---:|---|---|
| SOTA lunga corretta (denseFA + staging + HC scheduler) | prefill medio **116,1985 t/s** (110,7005 / 111,0928 / 126,8021) | [misurato su disco: tre `sota100k_ctx150k_densefa_stage_hc5_resident[_r2/_r3].summary.txt` in `D:\ds4_work\llama_run`; media esatta] | `ledger-porto-16`, `handoff-nuova-chat-15ago` |
| Decode associato allo stesso braccio | **7,9492 t/s**, `p1=.61702` | [misurato su disco: stessi tre summary, output SHA `D556C4C3…` identico nelle tre repliche, zero divergenze] | `ledger-porto-16` |
| Misura target-only precedente | 275,506 t/s | [dichiarato — esplicitamente declassata dai documenti: "non SOTA end-to-end"] | `docs-repo-15ago` |
| Traguardo dichiarato dall'utente | 500 t/s intermedio, 1000 t/s ideale | [dichiarato] | `docs-repo-15ago` |

Nota di lettura: la mediana del prefill è 111,09 t/s (le prime due repliche stanno allo
0,35%, la terza è +14% e traina la media). Il valore mediano è più rappresentativo della
media promossa nei documenti.

### 1.3 Configurazione, albero, build

**Dove vive il codice della SOTA.** Non nel repo `moe-aggressive-commit`. La SOTA è
prodotta da un binario costruito in `D:\llama-overlap` (fork `ggml-org/llama.cpp`), non
dalla famiglia `ds4-*` del repo principale (fork `antirez/ds4`, binari `ds4_server.exe`).
[misurato su disco: `Glob **/llama-server.exe` nel repo principale = 0 risultati; il
runner ufficiale `work\run_porto_hot.ps1` ha come default
`-ServerPath = D:\llama-overlap\build\bin\llama-server.exe`]. `handoff-porto-16`.

**Build più recenti** [misurato su disco]:
- `D:\llama-overlap\build\bin\llama-server.exe` — 16/08 02:30:55; `ggml-cuda.dll` 213 MB @ 00:48:15 (thin launcher + DLL).
- `D:\llama-bisect-893\build-vc\bin\llama-server.exe` — 16/08 01:13:05; HEAD `893a4867147db8185b0fd2fac44338ee3f292b05`, `git rev-list --count HEAD` = 10090 (entrambi identici alla citazione); unici file sporchi `topk-moe.cu/.cuh`.
- Tutta la famiglia `ds4-*` nel repo principale è ferma al 1-2 agosto: la build più recente è `ds4-port\build-verify\ds4-server.exe` del 02/08 12:27.

**Configurazione della SOTA** (dal log del record, non dal manifesto)
[misurato su disco: riga `cache-esperti:` di `mass2_copyall_stablelane_t473_d12_b1.server.log:259`]:
MASSA2 copy-all stable lanes, target **473 slot** da 6,75 MiB (3.194 MiB VRAM),
draft **12**, K=2, NMAX2, conf .8, AcceptMoE .75, FORK=2 con FORK_BLOCCHI=8,
`lru=1`, `scudo=0`, **`sfratto_par=1`**, `dma=0`.

**Avvertenza forte**: `docs/porto/dopo_il_riavvio.ps1` **non è** la configurazione della
SOTA. Lo script ha `MASSA=0`, `ACCEPTMOE=0`, `OVERLAP_BATCH_MAX=2`,
`SPEC_CONF_ESENTA_POS0=0`, `CACHE_BOZZA_SLOT=32`, `SLOT=512`; il record ha `MASSA=2`,
`ACCEPTMOE=1` soglia 0,75, `BATCH_MAX=3`, `ESENTA_POS0=1`, `BOZZA_SLOT=12`, `SLOT=473`.
Sono due banchi diversi. [misurato su disco: confronto riga per riga fra lo script e il
log del record]. `docs-repo-15ago`.

---

## 2. Cronaca 15/8 → 16/8

Ordine ricostruito dai quattro documenti e dai timestamp degli artefatti
[misurato su disco: mtime dei file in `…\work\runs\`, sequenza coerente].

**15 agosto, giorno.**
1. Si riparte dalla base decode autorevole 16,0733 t/s con gap dichiarato di
   12,214 ms/token verso 20 t/s. Si richiamano le famiglie già falsificate
   (FORK_RIUSA_SLOT, SALTA_COPIA_PARITA, BANCA_B, RCI mapped, whole-FFN, super-op CPU,
   lane transiente). `handoff-nuova-chat-15ago`
2. Prefill: promosso a **nuova base lunga corretta** il braccio denseFA + staging + HC
   scheduler (116,1985 / 7,9492 t/s). Bocciati i bracci con placement misto
   `blk.*=CPU`: crash `GET_ROWS_Q invalid index … i01=-1`, uno dei quali ha bloccato
   il PC. `ledger-porto-16`, `docs-repo-15ago`
3. Falsificate tre varianti **EXACT_DMA** (kernel-spin, memops64/runtime,
   memops64/Driver API): microtest isolati verdi, coda del grafo reale sempre ferma;
   codice rimosso. `docs-repo-15ago`
4. Respinti e rimossi: whole-FFN combinato (14,57 t/s, −9,35%), shared-overlap
   (14,55, −9,48%), RCI mapped burst MASSA2 (14,97, −6,86%), CPU FFN super-op
   (12,60 poi 11,40 t/s sulla fixture). `docs-repo-15ago`
5. **GPU lane B transiente**: multi-stream falsificata da due smoke test
   (`capturing stream has unjoined work`, poi deadlock reale); sottocancello
   single-stream chiuso a 11,37 t/s (−15,1%). [misurato su disco:
   `fixture_transient_gpu_lane_mass2_64.server.log:493`, nessun summary prodotto]
6. **VRES graphlet**: +8% pulito a K=0 (12,83 t/s) ma −12,7% con K=2 (14,03 t/s):
   il confine host blocca la composizione CPU/GPU. `handoff-nuova-chat-15ago`
7. **TILE GPU-driven**: corretto e bit-esatto (stesso SHA `E23927D4…` fra layer-3 e
   all-layer) ma falsificato per banda — 3.815 tile × 6,75 MiB = 25,15 GiB in 6,127 s
   = **4,10 GiB/s** contro i 7,86 richiesti. `docs-repo-15ago`, `handoff-nuova-chat-15ago`

**15 agosto, sera/notte.**
8. Collegato un agente DS4 locale read-only (porta 8110, tool read/search/git_diff).
   [misurato su disco: `work\start_ds4_agent_server.ps1`, `work\ds4_readonly_agent.py`]
9. **Planner globale target+DSpark con trasporto persistente** fuori dalla cattura dei
   CUDA graph: corretto (509/509 cicli, 43.244 copie, zero deadline miss) ma
   **+0,97%** (11,49 vs 11,38 t/s). Promosso come infrastruttura, non come guadagno.
10. **Macro-kernel decode v2 (planner → slot diretto)**: +31% sul K0 puro
    (11,50 vs 8,78 t/s) ma solo ~+1% sulla base K2 contingente.
11. **Fusione gate+up cache-aware**: +1,47% (10,37 vs 10,22 t/s B160), cioè
    0,033 ms/layer contro i 0,284 necessari. SHA identico alla reference.
12. Primo tentativo di **riuso esperti fra token** (port di
    `glm_routed_moe_gateup_tok2_reuse_kernel`): crash
    `GGML_ASSERT(i01 >= 0 && i01 < ne01)`, nessun t/s.

**16 agosto, notte.**
13. Scoperto che **la SOTA 16,0733 non è riprodotta dal binario corrente**; la
    regressione è localizzata in `graph_compute_async` (+18,238 ms/grafo).
14. Il crash expert-reuse viene riclassificato: **banco contaminato** (mancava
    `LLAMA_CACHE_ESPERTI_CALENDARIO_K0=1` con `SLOT_DIRETTI=1`). Rifatto il banco:
    no-dedup **bit-esatto** a 10,38 t/s; **tutte** le sette varianti di dedup/owner
    danno output errato o divergente (7,71 / 7,39 / 7,71 / 5,50 / 6,96 / 7,18 t/s).
15. Ipotesi "GPU sottoclockata" (780 MHz / 50-56 W contro 1950 MHz / 95-100 W storici):
    **avanzata e poi ritirata**. Un keeper esplicito peggiora (12,34 → 10,14 t/s).
16. Trovata e corretta la causa vera della divergenza dello **hot-replay**: il prompt
    veniva spezzato 67+1 invece del confine naturale ubatch 64+4. Dopo il fix, SHA
    `991AF3E1…` costante e switch ON/OFF/ON verificato (10,35 / 10,11 / 10,68 t/s).
17. **Esito**: col fix e lo snapshot verificati, B1200 resta 12,12/12,22 t/s. Il divario
    verso 16,0733 resta **aperto e non spiegato**. `ledger-porto-16`, `handoff-porto-16`

**Nota operativa sulle sessioni Codex** [misurato su disco: enumerazione di
`C:\Users\imanu\Documents\Codex\`]: nelle cartelle-data 13-15 agosto ci sono 7 sessioni;
**solo 1 su 7 ha prodotto file in `outputs/`** (la `2026-08-15\handoff-nuova-chat-15-agosto-md-3`,
2 file .md scritti il 16/8 alle 02:55). Le altre 6 hanno `outputs/` vuota. La cartella
`2026-08-16` non esiste. `.codex\sessions\2026\08\` ha 12 rollout per 14-15 agosto
(129.345.619 byte); il giorno 16 è assente.

---

## 3. Traccia PREFILL

### 3.1 Stato

- **Base corrente**: denseFA + staging + HC scheduler, **116,1985 t/s** su prompt
  101.597+64 token, ctx 150k, B/UB 2048, tre repliche con output SHA identico
  [misurato su disco]. `ledger-porto-16`
- **Guasto aperto**: ogni braccio full con placement misto `blk.*=CPU` produce
  `GET_ROWS_Q invalid index: src0='markov_w1.weight' … i01=-1 ne01=129280`
  [misurato su disco: `sota_ctx12000_bsparse_stage_hc5_placementcpu_pkt0_diag6k_f2_b8192.server.log:2650`].
  La catena è verificata nel codice: `dflash.cpp:299/323` costruisce il secondo indice
  Markov con `argmax(col)`, e `argmax.cu` lascia −1 se la colonna è tutta NaN
  [misurato su disco per `dflash.cpp` (corrispondenza esatta riga per riga);
  l'esistenza di `argmax.cu` è confermata, il comportamento −1/NaN è dichiarato].
- **Packetizer assolto**: con `packetizer=0` il guasto resta, quindi non è causa
  necessaria; la corruzione è già negli hidden/KV prodotti nel prefill.
  `docs-repo-15ago`
- **Super-op prefill v2**: i quattro file `dsv4-moe.cu/.cuh` e `dsv4-shared-hc.cu/.cuh`
  esistono in `D:\llama-overlap` come **file nuovi mai committati**, non toccati e non
  certificati [misurato su disco: presenti fra gli untracked del worktree].
- **Regressione 275,506 t/s**: declassata a misura target-only, non SOTA end-to-end.
- **Un braccio ha bloccato il PC** ed è operativamente bocciato: non si rilancia identico.

### 3.2 Fronti aperti

1. La corruzione hidden/KV DFlash nel prefill full non è né isolata né riparata.
2. La diagnostica temporanea `GET_ROWS_Q invalid index` è ancora dentro
   `ggml-cpu/ops.cpp` e va rimossa prima di una build Release pulita.
3. La patch phase-safe del packetizer (default-off, 4 file) non è né adottata né
   ritirata; `ggml-backend.cpp` contiene hunk preesistenti di altre sessioni e non va
   committato per intero.
4. Il super-op prefill v2 resta sospeso: i documenti dicono di correggere o ritirare
   prima il percorso che produce NaN nel grafo full.

### 3.3 Candidati prossimi passi (solo dai documenti)

- Discriminatore dichiarato: **block-sparse ON con esperti densi residenti,
  packetizer 0, HC_FUSO=5, UB2048/4096, completion ≥32, niente wildcard CPU**.
  `docs-repo-15ago`, `ledger-porto-16`
- Ritorno al prefill **solo dopo** aver chiuso il decode, con residenza virtuale
  phase-aware e tail FFN realmente fuso, portando il principio expert-tile
  read-once/compute/install. `handoff-nuova-chat-15ago`
- Rimuovere la diagnostica temporanea e rifare una Release pulita.
- Decidere esplicitamente il destino della patch phase-safe del packetizer.

---

## 4. Traccia DECODE

### 4.1 Stato

- **SOTA storica 16,0733 t/s certificata** ma non riprodotta. Il divario resta aperto
  dopo aver escluso: clock/potenza hardware, batching forzato del prompt, snapshot hot,
  strumentazione. `ledger-porto-16`, `handoff-porto-16`
- **La regressione è localizzata, non spiegata**: +18,238 ms/grafo dentro
  `graph_compute_async`, cioè il 90,8% del delta totale. L'attribuzione è verificata nel
  codice: `ggml-backend.cpp:1840` dichiara `us_calc_altro` come "graph_compute degli altri
  backend (lancio)" e le righe 2256-2264 avvolgono esattamente
  `ggml_backend_graph_compute_async` [misurato su disco]. Il documento stesso precisa che
  questo localizza **dove** si attende, non ancora **perché**.
- **Famiglie chiuse** (non ripetere): TILE GPU-driven, VRES a K=2, RCI mapped,
  whole-FFN / shared-overlap, EXACT_DMA in tutte e tre le forme, banca B multi-stream e
  single-stream, CPU FFN super-op, dedup/owner-mate dell'expert-reuse.
- **Infrastrutture corrette ma sotto budget**: planner globale + trasporto persistente
  (+0,97%), planner→slot diretto (+1% su base K2), fusione gate+up (+1,47%).
  Avvertenza di metodo: +0,97% e +1,47% sono singole ripetizioni e cadono **dentro la
  deriva di banco (2-3%)**; non distinguono le configurazioni. Il verdetto "sotto budget"
  regge lo stesso solo perché il budget richiesto è molto più grande.
- **Riuso esperti fra token**: ceiling globale 22,84%, sottoinsieme corretto
  same-channel **7,72%** (3.240/41.987 route) — insufficiente per 20 t/s anche se
  implementato bene [dichiarato, non verificato: i numeri compaiono solo nei documenti;
  lo script `analyze_route_trace.py` e le tracce esistono, ma nessun output dell'analisi
  è stato salvato].
- **Meccanismo hot verificato**: dopo il fix del confine 64+4, cattura e restore danno
  stesso SHA e stesso p1 su B160 e B1200 [misurato su disco: riga
  `porto-hot: cattura n_tokens=64, coda=4, mask=15 …`].

### 4.2 Fronti aperti

1. **P0 dichiarato**: bisect del tempo host di `ggml_cuda_graph_compute_one` / replay
   CUDA. Cancello esplicito: `calc altri ≤5 ms/grafo`, testo identico, `p1=.90025`,
   47.906 copie, **≥15,8 t/s**, poi tre repliche.
2. Regressione post-riavvio Windows (14,48 → 12,84 t/s dopo KB5123304 + KB5121003 +
   KB5120708, banda del letto mappato invariata a 24,47 GiB/s): mai chiusa
   [dichiarato, non verificato — esiste solo nel commento in testa a
   `dopo_il_riavvio.ps1`; i log delle corse citate non sono stati trovati].
3. Macro-kernel decode v2 attorno alla MMQ/MMVQ Porto: fondere route/sort,
   quantizzazione, dispatch e tail **senza riscrivere la GEMM**.
4. Expert-reuse: owner/mate map esplicita prodotta dal route kernel, invece di inferirla
   dentro ogni MMVQ; ramo sospeso finché il throughput non torna vicino ai 16 t/s.
5. Composizione con la corsia CPU della SOTA K2: CPU solo come rescue di deadline già
   persa, raccolta una volta per macro-fase, **mai 43 join per layer**.
6. Portare le leve da variabili d'ambiente a un control block atomico al confine token,
   e integrare lo snapshot nel prompt cache del server.
7. Verificare l'hot-replay su richieste successive multiple (oggi restano caldi solo
   processo, modello e DLL).

### 4.3 Candidati prossimi passi (solo dai documenti)

- **Prima il bisect, poi il macro.** Tutti e quattro i documenti mettono il recupero
  della regressione davanti alla caccia ai 20 t/s.
- Macro-kernel v2 sulla MMVQ esistente, con il planner come **solo** fornitore di
  residenza.
- Microcancello resident-expert-reuse a 2-3 token, con fixture isolata di un solo
  MMID/layer, gate/up separato da down, confronto dell'uscita MMID **prima** del router:
  se non produce ~5% su B160 a SHA/p1/planner coerenti, **chiudere l'intera famiglia**.
- Trasporto persistente batch/multi-layer con ownership e generazioni.
- Testa router addestrata / MTP nativo come oracolo di domanda futura — fronte aperto,
  mai tentato in questa ripresa.
- **30 t/s non è oggi una promessa credibile**: il solo ceiling DMA (~19,453 t/s) è già
  insufficiente [dichiarato, non verificato].

---

## 5. Inventario non committato

### 5.1 Tabella

| Percorso (relativo a `moe-aggressive-commit/` salvo diverso) | Natura | Lavoro unico | Raccomandazione |
|---|---|---|---|
| `ds4-p4a` | Clone git completo, **hub** di 20 worktree fratelli; owner filesystem `CodexSandboxOffline` | **Sì** — unica copia della storia di ~21 branch `port/*` + `codex/*`, nessuno mai pushato; più `FREE_AT_SIZE_ANALISI.md` non committato | **Committare/pushare per primo**; non eliminabile |
| `ds4-upstream-cuda-measure` | Worktree, **HEAD staccato** su `54b36ed` | **Sì, il più fragile** — `ds4_cuda.cu` modificato + 7 file nuovi in stage (tabelle dequant IQ1 CUDA, coda SPEX, `os_*`), nessun commit da nessuna parte | **Creare un branch e committare subito** |
| `ds4-port` | Worktree, `port/upstream-substrate`, **ahead 48**, tree pulito, 72 .md | Sì — 48 commit local-only, tronco di riferimento del porting | Pushare con priorità alta |
| `ds4-0731-moeio` / `-prefill` / `-tiering` / `-vittima` | Worktree, branch `port/v2-*` | Sì — branch local-only **+ `MANDATO.md` mai committato** (diverso in ognuna) | Committare `MANDATO.md` e pushare i branch |
| `ds4-0731-merge` | Worktree, `port/v2-merge` | Sì — branch local-only | Pushare |
| `ds4-port-blk3/4/5/6/10`, `-guard`, `-kv`, `-merge`, `-nucleo`, `-obs` | Worktree, un branch `port/*` ciascuna | Sì — tutti local-only; `blk10-iq1` è il più attinente al branch di ricerca corrente | Pushare tutti |
| `ds4-superchunk-prep2`, `ds4-vram-mass-prep1` | Worktree, branch `codex/*-20260726`, 95-96 .md ciascuna | Sì — local-only | Pushare |
| `ds4-stock` | Worktree, HEAD staccato = `upstream/main` esatto, pulito | **No** | **Eliminabile** (rigenerabile) |
| `reap-loop-p4a-ledger-sparse` | Clone completo, **hub** di 4 worktree; owner `CodexSandboxOffline` | Sì — tutti i branch local-only, incl. un `main` locale divergente (456 commit avanti); 38 ricevute di run mai committate | Pushare su nomi branch distinti |
| `reap-loop-ledger-main` | Worktree, branch `main` locale (≠ origin/main) | Sì — registra un esito **negativo** ("il nucleo portato NON si accende"); 1 file modificato | Committare; attenzione al conflitto di nome |
| `reap-loop-p4a-runtime-ledger`, `-superchunk-prep2-ledger`, `-vram-mass-ledger` | Worktree, branch `docs/*-20260726`, tree puliti | Sì — local-only | Pushare |
| `reap-loop-p4a-ledger` | Clone standalone, HEAD identico a origin, **indice git vuoto** (6835 falsi "D") | Il committato è al sicuro; incerti i 42 file sciolti sotto `artifacts/` | Verificare i 42 file, poi eliminabile |
| `.codex-f10-work` | Non-git, un solo `ds4_cuda.cu` da 1,9 MB (25/7) | Incerto — probabile bozza superata | Diff contro `ds4-upstream-cuda-measure`, poi archiviare |
| `.codex_runs` | Non-git, ~1,6 GB di output di run/quantizzazione | No — riproducibile | Archiviare fuori repo o eliminare |
| `.webui_secret_key` | 32 byte, verosimile segreto, untracked e **non in .gitignore** | No | **Aggiungere a `.gitignore`** |
| `.codex_build_4patch.bat`, `.codex_build_q1fix.bat`, `.codex_ds4_repro.ps1` | 3 script sciolti in radice | Parziale — ricette di build/patch/repro | Committare se ancora usate, altrimenti archiviare |
| `docs/porto/HANDOFF_NUOVA_CHAT_15_AGOSTO.md`, `..._NOTTE.md` | Nuovi, mai aggiunti a git (30 e 38 KB) | **Sì, alto valore** — sono la continuità del metodo di lavoro | **Committare con priorità immediata** |
| `docs/porto/LEDGER_15_AGOSTO.md` (+223/−0), `HANDOFF_15_AGOSTO.md` (+28/−3), `dopo_il_riavvio.ps1` | Tracciati, delta non committato | Solo il delta odierno è a rischio | Committare il delta |
| *(fuori repo)* `D:\llama-overlap` | Worktree runtime, 29 file modificati + oltre 100 untracked, nessun commit dopo `3014d375` del 14/8 | **Sì** — contiene il codice della SOTA e tutto il lavoro 15-16/8 | Non resettare; valutare un commit di salvataggio |
| *(fuori repo)* `…\Documents\Codex\2026-08-15\…-md-3\outputs\` | I due documenti `*_16_AGOSTO_2026.md` | **Sì** — l'audit del 16/8 non esiste nel repo | Portare nel repo |

### 5.2 I cinque rischi principali

1. **`ds4-p4a/.git` è un punto singolo di rottura invisibile.** È il database oggetti
   condiviso di 20 worktree; nessuno dei ~21 branch è mai stato pushato (verificato con
   `ls-remote` live contro `D:\ds4_work\m1-admin.git`). Cancellarlo distrugge l'intera
   storia del porting anche se le altre 20 cartelle restano fisicamente presenti — che
   diventerebbero link `.git` orfani.
2. **`ds4-upstream-cuda-measure` ha codice nuovo che git non protegge affatto.**
   Tabelle dequant IQ1 per CUDA, coda SPEX e layer `os_*` in stage su un HEAD staccato:
   un `checkout`, un `clean` o la cancellazione della cartella li perdono senza reflog.
   È esattamente il tema del branch di ricerca corrente.
3. **Il codice della SOTA non è in nessun commit.** `D:\llama-overlap` ha 29 file
   modificati e oltre 100 nuovi, ultimo commit 14/8: se quel working tree si perde, non
   esiste alcuna commit che ne conservi lo stato — e con esso sparisce la possibilità
   stessa di bisecare la regressione.
4. **Nessun remote è fuori macchina.** `D:\ds4_work\m1-admin.git` e
   `C:\Users\imanu\source\repos\reap-loop` sono entrambi cartelle locali sullo stesso PC:
   un guasto disco o un ransomware perde primaria e "copia" insieme.
5. **Il lavoro documentale più recente è il meno protetto.** +223 righe di ledger, due
   handoff da 30-38 KB mai aggiunti a git, e i due documenti del 16/8 che esistono solo
   in `Documents\Codex\…\outputs\`. È la continuità stessa del metodo, seduta su disco.

---

## 6. Incongruenze

### 6.1 Claim dichiarati e non verificabili

- **Il microprobe del clock non ha lasciato il suo reperto.** L'affermazione "il driver
  raggiunge 1935-1950 MHz e 124-126 W su carico compute, quindi non è un blocco esterno"
  è centrale nella rettifica del 16/8 (`handoff-porto-16` §20.1), ma l'unico output su
  disco di `cuda_clock_probe.exe` è `launches=2155 value=0`; nessun CSV, log o
  screenshot documenta quei valori. È **provato** solo il contrasto storico/corrente
  (1950 MHz-100 W contro 780 MHz-55 W) e il fatto che il keeper peggiora (12,34 → 10,14).
- **Il ceiling del riuso esperti (22,840% / 7,7167%, 3.240 su 41.987 route)** compare
  solo nel testo dei due documenti del 16/8. Lo script e le tracce esistono; nessun file
  di output dell'analisi è stato salvato. Rifacibile, non verificabile allo stato.
- **Il ceiling DMA ~19,453 t/s e il verdetto sui 30 t/s** sono aritmetica dichiarata,
  senza log di supporto. I documenti lo ammettono esplicitamente.
- **La regressione post-riavvio 14,48 → 12,84 t/s** e la banda 24,47 GiB/s esistono solo
  nel commento in testa a `dopo_il_riavvio.ps1`; le corse citate (f5b delle 05:06,
  j_rif delle 05:10) non sono state trovate.
- **La causa del primo crash expert-reuse** (banco senza `CALENDARIO_K0=1`) resta una
  spiegazione semantica: il crash è su disco, ma nessun log isola la variabile mancante.
  Regge solo l'argomento indiretto.
- **L'accesso in scrittura pieno a `D:\llama-overlap` e `D:\ds4_work`** (§0 di
  `HANDOFF_15_AGOSTO.md`) è narrativo: nessun percorso di verifica, nessun log di build.

### 6.2 Artefatti citati ma assenti o spostati

- **I due documenti del 16 agosto non sono nel repo.** `LEDGER_PORTO_16_AGOSTO_2026.md`
  e `HANDOFF_PORTO_16_AGOSTO_2026.md` esistono solo in
  `…\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\outputs\`. In
  `docs/porto/` non esiste alcun file `*16_AGOSTO*`. Tutto il lavoro del 16/8 è fuori dal
  versionamento.
- **`llama-server.exe` non esiste nel repo principale** (0 risultati ricorsivi): i binari
  `ds4-*` si chiamano `ds4_server.exe` / `ds4-server.exe`.
- **SHA della `ggml-cuda.dll` "build TILE testata"** (`8592E4BA…`) non corrisponde più al
  file attuale (`1ED035D3…`, ricompilato il 16/8 alle 00:48). Non è un errore del
  documento: è un'istantanea storica superata.
- **Due alberi di output con convenzioni simili.** I tag del 16/8 **non** sono in
  `D:\ds4_work\llama_run` (che si ferma al 15/8 10:50) ma in
  `…\Documents\Codex\2026-08-15\…\work\runs\`. Cercarli nella cartella sbagliata dà un
  falso negativo.
- **6 sessioni Codex su 7 (13-15 agosto) hanno `outputs/` vuota**; la cartella
  `2026-08-16` non esiste e non c'è alcun rollout del giorno 16.

### 6.3 Contraddizioni e imprecisioni fra documenti

- **Attribuzione del 12,22 t/s.** `ledger-porto-16` scrive
  "`current_clean_noprobes_b1200_r1_20260816` … 12,12 (R1), 12,22 (R2)", ma quel tag ha
  **una sola** ripetizione (12,12). Il 12,22 viene da `hotmask15_natural_full_b1200_r2`,
  cioè dal braccio cattura+restore. I due valori restano validi, non la stessa corsa.
- **Costo dello hot_snapshot.** Dichiarato "circa 7,1%"; il calcolo reale è −6,35% di t/s
  (121.586,51 contro 113.871,83 ms). E i due bracci hanno p1 e testo **diversi**
  (.85316 / 2.486 char contro .90025 / 3.574 char): non è un A/B pulito, e il documento
  stesso lo dice.
- **Lunghezza del testo.** "3.571 caratteri" è impreciso: `content_chars` dà 3.572, il
  conteggio reale senza BOM è 3.574 (3.575 con BOM).
- **Diff dichiarato di `HANDOFF_15_AGOSTO.md`**: la nota dice +31/−5, il reale è
  **+28/−3** (il file è stato ritoccato dopo la registrazione della nota). Il
  +223/−0 del ledger è invece esatto.
- **Riga dell'assert.** `ops.cpp:4823` è la `if` diagnostica; il
  `GGML_ASSERT(i01 >= 0 && i01 < ne01)` è alla **4831**, 8 righe sotto, stesso blocco.
- **Il repo "principale" non contiene il progetto corrente.** Tutti gli alberi `ds4-*`
  sono fermi al 1-2 agosto su base `antirez/ds4`; il lavoro decode/prefill descritto come
  corrente vive su `D:\llama-overlap` (base `ggml-org/llama.cpp`), un fork diverso.
- **Copertura incompleta dell'audit di codice.** `D:\llama-overlap` è hub di altri 15
  worktree fratelli (`llama-dspark`, `llama-mtp`, `llama-ring`, `wt-fiddler`, …) mai
  auditati singolarmente: potrebbero contenere altro lavoro non coperto.
- **Proprietà filesystem anomala.** `ds4-p4a`, `reap-loop-p4a-ledger` e
  `reap-loop-p4a-ledger-sparse` appartengono a `WORKSTATION\CodexSandboxOffline`, non
  all'utente: git li rifiuta come "dubious ownership" senza `safe.directory`.

---

## 7. Decisioni per l'utente

Queste richiedono giudizio umano e **non** sono state prese in questo audit.

**Salvataggio (urgente, indipendente dalla ricerca).**
1. Decidere se pushare i ~21 branch di `ds4-p4a` e i ~6 di `reap-loop-p4a-ledger-sparse`
   sui remote locali già configurati, **o** se serve prima un remote fuori macchina —
   oggi nessuna copia sopravvive a un guasto disco.
2. Decidere se creare un branch e committare il lavoro in stage di
   `ds4-upstream-cuda-measure` (tabelle IQ1 CUDA): oggi non è recuperabile da git in
   nessun modo.
3. Decidere se fare un commit di salvataggio su `D:\llama-overlap` — che contiene il
   codice della SOTA e non ha commit dal 14/8 — accettando che il worktree è "molto
   dirty" e le regole operative vietano reset/checkout distruttivi.
4. Decidere se portare nel repo i due documenti del 16/8 (`LEDGER_PORTO_16…`,
   `HANDOFF_PORTO_16…`) e committare i due handoff untracked più il delta del ledger.
5. Decidere se aggiungere `.webui_secret_key` a `.gitignore` prima che un `git add -A`
   lo faccia entrare nella storia.

**Pulizia (reversibile solo in parte).**
6. `ds4-stock` è eliminabile senza perdita; `.codex_runs` (~1,6 GB) è eliminabile **se**
   i numeri risultanti sono già trascritti in un ledger — va confermato.
7. `reap-loop-p4a-ledger` ha un indice git rotto: decidere se verificare a mano i 42 file
   sciolti sotto `artifacts/` o accettarne la perdita.
8. `.codex-f10-work` merita un diff contro `ds4-upstream-cuda-measure/ds4_cuda.cu` prima
   di qualunque decisione.

**Priorità fra le due tracce.**
9. I documenti sono unanimi nel mettere il **bisect della regressione decode** (P0) prima
   di qualunque caccia ai 20 t/s, e il prefill dopo il decode. Va confermato che questo
   ordine resta valido, dato che il bisect potrebbe non chiudersi.
10. Decidere se accettare il cancello proposto per il bisect
    (`calc altri ≤5 ms/grafo`, p1 `.90025`, 47.906 copie, ≥15,8 t/s, tre repliche) o
    fissarne uno diverso.
11. Decidere se il fronte **prefill** resta congelato: la base 116,1985 t/s è lontana dal
    traguardo 500 t/s, e il guasto `i01=-1` è aperto da giorni.

**Metodo e igiene di misura.**
12. Decidere se rimisurare la baseline corrente **a pari strumentazione** dello storico
    (profiler acceso su entrambi i lati) e con tre repliche: oggi molti confronti sono
    a una-due ripetizioni, dentro la deriva di banco del 2-3%.
13. Decidere se rifare e **salvare** l'analisi `analyze_route_trace.py`, il microprobe del
    clock e il microbench del letto mappato, così che i tre claim oggi solo dichiarati
    abbiano un artefatto.
14. Decidere il destino della patch phase-safe del packetizer (adottare o ritirare) e la
    rimozione della diagnostica temporanea da `ggml-cpu/ops.cpp`.
15. Decidere se chiudere la famiglia **expert-reuse**: i documenti stessi propongono un
    microcancello (~5% su B160) oltre il quale abbandonarla.
16. Decidere se investigare l'anomalia operativa delle sessioni Codex — 6 su 7 senza
    output e nessuna traccia del 16 agosto — prima di delegare altro lavoro.
