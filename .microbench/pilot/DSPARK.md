# DSPARK (deepseek-ai/DeepSeek-V4-Flash-DSpark) — il drafter ufficiale e i nostri GGUF "MTP"

Agente: Fable. Data: 2026-07-29. Correzione di bersaglio del mandato addendum: il riferimento e' il **repo
modello** https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-DSpark ("not a new model: the same checkpoint
with an additional speculative decoding module attached", metodo vLLM `dspark`, `num_speculative_tokens=7`,
greedy di default, licenza MIT — README HF, fetch 2026-07-29), non il codebase DeepSpec.
Niente build, niente server, D:\ sola lettura. Raccordo con `DEEPSPEC.md` in fondo (le sue conclusioni su
verify-semantics e confidence restano valide; questo file corregge l'identita' del modulo).

## Fonti
- **GGUF locale ispezionato a macchina** (lettore GGUF inline, header+tensori):
  `C:\ds4-models\DeepSeek-V4-Flash-MTP-Q4K-Q8_0-F32.gguf` — dump completo in sez. 1.
- **HF DeepSeek-V4-Flash-DSpark**: README (fetch), `config.json` (raw fetch), `inference/config.json` (raw),
  `inference/model.py` (raw, 45,1 kB, due fetch mirati), `inference/convert.py` (raw), file list `/tree/main`
  (48 shard safetensors, ~167 GB, fp8 + esperti fp4).
- **HF DeepSeek-V4-Flash (base)**: `config.json` (raw fetch).
- **HF antirez/deepseek-v4-gguf**: pagina repo (fetch) — provenienza dei nostri GGUF.
- **Misure GIA' IN CASA (2026-07-05)**: `runs/dspark/20260705_mtp_acceptance_pod3090/RISULTATI.md` (pod A) e
  `runs/dspark/20260705_dspark_b_v4flash_2xh200/RISULTATI.md` + `accept.csv` (pod B, modulo ufficiale).
- Materiale DSpark locale: `docs/CONSOLIDATION.md` (par. DSpark, righe 78-85),
  `reap-loop/docs/references/DSpark_paper.txt`, `reap-loop/docs/dspark/DESIGN_DSPARK_DS4.md`,
  `reap-loop/docs/briefs/BRIEF_DSPARK_MTP_DS4.md`, patch `reap-loop/patches/ds4/0008-0010-dspark-*`.
  **`DSpark_clean.txt` NON trovato** (cercato in `C:\Users\imanu\source\repos\*`, `D:\ds4_work`): il testo del
  paper in casa e' `DSpark_paper.txt`.

---

## 1. IPOTESI CENTRALE: i nostri GGUF "MTP" SONO il modulo DSpark?

**Verdetto: NO in senso stretto — sono il modulo NextN/MTP del V4-Flash BASE (1 blocco). Il modulo DSpark
ufficiale e' un artefatto PIU' GRANDE (3 blocchi + tre teste in piu') che NON abbiamo in GGUF. MA la versione
utile dell'ipotesi e' VERA: il drafter first-party ce l'abbiamo gia' in casa, e' quello che il runtime gia'
supporta con `--mtp`, e la sua accettazione e' GIA' MISURATA (sez. 4).**

Confronto tensore-per-tensore:

**Il nostro GGUF** (dump diretto, 32 tensori, `general.architecture=deepseek4_mtp_support`,
`deepseek4.mtp_layer_count=1`, `deepseek4.nextn_predict_layers=1`):
```
mtp.0.{e_proj,h_proj}          [4096,4096] Q8_0     <- combinatore V3-style (eh split in due)
mtp.0.{enorm,hnorm,norm}       [4096] F32
mtp.0.hc_head_{fn,base,scale}  [16384,4]/[4]/[1] F32
mtp.0.attn_{q_a,q_b,kv,output_a,output_b} Q8_0 (stesse shape del backbone: 4096x1024, 1024x32768,
                               4096x512, 4096x8192, 8192x4096) + sinks/norm F32
mtp.0.ffn_{gate,up,down}_exps  [4096,2048,256] Q4_K (type 12)   <- 256 esperti routed
mtp.0.ffn_{gate,up,down}_shexp [4096,2048]/[2048,4096] Q8_0     <- 1 shared
mtp.0.ffn_gate_inp [4096,256] F32 + exp_probs_b [256] F32       <- router
```
**Il modulo DSpark ufficiale** (`inference/model.py`, quote dal `DSparkBlock.__init__`):
- `n_mtp_layers = 3` blocchi transformer COMPLETI (attention senza compressione KV + MoE 256+1) —
  `inference/config.json: n_mtp_layers=3`; l'array `compression_ratios` ha **46 = 43+3** voci con le ultime tre
  a 0; la nostra run Strada B lo descrive misurato: "drafter DSpark-5: **3 layer MoE + Markov head**"
  (`runs/dspark/20260705_dspark_b_v4flash_2xh200/RISULTATI.md`).
- stage 0: `main_proj = Linear(dim * len(dspark_target_layer_ids), dim)` + `main_norm` → proietta il
  **concat degli hidden dei layer target [40,41,42]** (config.json: `dspark_target_layer_ids=[40,41,42]`).
- stage finale: `norm` + `markov_head = DSparkMarkovHead(vocab, 256)` + `confidence_head =
  DSparkConfidenceHead(dim + 256)` + `hc_head_{fn,base,scale}`.
- embedding e lm_head CONDIVISI col target (`self.mtp[-1].embed = self.embed; ... head = self.head`).
- **`e_proj`/`h_proj`/`enorm`/`hnorm` NON esistono da nessuna parte in model.py** (verificato con domanda
  mirata sul file).

Quindi: stessa FAMIGLIA (blocco MTP V4 con MoE 256+1, hc head, embed/head condivisi — le shape del blocco
combaciano al 100%), ma **il nostro file e' il NextN a 1 blocco con combinatore e_proj/h_proj** (il modulo che
il config del V4-Flash BASE dichiara: `num_nextn_predict_layers=1`, **zero chiavi dspark_**, fetch config base),
mentre **il modulo DSpark aggiunge: 2 blocchi in piu', main_proj su 3 hidden, testa Markov, testa confidence,
drafting a blocco con noise token** (`dspark_noise_token_id=128799`, `dspark_block_size=5`,
`dspark_markov_rank=256` nel config DSpark; `convert.py` mappa `markov_w1/markov_w2` e tratta tensori con
prefisso `mtp.`). Provenienza del nostro file: antirez/deepseek-v4-gguf lo pubblica come "MTP /
speculative-decoding support (optional, not standalone)", 3,6 GiB — la pagina cita l'architettura come
"deepseek4-dspark" per la famiglia, ma il contenuto convertito e' il NextN (il dump sopra e' l'evidenza).
Nota di coerenza: il backbone dei due repo HF e' DICHIARATO identico ("the same checkpoint"), quindi per il
target non cambia nulla; cambia solo QUALE drafter possediamo.

---

## 2. DOMANDA 1 — Architettura, parametri attivi, costo CPU per ciclo

**Parametri ATTIVI per posizione di draft** (esclusa la testa lm condivisa, 4096x129280 = 529,5M):
```
NOSTRO NextN (1 blocco):  attention 106,95M + shared 25,17M + 6 routed 151,0M + router 1,05M
                          + e_proj/h_proj 33,55M                      ≈ 317,7M attivi
DSpark ufficiale (3 bl.): 3 x 284,2M + main_proj 50,33M (12288x4096) + markov 66,2M  ≈ 969M attivi
```

**Costo CPU per token di draft — NOSTRO modulo** (riferimenti kernel: Q1_0 294,4 µs/expert @4 thread e
232,6 µs @12 (tools/audit0_microbench/results_cpu.md); IQ2 row-parallel 1,08 ms/expert misurato vivo
(LEDGER K1); DRAM ~44 GB/s; Q8 su CPU ~20-30 GB/s effettivi):
```
denso Q8 (attn 113,8 MB + shexp 26,7 MB + e/h_proj 35,7 MB = 176 MB): 5,9-8,8 ms
routed:  6 x Q1_0 (3,54 MB/exp, kernel audit0)      = 1,4-1,8 ms
         oppure 6 x Q4_K (14,16 MB/exp, kernel DA SCRIVERE, stima bandwidth) = 2,8-4,2 ms + dequant
attenzione: SWA <=128 posizioni (raw_window=DS4_N_SWA, ds4.c:10879-10886)  < 0,5 ms
testa lm:  su GPU (residente) ~2 ms | su CPU 562,6 MB = 14-28 ms
TOTALE/draft: ~10-13 ms (esperti Q1_0 + testa GPU) | ~12-16 ms (Q4_K CPU) | ~25-45 ms (tutto CPU)
```
**Ciclo di speculazione k=7 (il nostro modulo e' AUTOREGRESSIVO: 7 forward in catena, ds4.c:21227-21250):**
```
k=7 x (10-13 ms)  = 70-90 ms/ciclo   (Q1_0 + testa GPU; CPU occupata ~60-75 ms, GPU ~14 ms)
k=7 x (12-16 ms)  = 85-115 ms/ciclo  (Q4_K CPU, kernel da scrivere)
contro un budget di 295 ms/token nel regime gate: il ciclo costa 0,24-0,39 token-equivalenti
```
Il modulo ufficiale ammortizzerebbe meglio (backbone parallelo sul blocco: UNA passata per 5-7 posizioni +
correzione Markov sequenziale quasi gratis — la firma "semi-autoregressive" del paper), ma **il trucco non si
trasferisce al nostro NextN**: il blocco parallelo richiede il training coi noise token
(`dspark_noise_token_id`), che il nostro 1-blocco non ha. Il DSpark ufficiale su CPU costerebbe ~3x il blocco
nostro per posizione ma x1 per ciclo grazie al blocco parallelo (~35-50 ms/ciclo stimati); oggi pero' NON e'
convertito ne' supportato dal motore (sez. 6).

## 3. DOMANDA 2 — Ingresso del modulo, compatibilita' col punto ds4_server.c:7466

- **Ufficiale**: `forward_spec(input_ids, main_hidden, start_pos)` — `main_hidden` = concat degli hidden dei
  layer **[40,41,42]** del forward target appena concluso (mediati sulla dimensione HC), proiettati da
  `main_proj`; il blocco draft parte da `input_ids` = token corrente REALE in posizione 0 + noise token
  (`forward_embed`, model.py). Durante il prefill (`start_pos==0`) costruisce solo la propria KV.
- **Nostro**: `metal_graph_eval_mtp_draft_from_hc(g, ..., g->cur_hc, token, pos, ...)` (ds4.c:15404-15425) —
  hidden HC finale del token appena committato via `h_proj` + embedding del token noto via `e_proj`.
- **Compatibilita' col nostro punto di campionamento**: PIENA per entrambi. Il server campiona il token in
  testa al loop (`int token = ds4_session_sample(...)`, ds4_server.c:7466) e solo dopo chiama eval: al momento
  del draft il token vero t+1 e' noto, che e' esattamente il contratto dei due moduli (token corrente +
  hidden dell'ultimo forward). Per una esecuzione CPU del NOSTRO modulo il ponte dati e' un D2H di
  `cur_hc` (4x4096 F32 = 64 KB/token) — stessa classe del ponte lane gia' misurato (16 KB).
  Per il modulo ufficiale servirebbero gli hidden di 40/41/42 (3x16 KB dopo la media HC).

## 4. DOMANDA 3 — Accettazioni: dichiarate e MISURATE IN CASA; il vincolo >=0,68; Colibri

**Il repo HF non dichiara numeri** (README: nessuna accettazione/speedup; il paper DSpark arXiv:2607.05147
dichiara +60-85% velocita' per-utente su V4). MA il progetto li ha GIA' MISURATI il 2026-07-05, su entrambe
le teste, greedy teacher-forced:

**(a) Il NOSTRO GGUF Q4K sul NOSTRO target 2-bit** (pod 3090, combo probe `--mtp-draft 2 +
DS4_MTP_SPEC_DISABLE=1 + DS4_MTP_PROBE=1`, 149 confronti/run, doppi run bit-identici —
`runs/dspark/20260705_mtp_acceptance_pod3090/RISULTATI.md`):
```
acceptance top-1 (pos1):  code 0.872 | math 0.846 | chat 0.604
```
**(b) Il modulo DSpark UFFICIALE su V4-Flash fp8/fp4** (2xH200, 195 cicli/dominio, 585 righe accept.csv —
`runs/dspark/20260705_dspark_b_v4flash_2xh200/RISULTATI.md`):
```
acceptance condizionale: code pos1..5 = 0.979/0.948/0.928/0.899/0.821  τ=5.18/6
                         math          0.959/0.936/0.903/0.880/0.863   τ=5.00/6
                         chat          0.713/0.612/0.635/0.667/0.500   τ=2.70/6
```

**Contro il vincolo >=0,68** (dal batch-verify k<=16, ANALISI_FABLE.md sez. 6): il nostro NextN Q4K lo
SUPERA a pos1 su code (0,87) e math (0,85), lo MANCA su chat (0,60) — e il regime gate e' 2 famiglie di cui
una chat/HTML-like. Buco dichiarato: **l'accettazione condizionale a pos>=2 del NOSTRO modulo non e' mai
stata misurata** (il pod A misuro' solo MTP-1); il decadimento lento dell'ufficiale (code 0,82 a pos5) NON e'
trasferibile automaticamente a un 1-blocco. E' esattamente il buco che T0.3 chiude, con la stessa combo probe
gia' provata.

**Colibri (int8 ok, int4 0-4%): SUPERATO dai dati di casa.** Due fatti: (i) il modulo ufficiale gira con
**esperti fp4 nativi** (config: `expert_dtype: fp4`) e fa τ≈5/6 su code — 4-bit-class NON uccide un drafter
ADDESTRATO/nato a quella precisione; (ii) il nostro Q4K (convertito dal fp8/fp4 nativo) misura 0,60-0,87, non
0-4%. La lettura corretta del dato Colibri: il collasso int4 riguarda la quantizzazione POST-HOC naive di una
testa nata bf16 — e infatti il rischio residuo da noi e' il **Q1_0 requantizzato** (cosine 0,798-0,793 vs
Q4K, LEDGER AS:15963-15990), non il Q4K. **Il Q4K nostro e' abbastanza per code/math; chat va misurato oltre
pos1 prima di giudicare.**

## 5. DOMANDA 4 — Calibrazione: il materiale locale descrive QUESTO modulo?

**SI'.** Tre riscontri:
1. `docs/CONSOLIDATION.md:78-85` descrive la macchina DSpark: "**confidence head** σ(w·[hidden ;
   Markov-embedding]) che predice l'accettazione; **Sequential Temperature Scaling (STS)** ... minimizzando
   l'ECE su held-out; **scheduler hardware-aware**". Combacia col codice ufficiale:
   `DSparkConfidenceHead(dim + markov_rank)` = proiezione su [hidden ; markov-embedding] → scalare, e
   `DSparkMarkovHead(vocab, 256)` (model.py, quote in sez. 1).
2. Il paper in casa (`reap-loop/docs/references/DSpark_paper.txt`, righe 21, 75-76, 173-175, 203-204) descrive
   confidence-scheduled verification e lo scheduler di prefisso — la stessa pipeline del modulo.
3. **Il primo dataset di calibrazione sul modello vero esiste gia'**: `accept.csv` (585 cicli con LOGIT
   pre-sigmoide c1..c5 della confidence head, fp32) + la tabella ECE misurata (code pos1 0,014 → pos5 0,151;
   chat 0,118 → 0,36-0,44: sottoconfidente in profondita' — RISULTATI.md Strada B), con la nota esplicita che
   serve la STS del paper §3.2.1 per i valori assoluti.
**Limite onesto**: teste Markov+confidence appartengono al modulo UFFICIALE; il nostro NextN non le ha. La
macchina di calibrazione in casa serve quindi (a) subito, come criterio di schedulazione basato su margine
(il nostro margin gate ds4.c:21258-21301 e' il surrogato a 1 feature, gia' nel motore); (b) come progetto
completo solo se si converte il modulo ufficiale o si addestra una confidence head sopra il NextN.

## 6. DOMANDA 5 — INNESTO: cosa manca esattamente (a pezzi, in ordine)

Verificatore k<=16: GIA' PRONTO (`metal_graph_verify_suffix_tops` ds4.c:16157-16231; `drafts[16]` 21179;
clamp `--mtp-draft` 1..16 a 19711-19712; server `toks[17]` ds4_server.c:7479). Consuma solo interi.

**(a) Caricare il modulo — perche' "il loader rifiutava":** distinguere i due casi, entrambi verificati:
- **Q4K: il loader NON rifiuta.** Load + secondary map OK (probe AR: "MTP support model loaded ...
  secondary-map-ready", LEDGER:15855-15880). A morire e' il **dispatcher CUDA routed**, che accetta solo
  IQ2/Q2, IQ1_S, Q1_0 e ritorna zero silenzioso su Q4_K (`routed_moe_launch_impl`, ds4_cuda.cu:46893+,
  predicato ~46978) → "mtp probe draft failed" a ogni token.
- **Q1_0: il loader rifiuta davvero.** `tensor_is_routed_expert_type` (ds4.c:2907-2912) include Q4_K ma
  OMETTE Q1_0 → il bind MTP fallisce ("type 41 ... expected a routed expert quant type", LEDGER:16157-16180);
  e anche corretto il predicato, la route Q1_0 dalla mappa MTP e' fail-closed (il selected loader esige
  l'identita' della mappa sidecar globale — analisi AS, LEDGER:15994-16022). **Due gate, entrambi noti.**

**(b) Eseguire su CPU** (la via che non tocca la VRAM ne' gli sfratti — M2: dual-map GPU = +1094
evict/token, LEDGER:17337-17347):
1. **Kernel CPU routed Q4_K** — ASSENTE nel motore (il CPU routed fa IQ2 pair + Q2_K: ds4.c:4760, 4928;
   conferma dossier `D:\ds4_work\c3c_mtp_cpu.log`). Riferimenti pronti: dequant Q4_K con golden vectors in
   `tools/mtp_q4k_requant.c`; harness di misura classe audit0. Stima: 1-2 giorni con bench.
   (Alternativa: esperti Q1_0 col kernel classe audit0 gia' misurato — ma richiede il fix (a)-Q1_0 nel
   VALIDATORE cpu-side e paga il rischio qualita' cosine 0,80 → T0.3 arbitra.)
2. **Forward CPU del blocco MTP** — assente come funzione unica; i pezzi esistono (shared Q8:
   ds4.c:6094-6141; attenzione SWA-128 da scrivere lato CPU; hc head; e_proj/h_proj = matvec Q8 esistenti).
   Stima del dossier c3c: classe L; con la nostra aritmetica: 10-13 ms/draft con testa su GPU.
3. **Ponte dati**: D2H `cur_hc` 64 KB/token a fine token (pattern ponte lane, 16 KB gia' misurato) + H2D del
   token/hidden per la testa GPU (16 KB) — idraulica gia' provata (input_bytes/partial_bytes della lane).
4. **Testa lm**: consigliata su GPU (residente, ~2 ms/draft, GEMV con topk esistente
   `ds4_gpu_indexer_topk_tensor`, gia' usato in verify a ds4.c:16208-16213).

**(c) Collegare i k draft al verificatore:**
5. Sostituire dietro flag le due chiamate di drafting GPU (`metal_graph_eval_mtp_draft` a ds4.c:21106-21118 e
   `..._from_hc` a 21231-21243) con la sorgente CPU; la contabilita' `DS4_MTP_KEEP_ACCEPTED`/`mtp_n_raw`
   (21220-21225) migra su stato CPU. Il resto della macchina (margin gate, decode2-exact, batch verify,
   commit/replay) resta INTATTO. Stima: 0,5-1 giorno una volta che (b) esiste.
6. **Gap temperatura** (ereditato, non nuovo): il percorso speculativo si ingaggia solo a `temperature<=0`
   (ds4_server.c:7484-7486) e verifica greedy; il gate gira a 0,7. Le accettazioni di sez. 4 sono greedy.
   Per T2 in-protocollo serve l'accept-rule a rejection sampling — algoritmo di riferimento gia' individuato
   (DeepSpec `base_evaluator.py:186-303`, vedi DEEPSPEC.md), ~60 righe, i logits per-riga ci sono gia'
   (`metal_graph_read_spec_logits_row`, ds4.c:16233-16241). In alternativa: negoziare il gate a temp 0.
7. (Solo se si vuole il drafter UFFICIALE, piu' avanti): conversione fp8/fp4→GGUF dei 3 blocchi + markov +
   confidence + main_proj dagli shard HF (tool nuovo classe mtp_q4k_requant, 1-2 giorni) + supporto motore a
   `mtp.{0,1,2}` + main_proj su 3 hidden + noise-block drafting (classe settimana). Da NON fare prima che il
   NextN a k>=2 abbia numeri (T0.3): τ=5/6 dell'ufficiale e' il tetto che giustificherebbe questo lavoro.

**Ordine consigliato**: T0.3 (accettazione condizionale pos>=2 del NextN, offline/probe, 0 rischio) → (b1)+(b2)
kernel Q4K CPU + forward blocco → (c5) innesto drafting → misura accettazione live greedy → (c6) rejection
sampling per il protocollo a 0,7 → solo con τ misurata ≥~1,7-2 su code+chat, valutare (7).

## 7. Raccordo con DEEPSPEC.md

DeepSpec (github) e' il codebase di TRAINING/EVAL della famiglia (varianti Qwen3/Gemma4: 5 blocchi densi,
block 7); il modulo di PRODUZIONE per V4-Flash e' quello descritto qui (3 blocchi MoE, block 5, target layer
40-42). Le conclusioni di DEEPSPEC.md restano valide e complementari: (i) la semantica di verifica ufficiale
e' rejection sampling con residual-sample al primo miss (il pezzo che ci manca per temp 0,7); (ii) confidence
head + STS sono la macchina di ammissione, e ora sappiamo che accept.csv ne e' gia' il primo dataset di
calibrazione sul modello vero; (iii) nessuna delle implementazioni pubbliche gestisce la fedelta' di ROUTE
nel draft — il pilota route-first di ANALISI_FABLE.md resta scoperto da prior art e da codice pronto.
Correzione rispetto a DEEPSPEC.md: la' scrivevo "il drafter ufficiale non e' in casa"; vero per il modulo
DSpark a 3 blocchi, ma il **NextN/MTP a 1 blocco in casa C'E', gira col runtime, e ha accettazioni misurate
0,60-0,87** — e' il punto di partenza giusto per T2.
