# ANALISI DI FATTIBILITA' — pilota speculativo su substrato CPU (MTP / DSpark / SPEX / shared-expert)

Agente: Fable. Data: 2026-07-29. Mandato: `scratchpad/mandato_pilot.txt` + aggiunta traccia 6 (shared expert su CPU).
Nessuna patch, nessuna build, nessun server avviato. D:\ letto in sola lettura. Tutto il codice citato e' il tree
`ds4-p4a` (l'albero della campagna corrente); il ledger e' `reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md`
(citato come `LEDGER:riga`). Un `ANALISI.md` di altro agente e' comparso in questa cartella durante il lavoro:
NON letto, NON toccato, come da istruzione.

---

## 0. VERDETTO IN BREVE

1. **Il pilota per il routing (livello A) e' l'unica idea dei tre motori che attacca l'asse validato** (ridurre il
   NUMERO di miss VRAM, curva di capacita' validata all'1%, LEDGER:17602-17640). Aritmetica del tetto: conversione
   perfetta dei miss in hit ≈ **6,2 t/s** nel regime gate (baseline 3,39); il gate a 5 t/s richiede
   **conversione ≥ ~0,75 con precisione ≥ ~0,85**. Nessun predittore misurato oggi arriva a quei numeri:
   SPX1 locale recall@6 = 0,31 (G15), pod = 0,52-0,73 (J15). Solo il **forward approssimato col token vero**
   (variante c-lite, senza MTP) puo' plausibilmente arrivarci — ed e' misurabile OFFLINE prima di ogni patch (T0).
2. **MTP**: oggi e' morto a runtime per FORMATO, non per speculazione: Q4_K prende zero silenzioso nel dispatcher
   CUDA (`ds4_cuda.cu:46893` + check tipi ~46978), Q1_0 e' rifiutato dal loader (`ds4.c:2907-2912`); probe
   confermato a runtime (LEDGER:15855-15880). Su CPU la testa costa **~8-12 ms/token + head** (head su GPU ~2 ms,
   head su CPU 14-28 ms): sta nel budget per-token, ma da sola NON produce le route del backbone — serve comunque
   il forward approssimato. Per il COMMIT (livello B) il dato Colibri (int4 → 0-4% accettazione, LEDGER:17684-17686)
   rende il Q1_0 (cosine 0,798) quasi certamente inutile; il Q4K va misurato offline (T0.3), niente kernel CUDA
   Q4_K routed esiste (24-40 h stimate, LEDGER:15612-15635).
3. **DSpark batch-verify**: il meccanismo k-token-in-una-passata **esiste gia' end-to-end** nel runtime fino a k=16
   (`ds4.c:16157-16231` verify_suffix_tops batch; `drafts[16]` a 21179; clamp a 16 a 19711-19712; server
   `toks[17]` a `ds4_server.c:7479`). Cio' che manca non e' k>2: e' un drafter che dia accettazione ≥ ~0,68 —
   prerequisito identico al punto 2.
4. **SPEX**: l'artefatto SPX1 ESISTE (`runs/spex/spex_model/ds4flash_d2_nextlayer.spex`, 90.177.568 B) e il tree
   locale ha GIA' l'intero stack: load (`DS4_SPEX_FILE`, ds4.c:10173), score/topK GPU (ds4.c:10311-10318), probe
   CPU (ds4.c:9652-9830), e perfino il **prefetch funzionale K1 gia' costruito e misurato** (G16, 2026-07-13):
   meccanica corretta, throughput **-54%** sul prompt lungo nel vecchio regime SSD. Orizzonte strutturale = 1
   layer, recall/precisione insufficienti da solo: declassato a correttore di coda del pilota, non a pilota.
5. **Traccia 6 (shared expert su CPU)**: i sei punti REGGONO alla verifica sul sorgente, con due correzioni
   (162 slot, non 170; join fuso da spezzare in modalita' non-fusa che gia' esiste). E' il T1 piu' semplice e
   l'unico a beneficio DOPPIO: libera **1.149.763.584 B = 162 slot IQ2** (curva → ~+0,4-1,0 t/s) e riusa
   l'idraulica G132 con costo CPU ~0,6-1,2 ms/layer dentro una finestra worker media di 4,9 ms/layer. Rischio
   principale: non e' bit-exact (ordine di somma float) e il beneficio di capacita' dipende dal fatto che gli
   range Q8 dello shared siano rilasciabili singolarmente (evidenza a favore: staging per-range da 8,50 MiB
   esatti = una matrice shexp; da provare con un contatore, T0.4).
6. Ordine consigliato del piano (sez. 8): **T0 offline (4 misure, zero rischio) → T1-bis shared-CPU → T1 pilota
   solo-prefetch → T2 commit/DSpark**. Ogni stadio ha numeri di morte espliciti.

---

## 1. CORREZIONI ALLE PREMESSE DEL MANDATO (obbligo di dirlo)

| # | Premessa nel mandato | Stato | Evidenza |
|---|---|---|---|
| P1 | "MTP-Q4K ... (1,09 GB)" | **SBAGLIATA: il Q4K pesa 3.807.602.400 B (3,81 GB)**; 1.089.693.408 B (1,09 GB) e' il **Q1_0** requantizzato | LEDGER:15540-15543 (AQ1), LEDGER:15939-15955 (AS); entrambi i file presenti in `C:\ds4-models\` (verificato a directory) |
| P2 | "exact-accept ds4.c:21157-21181, gate ds4_server.c:7483-7485" | **Righe stantie** (erano del tree di MANDATO C, 28/7). Nel tree corrente: exact-accept del primo draft `ds4.c:21200-21212`; verifier decode2-exact `ds4.c:21309-21366`; gate server `ds4_server.c:7484-7486` | letto direttamente |
| P3 | "DS4_MTP_BATCH_VERIFY e' l'interruttore di SPEGNIMENTO" | **Impreciso**: non spegne l'MTP; disattiva il verifier decode2-ESATTO forzando il micro-verifier batch (`ds4.c:21309-21310`). Lo spegnimento globale e' `DS4_MTP_SPEC_DISABLE` (`ds4_server.c:7486`). Gia' notato da AO5: "non e' un enable d'ingaggio" (LEDGER:15337-15340) | codice + LEDGER |
| P4 | "file MAI caricati in campagna" | **Impreciso**: caricati eccome (probe AR 27/7: load + secondary map ready + `mtp probe draft failed` x32, LEDGER:15855-15880; M2 28/7: caricato, ~2.000 ms/token, evict_backbone_delta≈1094, LEDGER:17337-17347). Mai hanno **DRAFTATO** con successo: questa e' la formulazione corretta. Il "+946-1094 sfratti/token": il 1094 e' M2; il 946 non l'ho ritrovato nei log superstiti (i due run c3a del 22/7 su D:\ds4_work\c3a_mtp_gate\ sono entrambi ERROR prima della misura) — ordine di grandezza comunque confermato da M2 | LEDGER + D:\ds4_work |
| P5 | "i 140 che abbiamo BASTANO" (finestra 60-120 slot) | **Vera aritmeticamente, ma con un vincolo taciuto**: la finestra CONVIVE con l'insieme LRU negli stessi 140 slot; a finestra 120 restano 20 slot per il riuso reattivo che oggi vale il 26% di hit. Il guadagno netto della finestra deve battere anche questa perdita. La traccia 6 (162 slot in piu') scioglie il vincolo | J17/J31 (LEDGER:365,379) + curva LEDGER:17602-17640 |
| P6 | "CPU in decode: 1,9 core usati su 16" | Vero, ma sono 16 **logici** su 8 fisici (Ryzen 7 5800X) — rilevante per stimare i tetti dei kernel CPU | `tools/audit0_microbench/results_cpu.md` (host e CPUID) |
| P7 | "pavimento DRAM ~194 ms/token" (backbone CPU full-precision) | Non ritrovato nel ledger con questa cifra; coerente con ~8,5 GB di denso classe-fp16 a ~44 GB/s. Lo tratto come dato del mandato, non riverificato | — |
| P8 | "spec_trace.patch consegnato e mai rigirato" | Il **codice della patch e' GIA' nel tree** (la riga `mtp conf path=decode2-exact` e' a `ds4.c:21332-21344`, identica al diff in `.microbench/gran_spec/spec_trace.patch`); "mai rigirato" e' vero per i RUN diagnostici, non per l'applicazione | `.microbench/gran_spec/spec_trace.patch` + ds4.c |
| P9 | "trovalo (il file SPX1)" | **TROVATO**: `runs/spex/spex_model/ds4flash_d2_nextlayer.spex`, 90.177.568 B = 32 B header + 43x4096x256 fp16 (piu' compagno `.npz`). Env di load nel tree: `DS4_SPEX_FILE` (ds4.c:10173) | filesystem + codice |
| P10 | Traccia 6: "~170 slot expert IQ2" | **162**, non 170: 1.149.763.584 / 7.077.888 = 162,4 (aritmetica in sez. 7) | codice (dimensioni tensori) |
| P11 | Traccia 6: "shared Q8 a ds4.c:2405" | Riga stantia (Addendum 32 del 24/7): nel tree corrente la dichiarazione e' `ds4.c:2540-2542`, il layout Q8_0 e' imposto a `ds4.c:3044-3046`, il bind a `ds4.c:3335-3337` | codice |

Nessuna di queste correzioni rovescia l'idea del mandato; P1/P3/P4 cambiano pero' i numeri di partenza del piano MTP.

---

## 2. INVENTARIO VERIFICATO DEL SUBSTRATO (cosa esiste GIA', con righe)

**Motore CPU (completo, non solo la lane):**
- forward CPU intero (backend `DS4_BACKEND_CPU`, usato dalla campagna teacher GPTQ): scratch `ds4_cpu_decode_scratch`
  (ds4.c:260), kernel routed IQ2_XXS pair (ds4.c:2426, 4760, 4851), Q2_K expert (ds4.c:4928, e wrapper G132
  `ds4_g132_matvec_q2_k_expert` a 4965), accumulo prequant (ds4.c:5019, 6710, 6805).
- **shared expert su CPU gia' scritto**: matvec_q8_0 fuso gate+up + down, versione plain (ds4.c:6094-6111) e
  versione decode-scratch (ds4.c:6126-6141). Questo risponde alla traccia 6, punto 5: il forward Q8 ESISTE.
- pool row-parallel G132 (thread pool persistente): ds4.c:827-895 (`g_g132_pool`, worker, shutdown).
- lane CPU per gli esperti routed: strutture `cuda_g132_cpu_lane` (ds4_cuda.cu:1668-1807: MAX_ROUTES=8, 43 layer,
  backing ARENA/ROUTE_STAGING), init e flag (`DS4_G132_CPU_LANE` + `DS4_G132_CPU_LANE_GENERAL`,
  ds4_cuda.cu:49136-49137 e 49676-49793), ponti misurati **input 16.384 B (ffn_norm) / parziale 16.384 B**
  (log `[g132-cpu-lane] result=ready ... input_bytes=16384 partial_bytes=16384`, LEDGER:17738-17740).
- **Verdetto lane sul percorso generale: PERDITA STRUTTURALE** (catena E, 2026-07-29): expert CPU ~1 ms/layer >
  fase esperti GPU 0,4 ms/layer; tre misure convergenti 229/267/426 ms PRE per 0/1/3 route CPU
  (LEDGER:18070-18116). Il pilota NON deve rimettere calcolo CPU sul cammino critico: deve stare DAVANTI.

**Stack SPEX nel tree (piu' avanti di quanto il mandato assuma):**
- loader SPX1: `ds4_spex_predict.h/.c` (magic "SPX1" a ds4_spex_predict.c:17), env `DS4_SPEX_FILE` +
  `DS4_SPEX_DRY_RUN` (init ds4.c:10168-10200), stage/cap (`DS4_SPEX_STAGE`, `DS4_SPEX_CAP`).
- score/topK **su GPU** gia' cablati: `ds4_gpu_spex_hidden_score_tensor` / `..._topk_tensor` (chiamate a
  ds4.c:10311-10318), coda prefetch (`ds4_spex_queue.h`, reset a ds4.c:10153).
- probe CPU asincrono (D2H ffn_norm 16 KB su ring pinned a 8 slot + worker che quantizza Q8_K e valuta gate/up
  IQ2 sul mapping RAM): ds4.c:9652-9830 (`DS4_SPEX_CPU_PROBE_K=1|2`).
- **prefetch funzionale K1 gia' costruito**: `DS4_SPEX_PREFETCH_K=1` (ds4.c:10161-10166), worker con handle
  modello duplicato, staging pinned, stream dedicato, chiavi epoch/seq/layer, scarto dei tardivi
  (G16_SPEX_K1_PREFETCH_RESULTS.md, in ds4-p4a/).
- risultati misurati (macchina locale, 13-15/7, regime VECCHIO senza cache residente):
  - G15 (ds4-p4a/G15_SPEX_CAP_PROFILE_RESULTS.md, tabella): recall/precisione K1 0,0895/0,537; K2 0,155/0,464;
    K4 0,254/0,381; **K6 0,308/0,308** (≈1,85 esperti utili/layer su 6).
  - G16 (tabella "Measured results"): mecc. esatta (406/756 matched = 53,7%, 0 late/0 errori), throughput
    Hi ±3%, **Cyber64 -54,29%** — prefetch da FILE in regime QD1 senza cache: il costo I/O speculativo uccide.
  - G34 (ds4-p4a/G34_SPEX_CPU_OBSERVE_RESULTS.md, verdict): esecuzione speculativa IQ2 su CPU **respinta**
    (solo 20,4% delle predizioni corrette E pronte al join; -3,37% server): "the data favors using SPEX to
    stage or pin high-confidence expert bytes, not to execute".
  - Pod (LEDGER:363, J15): SPX1 su traccia DS4 reale: recall top6 0,5155 / top16 0,6779 / top23 0,7260,
    hit_any 0,987-1,0. Divergenza dal G15 locale (0,31@6): regimi/prompt diversi, MAI riconciliata — e' una
    misura da rifare in T0, non un numero da scegliere a piacere.

**Stato MTP a runtime (tutto verificato):**
- struttura: blocco transformer completo con MoE (bind ds4.c:3632-3667; layout ds4.c:3053-3098): attention MLA
  Q8_0 + shared expert Q8_0 + router F32 + **3 stack routed [4096,2048,256] = 6,44 G elementi** (Q4_K nel file
  originale); e_proj/h_proj Q8_0 4096x4096; niente embedding ne' lm_head nel file (usa `token_embd` F16 e
  `output` Q8_0 del base: ds4.c:2988, 2993).
- **attenzione MTP su finestra SWA ≤128 posizioni** (raw_window = DS4_N_SWA = 128, ds4.c:10879-10886; cache raw
  MTP propria con contatore `mtp_n_raw`, commento ds4.c:21214-21219): per un porting CPU **niente problema
  KV-150k**; la KV da leggere e' ≤128 righe.
- ingresso: `metal_graph_eval_mtp_draft(_from_hc)` prende `g->cur_hc` (lo stato HC del token appena committato)
  + token (ds4.c:15404-15425): per una testa su CPU serve UN D2H di hc (16 KB x DS4_N_HC=4 = 64 KB) per token.
- morte a runtime: (i) Q4_K accettato dal loader (`tensor_is_routed_expert_type`, ds4.c:2907-2912 include Q4_K)
  ma **zero silenzioso** nel dispatcher routed CUDA (`routed_moe_launch_impl`, ds4_cuda.cu:46893; il predicato
  `!route_iq2_q2 && !route_iq1_s && !route_q1_0 → return 0` e' ~46978); probe runtime confermato
  (LEDGER:15855-15880). (ii) Q1_0 (file requantizzato, cosine 0,798-0,798-0,793, LEDGER:15963-15990) rifiutato
  PRIMA, dal predicato stesso che **omette Q1_0**; e anche corretto quello, la route Q1_0 dalla mappa MTP e'
  fail-closed perche' il selected loader esige l'identita' della mappa sidecar globale (diagnosi AS,
  LEDGER:15994-16022; fallimento runtime "type 41 ... expected a routed expert quant type", LEDGER:16157-16180).
- dual-map MTP: finestra host-pinned read-only da 3,55 GiB separata dalla primaria (AH, LEDGER:14003-14034) —
  e' QUESTA la fonte della tempesta di sfratti M2 (+1094/token) via pressione sugli range: su CPU sparirebbe.

**Percorso di promozione VRAM (per l'innesto, domanda 3):**
- contatore `vram_promotions` e siti: ds4_cuda.cu:28385 (campo), incrementi a 38001 (bulk), 39644, 41820, 42200.
- politica decode: admit per-route in `cuda_moe_tiering_observe_route` (chiamata nel worker,
  ds4_cuda.cu:41387-41400), heat/knock mass-lfru, **budget advisory g133**: `DS4_G133_PROMOTE_BUDGET` default 8,
  range 1..512 (ds4_cuda.cu:32742-32743), con reserve/refund atomici gia' pronti (ds4_cuda.cu:32114-32155).
- **percorso a LISTA gia' esistente ma one-shot**: il seed prefill→VRAM prende un vettore `selected[]` di
  entry (layer*256+expert, prior_weight) e riempie in blocco gli slot come `CUDA_MOE_TIER_VRAM_PROTECTED`,
  contando `vram_promotions`/`policy_free_promotions` (ds4_cuda.cu:37964-38011, log
  `[prefill-vram-seed-source] ... semantics=one-time-exact-iq2`).
- precedente diretto: **P4a demand pipeline** (H2D compattato per layer + un solo publish kernel):
  exact/counter PASS, **performance FAIL** (LEDGER:13113-13222) — batching a scala di LAYER dei miss sincroni
  non paga; il pilota batcha a scala di TOKEN, prima del bisogno: e' un'altra classe, ma quel codice
  (staging compatta + publish batch, ds4_cuda.cu:34156-36420 all'epoca) e' idraulica riusabile.

**Regime di riferimento (numeri ancorati):**
- baseline gate misurata: PRE 220-229 ms/token (4,54-4,37 t/s), POST-cliff **295-305 ms (3,39-3,28)**
  (LEDGER:17889-17913, 18085-18092). Per-layer: 5,1-5,3 ms PRE, 6,9-7,1 POST (=/43).
- staffetta route (relay sincrono worker→GPU): **~150 ms/token** (nota drain4, LEDGER:18120-18124); coerente con
  worker_service medio 4,9 ms/layer x43 = 211 ms nel run trace-on non stallato (AR RUN2, LEDGER:15767-15775).
- curva capacita' (validata all'1%): 140 slot→26% hit→4,2 t/s; 258→34%→4,6; 512→61%→7,9; 1024→75%→12,3
  (LEDGER:17602-17621). Identita' del trasporto: ogni selezione non-VRAM = copia intera 7.077.888 B.
- H2D effettivo sostenuto oggi: 1,353 GB/token / 0,295 s ≈ **4,6 GB/s** — e' il ritmo con cui QUALSIASI
  promozione anticipata deve convivere (stessi byte, stesso bus).

---

## 3. DOMANDA 1 — RITMO: chi sta sotto ~5 ms/layer, con che margine

Budget: la finestra per-layer del GPU e' 5,1 ms (PRE) / 6,9 ms (POST). Byte per expert: IQ2 7.077.888 B
(2x2.162.688 gate/up IQ2_XXS + 2.752.512 down Q2_K); Q1_0 3.538.944 B (3x1.179.648).

**(a) SPEX hidden (SPX1), niente forward.**
- Costo per layer: slice W_nl [4096x256] fp16 = 2.097.152 B; GEMV 1,05 MMAC.
  - CPU: 2,1 MB a ~20 GB/s ≈ **0,10-0,5 ms/layer** (1 thread basta).
  - GPU (misurato, classe J23 su pod): +2,6 s su 160 tok x43 layer ≈ **+0,38 ms/layer**; nel tree locale il
    kernel c'e' gia' (ds4.c:10311-10318).
- Margine sul budget: 10-50x. **MA orizzonte = 1 layer**: la predizione di L+1 nasce dopo ffn_norm(L); i byte
  promuovibili entro la scadenza ≈ 4,6 GB/s x ~4,5 ms ≈ 21 MB ≈ **3 esperti IQ2**. Con precision@3 ≈ 0,40 (interp.
  G15) converte ~1,2 selezioni/layer su ~4,4 miss → r ≈ 0,27 → (formula in sez. 4) ≈ 3,9 t/s: **da solo non
  passa il gate**, coerente con l'esito piatto/negativo di G16. Per l'orizzonte 10-20 layer servirebbe predizione
  concatenata: recall^k muore subito (0,31^2=0,10 gia' a 2 passi). Ruolo sensato: **correttore di coda** sopra il
  pilota c-lite (rimpiazza le predizioni della finestra quando il router reale di L smentisce il pilota).

**(b) MTP-head-only su CPU (costo della testa per DRAFT TOKEN, non per layer).**
Pesi letti per token (Q8_0 = 1,0625 B/elem):
```
e_proj 4096x4096      = 17.825.792 B     h_proj 4096x4096   = 17.825.792 B
attn_q_a 4096x1024    =  4.456.448 B     attn_q_b 1024x32768= 35.651.584 B
attn_kv 4096x512      =  2.228.224 B     attn_out_a 4096x8192=35.651.584 B
attn_out_b 8192x4096  = 35.651.584 B     shexp 3x(4096x2048)= 26.738.688 B
                                          totale Q8 ≈ 176,0 MB (+ ~4-8 MB F16/F32)
```
- blocco (senza head): 176-184 MB a 20-30 GB/s effettivi ≈ **6-9 ms**; + 6 esperti routed:
  - in Q1_0 col kernel classe audit0: 6 x 294,4 µs (mediana @4 thread, `tools/audit0_microbench/results_cpu.md`)
    ≈ **1,8 ms** (a 12 thread: 6x232,6 = 1,4 ms);
  - in Q4_K su CPU: **kernel assente** (il CPU routed fa IQ2/Q2: ds4.c:4760/4928; conferma indipendente in
    `D:\ds4_work\c3c_mtp_cpu.log`: "CPU ds4.c does not implement Q4_K expert matvec").
  - attenzione: SWA ≤128 posizioni → <0,5 ms (niente muro KV-150k, vedi sez. 2).
- head (argmax del draft): `output` Q8_0 [4096x129280] = 562.626.560 B:
  - su CPU: pavimento DRAM ~13-14 ms, realistico **20-40 ms** (stima convergente del dossier c3c del 22/7);
  - su GPU (residente): hidden 16 KB H2D + GEMV 562,6 MB a ~250-300 GB/s ≈ **~2 ms** una volta per token,
    schedulabile nella finestra logits; e' l'opzione giusta.
- **TOTALE testa: ~8-12 ms/token (head su GPU) o ~28-50 ms (tutto CPU)** contro un budget di 295 ms/token: 3-17%.
  Il dossier c3c stimava 45-90 ms con esperti Q4_K non ottimizzati: coerente, e il Q1_0 abbatte il termine esperti.
- **Limite di ruolo**: la testa da' il TOKEN draft, non le route del backbone. Per il pilota A serve comunque (c).
  Nota che per l'orizzonte a UN token l'MTP e' perfino superfluo: il token t+1 REALE e' noto al pilota all'inizio
  del passo (il server CAMPIONA in testa al loop, `int token = ds4_session_sample(...)` a ds4_server.c:7466, e
  solo dopo chiama eval a 7489/7505) — un pilota che parte dal token campionato ha errore-token ZERO. L'MTP diventa necessario solo da orizzonte ≥2 token (pipeline piu' profonda)
  o per il commit (livello B).

**(c) Forward approssimato Q1 top-1 per LAYER (il vero rivelatore di route).**
Due sotto-varianti, costi al pavimento DRAM (~44 GB/s) piu' compute:
- **c-full (con attenzione vera)**: i PESI di attenzione del layer base sono ~113,8 MB Q8 (q_a+q_b+kv+out_a+out_b,
  stesse shape dell'MTP sopra) → **≥2,6 ms/layer di sole letture pesi**; e a ctx 150k l'attenzione vera richiede
  indexer+KV compressa (a 150k la lettura KV per layer e' ~150.000x576x2 B ≈ 172,8 MB → ~4 s/layer su CPU senza
  indexer; replicare l'indexer su CPU non e' "minimo"). Inoltre 43x117 MB ≈ **5,0 GB/token di DRAM** che
  competono con lo stream H2D pinned (4,6 GB/s dalla stessa DRAM). **c-full: bocciata al regime gate.**
- **c-lite (senza attenzione: hidden avanzato solo con FFN)**: per layer = top-1 expert Q1_0 (294 µs) +
  router (ffn_gate_inp [4096x256] ~2-4 MB → ~0,1 ms) + shared Q8 opzionale (26,7 MB → 0,6-1,2 ms) ≈
  **0,4-1,6 ms/layer → margine 3-12x sul budget**; DRAM ~0,25-1,4 GB/token: compatibile con l'H2D.
  Registra le top-6 dal router VERO (F32) su hidden approssimato: la precisione non e' quella di un predittore
  esterno ma quella del router su input degradato. **Fedelta' di route: SCONOSCIUTA — e' l'incognita che decide
  tutto, ed e' misurabile offline (T0.2) senza toccare il runtime.**
  Nota di fisica: il ledger dichiara "il calcolo anticipato e' impossibile: la predizione da' gli ID, non il
  vettore da 4096" (LEDGER:17660-17667). c-lite non contraddice quella nota: non calcola il layer VERO in
  anticipo, ne approssima la traiettoria per interrogare il router — l'output resta della GPU, sempre.

**Quota riassuntiva (per layer):** (a) 0,1-0,5 ms CPU / 0,38 ms GPU, margine 10-50x, orizzonte 1;
(b) non-per-layer: 8-12 ms/token con head GPU; (c-lite) 0,4-1,6 ms/layer, margine 3-12x, orizzonte 10-20 layer
sostenibile (0,4-1,6 < 5,1); (c-full) bocciata (≥2,6 ms/layer solo pesi + indexer mancante + 5 GB/token DRAM).

---

## 4. DOMANDA 2 — TETTO DEL GUADAGNO (tracce, aritmetica, numeri di morte)

**Dove ho cercato le tracce ID (J17/J31, LOG_IDS):**
- `D:\ds4_work\` (listato + find per `*ids*.jsonl`, `*observe*ids*`, `*tiering*`): solo risultati .md dei cloni;
- `C:\Users\imanu\AppData\Local\ds4-win-work\` (find): solo `runtime_telemetry.jsonl` G25/G26/G36/G41 (senza ID
  per-selezione);
- repo (`runs/`, `.microbench/`, `artifacts` non presente in questo checkout): niente;
- WSL: i vhdx esistono (`C:\Users\imanu\AppData\Local\wsl\{...}\ext4.vhdx`) ma montarli e' fuori mandato;
- la J17 viveva su `/root` del pod (LEDGER:365) → **persa col pod** (memoria di progetto: /root si azzera).
**Inoltre l'emettitore stesso non esiste nel tree corrente**: in ds4-p4a c'e' `DS4_EXPERT_TIERING` observe/enforce
(ds4_cuda.cu:31549) ma NESSUN `LOG_IDS` (grep vuoto); il decode-trace v2 registra tempi/trasporti, NON gli ID
(`cuda_decode_trace_record`, ds4_cuda.cu:28706-28744). → **Il run minimo richiede un emettitore nuovo**:
~25 righe observe-only nel punto esatto in cui il worker itera le route (`cuda_moe_tiering_observe_route`,
ds4_cuda.cu:41387-41400), dietro env, formato (seq_token, layer, expert, weight). Run: 2 famiglie x 160+ token,
ctx/KV come da protocollo gate, temp 0,7, flag tutti default. Costo: minuti. E' il primo atto di T0.

**Cio' che le tracce gia' dicono (LRU, non per-layer):** J17: LRU su ID compatti cap64/128 = 0,0000 (!),
cap258 0,3396, cap512 0,5927, cap1024 0,7438 (LEDGER:365). J31 (locale, run duplicato): cap258 0,3413/0,3450,
cap512 0,6099/0,6139, cap1024 0,7609/0,7622, cap2048 0,8146/0,8138 (LEDGER:379). Lettura: a 140 slot il riuso
reattivo per-token e' quasi nullo sull'intreccio dei 43 layer (distanza di riuso ~258 > 140); il riuso ESISTE
(74-76% entro 1024) ma e' irraggiungibile per capacita' — **e' esattamente cio' che una finestra predittiva
raggiunge senza capacita'**. L'overlap per-layer t vs t+1 (la base che LRU gia' sfrutta e che il pilota deve
superare) NON e' nel ledger: esce dalla stessa traccia T0.

**Aritmetica del tetto (regime gate, POST: 295 ms/token, 3,39 t/s).**
Voce aggredita: la staffetta sincrona ~150 ms/token (LEDGER:18124). Residuo incomprimibile della fase esperti
all-hit: ~0,4 ms/layer x 43 ≈ 17 ms. Quota massima spostabile fuori dal cammino critico ≈ 133 ms/token.
Con conversione r (frazione di selezioni-miss che il pilota rende hit puntuali):
```
t(r) ≈ 295 - 133*r  ms/token
r=0,50 → 228 ms → 4,38 t/s      r=0,70 → 202 ms → 4,95 t/s
r=0,60 → 215 ms → 4,65 t/s      r=0,75 → 195 ms → 5,12 t/s   ← GATE
r=1,00 → 162 ms → 6,17 t/s (tetto assoluto del pilota)
```
(PRE-cliff, 220 ms: r=0,75 → ~7 t/s.) Caveat dichiarato: il "150" e' l'attribuzione drain4 (n=1); se la voce vera
fosse 120, il tetto scende a 5,6 e il gate chiede r≈0,85.

**Il secondo numero, che nessuno cita mai: la PRECISIONE (byte sprecati).**
Promuovere k=6 predetti/layer con precisione p spreca 6(1-p)x7,08 MB/layer:
```
p=0,85 → 274 MB/token extra (+20% bus)   p=0,54 (SPX1@K1) → +71%
p=0,31 (SPX1@K6 locale) → +125%: bus raddoppiato → FALSIFICATO in partenza
```
Regola derivata dall'identita' del trasporto: **il pilota vive solo se r ≥ ~0,75 E p ≥ ~0,85**. SPX1 misurato non
c'e' vicino (0,31/0,31 locale; 0,52@6 pod). L'unico candidato plausibile e' c-lite (router vero su hidden
approssimato) — che non ha ancora UN numero: T0.2 lo produce offline.

**Baseline da battere**: l'overlap t/t+1 per-layer che LRU gia' cattura a 140 slot ≈ hit 26% complessivo. Ogni
r va letto come conversione DEI MISS (il 74%), non delle selezioni totali.

---

## 5. DOMANDA 3 — INNESTO nel percorso di promozione

**Il tiering puo' ricevere una lista (layer,expert) dall'esterno senza cambiare politica?**
Risposta secca: **a meta'**.
- ESISTE il consumo a lista, ma one-shot al prefill: `selected[]` → slot bulk `VRAM_PROTECTED` con contabilita'
  promozioni corretta (ds4_cuda.cu:37964-38011). Non e' rientrante a meta' decode (fa swap della mappa
  host_slot_by_layer_expert e riparte da zero).
- In decode le promozioni passano SOLO dalla politica (observe_route → admit knocks/mass → budget advisory
  g133 con reserve/refund, ds4_cuda.cu:32114-32155; budget `DS4_G133_PROMOTE_BUDGET` 1..512 default 8,
  ds4_cuda.cu:32742). Un'iniezione esterna che scavalchi gli admit-knock E' un cambio di politica: va dichiarato,
  non nascosto. La forma minima onesta: una **advisory queue per-layer bounded** che consuma il budget g133
  esistente (stesso rubinetto, stessa contabilita': `policy_free_promotions`/`vram_promotions`), con TTL
  sull'entry promossa (se il router non la seleziona entro N layer, torna vittima preferenziale) — cosi' la
  politica di eviction resta mass-lfru e il pilota e' solo un SUGGERITORE.
- Rischio specifico da progettare subito: la finestra NON deve sfrattare residenti caldi. Vittime solo dalla coda
  LRU sotto soglia di heat; cap della finestra in-flight (≤60 slot) finche' la traccia T0 non dice di piu'.

**Dove vive il pilota?**
- **NON nei worker della lane G132 sul cammino critico** (verdetto strutturale, LEDGER:18104-18116).
- Il modello provato in-tree e' il **worker G16**: thread dedicato, handle modello duplicato, staging pinned,
  stream CUDA proprio, chiavi epoch/seq/layer e scarto-tardivi (G16_SPEX_K1_PREFETCH_RESULTS.md, sezione
  Implementation). Quel worker prefetchava da FILE in slab laterali; il pilota promuove RAM(arena/pagecache)→slot
  cache via il rubinetto g133 di cui sopra.
- Il forward c-lite gira sul **pool row-parallel g132 gia' esistente e fermo** (ds4.c:827-895): 1,9/16 logici
  usati in decode, ~6 fisici liberi (LEDGER:17624-17630). Ingressi che gia' esistono: D2H di hc/ffn_norm 16 KB
  (ponte lane; ring pinned a 8 slot del probe SPEX, ds4.c:9679-9760); embedding F16 leggibile dal mmap host
  (`embed_token_f16`, ds4.c:3675-3690).
- Sincronizzazione col GPU: il pilota per token t+1 parte quando il server conosce il token campionato
  (ds4_server.c:7466) e insegue con 0,4-1,6 ms/layer contro 5,1-6,9 della GPU: guadagna 4-5 ms di vantaggio
  per layer, quindi la finestra 10-20 layer si costruisce nei primi 3-4 layer del token.

---

## 6. DOMANDA 4 — LIVELLO B: draft CPU al validatore, e DSpark k>2

**Cosa consuma il validatore.** Solo `drafts[]` di interi + lo stato del grafo BASE: decode2-exact
(`metal_graph_verify_decode2_exact`, ds4.c:16248+, chiamata a 21323-21331) e batch verify
(`metal_graph_verify_suffix_tops`, ds4.c:16157-16231, chiamata a 21440-21448) usano `e->model`/`e->weights`,
non i pesi MTP. La contabilita' MTP-lato-GPU (`DS4_MTP_KEEP_ACCEPTED` su `mtp_n_raw`, ds4.c:21220-21225) con una
testa CPU migra su stato CPU. Conferma indipendente nel dossier c3c: "target verify already consumes draft token
ids; H2D of draft state is not needed if MTP state stays CPU".

**Cosa manca per un draft CPU** (in ordine di lavoro):
1. forward del blocco MTP su CPU: i pezzi esistono (shared Q8: ds4.c:6094-6141; router; attention SWA-128 da
   scrivere su CPU ma senza muro KV; esperti: **Q1_0 kernel c'e' come tool (audit0), non come funzione del
   motore CPU** — il motore CPU routed fa IQ2/Q2, ds4.c:4760/4928). Stima classe "L" del dossier c3c invariata.
2. lettura di `cur_hc` a fine token: D2H 64 KB/token (4x4096 F32) — ponte identico a quello della lane.
3. head su GPU (consigliato): GEMV `output` (Q8 residente) su hidden proposto via H2D 16 KB + argmax
   (`ds4_gpu_indexer_topk_tensor` gia' usato per top1 batch a ds4.c:16208-16213).
4. innesto: sostituire le chiamate `metal_graph_eval_mtp_draft*` (ds4.c:21106-21118 probe; 21231-21243 ricorsiva)
   con la sorgente CPU dietro flag; il resto della macchina a stati (margin gate 21258-21301, decode2 21309-21366,
   batch 21407-21530) resta intatto.

**DSpark batch-verify: cosa c'e' GIA'.**
- k e' gia' parametrico: `--mtp-draft N` (ds4_server.c:8457-8458) → clamp 1..16 (ds4.c:19711-19712) →
  `drafts[16]` (21179) → drafting ricorsivo (21227-21250) → verify batch di n_tokens in UNA passata layer-major
  (16186-16194: `metal_graph_encode_layer_batch` per layer su n_tokens) → server consuma fino a 17 token/passo
  (`int toks[17]`, ds4_server.c:7479). **L'ammortamento della staffetta e' strutturale**: 1 relay per layer per
  PASSATA, non per token; per k accettati la staffetta si divide per k (col volume che cresce solo dell'unione
  delle route, non del numero di passate).
- Cosa manca per k>2 UTILE: (i) un drafter vivo (vedi sopra: oggi drafted=0 per formato); (ii) accettazione:
  con accettazione a2 del secondo token e costo di verifica ≈1,0-1,2 token-equivalenti,
  throughput ≈ (1+a2)/(1,1+d/295): per passare da 3,39 a 5,0 serve **a2 ≥ ~0,68**; (iii) qualita': il verifier
  batch usa i kernel batch, che possono flippare greedy quasi-pari (commento esplicito nel sorgente,
  ds4.c:16240-16247: "not a safe substitute for autoregressive decode") — per il regime gate a temp 0,7 il rischio
  va rimisurato col rubric, non assunto.
- Soglia di precisione del drafter (Colibri, LEDGER:17684-17686): "testa MTP a int8 ok; in int4 l'accettazione
  crolla allo 0-4%". Il Q1_0 requantizzato (cosine ~0,80) e' sotto la classe int4 → per il COMMIT e' quasi
  certamente morto; il Q4K (classe intermedia 4-bit con scale) va MISURATO, non dichiarato: T0.3 da' l'agreement
  argmax Q1_0-vs-Q4K e l'accettazione teacher-forced di entrambi su stream reali, tutto offline su CPU.

---

## 7. TRACCIA 6 — SHARED EXPERT SU CPU (verifica dei sei punti)

Contesto storico corretto: il piano in due passi e' Addendum 32 (LEDGER:4857-4870: "NEXT: prototipo =
shared-expert su CPU da RAM → misurare; poi estendere ai cold routed"); il passo 1 fu saltato, il passo 2 e'
diventato la lane, morta sui routed coi numeri (LEDGER:18104-18116). Lo shared non e' mai stato prototipato.
Attenzione: Addendum 32 stimava lo shared "6,75 MB/token": era l'equivoco slot-IQ2 — lo shared e' Q8 e pesa
26,7 MB/layer (sotto).

**1) Zero predizione — VERO.** Un solo shared per layer (DS4_N_EXPERT_SHARED=1, ds4.c:117), eseguito
incondizionatamente nel grafo del layer (gate/up/SwiGLU a ds4.c:12232-12244 o fusi 12213-12222; down a
12233-12251). Identita' nota a priori, nessun router.

**2) Concorrente per costruzione — VERO, con un dettaglio.** L'input dello shared e' `g->ffn_norm` (12222, 12227,
12231), lo stesso vettore da 16 KB che la lane gia' porta a terra (input_bytes=16384). Il join col routed:
- percorso di produzione (fuso): `ds4_gpu_shared_down_hc_expand_q8_0_tensor(after_ffn_hc, shared_out, ...,
  shared_mid, routed_out, after_attn_hc, ...)` — **ds4.c:12233-12245**: down(shared)+somma+HC in un kernel.
- percorso NON fuso gia' esistente: shared_out calcolato prima, poi
  `ds4_gpu_hc_expand_add_split_tensor(after_ffn_hc, routed_out, shared_out, after_attn_hc, ...)` —
  **ds4.c:12275-12282** (piu' `ds4_gpu_add_tensor(ffn_out, shared_out, routed_out)` a 12258-12259 quando serve
  ffn_out). → Il punto di somma accetta uno `shared_out` prodotto ALTROVE: per il contributo CPU basta un H2D di
  16 KB in `shared_out` prima del lancio del kernel di join, cioe' lo stesso contratto di consegna del parziale
  della lane (ownership device-side del fix Fable, .microbench/lane_fable/). L'arrivo tardivo e' tollerato fino
  al punto in cui il main thread accoda il join: su layer con miss la finestra e' la staffetta (media 4,9 ms/layer
  nel regime gate, AR RUN2); su layer all-hit e' ~0,4 ms.
- AV (inventario indipendente, LEDGER:16493-16556) conferma: shared gate/up/SwiGLU spostabile, "fused
  shared-down/HC legge routed_out → NO prima del routed", e **"non esiste nei dati una durata reale dello shared
  expert"** — quindi i miei costi sotto sono aritmetica, non misura.

**3) Libera residenza, non trasporto — VERO nei numeri, CONDIZIONATO nel meccanismo.**
```
Q8_0 = 34 B / 32 elem.  Per layer: 3 matrici 4096x2048 = 25.165.824 elem
  → 25.165.824/32*34 = 26.738.688 B/layer (=3 range da 8.912.896 B = 8,50 MiB l'uno)
  → x43 layer = 1.149.763.584 B = 1,0707 GiB
Slot IQ2 = 7.077.888 B → 1.149.763.584 / 7.077.888 = 162,4 → +162 slot (non ~170)
Swap byte-per-byte: 162*7.077.888 = 1.146.617.856 B ≤ 1.149.763.584 → pressione VRAM netta ≈ -3,1 MB (neutra)
```
- Il precipizio-V2 (211 slot → 883.704 sfratti backbone, LEDGER:17564-17584) nasceva dal CRESCERE della cache
  sopra un backbone intatto usando una fotografia bugiarda della VRAM libera; qui il backbone CALA degli stessi
  byte: il driver del precipizio e' neutralizzato per costruzione. Da provare comunque (T1-bis gate 2), perche'
  V1 ha mostrato ~730 sfratti/token di fondo non attribuiti (LEDGER:17540-17547).
- CONDIZIONE ABILITANTE da verificare per prima (T0.4): che i range shexp siano **individualmente rilasciabili**.
  Evidenza pro: lo staging del modello alloca per-range con nome per coppia (`CUDA model range alloc failed for
  q8_0_pair0/pair1 (8.50 MiB)`, log L2/L3 in LEDGER:17714-17719 — 8,50 MiB = esattamente UNA matrice shexp);
  eviction per-range esistente (`cuda_model_pick_victim`, LEDGER:17860-17864). Evidenza contro: il pin.patch
  dichiara che lo slab expert contiguo "si sovrascrive ma non si restituisce al driver" (LEDGER:17866-17870) —
  se anche i range del backbone fossero sub-allocati in regioni fuse, il rilascio non darebbe VRAM vera e la
  traccia 6 perderebbe il beneficio di capacita' (morte immediata, vedi criteri).
- Secondo beneficio non quantificato nel mandato: se oggi parte dei 722 sfratti backbone/token colpisce range
  shexp, spostarli su CPU toglie anche quei ricarichi dal bus. Attribuzione assente → contatore da 5 righe in T0.4.

**4) Ritmo CPU — VERO con margine, nel regime ATTUALE.**
```
26.738.688 B/layer a ~44 GB/s DRAM = 0,61 ms/layer (pavimento)
realistico con pool row-parallel (dequant Q8 banale, kernel classe-bench):  0,6-1,2 ms/layer
finestra di consegna: staffetta media 4,9 ms/layer (regime gate, hit 26%)
P(layer all-hit) ≈ 0,26^6 ≈ 0,03% → oggi la finestra c'e' su ~100% dei layer
```
- MA: la finestra si restringe proprio quando il PILOTA funziona (layer all-hit → finestra 0,4 ms < 1 ms CPU).
  Interazione quantificata: a conversione piena, tassa ~+0,6 ms x 43 = **+26 ms/token** che eroderebbe il tetto
  del pilota da 6,2 a ~5,3 t/s. Le due leve si pesano INSIEME nel piano: lo shared-CPU va misurato anche
  nell'arm col pilota acceso, non solo da solo. (In compenso i suoi +162 slot regalano al pilota una finestra
  senza sacrificare la LRU: scioglie P5.)
- Il guadagno GPU diretto e' trascurabile (26,7 MB a ~300 GB/s ≈ 0,09 ms/layer): il valore sta TUTTO nei 162
  slot e negli eventuali ricarichi shexp evitati. Chi si aspetta il layer piu' veloce di 1 ms restera' deluso:
  dirlo prima.

**5) Idraulica riusabile — VERO al 70%.** Riusabile: ponte D2H ffn_norm 16 KB, H2D parziale 16 KB, join
device-side (pattern fix-Fable), pool worker. Mancante: (i) un job-type "shared" nella lane (oggi tratta solo
route IQ2/Q2 con backing arena/staging, enum a ds4_cuda.cu:1673-1675); (ii) il forward Q8 CPU **esiste**
(ds4.c:6094-6141) ma va incapsulato row-parallel come fu fatto per il kernel della lane
(.microbench/lane_kernel/); (iii) un flag che salti i kernel shared GPU e instradi il join sul percorso non-fuso
(gia' esistente, punto 2). Nessun kernel CUDA nuovo.

**6) Qualita' — Q8=Q8 ma NON bit-exact.** Stessa precisione di formato; cambia l'ordine di somma float
(riduzioni GPU vs accumulo CPU). Il metro per quantificare esiste in-tree: il graph-test stampa il diff CPU/GPU
per stadio, incluso `shared=%g/%g` (max/rms) — ds4.c:12663-12677 — eseguibile con binari esistenti (e' un run
del motore: NON eseguito ora per mandato). Conseguenza di metodo da dichiarare al progetto: un arm shared-CPU
non passera' MAI il confronto sha golden/current; il gate di qualita' deve essere il rubric cieco (protocollo
fail-fast, n≥3). Evitare il fallback dinamico per-layer CPU→GPU (renderebbe il testo non riproducibile
run-su-run): se il deadline manca, meglio uno split STATICO di layer.

---

## 8. DOMANDA 5 — PIANO A STADI CON CRITERI DI MORTE

Il protocollo di misura resta quello del gate (>=5 t/s sostenuto, 2 famiglie, doppio prompt KV in cache,
ctx/KV 150k, testo integro — LEDGER:17749-17765) + regola fail-fast (stop alla prima degenerazione).

### T0 — OFFLINE, zero server, zero rischio (2-4 giorni-agente, parallelizzabile)
| # | Misura | Come (con l'esistente) | UCCIDE se |
|---|---|---|---|
| T0.1 | Traccia ID per-selezione: overlap per-layer t/t+1, hit-rate finestra-oracolo a 140 e a 302 slot, distanza utile di lookahead | emettitore ~25 righe in `cuda_moe_tiering_observe_route` (ds4_cuda.cu:41387-41400) dietro env; run 2 famiglie x 160 tok; sim offline stile `analyze_tiering_observe` (J22/J25) | oracolo-finestra a 140 slot converte < 0,75 dei miss → il gate e' irraggiungibile per QUALSIASI pilota → resta solo traccia 6; se < 0,5 chiudere il filone A |
| T0.2 | Fedelta' route di c-lite: recall/precision@6 del router VERO su hidden avanzato senza attenzione (e variante SWA-128), a orizzonte 1/5/10/20 layer | replay CPU teacher-forced su stream corti (200 tok) col backend CPU esistente (DS4_BACKEND_CPU; ~194 ms/token → ~40 s/run); confronto route reali vs route c-lite | recall@6 < 0,75 O precision < 0,85 a orizzonte 10 → c-lite muore; fallback: orizzonte ridotto (5) + SPX1 in coda; se anche a orizzonte 3 < 0,6 → livello A chiuso |
| T0.3 | Drafter: agreement argmax MTP-Q1_0 vs MTP-Q4K + accettazione teacher-forced vs target, su 500+ token reali | tool standalone CPU (dequant Q4_K esiste in `tools/mtp_q4k_requant.c` con golden; kernel Q1 audit0); target argmax dal backend CPU | accettazione Q4K < 0,35 a k=2 → livello B chiuso (Colibri conferma); Q1_0 < 0,6 di agreement → Q1_0 solo-routing, mai commit |
| T0.4 | Traccia 6, condizione abilitante: attribuzione sfratti per range (quanti dei 722/token sono shexp?) + prova che un range shexp e' rilasciabile con VRAM restituita | contatore da ~5 righe in `cuda_model_pick_victim` + probe cudaMemGetInfo; graph-test per il diff `shared` per stadio (ds4.c:12663) | range shexp NON rilasciabili singolarmente → il +162 slot e' finto → traccia 6 ridotta a ~0 beneficio → morta |

### T1-bis — SHARED-CPU dietro flag (la piu' semplice, dopo T0.4)
Arm A: solo offload (slot INVARIATI a 140) → gate 1: PRE non peggiora oltre il 2% (222,4 ms → ≤227) e rubric
cieco n≥3 senza degenerazioni. Arm B: offload + swap slot 140→302 → gate 2: sfratti backbone ≤ 722/token
(niente precipizio) e POST ≥ +0,3 t/s (3,39 → ≥3,7).
**MUORE se**: gate 1 fallisce (tassa join > beneficio zero — a slot invariati il beneficio E' zero, quindi il
gate 1 misura SOLO la tassa); gate 2 sotto +0,3 t/s; o qualita' rubric < baseline. Nota pre-registrata: il
beneficio atteso da curva a 302 slot e' +0,4-1,0 t/s (interpolazione 258→512), NON il gate da solo.

### T1 — PILOTA SOLO-PREFETCH dietro flag (zero rischio qualita': il token vero resta della GPU)
Composizione minima: token campionato (niente MTP) + c-lite sul pool g132 + advisory queue nel budget g133 con
TTL + finestra cap 60 slot; SPX1 opzionale in coda. A/B stesso binario, metrica primaria vram_hits/selected e
staffetta ms/token, POI t/s.
**MUORE se** (numeri, ciascuno sufficiente):
1. conversione misurata < 0,5 (da telemetria hit) → resa massima < +0,25 t/s → chiuso;
2. byte H2D/token > +15% vs ancora (precisione runtime sotto ~0,85) → falsificato dall'identita' del trasporto;
3. sfratti backbone > 722/token o vram_hits dei NON-finestra in calo > 5 punti (la finestra cannibalizza) —
   a meno che T1-bis non sia gia' promosso (302 slot);
4. POST < +0,4 t/s con conversione ≥ 0,6 → il modello staffetta→tempo e' sbagliato → STOP e ridiagnosi (non
   tarare a caso: regola del ledger).
Bersaglio dichiarato falsificabile: conversione 0,75 → 5,1 t/s POST.

### T2 — COMMIT (MTP+DSpark), solo se T0.3 e' vivo
Ordine: (1) testa MTP ibrida (blocco CPU + head GPU) che riempie `drafts[]`; (2) k=2 con decode2-exact
(percorso esatto esistente); (3) k>2 col verifier batch SOLO dopo rubric sul flip greedy (ds4.c:16240-16247).
**MUORE se**: accettazione live k=2 < 0,35 (throughput teorico < +10% al costo di 10-14 ms/token di draft);
o il rubric segna degenerazioni sul verifier batch; o l'occupazione CPU del draft ruba al pilota T1 (i due
condividono il pool: budget core esplicito, il pilota ha precedenza — il commit e' il ciliegino, non la torta).

### Confronto finale delle quattro tracce (costo → tetto → primo numero che le uccide)
| Traccia | Lavoro fino al primo verdetto | Tetto t/s (POST) | Primo kill-number |
|---|---|---|---|
| Shared-CPU (6) | T0.4 (giorni) + T1-bis | ~3,7-4,4 da sola | range non rilasciabili (T0.4) |
| Pilota c-lite (A) | T0.1+T0.2 offline | 6,2 (r=1); 5,1 a r=0,75 | recall@6 < 0,75 a orizzonte 10 (T0.2) |
| SPEX SPX1 solo | gia' misurato (G15/G16/G34) | ~3,9 | GIA' morto come solista; vive da correttore |
| MTP commit + DSpark (B) | T0.3 offline | 3,39x(1+a2)/1,1 → 5,0 a a2≈0,68 | accettazione Q4K < 0,35 (T0.3) |

Le tracce si COMPONGONO: shared-CPU (302 slot) rimuove il vincolo P5 del pilota; il pilota rimuove la staffetta
che e' il muro di entrambe; il commit moltiplica solo cio' che gia' funziona. Ma la sequenza di verdetti e' tutta
offline-first: **quattro numeri (T0.1-T0.4) decidono l'intero filone senza toccare un server**.

---

## 9. REGISTRO FONTI PRINCIPALI
- Codice: `ds4-p4a/ds4.c` (gate spec 21078-21081; probe/draft 21106-21118, 21227-21250; margin 21258-21301;
  decode2 21309-21366; batch 21407-21530; verify 16157-16247; MTP bind/layout 3053-3098, 3632-3667; shared CPU
  6094-6141; join shared/routed 12233-12282; SPEX 9652-9830, 10161-10200, 10311-10318; pool 827-895; costanti
  104-126; predicato routed 2907-2912; clamp draft 19711-19712), `ds4-p4a/ds4_server.c` (7466, 7479, 7484-7486,
  8455-8460), `ds4-p4a/ds4_cuda.cu` (dispatcher 46893+; lane 1668-1807, 49136-49137, 49676-49793; tiering
  31549, 32114-32155, 32742, 37964-38011, 41387-41400; trace 28706-28744).
- Risultati in-tree: `ds4-p4a/G13..G16_SPEX_*.md`, `G34_SPEX_CPU_OBSERVE_RESULTS.md`,
  `tools/audit0_microbench/results_cpu.md`.
- Ledger: sezioni E/F (105-128), J4-J32 (352-380), Addendum 32/33 (4857-4875), Addendum 36 (4906-4999),
  AE (13113+), AF-AH (13708-14117), AN (14785+), AO5 (15319-15366), AQ (15528-15667), AR (15667-15904),
  AS (15904-16068), AT (16157-16193), AV (16312-16717), M1/M2+mandati (17329-17360), curva (17552-17640),
  Colibri (17641-17686), lane (17688-17750, 17824-17870, 17889-17953, 18013-18127).
- D:\ (sola lettura): `ds4_work/c3c_mtp_cpu.log` (dossier MTP-CPU 22/7), `ds4_work/c3a_mtp_gate/*` (2 run ERROR),
  `ds4_work/` (nessuna traccia LOG_IDS trovata).
- Artefatti: `runs/spex/spex_model/ds4flash_d2_nextlayer.spex` (90.177.568 B), `C:\ds4-models\` (MTP Q4K 3,81 GB
  e Q1_0 1,09 GB presenti), `.microbench/gran_spec/spec_trace.patch` (gia' nel tree).
