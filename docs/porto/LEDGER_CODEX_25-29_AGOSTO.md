# LEDGER CODEX — campagna «dspark-20tps-replacement», 25-29 agosto 2026

Riconciliazione a posteriori, sola lettura, 30 agosto. Fonte: ~150 .md in
`C:\Users\imanu\Documents\Codex\2026-08-26\dspark-20tps-replacement\outputs\` (390 file totali).
Nessuno di questi bracci era finora nei ledger del progetto. Verifiche di sorgente incrociate:
tre agenti in sola lettura (resto-64 su b20; anatomia CE-WB; questa riconciliazione).

## Perimetro e disegno

Brief: `…\2026-08-25\https-github-com-imanu86-moe-aggressive\outputs\HANDOFF_DS4_DSPARK_20TPS_20260826.md`.
Tesi DSpark-first: ottimizzare «token accettati / costo del giro di verifica»,
non l'hit-rate. Cinque strati: cache 473 slot memory-neutral con W-bank sulle
lane 469..472; FRONTIER (pubblicazione degli esperti PRIMA della verifica);
RESIDENT a lease/merito; controller di accettazione a profondità adattiva;
kernel multirow 2..8 con grafi CUDA ristretti ai ruoli caldi. Sopra, «Porto»:
snapshot phase-cold di target+draft+cache.

Catena di promozione: audit → patch congelata → review indipendente → build gate
(653/653) → **canary P25 bit-esatto** (68/192, temp 0, seed 123456, una lifetime,
un POST, zero retry; gate = uguaglianza byte del solo `message.content` contro
l'oracolo `B224780460E238DAA8FB2AC0953D5648899B91AEF063CFE75CB32CD6F77314CE`)
→ L6 sintetica → 1.200 → 8.192. **Il cancello P25 non è mai stato attraversato
in modo da abilitare una L6 valida.**

## Fatti

- ~68 bracci in 5 giorni. **Zero corse lunghe completate.** Le uniche tre del
  26/8: `bfull_dspark_v1` CUDA OOM al flip `0→476 slot +3215 MiB`;
  `bfull_..._b2_memneutral` `REQUEST FAILED`; `b3_dspark_nmax5_mrow_graphvariants`
  troncata a 511/1200 token, **decode ~6,1 t/s**, con `CE-WB lane=0..3
  selected=0`, `jobs 0/0/0/0`, `owner_zero=1` — il W-bank non è mai stato raggiunto.
- Unica misura L6: **9,955529 t/s** ad accettazione sintetica **100%**
  (995/995, len 6,000), ctx 150k, 1200 token, prefill 117,58 t/s. Classificata
  **INVALID** per cattura hot fallita (`target=0, draft=1`).
  `B32_2A_L6_ONLY_SYNTH_CEILING_REPORT_20260829.md`.
- Prima corsa reale (B4 P1): **INVALID/UNREACHED**, 9,35 t/s,
  `ready_before_verify=0`, `committed=0`, `pinned_route=0`, `overflow=1114`,
  **669 sfratti grafi per anzianità**. `B4_P1_REACHABILITY_0826A_RESULT.md`.
- Catena B29: divergenza byte 0 → byte 166, mai risolta in 11 sottobracci.
  Il payload sidecar è **scagionato** dalla leva `DIAG_NOJOB` (1632 soppressioni,
  zero job, zero byte copiati, output identico a P30).
  `P29_BYTE0_…`, `P30_BYTE166_…`, `P31_B29_2_GATE_UP_…`, `P33_B29_3_…DESIGN…`.
- **Esistono due lineage.** P26 (tree `27f7b219…`) è bit-esatta con l'oracolo:
  lo provano B52 (`PASS_SHORT_CANARY`) e B54-clean (P25 `B224…`, acceptance
  0,82963). B29.3.3 (tree `19b899da…`) **non lo è**: a leve tutte spente produce
  `F1E9B34A…`. `B51_1_B2933_BASE_OFF_P25_DISCRIMINANT_RESULT_20260829.md`.
  L'unico candidato isolato è stato falsificato da B53 (terzo output `FA6A9652…`).
  La bisezione larga **non è stata fatta**.
- Ultimo braccio, **B54.1, NO-GO semantico senza retry**: divergenza al carattere
  151, acceptance 0,716667 contro 0,747253, decode 8,578674 t/s (descrittivo).
  Blocker tecnico però **chiuso**: 12 viste writer wrapped / 6 reader compattate,
  restore host 78 MiB in 4,2 ms, zero assert.
  `B54_1_LONG_WRAP_REAL_CANARY_RESULT_20260829.md`.
- Bracci senza esito documentato: B6, B8, B14, **B38** (il canary che B39
  attendeva), B41, B44, B45, B47, B20.2-A/P24, P27 — esistono solo come
  cartelle `work/`.

## Contraddizioni con la linea canonica

1. **Il fix resto-64 è assente dalla base e presente nell'oracolo lungo.**
   La stringa non compare in nessun .md della campagna. Il runtime dell'oracolo A
   è `backup_pre_chirurgo14` con `llama.dll = 40E1DEAF…`
   (`P25_ORACLE_A_PREPARATION_CARD.md:46,119`) — che `LEDGER_23_AGOSTO.md:2050`
   chiama «la pre-fix 40E1DEAF di allora». Ma l'oracolo lungo di B54.1 è la
   response `sota_..._e35_anchor102k_20260824_f2_b2048_q1.response.json`
   (mtime 24/8 22:40, `p1=0.74725`, 884 char, decode 11,596 t/s), prodotta nel
   turno esecutore 35 che apre con «`llama.dll = ECAEA60B…` CONFERMATO»
   (`LEDGER_23_AGOSTO.md:2109`). **B54.1 confronta un candidato pre-fix contro un
   oracolo post-fix**, su un fix che tocca `llama-context.cpp` — lo stesso file
   di `llama_io_read_device:3861` che aveva ucciso B54-clean. Confondimento non
   dichiarato in nessuna carta. **Il NO-GO di B54.1 non è un verdetto valido.**
2. **Secondo confondimento nello stesso confronto**: il summary dell'ancora e35
   dichiara `porto_cb = nessuno (leva invariata)` e lo marca `(difetto)` —
   l'oracolo non fa alcun porto hot snapshot, il candidato gira con
   `PORTO_HOT_MASK=15` e cattura/restore completi.
3. **FORK_DOWN_TARDI** è usata dalla campagna (B3/B4/B-FULL) ma **assente
   dall'oracolo lungo** contro cui la campagna si misura.
4. **Il tetto della pinnata (~74,7 GiB) non è mai citato.** La campagna ha
   cercato 32 MiB in VRAM per due giorni (`B29_PHYSICAL477_CAPACITY_AUDIT`,
   `B29_DEVICE_RECLAIM_AUDIT`, entrambi NO-GO) senza considerare il vincolo host
   già misurato.
5. **Il bug indice −1 non è mai stato incontrato**: la campagna gira ovunque a
   `OVERLAP_BATCH_MAX=3` e `reasoning-budget-tokens=0`. Non lo conferma né lo
   smentisce — ma **non esercita mai la transizione di fine-reasoning**, quindi
   le sue promozioni sono cieche sul ramo che in produzione c'è sempre.

## Verdetti di sorgente (agenti 30/8, sola lettura)

- **b20/accept NON contiene il fix resto-64**: sito pre-fix verbatim a
  `src/llama-context.cpp:2296-2302`, nessun `resto_prefill`, nessun lettore di
  `LLAMA_VRAM_FASE_RESTO_FIX` — e lo staging layer-major (la risorsa il cui
  sfratto È il crash) è presente e raggiungibile in config di produzione.
  Il fix canonico `5804c9f` è 223+16 righe su `llama-context.{cpp,h}`: innesto piccolo.
- **Sorprese inverse**: b20/accept HA committati il cancello a VALORE di
  `DISABLE_GRAPHS` (bonifica 18/8) e lo sfratto grafi a conteggio — che su
  `overlap` vivono solo nei working tree, mai committati. E ha già la
  strumentazione dell'indice −1 (`ops.cpp:4823-4830`).
- **Perché CE-WB non ingaggia**: `armed=1` è scritto SOLO nel ramo replay dei
  grafi (`ggml-cuda.cu:6376`); con `GRAPH_VARIANTS=1` il replay è crollato al
  5,4% (canonica 80,3%; varianti sature 256/256 con 622 chiavi, hit 9,6% contro
  il gate del 90%) ⇒ la banca esce sempre a `if (!armed) return`
  (`cache-esperti.cu:11140`). Secondo blocco: mailbox `published_n==rows`
  strutturalmente irraggiungibile a nmax=5 (n_pos≤5 contro rows≈8).
  `active=1` è un contatore che MENTE (eco di config). Manca `CE_WB_UNARMED_EXIT`.
- **Geometrie**: v0.5 (476 fisici, banca sopra il budget) → OOM a
  `cudaGraphLaunch` con VRAM libera 0: DA RITIRARE. v0.6 memory-neutral
  (473 fisici, 469 canonici + 4 lane nel medesimo slab, −20,26 MiB di capienza)
  è l'unica geometria ammissibile a 12 GiB.
- **Il 6,1 t/s della corsa b3 NON è il costo della banca**: è il collasso dei
  grafi da GRAPH_VARIANTS (costo/token accettato ~1,9-2,1× a lavoro appaiato).
  Banca e varianti innestate nello stesso binario: cause non separabili da quei
  log. FORK_DOWN_TARDI era attiva via porto_cb nonostante il manifesto dicesse
  0(D): ennesima conferma che il manifesto non è la configurazione.

## Conferme e duplicazioni

- **CONFERMA INDIPENDENTE, con meccanismo**: lo sfratto grafi a conteggio ha un
  BUG di contabilità — `cuda_graph()` incrementa `graph_calls` ~5 volte per
  replay, quindi la soglia d'età 16.384 scatta a ~3.300 replay veri ⇒ 669
  sfratti per anzianità in una corsa corta (`B4_1_GRAPH_RUNTIME_AUDIT_MANIFEST.md:57`).
  B4.1 lo cura con un registro a 64 ruoli inline. DA PORTARE sulla linea canonica.
- **DUPLICAZIONE**: B12/B19 hanno rifatto l'oracolo di cache e si sono
  auto-falsificati (70,49% → 62,61% atomico); B30/B31 hanno ri-falsificato
  offline prefetch e no-chase, già falsificati al banco dalla linea canonica.
- **CONVERGENZA SUL NUMERO**: L6 a 9,955 t/s con accettazione 100% dice, per via
  indipendente, che il collo non è l'accettazione — la tesi canonica.

## Danni e pendenze operative

- **Primario `D:\llama-dspark` congelato** dal 28/8 11:00 (apply B29 indirizzato
  male: CWD rimasta sul primario). Ramo `jacobi`, HEAD `0d655126…` fermo al 7/8,
  **201 percorsi in stage, +139.586/−13.481**, cancellati `common/reap.cpp` e
  `common/reap.h`. HEAD e reflog non mossi. Backup fuori repo
  `RECOVERY_PRIMARY_AFTER_B29_MISDIRECTED_APPLY.patch` (7.508.034 B).
  **Non applicato. Sporco ancora oggi 30/8.** Decisione di recovery = utente.
- **`D:\b*` = 102 directory, 42,86 GB.** 30 sono worktree registrati nel
  primario congelato (≈13 GB): non rilasciabili con `git worktree remove`
  finché il freeze regge. 45 cloni standalone (≈22 GB) e 21 dir di sola build
  (≈8 GB) cancellabili a filesystem. Dipendenza: `b541` è worktree di `D:\b2932z`.
- **Da conservare**: `D:\b52` (unica lineage bit-esatta con build), `b54c`/`b54cb`,
  `b541`/`b541b`, `b29g` (testimone pulito), `b20` (base P26, ma è worktree del congelato).
- **Disco**: C: 32 GB liberi su 931 (97% pieno); D: 61 GB su 953 (94%).
  La campagna corre in `…\dspark-20tps-replacement\work\` (1,7 GB su C),
  NON in `D:\ds4_work\llama_run`: i log 27-29/8 vanno cercati lì.

## Verdetti

- **Obiettivo 20 t/s: non avvicinato.** Nessuna corsa lunga completata in
  cinque giorni; nessun claim prestazionale emesso dalla campagna stessa.
- **La campagna è metodologicamente rigorosa e strutturalmente cieca**: la
  disciplina un-POST/zero-retry/bit-esatto è ineccepibile, ma il gate poggia su
  un oracolo prodotto da un binario diverso da quello dei candidati.
- **La pendenza vera non è B54.1: è la bisezione mai fatta** fra la lineage P26
  (sana) e la B29.3.3 (derivata), più la ricostruzione dell'oracolo su binario
  coerente (post resto-64).
- **Azione col miglior rapporto informazione/costo**: rieseguire la sola L6 di
  B32.2A sulla lineage P26 con la carta congelata di B54-clean
  (`B54_CLEAN_L6_ONLY_SYNTH_CEILING_RUN_CARD_20260829.md`). Confermerebbe o
  smentirebbe il 9,955 t/s ad accettazione perfetta — il numero più informativo
  prodotto in cinque giorni.
- **Difetto di gate da correggere prima di qualunque ripresa**: le carte
  pretendono geometria `473/43/256`, il runtime attesta `473/64/256`
  (64 = `CACHE_ESPERTI_MAX_STRATI`; 43 = layer del modello). Applicata alla
  lettera, la regola invaliderebbe corse sane.

---

## ADDENDUM 30/8 — innesto resto-64 sulla lineage P26 (D:\b52): FATTO

Chirurgo opus, solo editing, niente build/commit. Esito: **b52 conteneva gia' il 95% di
`5804c9f`** — i compositi P26 portavano l'intero working tree chirurgo15 TRANNE i cinque
identificatori del resto-64 (coerente col reperto «b20 = stesso working tree con i hunk del resto
asportati»). Aggiunte solo **37 righe in `src/llama-context.cpp` + 2 in `src/llama-context.h`**,
verificate in doppia direzione: ogni riga aggiunta byte-identica al patch canonico, ogni riga
canonica non aggiunta gia' presente. Guardia anti-warmup `vram_fasi_taglia_prefill` presente e non
semplificata; lettore env nel blocco one-shot (sentinella `< 0`), raggiungibile anche a leva spenta;
graffe bilanciate; HEAD `98ee8c76` invariato; le 26 voci staged pre-esistenti intatte (il fix e'
volutamente NON-staged per restare verificabile con `git diff`).

**Cancelli pre-registrati per la build futura di b52** (quando la macchina si libera):
1. canary P25 corto ancora **bit-esatto** `B2247804…` (il fix non tocca i prompt corti);
2. repro resto-64: prompt 32.782 token ⇒ **due `flip rinviato`** e completion piena
   (il binario pre-fix moriva OOM a `mmq.cu:183`, 3/3);
3. solo dopo: la **L6 congelata** di B54-clean (decide se il programma W-bank puo' arrivare a 20).

Nota delega: il sandbox Codex NON puo' scrivere fuori dal proprio progetto (due fermate pulite:
dubious ownership + «writing outside of the project») ⇒ a Codex analisi/lettura, a opus le
chirurgie sugli alberi D:\.
