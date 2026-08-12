# DEEPSPEC (deepseek-ai/DeepSpec) — esame per il pilota c-lite e per T2

Agente: Fable. Data: 2026-07-29. Addendum al mandato pilota (richiesta utente).
Nessuna build, nessun server, D:\ sola lettura, scrittura solo in `.microbench/pilot/`.

## Fonti (in ordine di autorevolezza)

1. **Clone shallow LOCALE, ispezionato riga per riga**:
   `C:\Users\imanu\AppData\Local\Temp\deepspec-analysis-20260722`, commit
   `005e03b81cec38b7da6399833d609ee89a2587f2` ("Merge pull request #62 ... fix/atomic-step-latest-symlink"),
   verificato con `git log`. Tutte le citazioni `deepspec/...` e `config/...` sotto sono file di questo clone.
2. **GitHub raggiungibile**: https://github.com/deepseek-ai/DeepSpec — README coerente col clone (stessa tabella
   checkpoint, stessi riferimenti paper). Non ho ri-clonato: il clone locale basta ed e' ispezionabile offline.
3. **Analisi precedente gia' in casa** (22/7, oracolo Codex): `D:\ds4_work\g73_fix\deepspec_oracle.out.log`
   (copia identica: `C:\Users\imanu\AppData\Local\Temp\codex_deepspec.txt`). La cito come [oracle] solo dove non
   ho riverificato io direttamente; dove ho riverificato, cito il file del clone.
4. Paper: DSpark = arXiv:2607.05147; DFlash = arXiv:2602.06036; Eagle3 = arXiv:2503.01840 (README.md:69,97).
   Dell'abstract DSpark ho il fetch: dichiara "accelerates per-user generation speeds by **60 to 85 percent** at
   matched throughput levels" su DeepSeek-V4 e "confidence-scheduled verification ... semi-autoregressive
   architecture, coupling a parallel backbone with a lightweight sequential module". Nessun numero di
   accettazione nell'abstract; i numeri sono nella Table 1 del paper (README.md:55 rimanda li').

Cosa c'e' nel repo: "full-stack codebase for training and evaluating draft models" con tre algoritmi — DSpark,
DFlash, Eagle3 — target Qwen3-4B/8B/14B e Gemma4-12B, checkpoint BF16 su HF (README.md:55-63). **Nessun
checkpoint con target DeepSeek** e nessun supporto al nostro runtime: e' PyTorch/HuggingFace, BF16, GPU-residente
([oracle], sez. A/C; evaluator: `deepspec/eval/dspark/evaluator.py`).

---

## DOMANDA 1 — Il disegno del drafter, e cosa si trasferisce al nostro c-lite

### Come sono fatti (verificato nel clone)

| | DSpark / DFlash | Eagle3 |
|---|---|---|
| corpo draft | **5 layer** transformer alla larghezza del target (`config/dspark/dspark_qwen3_4b.py:14` `num_draft_layers=5`) | **1 layer** (asserito: `deepspec/eval/eagle3/evaluator.py:33-36`) |
| proposta | **blocco di 7 posizioni in UNA passata non-autoregressiva** (`block_size=7`, config:13; `is_causal=False` in `deepspec/eval/dspark/draft_ops.py:36-43`) | catena autoregressiva di 7 (`ttt_length`, evaluator.py:41) |
| ingresso | embedding del blocco: primo token REALE + token mask/noise (`mask_token_id`, config:16; `create_noise_embed`, `deepspec/modeling/dspark/qwen3/modeling.py:404-411`) | embedding dei token shiftati |
| contesto dal target | **concat degli hidden di 5 layer SPARSI del target** — per Qwen3-4B `target_layer_ids=[1,9,17,25,33]` (config:15) — estratti da `extract_context_feature` (`deepspec/modeling/dspark/common.py:52-57`) | identico (5 hidden concatenati) |
| fusione del contesto | `fc = Linear(5*hidden → hidden, bias=False)` + RMSNorm (`modeling.py:240-245`, applicata a `modeling.py:373`); il risultato entra in OGNI layer draft come K/V di contesto (`k_ctx/v_ctx` da `target_hidden_states`, `modeling.py:98-106`) | analogo |
| moduli extra DSpark | testa **Markov low-rank sui TOKEN** (Embedding vocab→256 + Linear 256→vocab, `deepspec/modeling/dspark/markov_head.py:8-26`) applicata in sequenza sul blocco parallelo (il "lightweight sequential module" dell'abstract; `modeling.py:309-333`), e **confidence head** = `AcceptRatePredictor: Linear(H→1)` (`common.py:42-47`) che TRONCA la proposta al prefisso confidente (`draft_ops.py:83-97,124-131`) | nessuno (DFlash = DSpark con `markov_rank=0` e senza confidence, [oracle] sez. A) |

**Stato d'ingresso per il "layer k del draft"** (la domanda esatta): NON esiste un hidden target per-layer-k.
Il draft e' un piccolo transformer separato il cui stato e' l'embedding del blocco (mask/noise) evoluto dai SUOI
layer; il contesto target entra come **riassunto statico** (i 5 hidden proiettati), identico per tutti i layer
del draft. DeepSpec **non insegue la traiettoria layer-per-layer del target**: la comprime una volta e basta.

### Fedelta' del routing MoE nel draft: NON GESTITA, e nemmeno posta

- I layer del draft sono densi; per il target MoE (Gemma4) il blocco MoE e' **esplicitamente non supportato**:
  `assert not bool(config.enable_moe_block)` — `deepspec/modeling/dspark/gemma4/modeling.py:175-176` e
  `deepspec/modeling/eagle3/gemma4/modeling.py:191-192`.
- L'eval non misura NULLA sulle route: `deepspec/eval/base_evaluator.py` raccoglie solo acceptance_length,
  verify_rate, accept_rate@position (righe 115-165); nessuna metrica expert/route/prefetch ([oracle] sez. B,
  riverificato con grep su `deepspec/modeling/` e `deepspec/eval/`: zero hit per moe/router/expert fuori dagli
  assert Gemma4).
- [oracle, Fonte esterna] Nell'implementazione ufficiale V4 (HF `DeepSeek-V4-Flash-DSpark/inference/model.py`)
  i primi tre layer di routing sono hash/token-ID; i successivi gate appresi sugli hidden. **Cross-check nel
  NOSTRO tree, verificato ora**: `DS4_N_HASH_LAYER = 3` (ds4-p4a/ds4.c:120) e per i layer 0-2 la route e' una
  **lookup I32 `ffn_gate_tid2eid` [6 x 129280]: token-ID → 6 expert** (ds4.c:3047-3049 layout, 3339-3341 bind,
  6210-6213 e 6688 uso). Conseguenza diretta per il pilota: **appena il token t+1 e' campionato
  (ds4_server.c:7466), le route dei layer 0-2 sono ESATTE gratis** — 3/43 layer di finestra senza forward ne'
  predizione, e un avvio pulito per la traiettoria c-lite.

### Cosa si trasferisce al nostro route-forward da 0,4-1,6 ms/layer (e cosa no)

Il nostro vantaggio dichiarato nel mandato — **token vero noto, errore-token zero** — rende superfluo l'intero
scopo primario di DSpark (indovinare i token del blocco). Quello che resta trasferibile e' il contorno, ed e'
roba buona:

1. **La ricetta delle feature** (concat di hidden MULTI-layer sparsi + proiezione lineare + norm) e' il progetto
   naturale di un eventuale "SPX2" addestrato: predire route(t+1, L) da [hidden(t) di 4-5 layer sparsi +
   embedding(token t+1)], per-layer, a costo di lookup. SPX1 usa il solo hidden di L (43 matrici 4096x256): la
   lezione DeepSpec e' che il segnale multi-layer + il token successivo REALE e' un input piu' ricco a costo
   simile. E' un'alternativa ADDESTRATA a c-lite se T0.2 boccia il forward approssimato — con lo stesso dataset
   di cattura 40/40 layer gia' in casa.
2. **Confidence head come ammissione**: `Linear(H→1)` che decide QUANTO fidarsi (loro: lunghezza della proposta;
   noi: se promuovere o no una predizione di route). Mappa 1:1 sul requisito precisione ≥0,85 di
   ANALISI_FABLE.md sez. 4: promuovere solo sopra soglia di confidenza e' il meccanismo che tiene i byte
   sprecati sotto il tetto. Il nostro margin gate MTP (ds4.c:21258-21301) ne e' gia' una versione a 1 feature.
3. **La conferma della circolarita'** ([oracle] sez. D, riverificata: il draft consuma hidden target di layer
   GIA' calcolati e produce token, mai route future): DeepSpec non contiene una soluzione pronta al nostro
   problema. Il pilota route-first non ha prior art qui dentro — ne' codice da copiare, ne' smentita.
4. NON si trasferisce: il corpo del draft (5 layer a larghezza target = 2,6-6,9 GB BF16, [oracle] sez. A/C —
   incompatibile con 12 GB e col formato ds4), la pipeline di training standard (cache hidden target da ~38 TB
   per Qwen3-4B, `scripts/data/README.md` via [oracle] sez. C), e qualunque checkpoint (nessun target DeepSeek).

---

## DOMANDA 2 — Accettazioni dichiarate e precisione della testa (per T2)

**Numeri di accettazione nel repo: NESSUNO.** Il README rimanda alla Table 1 del paper (README.md:55); l'eval
li calcola (acceptance_length, verify_rate, accept_rate@position — `base_evaluator.py:115-165`) ma il clone non
contiene risultati. L'abstract del paper DSpark dichiara solo **+60-85% di velocita' per-utente** su DeepSeek-V4
a throughput pari (arXiv:2607.05147) — su stack PyTorch/BF16/GPU-residente, cioe' un regime che non e' il nostro.

**Precisione della testa: SOLO BF16, mai quantizzata.**
- training `precision="bf16"` (`config/dspark/dspark_qwen3_4b.py:38`);
- gli evaluator caricano target e draft in BF16 sullo stesso device, **nessuna modalita' quantizzata o
  CPU-offload** ([oracle] sez. A, [Codice verificato] su `deepspec/eval/dspark/evaluator.py` e
  `deepspec/eval/eagle3/evaluator.py`);
- checkpoint BF16 1,85-6,86 GB ([oracle] sez. C, tabella HF).

**Risposta secca alla domanda "DeepSpec conferma o smentisce Colibri?"**: **NE' l'uno ne' l'altro — non tocca
mai il punto.** DeepSpec non scende mai sotto BF16, quindi non produce alcun dato sull'asse
int8-ok/int4-morto (Colibri, LEDGER:17684-17686) che governa il nostro T2. Il vincolo misurato nostro
(accettazione ≥0,68 per il gate col batch-verify k≤16, ANALISI_FABLE.md sez. 6) resta senza dato esterno per
teste Q4K/Q1: **T0.3 (agreement e accettazione offline delle teste MTP Q4K vs Q1_0) resta obbligatorio e non
sostituibile con letteratura.** L'unico contributo indiretto di DeepSpec: con testa in PIENA precisione e
blocco 7 su target denso, il guadagno e' 60-85% — leggilo come il TETTO ottimistico della famiglia, non come
una promessa per un 2-bit orchestration-bound su 12 GB.

Nota di riuso concettuale per T2: la **verifica confidence-scheduled** (lunghezza di proposta adattiva stimando
la sopravvivenza del prefisso — abstract + `draft_ops.py:83-97`) e' direttamente compatibile col nostro k≤16
parametrico (`--mtp-draft`, clamp 1..16 a ds4.c:19711-19712): k adattivo per richiesta invece di k fisso e' la
forma giusta di T2 se l'accettazione misurata sara' borderline.

---

## DOMANDA 3 — Semantica del verify: coincide col nostro k≤16?

**La loro** (`verify_draft_tokens`, `deepspec/eval/base_evaluator.py:186-303`, letta integralmente):
1. UNA passata target su `[token_corrente, draft_1..draft_k]` (`verify_length = k+1`, righe 214-222) con KV
   cache che avanza — stessa classe di ammortamento della nostra passata batch layer-major
   (`metal_graph_verify_suffix_tops`, ds4.c:16157-16231).
2. **Accettazione = REJECTION SAMPLING, non exact-match**: `accept_prob = clamp(p_target/p_draft, max=1)` per
   token proposto, estrazione Bernoulli, `cumprod` → prefisso accettato contiguo (righe 252-258).
3. **Primo miss**: il token rifiutato e' sostituito campionando dalla **distribuzione residua**
   (`sample_residual(target_probs - draft_probs)`, righe 278-283); se tutto accettato, token bonus campionato
   dall'ultima riga (riga 284-285). Max k+1 token per passata — identico al nostro tetto.
4. EOS dentro il prefisso accettato tronca (righe 264-276). KV del draft: cache separata con `crop(start)` per
   blocco (`draft_ops.py:44`) — stessa filosofia del nostro contatore `mtp_n_raw` (ds4.c:21214-21225).
5. **Ammortamento dei load esperti: concetto INESISTENTE** — target BF16 interamente residente, nessun tiering,
   nessuna nozione di costo per-expert. Il nostro ammortamento della staffetta (1 relay per layer per passata
   invece che per token) e' una proprieta' del NOSTRO runtime che loro non misurano ne' modellano.

**Divergenze rilevanti per T2** (in ordine di peso):

1. **Temperatura — la divergenza che conta.** Il loro verify e' distribution-exact a QUALSIASI temperatura;
   il nostro percorso speculativo e' greedy/argmax (`row0_top == drafts[1]` a ds4.c:21345;
   `row_tops[i-1] == drafts[i]` a ds4.c:21453-21456) e **si ingaggia SOLO a temperature <= 0**
   (ds4_server.c:7484-7486). Il protocollo gate gira a temp 0,7: cosi' com'e', T2 non puo' nemmeno accendersi
   nel regime del gate. Due strade: (a) negoziare il gate a temp 0 (cambia il protocollo pre-registrato);
   (b) portare nel runtime l'accept-rule di DeepSpec — `verify_draft_tokens` e' l'algoritmo di riferimento,
   ~60 righe, e noi ABBIAMO gia' i logits per-riga necessari (`metal_graph_read_spec_logits_row`,
   ds4.c:16233-16241; `row0_logits` nel decode2). E' il singolo pezzo di DeepSpec piu' utile da portare a casa.
2. **Bit-exactness vs tolleranza.** Noi trattiamo il flip greedy dei kernel batch come rischio di qualita'
   (commento esplicito ds4.c:16240-16247, e la coppia snapshot/replay `spec_frontier` per il partial accept);
   loro non hanno il problema: con accettazione stocastica il rumore dei kernel e' assorbito nella
   distribuzione. Se T2 adotta il rejection sampling, l'obiezione butterfly-greedy cambia natura (non sparisce:
   la nostra igiene golden/current sha resta incompatibile con QUALSIASI speculazione a temp>0 — gate di
   qualita' = rubric, come gia' notato per la traccia 6).
3. **Gestione del primo miss.** Loro: residual-sample al posto del rifiutato (un token comunque committato).
   Noi: commit del prefisso + replay/prefix-1 (ds4.c:21368-21393, 21529+). Mecanicamente compatibili; il
   residual-sample e' persino piu' economico del nostro replay quando i logits della riga sono gia' a terra.
4. **Forma della proposta.** Loro DSpark propone il blocco in una passata draft NON autoregressiva
   (mask/noise); il nostro drafting MTP e' ricorsivo autoregressivo (ds4.c:21227-21250). Non e' una divergenza
   del VERIFY ma del drafter: con k grandi il loro schema paga 1 passata draft invece di k. Rilevante solo se
   T0.3 promuove teste con accettazione alta.

**Coincidenza netta**: struttura della passata (k+1 in un forward, prefisso contiguo, bonus token, cap k),
gestione cache draft. **Divergenza netta**: regola di accettazione (stocastica vs greedy) e la conseguente
compatibilita' con temp 0,7 — che per il nostro gate e' decisiva.

---

## VERDETTO ADDENDUM

DeepSpec **non contiene il nostro pilota** (nessuna nozione di route/expert nel draft, MoE perfino asserito
non supportato) e **non tocca il nodo precisione-della-testa** (solo BF16): T0.2 e T0.3 di ANALISI_FABLE.md
restano necessari e non sostituibili. Porta pero' quattro cose concrete:
1. l'**accept-rule a rejection sampling** (`base_evaluator.py:186-303`) — il riferimento pronto per rendere T2
   compatibile col gate a temp 0,7, unica divergenza strutturale vera col nostro k≤16;
2. il **confidence head come ammissione** (Linear(H→1) + soglia) — stessa forma che serve al pilota per il
   vincolo precisione ≥0,85 e a T2 per il k adattivo;
3. la **ricetta feature multi-layer** (concat hidden sparsi + fc + norm) come piano B addestrato ("SPX2
   route-head") se il c-lite training-free fallisce T0.2;
4. il **cross-check hash-layer**: il nostro ds4 ha davvero 3 layer a route token-esatta via `ffn_gate_tid2eid`
   (ds4.c:120, 3047-3049, 6688) → 3/43 layer della finestra del pilota sono gratis ed esatti dal momento del
   campionamento (ds4_server.c:7466). Nessuna patch derivata da questo documento: solo disegno.
