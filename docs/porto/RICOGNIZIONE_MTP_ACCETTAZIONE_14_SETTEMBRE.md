# Ricognizione — accettazione della bozza MTP e uso della testa MTP (14 settembre 2026)

Solo lettura. Nessun download di modelli, nessuna build, nessun server, nessun commit.
Ogni numero qui sotto ha un URL. Dove non ho trovato niente, lo scrivo.

## Il nostro punto di partenza (misure nostre, 14/9)

| grandezza | valore |
|---|---|
| MTP spento | 24,44 t/s (40,9 ms/token) |
| MTP bozza 1 token | **28,66 t/s**, accettazione 0,785 |
| MTP bozza 2 token | 27,50 t/s, accettazione alla 2a posizione 0,553 (pareggio 0,633) |
| testa non condivisa | 0,780 — nessun guadagno |
| costo di una riga di verifica in piu' | 16,6 ms (mmvq +6,6 · trasferimenti esperti +6,4) |
| costo della testa per token abbozzato | 5,5 ms |
| bozza a 3 | impossibile (assert nel fork) |

Verifica del modello di costo con i numeri sopra: ciclo k=1 = 40,9 + 16,6 + 5,5 = 63,0 ms per
1,785 token = 35,3 ms/token = 28,3 t/s (misurato 28,66). Ciclo k=2 = 85,1 ms per 2,219 token
= 38,4 ms/token = 26,1 t/s (misurato 27,50, quindi la seconda chiamata alla testa costa un po'
meno di 5,5 ms). **Il modello regge**: e' la riga di verifica, non l'accettazione, la voce dominante.

---

## 1. llama.cpp upstream — stato dell'MTP

| fonte | data | cosa fa | numero riportato | per noi |
|---|---|---|---|---|
| [PR #22673 `llama + spec: MTP Support` (am17an)](https://github.com/ggml-org/llama.cpp/pull/22673) | proposta 4/5/2026, **merged 16/5/2026** | infrastruttura MTP generale: la testa e' un *modello separato* caricato dallo stesso GGUF, con contesto e KV suoi, agganciato dopo ogni ubatch | Qwen3.6-27B su DGX Spark: 3 bozze `aggregate_accept_rate 0,7218` (7,0→21,6 t/s); 2 bozze 0,8258 (7,0→18,2). RTX 3090: 22,97→42,45 t/s ma prefill a 0,51x. 3×RTX 3060 6 GB: +74% a 3 bozze | **SI'** (e' la base da cui deriva il nostro ramo). Nota: rendimenti calanti gia' oltre 3, e prefill penalizzato dai trasferimenti D2H degli embedding |
| [PR #27836 `qwen4exp: add NextN/MTP draft head (--spec-type draft-mtp)` (rmonsurate)](https://github.com/ggml-org/llama.cpp/pull/27836) | aperta 27/8/2026, **draft** | **e' la PR del nostro modello.** La testa piega l'embedding del token successivo nel residuo iper-connesso largo del tronco, esegue un blocco in stile tronco (attenzione densa + MoE) e lo richiude col mixer suo, riusando la LM head del tronco. Per n>1 e' **ricorsiva sul proprio stato nascosto** (`t_h_nextn`, il residuo largo pre-collasso, viene riesportato e reimmesso) — **niente teacher forcing** | M3 Max 128 GB: 89,2% a `n-max 2`, +35,7% (n-max 2) / +41,6% (n-max 3) su 27,43 t/s base. Strix Halo ROCm: 60-74% a n-max 2, 86% a temp 0. RTX 3090 CUDA: 84-91% su codice, 75-82% su ragionamento, +61% su codice dopo il fix `LLAMA_STATE_SEQ_FLAGS_ON_DEVICE` | **SI'** — e da leggere riga per riga. Espone `--spec-draft-n-max`, **`--spec-draft-p-min`** (es. 0,7) e `--spec-draft-backend-sampling`. Avverte che il combiner deve agire **per flusso di iper-connessione**: il mean pooling fa crollare l'accettazione (candidato n.1 se la nostra accettazione e' piu' bassa dell'atteso) |
| [PR #28243 `models: Qwen3.8-Flash-Next MTP` (danielhanchen/unsloth)](https://github.com/ggml-org/llama.cpp/pull/28243) | 2/9/2026, **draft** | porta l'MTP di Flash-Next verso mainline + moduli MTP *condivisi* che riusano `embed_tokens`; include il fix della chiave della cache dei grafi CUDA | 5090+5060 Ti: +25-40%, accettazione 0,77. Metal M5 Pro: n-max 2 identico al greedy, n-max ≥3 **diverge**. 4 GPU a 128k: accettazione 0,829 ma lunghezza media accettata 2,8 → perdita netta | **SI'** per il fix dei grafi; **NO** per il resto (e' la stessa testa che gia' usiamo). Segnalata una regressione aperta: stesso file di bozza, accettazione 0,32-0,38 contro 0,82-0,95 su un altro ramo — "qualcosa fra i commit regredisce l'accettazione di draft-mtp" |
| [`docs/speculative.md`](https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md) | master | manopole documentate | `--spec-draft-n-max` default **3**; `--spec-draft-n-min` default **0**; `--spec-draft-p-min` default **0,00** (greedy); `--spec-draft-p-split` default 0,10. `--spec-type`: `draft-simple`, `draft-eagle3`, `draft-dflash`, `draft-dspark`, `draft-mtp`, `ngram-*` | **SI'** — `p-min` e `n-min` esistono gia' a monte e sono a zero di default: **la bozza a lunghezza dinamica per confidenza e' gia' cablata, spenta** |
| [Discussione #25198 `Pushing MTP to the limit with --spec-draft-p-min (15% faster)`](https://github.com/ggml-org/llama.cpp/discussions/25198) | 2026 | sweep di `p-min` con `n-max` alto | Gemma-4-31B 112→163 t/s e Qwen3.6-27B 112→178 t/s con `--spec-draft-n-max 16 --spec-draft-p-min 0,8` su refactoring di funzioni; su carico reale lungo +15-20% con lunghezza media della bozza 3,71→5,39 e accettazione **in calo** 67,8%→55,7%. Un utente: n-max 6 / p-min 0,6 ottimo, 0,7-0,8 peggio | **FORSE** — il regime e' opposto al nostro (loro pagano poco la riga, quindi allungano; noi paghiamo 16,6 ms, quindi **accorciamo**). Utile come prova che il gate funziona e va *sweepato*, non adottato |
| [PR #27173 `speculative: draft performance improvement + token rollback bugfix` (PatrickWalther)](https://github.com/ggml-org/llama.cpp/pull/27173) | ago 2026, aperta | bozza *concatenata* (tutti gli n_max token con un solo decode, niente round-trip host), la GPU restituisce solo id+probabilita' invece dell'intero vocabolario, pooling dello scheduler; fix del rollback (i batch corti sovrascrivevano gli stati salvati dei modelli ricorrenti) | Qwen3.8-27B Q8_0, 2×5090: 142,2 t/s (depth 3) → 160,4 t/s (depth 5), **+12,8%**; su RTX PRO 4000 45,9→55,4 (+20,8%). Accettazione **scesa** 42,46%→37,59% ma throughput su | **FORSE** — attacca il costo della *testa* (5,5 ms), non quello della riga. Il fix del rollback su stati ricorrenti ci riguarda (QSA) |
| [PR #28549 `Enable CUDA graph for MTP draft` (gaugarg-nv)](https://github.com/ggml-org/llama.cpp/pull/28549) | 7/9/2026, aperta | seconda arena di risultati per i batch senza output, cosi' le due forme di grafo hanno chiavi distinte e si smette di ricatturare il grafo a ogni iterazione | RTX 5090 + Qwen3.6-35B-A3B MTP3: 279,04→291,33 pred_t/s (**+4,4%**) | **SI'** — patch piccola, effetto diretto sul nostro overhead per token abbozzato |
| [Issue am17an/llama.cpp #45 `CUDA graphs: speculative decoding repeatedly resets warmup state`](https://github.com/am17an/llama.cpp/issues/45) | 2026 | la cache dei grafi era indicizzata sull'**indirizzo del primo nodo**: forme di batch diverse collidono; la decodifica speculativa cambia forma a ogni chiamata e **azzera il warmup ogni volta**, non raggiunge mai il replay stazionario. Fix: chiave = primo nodo + ultimo nodo + numero di nodi, con LRU a 64 grafi | nessun t/s isolato nella issue | **SI'** — da verificare nel nostro albero: se ci colpisce, e' costo puro sulla riga di verifica |
| [Issue #28090 `Add an sm_86 entry to the MMVQ cutoff table`](https://github.com/ggml-org/llama.cpp/issues/28090) | 31/8/2026, aperta | la tabella in `ggml/src/ggml-cuda/mmvq.cu::ggml_cuda_should_use_mmvq()` ha voci per Ada, Blackwell, DGX Spark, CDNA — **non per sm_86** (la nostra 3060) | A10 (sm_86, come noi), Q4_0 denso: incrocio a `ne11 == 8`, **+9,1%** di prefill forzando MMQ | **FORSE** — riguarda il denso, non il MoE (vedi riga sotto) |
| [PR #26079 `CUDA: switch points per HW and quant type to tune the mvq→MMQ crossover` (ORippler)](https://github.com/ggml-org/llama.cpp/pull/26079) | **merged 20/8/2026** | tabella di soglie per hardware/quant; `get_mmvq_mmid_max_batch()` gestisce il percorso MoE | RTX 5090 K-quant a B=8: +22-49%. **MUL_MAT_ID escluso di proposito: forzare MMQ sul MoE costa 38-62% su Qwen3-30B.** L'env var `GGML_CUDA_MMVQ_MAX` c'era nelle prime revisioni ed e' stata **tolta** prima del merge | **NO** come rimedio pronto ai nostri +6,6 ms: a monte hanno *misurato* che MMQ sul MoE peggiora. Resta da verificare nel nostro albero *perche'* 2 righe costino +6,6 ms di mmvq quando MMVQ supporta gia' fino a 8 colonne (`MMVQ_MAX_BATCH_SIZE = 8` in `mmvq.cuh`) |
| [Issue stamsam/llama.cpp #2 `tq2_0: MMVQ unreachable for MoE (get_mmvq_mmid_max_batch returns -1)`](https://github.com/stamsam/llama.cpp/issues/2) | 6/8/2026 | per alcuni quant la funzione restituisce −1 e il MoE cade su dequantizza-a-F32 + GEMM a *tutte* le taglie di batch | RTX 4080 SUPER, tq2_0: 52,1 → 254,8 t/s solo abilitando MMVQ, 376,7 dopo la vettorizzazione (**7,2x**) | **FORSE, da controllare subito**: e' un `grep` di dieci minuti. Se `get_mmvq_mmid_max_batch()` restituisce un valore basso o −1 per **IQ2_S / IQ4_NL**, i nostri +6,6 ms per riga hanno una spiegazione banale. La issue non parla di IQ |
| [Discussione #24528 `RFC: MoE expert cache, VRAM caching of hot CPU-resident experts`](https://github.com/ggml-org/llama.cpp/discussions/24528) | giu 2026 (@leloch) | cache in VRAM degli esperti caldi residenti in RAM, esecuzione ibrida hit/miss | 4×3090: GLM-5.1 754B +25%, Qwen3.5 397B +7%, +10…+57% su 13 modelli; hit 50-80% | **SI' come avvertimento**: nel filo si legge che i **batch di verifica sotto il gate `max_batch` a volte scavalcano del tutto la cache**, e che la cache compone con un drafter **solo se il drafter non sta sulla GPU** (drafter su GPU = zero colpi). Da verificare che la nostra cache a 64 slot sia davvero ingaggiata sulle righe 2..k |

---

## 2. Fork della comunita'

| fonte | data | cosa fa | numero riportato | per noi |
|---|---|---|---|---|
| [markldn/llama.cpp-qwen4exp-rdnaport-latest](https://github.com/markldn/llama.cpp-qwen4exp-rdnaport-latest) | base su upstream 4a8993735 del **13/9/2026** | MTP nativo + **cache LRU degli esperti** (`--moe-expert-cache-experts N`, worker in background fuori dal percorso critico, pinning in loco senza copia) + Speculative Prefill (PR #27692) + boost RDNA4 | dichiarano **90%** di accettazione in produzione; AMD R9700 32 GB, Flash-Next UD-Q4_K_XL: decode 21,24 t/s, prefill 299,1. Cache isolata: 12,2→15,1 t/s (+24%) e 207→254 prefill (+23%) su prompt da 8000 | **FORSE** — l'architettura della cache LRU (worker fuori dal percorso critico, fallback su CPU al miss invece di stallo) e' la cosa da leggere: se la nostra cache stalla al miss durante la riga 2, e' li' che se ne vanno i 6,4 ms |
| [EngramHalo.cpp — Qwen 3.8 Flash Next a 38 t/s su Strix Halo](https://sleepingrobots.com/dreams/engramhalo-qwen38-flash-next-strix-halo/) | 29/8/2026 | gather sparso QSA (~2,3k righe invece della cache intera oltre i 16k) + testa MTP Q8_0 da ~4 GB + tuning dei kernel | Ryzen AI MAX+ 395, 128 GB, AD-4.27bpw, `--spec-draft-n-max 4 --spec-draft-p-min 0,75`: base/MTP a 185 tok 21,9/29,3 · 1k 20,4/28,2 · 3,4k 19,8/**38,5** · 6,6k 19,0/23,5 · 13k 17,6/31,7 · 26k 15,5/**15,0** | **SI' come precedente**: un altro sistema affamato di banda usa **n-max 4 con p-min 0,75**, non n-max fisso basso. Nota il crollo a 26k: l'MTP li' perde. Accettazione non quantificata per posizione |
| [GenerelSchwerz/llama.cpp — wiki Notable Runs](https://github.com/GenerelSchwerz/llama.cpp/wiki/Notable-Runs) | 7/9/2026 | il fork `moe-cache-drafting` che gia' conosciamo | RTX 5070 Ti 16 GB + 64 GB RAM, UD-Q3_K_XL, ctx 12288, 158 prompt / 1024 generati: **47,00 t/s** con `--load-mode none`, lazy on, **80 slot** di cache esperti, KV q8_0 — **speculazione disattivata, drafting non abilitato** | **SI' per il percorso base, NO per l'MTP**: il loro 47 t/s e' *senza* bozza, su quant piu' piccolo, GPU piu' grande e contesto corto. Non e' un numero trasferibile |
| [GenerelSchwerz wiki — 16GB VRAM Setup](https://github.com/GenerelSchwerz/llama.cpp/wiki/16GB-VRAM-Setup) | 2026 | requisiti del drafting con cache MoE | "il drafting con cache MoE richiede caricamento esperti non-mmap: `--load-mode none`"; con mmap si cade sul percorso di decode cached piu' lento e la L2 pinnata opzionale non recupera il guadagno del percorso raggruppato. Nessuna accettazione ne' t/s misurati con verifica speculativa | **SI'** — conferma il vincolo `--load-mode none` (gia' nostro) come precondizione perche' la bozza non disattivi il percorso raggruppato |
| [LaurentZuijdwijk/llama.cpp (`--spec-draft-adaptive`)](https://github.com/LaurentZuijdwijk/llama.cpp) | 2026 | lunghezza della bozza che **segue l'accettazione misurata** fra `n-min` e `n-max` | Strix Halo: n fisso 3 = 95% accettazione (sotto-utilizza), n fisso 7 = 18% (eccede), adattivo n-min 3 / n-max 7 = **96%** a throughput maggiore. Qwen3.8-27B FP4 + DFlash2: 65,6 t/s strutturato (4,7x), 26,1 prosa. **"Per l'MTP tenere n-max stretto (3-4): gli strati nextn successivi sono meno accurati e il costo della bozza resta lineare"** — n fisso 3 = 104,0 t/s strutturato contro n-max 7 = 85,7 | **SI'** — e' l'implementazione di riferimento del controllore adattivo, e la sua raccomandazione per l'MTP (n-max stretto) e' esattamente il nostro regime. Su un MoE (Ornith-1.5-35B) dichiarano generazione **in pari** con mainline: il guadagno viene dal prefill, non dalla speculazione |
| [thecodacus/llama.cpp](https://github.com/thecodacus/llama.cpp) | 2026 | prefetch degli esperti di ogni strato su un secondo stream CUDA, sovrapposto al calcolo; pinning delle pagine mmap (da ~6-7 a ~20 GB/s H2D) | output identico al mainline; due ottimizzazioni opt-in via env | **SI' per il meccanismo** (secondo stream + pinning gia' nostri), **ma attenzione**: il nostro ledger ha gia' falsificato il prefetch nel regime a riga singola (`prefetch-piu-anticipo-meno-colpi`). Il regime nuovo e' *durante la testa*, non durante il decode |
| [pwilkin, PR #16095 `Model: Qwen3 Next`](https://github.com/ggml-org/llama.cpp/pull/16095) | 2025-2026 | il gating dell'attenzione in GGML, "correttezza soltanto" | nessun numero di accettazione | **NO** per l'accettazione; e' il livello architetturale, non la bozza |
| ["Halo" / patch FA](https://github.com/markldn/llama.cpp-qwen4exp-rdnaport-latest) | — | gia' ricognito il 13/9: patch su vec/tile, noi usiamo MMA | — | **NO** (verdetto gia' nostro, confermato) |

---

## 3. vLLM / SGLang / TensorRT-LLM / ktransformers

| fonte | data | cosa fa | numero riportato | per noi |
|---|---|---|---|---|
| [vLLM recipes — Qwen/Qwen3.8-Flash-Next](https://recipes.vllm.ai/Qwen/Qwen3.8-Flash-Next) | 2026 | ricetta ufficiale: `--speculative-config '{"method":"mtp","num_speculative_tokens":3}'` | 4×H100: MTP **peggiora** il throughput a ogni concorrenza testata (8 e 64): −8/−36% di richieste, +32/+173% di latenza per token, accettazione **~36%**. "Non abilitarlo di default qui" | **SI' come monito**: la ricetta ufficiale del *nostro modello* dice che l'MTP a 3 e' una perdita anche su H100. La nostra misura (28,66 a k=1) e' gia' meglio di quello che vLLM ottiene |
| [vLLM issue #55357 — Flash-Next + MTP: crolli episodici a 0% di accettazione](https://github.com/vllm-project/vllm/issues/55357) | aperta **4/9/2026** | episodi di ore con accettazione **esattamente 0,000%** e collasso in ripetizione dentro il blocco di ragionamento fino a `max_tokens`; stesso sintomo su Gemma 4 26B → sospetto bug di stato a livello di motore, non del modello. Sospettati: i gruppi ricorrenti mamba/QSA trattati come gruppo di bozza, e il decode di bozza multi-step non fuso per `QWEN4_EXP_EXP_QSA_STATE` che forza la ricostruzione dei metadati a ogni passo | vita media 20% (5,35M abbozzati / 1,09M accettati); finestre sane 50-85% a 95-135 t/s; finestre in crollo 0% a 64-70 t/s | **SI' come protocollo**: qualunque banco MTP nostro deve registrare l'accettazione *per finestra*, non solo la media, e deve girare col ragionamento acceso (il nostro caso d'uso) perche' e' li' che si manifesta. Nessun rimedio noto, issue aperta |
| [vLLM issue #47602 — l'accettazione MTP nativa decade con la lunghezza del contesto](https://github.com/vllm-project/vllm/issues/47602) | 2026 | Qwen3.6-27B, contesto in range, senza `--hf-overrides` | decadimento dell'accettazione con il contesto totale | **SI'** — coerente col crollo a 26k di EngramHalo e col nostro caso 32k-262k: **l'accettazione va misurata alla profondita' d'uso, non a 2k** |
| [Red Hat Developer — Optimize vLLM speculative decoding with FastMTP heads](https://developers.redhat.com/articles/2026/09/08/optimize-vllm-speculative-decoding-fastmtp-heads) | **8/9/2026** | riaddestramento ricorsivo della testa MTP nativa (FastMTP) dentro vLLM | Qwen3-Next-80B-A3B-Instruct su GSM8K, accettazione per posizione **0: 0,897→0,912 · 1: 0,719→0,776 · 2: 0,476→0,616**; fino a **1,25x** sulla latenza mediana inter-token. Addestramento: ~8000 campioni GSM8K, 2×H200, **443 secondi**, 3 passi speculativi, β=0,6, 3 epoche a 1e-4 | **SI' come direzione, costoso**: e' l'unica cosa trovata che alza davvero l'accettazione **per posizione**. Vedi §"tre cose", n.3 |
| [FastMTP, arXiv 2509.18362](https://arxiv.org/abs/2509.18362) | set 2025 | una sola testa MTP a pesi condivisi fra posizioni, riaddestrata su dati auto-distillati, cosi' impara a consumare i propri output; + compressione dinamica del vocabolario nella testa | accettazione media **80% a k=1, 56% a k=2, 36% a k=3**; sul ragionamento matematico oltre 50% a k=3 contro il **3%** dell'MTP vanilla | **SI' come teoria**: spiega esattamente il nostro 0,785 → 0,553. La testa spedita e' addestrata solo teacher-forced sul token vero, non ha mai visto i propri stati |
| [Self-Distillation for Multi-Token Prediction, arXiv 2603.23911](https://arxiv.org/pdf/2603.23911) | 2026 | stessa famiglia (auto-distillazione per l'MTP) | — | **FORSE** — alternativa a FastMTP, stesso costo (addestramento) |
| [Nemotron 3 Super, arXiv 2604.12374](https://arxiv.org/html/2604.12374v1) | 2026 | formulazione a **pesi condivisi fra le teste MTP durante l'addestramento**: regolarizza la testa sugli orizzonti e la rende robusta agli stati nascosti auto-generati, cosi' la stessa testa si applica ricorsivamente con accettazione piu' stabile | descrive esplicitamente il disallineamento addestramento/inferenza: "miscela rumorosa" di stati del modello bersaglio e stati generati dall'MTP | **NO** operativamente (e' una scelta di pre-addestramento di un altro modello), **SI'** come conferma diagnostica |
| [ktransformers (SOSP'25, kvcache-ai)](https://dl.acm.org/doi/10.1145/3731569.3764843) e [release](https://github.com/kvcache-ai/ktransformers/releases) | 2026 | inferenza ibrida CPU/GPU per MoE; supporto speculativo esteso a EAGLE-3, MTP, STANDALONE, NGRAM; `--numa-nodes` | riportato in rete il caso opposto: 35B-A3B con drafter piccolo **da 17 a 11 t/s** al 65% di accettazione su sistemi a poca VRAM | **NO come codice** (non e' llama.cpp), **SI' come verdetto**: su poca VRAM il drafter piccolo peggiora — la nostra scelta della testa nativa e' quella giusta |
| [Jetson AI Lab — Speculative Decoding: MTP, DFlash, DSpark](https://www.jetson-ai-lab.com/tutorials/speculative-decoding/) | 2026 | ricette ufficiali NVIDIA per llama.cpp | MTP su Qwen3.8-27B/Thor: ~13 → ~35 t/s a depth 3 (2,7x). **DSpark non e' supportato in llama.cpp.** Nota esplicita: "un valore piu' piccolo puo' vincere quando la verifica parallela attiva esperti in piu' in un modello MoE" | **SI' per quella frase**: e' esattamente il nostro vincolo, scritto da loro. Niente numeri per Flash-Next |
| [HackMD — testati tutti i modi speculativi su Qwen3.6-35B-A3B + RTX 3090](https://hackmd.io/ODXuOQNzSiyUITz7g9mtBw) | 2026 | 19 configurazioni, tutte in VRAM | base 139,9 t/s; ngram-mod aggressivo −39%; drafter esterno (Qwen3.5-0.8B, vocabolario allineato) −54…−60%; migliore risultato 85,6 t/s. Causa attribuita alla **saturazione degli esperti**: la verifica carica fette fresche di esperti, e il costo supera il guadagno **anche al 100% di accettazione** | **SI'** — e' la stessa fisica nostra, su un sistema che non ha nemmeno l'offload: la riga di verifica del MoE e' il nemico |

---

## 4. Tecniche per l'accettazione **per posizione**, senza albero

| fonte | data | cosa fa | numero | per noi |
|---|---|---|---|---|
| [AdaEDL, arXiv 2410.18351 / PMLR v262](https://arxiv.org/abs/2410.18351) | 2024 | stop anticipato della bozza da un **limite inferiore entropico** sulla probabilita' di accettazione del token corrente | "training and parameter-free", non dipende dal dataset, iperparametri poco sensibili | **SI'** — e' il criterio giusto per decidere se abbozzare il 2º token. Piu' principiato di una soglia `p-min` secca, e non serve addestramento. Costo: una patch di poche righe sopra il gate `p-min` gia' esistente |
| [SpecDec++, arXiv 2405.19715](https://arxiv.org/pdf/2405.19715) | 2024 | politica ottima = **politica a soglia**: fermarsi quando la probabilita' di rifiuto supera una soglia; usa una testina addizionale che predice la probabilita' condizionata di accettazione | — | **FORSE** — la parte teorica (politica a soglia) giustifica il gate; la testina addizionale richiede addestramento, non ci serve |
| [AdaSD, arXiv 2512.11280](https://arxiv.org/html/2512.11280) | 2025 | lunghezza adattiva della bozza | — | **FORSE** — stessa famiglia |
| [EcoSpec — Less Experts, Faster Decoding, arXiv 2607.12696](https://arxiv.org/abs/2607.12696) | 14/7/2026 | incorpora il **costo marginale previsto di attivazione degli esperti** nella scelta della bozza: preferisce percorsi che riusano esperti gia' coperti dall'insieme di verifica corrente; predittore leggero di esperti + buffer dinamico. **Non modifica la regola di verifica → greedy-lossless, niente addestramento del modello base** | fino a **1,62x** su DeepSeek-V3.1, Qwen3-235B-A22B, GPT-OSS-120B | **FORSE, alto interesse**: e' l'unico lavoro che monetizza esattamente il nostro vincolo (i byte non si comprimono fra le righe). Ma e' formulato su **alberi** di bozza: con una catena a un solo candidato per posizione l'unica leva e' scegliere fra top-1 e top-2 quando sono vicini — guadagno incerto, misura non banale |
| [SP-MoE, arXiv 2510.10302](https://arxiv.org/pdf/2510.10302) | 2025 | **usa il tempo della bozza per prefetchare gli esperti** che serviranno alla verifica; introduce lo "strato di taglio" da cui far partire il prefetch selettivo. **Training-free** | migliora l'accuratezza di hit degli esperti; guadagni dichiarati nell'ordine 1,3-2,0x | **SI'** — e' il meccanismo della leva n.2 (sotto). Da noi la testa gira 5,5 ms *prima* della verifica, e in quei 5,5 ms il bus e' quasi fermo (gli esperti della bozza sono il 6% del traffico, misura nostra 13/9) |
| [DraftExpert, arXiv 2607.24434](https://arxiv.org/abs/2607.24434) | lug 2026 | un esperto di bozza leggero residente in acceleratore per strato, auto-distillato dal MoE congelato con perdite su residuo/logit/token **e accordo del router**; il router della bozza **lancia prefetch non bloccanti degli esperti del verificatore** man mano che i token sono accettati | DeepSeek-V2-Lite e Moonlight-16B-A3B su offload CPU→GPU (RTX 4090) e Flash→NPU: **+1,45x** medio, accettazione **84-87%**, **hit del prefetch 86-88%**; con prefetch il costo della verifica scende a **1,25-1,28x** di un passo autoregressivo singolo | **SI' come bersaglio numerico**: 1,25-1,28x invece del nostro 1,41x (16,6/40,9 = +41%). Richiede addestramento degli esperti di bozza → **NO** cosi' com'e'; ma la parte del prefetch guidato dal router e' separabile e training-free |
| [AcceptMoE, arXiv 2608.02989](https://arxiv.org/html/2608.02989) | ago 2026 | sceglie e dimensiona dinamicamente il sottoinsieme di esperti ammessi alla verifica; sotto offload **pota i membri non residenti** | — | **NO** — gia' nel nostro ledger (`staging-ritaglia-dal-pool-acceptmoe-scarta-per-residenza`). Potare esperti dalla riga di verifica cambia il token prodotto: non e' greedy-lossless |
| [LayerSkip, arXiv 2404.16710](https://arxiv.org/abs/2404.16710) | 2024 | uscita anticipata + auto-speculazione: la bozza e' il modello stesso troncato, con attivazioni e pesi condivisi | — | **NO** — richiede layer-dropout in addestramento per rendere accurate le uscite anticipate. Su Flash-Next non esiste |
| [CLaSp, arXiv 2505.24196](https://arxiv.org/pdf/2505.24196) e [KnapSpec, arXiv 2602.20217](https://arxiv.org/pdf/2602.20217) | 2025-2026 | selezione **in contesto** degli strati da saltare per l'auto-speculazione, senza addestramento (CLaSp); scelta degli strati come problema dello zaino (KnapSpec) | — | **FORSE, ma sospetto per noi**: saltare strati non riduce il traffico degli esperti in proporzione, e noi non siamo compute-bound. Il nostro ledger ha gia' il verdetto "il collo e' il bus della GPU" |
| [hqmtp (avifenesh) — banco di ricerca su teste MTP](https://github.com/avifenesh/hqmtp) | 2026 | ricette a zero addestramento (quantizzazione) contro tagli funzionali (pruning, low-rank, distillazione) su Qwen3.5-9B | NVFP4 **senza degrado** (±0,03 di accettazione a ogni profondita', replay forzato fino a 64k). Accettazione per slot del teacher: 0,740 / 0,598 / 0,520 / 0,470 (catena 0,593). I tagli funzionali costano **10-19 punti** fuori distribuzione; addestrare su corpora generici perde 17 punti contro le proprie generazioni | **SI' come metodo**: (a) la quantizzazione della testa e' gratis (coerente col nostro "bozza Q4 neutra"), (b) se mai addestreremo, **sulle nostre generazioni**, non su corpora generici, (c) il *replay forzato* a profondita' reale e' il modo giusto di misurare l'accettazione |
| [D-PACE, arXiv 2605.18810](https://arxiv.org/pdf/2605.18810) | 2026 | cross-entropy dinamica consapevole della posizione per il drafting parallelo | — | **NO** — e' una perdita di addestramento |
| [LK Losses, arXiv 2602.23881](https://arxiv.org/pdf/2602.23881) | 2026 | ottimizzazione diretta del tasso di accettazione come obiettivo | — | **NO** — addestramento |

---

## 5. Teste addestrate disponibili per il nostro modello

| fonte | data | cosa e' | numero | per noi |
|---|---|---|---|---|
| [unsloth/Qwen3.8-Flash-Next-GGUF — MTP/README.md](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/blob/main/MTP/README.md) | 2026 | **la testa che gia' usiamo**. `shared-Q8_0` 2,60 GB (consigliata), `shared-Q4_K_M` 1,78 GB (~2 punti di accettazione in meno), `shared-BF16` 4,87 GB (piu' lenta), piu' varianti autonome. "Shared" riusa gli embedding del modello principale, risparmia ~1,3 GB | B200, greedy, singolo stream: UD-Q4_K_XL 83,2→**138,8** t/s (1,67x); UD-IQ1_S 90,1→120,9 (1,34x). Accettazione **66,1% (Q8_0), 66,5% (BF16), 64,4% (Q4_K_M)**. Consiglio: `--spec-type draft-mtp --spec-draft-n-max 2`, "2 e' un buon default". A concorrenza 8 e' una **perdita netta (0,81-0,87x)**. Serve `-md` esplicito (l'autodiscovery non guarda in `MTP/`) | **SI'** — conferma tre cose nostre: n-max 2 e' il default sensato, il Q4 costa poco, la testa BF16 non compra niente. E la nostra accettazione a k=1 (0,785) e' **sopra** la loro aggregata (0,661) |
| [dzannotti/Qwen3.8-Flash-Next-MTP-GGUF](https://huggingface.co/dzannotti/Qwen3.8-Flash-Next-MTP-GGUF) | 2026 | conversione GGUF della testa (un blocco `qwen4exp` pieno: attenzione + MoE a 512 esperti + iper-connessioni, 4B parametri) che gira su **kernel llama.cpp stock**, non sui tipi di quant di un fork. Q4_K_M 2,5 GB con embedding a Q4_K "per migliorare l'accuratezza della bozza"; BF16 7,8 GB | Strix Halo: accettazione **0,90 su codice** (ROCm) / 0,88 (Vulkan); 35,8 t/s su codice e **22,6 t/s su prosa** con UD-Q4_K_XL. Dichiara di usare **drafting adattivo con p-min 0,75** invece di una profondita' fissa | **SI'** — altro precedente per `p-min 0,75` su hardware affamato di banda, e il divario codice/prosa (35,8 vs 22,6) e' la stessa forma del nostro problema |
| [agentionai/...-MTP-Q8_0-GGUF](https://huggingface.co/agentionai/Qwen3.8-Flash-Next-MTP-Q8_0-GGUF), [pugant/...-ROCMFP4](https://huggingface.co/pugant/Qwen3.8-Flash-Next-MTP-DRAFT-HEAD-ROCMFP4-GGUF), [quimmedes](https://huggingface.co/quimmedes/Qwen3.8-Flash-Next-MTP-GGUF), [sh0wie MLX](https://huggingface.co/sh0wie/Qwen3.8-Flash-Next-MTP-Drafter-MLX-bf16) | 2026 | riconversioni della **stessa** testa ufficiale in formati diversi | — | **NO** — nessun peso nuovo, nessun riaddestramento |
| EAGLE-3 / HASS / Medusa / FastMTP **per Qwen3.8-Flash-Next** | — | — | — | **NON TROVATO.** Esistono EAGLE-3 per Qwen3.6-27B ([Ex0bit/PRISM-EAGLE3](https://huggingface.co/Ex0bit/Qwen3.6-27B-PRISM-EAGLE3)), Qwen3.5-397B, Qwen3-235B, Qwen3-4B; DFlash2 per **Qwen3.8-27B** ([z-lab](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2), [GGUF](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2-GGUF)); DSpark per Qwen3.8-27B e DeepSeek-V4-Flash. **Nessuno per Flash-Next.** Nessuna testa FastMTP pubblicata per nessun Qwen3-Next/3.8 |
| [Ex0bit/Qwen3.6-27B-PRISM-EAGLE3](https://huggingface.co/Ex0bit/Qwen3.6-27B-PRISM-EAGLE3) | 2026 | EAGLE-3 su un fratello del nostro modello | lunghezza media accettata **2,4** su PRISM-PRO e 2,2 su Qwen3.6-27B stock. **Il drafting ad albero (`--speculative-eagle-topk 4`) porta la lunghezza a ~3,35 ma e' neutro sul throughput su bersaglio ibrido GatedDeltaNet: "si consiglia la catena"** | **SI' come argomento contro gli alberi**, da un fork che ha tutto in VRAM e non paga nemmeno l'offload |

---

## 6. Costo della riga di verifica — riepilogo di cosa esiste gia'

Non ho trovato a monte nessuna PR che riduca specificamente i `+6,6 ms` di mmvq per riga aggiuntiva su `MUL_MAT_ID` con quant IQ. Quello che esiste:

- [PR #26079](https://github.com/ggml-org/llama.cpp/pull/26079) (merged 20/8) ha tarato l'incrocio MMVQ→MMQ **solo per il denso**, lasciando `get_mmvq_mmid_max_batch()` al default 8, **dopo aver misurato che forzare MMQ sul MoE costa 38-62%** su Qwen3-30B. L'env var `GGML_CUDA_MMVQ_MAX` e' stata rimossa prima del merge.
- [Issue #28090](https://github.com/ggml-org/llama.cpp/issues/28090) chiede una voce sm_86 (la nostra 3060) nella tabella: +9,1% su A10 con Q4_0 **denso**. Aperta.
- [Issue stamsam #2](https://github.com/stamsam/llama.cpp/issues/2) mostra che per certi quant `get_mmvq_mmid_max_batch()` restituisce −1 e il MoE cade su dequant-a-F32 + GEMM: 7,2x lasciato sul tavolo. Non dice niente su IQ2_S/IQ4_NL.
- Il [blog ZINC (11/6/2026)](https://zolotukhin.ai/blog/2026-06-11-cuda-llm-decode-optimization-batched-moe-kernel-fusion/) sostituisce il ciclo per-esperto con due kernel batchati (gate/up fuso + down) su tutti gli esperti attivi in una sola griglia: Qwen3.6-35B-A3B ~9→~40 t/s e Gemma-4-26B-A4B ~10→~52 su RTX 4090. **Non e' llama.cpp e non e' stato portato a monte**, e non riporta niente su batch da 2-6 righe ne' su quant IQ.

---

# Le tre cose piu' promettenti per noi

Ordinate per guadagno atteso diviso costo.

## 1 — Bozza a lunghezza dinamica per confidenza: `--spec-draft-p-min` (+ `n-min`), sweep a n-max 2-4

**Meccanismo.** La manopola esiste gia' a monte (`--spec-draft-p-min`, default 0,00) ed e' elencata
fra quelle della PR #27836, cioe' del ramo da cui deriviamo: la bozza si ferma quando la
probabilita' del token proposto scende sotto la soglia. E' un gate sulla *proposta*, non sulla
verifica: il testo greedy resta identico.

**Perche' da noi.** Il nostro 0,553 alla seconda posizione e' una **media** fra tratti di copia/codice
(dove i fork misurano 0,88-0,96) e tratti di prosa/ragionamento (0,65-0,80 o meno, [riferimento
per posizione su Qwen3.5](https://github.com/patrickbdevaney/qwen-3.5-35b-a3b-vllm-resources/blob/main/MTP_SPECULATIVE.md)).
Il pareggio e' 0,633: la seconda riga ci conviene solo sui tratti facili. Il gate compra
esattamente quella separazione e in piu' ci lascia alzare `n-max` a 3-4 *senza* pagare la riga
quando la testa non e' sicura. Due precedenti su hardware affamato di banda usano proprio questa
forma: [EngramHalo](https://sleepingrobots.com/dreams/engramhalo-qwen38-flash-next-strix-halo/)
con `n-max 4 p-min 0,75`, la [testa dzannotti](https://huggingface.co/dzannotti/Qwen3.8-Flash-Next-MTP-GGUF)
con drafting adattivo a `p-min 0,75`; e [sudoingX](https://github.com/sudoingX/qwen38-mtp) lo dice
per esteso: "su sistemi affamati di banda ~0,60-0,75 aiuta; su schede ad alta banda il gate riduce
il throughput; **sweepalo, non adottarlo**".

**Aspettativa onesta.** Con il nostro modello di costo il guadagno del solo gate a n-max 2 e'
piccolo: se il 40% delle posizioni avesse accettazione condizionata 0,85 e il 60% 0,34 (media
0,553), il ciclo misto darebbe ~35,1 ms/token contro i 35,3 attuali, cioe' **+1%**. Il gate vale
davvero solo se **sblocca n-max 3-4 sui tratti facili** — ed e' li' che casca l'assert.

**Cosa serve.** (a) verificare col `grep` che `--spec-draft-p-min` e `--spec-draft-n-min` siano
raggiungibili nel nostro binario e non solo presenti (regola nostra: *una leva esiste solo se il
ramo e' raggiungibile*); (b) **rimuovere l'assert a 3 righe di verifica** — e' la precondizione,
perche' senza n-max ≥3 il gate ha poco da guadagnare; (c) sweep.

**Come si misura.** Banco deterministico, greedy, `-np 1`, impronta che include `reasoning_content`.
Matrice: `n-max ∈ {2,3,4} × p-min ∈ {0,0 · 0,5 · 0,6 · 0,7 · 0,8}`, B di riferimento = 28,66 a
n-max 1. Registrare **accettazione per posizione e per finestra** (non solo la media: vLLM #55357)
e ripetere a 32k e a 131k (vLLM #47602: l'accettazione decade col contesto).

**Rischio.** Basso. Nessuna modifica al testo. Il rischio vero e' che non paghi: il ceiling e'
+1-3% finche' l'assert resta.

## 2 — Nascondere i trasferimenti degli esperti della riga di verifica dietro il passo della testa (prefetch guidato dalla bozza)

**Meccanismo.** SP-MoE ([arXiv 2510.10302](https://arxiv.org/pdf/2510.10302), training-free) e la
parte di prefetch di DraftExpert ([arXiv 2607.24434](https://arxiv.org/abs/2607.24434)) fanno la
stessa cosa: **il tempo di drafting e' tempo in cui il bus e' libero**, e va usato per portare in
VRAM gli esperti che servira' alla verifica. DraftExpert misura **86-88% di hit del prefetch** e,
con quello, porta il costo della verifica a **1,25-1,28x** di un passo autoregressivo.

**Perche' da noi.** Il nostro costo per riga e' 16,6 ms di cui **6,4 sono trasferimenti**, e la
testa gira 5,5 ms **prima** della verifica usando quasi niente banda (gli esperti della testa sono
il 6% del traffico — misura nostra 13/9). Il rapporto verifica/passo base da noi e' 16,6/40,9 =
**1,41x**: il bersaglio di DraftExpert e' 1,25-1,28x. Se recuperiamo anche solo 4 dei 6,4 ms,
la riga passa da 16,6 a 12,6 ms: ciclo k=1 = 59,0 ms per 1,785 token = 33,1 ms/token = **30,2 t/s**
(**+5,4%** su 28,66), e — piu' importante — il pareggio per la seconda riga scende da 0,633 a
~0,52, sotto il nostro 0,553 misurato: **k=2 diventa redditizio**. Con k=2 e riga a 12,6 ms:
ciclo 77,1 ms per 2,219 token = 34,7 ms/token = **28,8 t/s**, e con il gate del punto 1 sopra.

**Cosa serve.** Patch nostra, media. Niente addestramento. Il predittore c'e' gia': il nostro
ledger ha `predittore-route-gate-strato-dopo` ("il predittore di route e' GRATIS") e il macchinario
di prefetch su secondo stream (cfr. anche [thecodacus](https://github.com/thecodacus/llama.cpp)).
Il pezzo nuovo e' il **quando**: emettere le copie per le righe 2..k durante il forward della testa
e lo strato precedente della verifica, non durante il decode a riga singola. Prima di tutto:
verificare che la cache a 64 slot sia davvero **ingaggiata** sui batch di verifica — nel filo della
[RFC #24528](https://github.com/ggml-org/llama.cpp/discussions/24528) si legge che i batch di
verifica sotto il gate `max_batch` a volte **scavalcano del tutto la cache**, e che un drafter
residente su GPU azzera i colpi.

**Come si misura.** B = 28,66 a k=1. Strumentare separatamente `t_mmvq` e `t_trasferimenti` per
riga (li abbiamo gia' scomposti: 6,6 / 6,4). Il criterio di successo e' il **costo della riga**, non
i t/s: se la riga non scende sotto 14 ms, la leva e' morta e si chiude. Poi ri-sweep del punto 1.

**Rischio.** Medio. Il nostro ledger ha gia' falsificato il prefetch (`prefetch-piu-anticipo-meno-colpi`,
`prefetch-falsificato-sfratto-vale-23-punti`) — **ma nel regime a riga singola**, dove il tempo
libero non c'e'. Qui il regime e' diverso e l'ipotesi va rifatta, non riciclata. Rischio secondario:
lo sfratto causato dal prefetch delle righe di bozza puo' abbassare il 75,5% di colpi caldi del
percorso principale.

**Contorno gratuito da fare insieme (piccolo, indipendente):**
[PR #28549](https://github.com/ggml-org/llama.cpp/pull/28549) (grafo CUDA per la bozza MTP, +4,4%
misurato su 5090) e il fix della chiave della cache dei grafi
([am17an #45](https://github.com/am17an/llama.cpp/issues/45): la chiave sul solo primo nodo fa
azzerare il warmup a ogni cambio di forma del batch — e la speculazione cambia forma **sempre**).
Entrambi sono patch di poche righe e attaccano l'overhead per riga e per token abbozzato.

## 3 — Riaddestrare la testa alla ricorsione (FastMTP), sulle nostre generazioni

**Meccanismo.** Una sola testa a pesi condivisi fra posizioni, riaddestrata su **dati auto-distillati**
perche' impari a consumare i propri stati nascosti invece degli stati veri
([FastMTP, arXiv 2509.18362](https://arxiv.org/abs/2509.18362)). E' l'unica cosa trovata che alza
davvero l'accettazione **per posizione** invece di spostare il costo.

**Perche' da noi.** Il nostro profilo (0,785 / 0,553) e' la firma esatta del difetto che FastMTP
descrive: la testa spedita e' addestrata solo teacher-forced. I numeri pubblicati su
Qwen3-Next-80B-A3B sono **0,719→0,776 alla posizione 1 e 0,476→0,616 alla posizione 2**
([Red Hat, 8/9/2026](https://developers.redhat.com/articles/2026/09/08/optimize-vllm-speculative-decoding-fastmtp-heads)).
Un delta analogo porterebbe il nostro 0,553 a ~0,70, **sopra il pareggio 0,633**: k=2 diventerebbe
un guadagno netto anche senza toccare il costo della riga (ciclo 85,1 ms per 1+0,785+0,785·0,70 =
2,335 token = 36,4 ms/token = **27,4 t/s**... cioe' ancora sotto i 28,66 di k=1). **Attenzione: da
soli non bastano.** Il riaddestramento della testa paga solo *insieme* alla leva 2: con riga a
12,6 ms e accettazione 0,70, k=2 da' 77,1 ms per 2,335 token = 33,0 ms/token = **30,3 t/s**.
Per questo e' terzo, non primo.

**Cosa serve.** Addestramento. Il costo pubblicato e' modesto in assoluto — ~8000 campioni,
2×H200, **443 secondi** — ma la testa di Flash-Next e' un blocco `qwen4exp` da 4B con MoE a 512
esperti: non si addestra su una 3060, servono GPU affittate e il checkpoint BF16. In piu'
[hqmtp](https://github.com/avifenesh/hqmtp) avverte che addestrare su corpora generici perde **17
punti** contro addestrare sulle proprie generazioni, e che i tagli funzionali costano 10-19 punti
fuori distribuzione: quindi il corpus dovrebbe essere **le nostre generazioni, col ragionamento
acceso, ai nostri contesti**. Il guadagno pubblicato e' su GSM8K, cioe' su dominio: rischio di
regressione sulla prosa.

**Come si misura.** Prima di spendere: **replay forzato** (metodo hqmtp) sulle nostre tracce
per stimare l'accettazione per posizione a 32k e 131k con la testa attuale, e stimare il delta
richiesto perche' k=2 superi B=28,66 col costo di riga che avremo *dopo* la leva 2. Se il delta
richiesto e' > 0,15, non partire.

**Rischio.** Alto in costo, medio in esito. E: **nessuna testa FastMTP e' pubblicata per Flash-Next
ne' per nessun Qwen3-Next/3.8** — non l'ho trovata. Andrebbe fatta da zero.

---

# Cose che NON ci servono, e perche'

- **Alberi di bozza** (Medusa, EAGLE tree con `--speculative-eagle-topk`, `--spec-draft-p-split`,
  DFlash2 a blocco con piu' candidati per posizione). Ogni candidato in piu' e' **una riga di
  verifica a 16,6 ms**, cioe' il 41% di un token intero, e la nostra simulazione su tracce vere dice
  che **i byte non si comprimono fra le righe** (i trasferimenti restano ~2,3 esperti/strato per
  riga anche se gli esperti unici per riga scendono da 10 a 5,7). Oltre 6 righe gli unici superano i
  64 slot. Prova esterna nella stessa direzione, e su un sistema **senza** offload:
  [PRISM-EAGLE3](https://huggingface.co/Ex0bit/Qwen3.6-27B-PRISM-EAGLE3) misura che l'albero porta la
  lunghezza accettata da 2,4 a 3,35 ma e' **neutro sul throughput**, e raccomanda la catena; e
  [Jetson AI Lab](https://www.jetson-ai-lab.com/tutorials/speculative-decoding/) scrive che un
  valore piu' piccolo vince "quando la verifica parallela attiva esperti in piu' in un modello MoE".
- **Bozze piu' lunghe per ammortizzare i trasferimenti** (la tesi di
  [SpecMoEOff, arXiv 2508.21706](https://arxiv.org/abs/2508.21706), 2,5x su offload MoE, che allarga
  il carico per esperto). E' l'opposto del nostro caso misurato: da noi allungare non ammortizza,
  perche' i byte non si condividono fra righe. Falsificata a casa nostra prima di provarla fuori.
- **N-gram** (`ngram-cache`, `ngram-mod`, `ngram-map-k`). Verdetto nostro gia' preso (aiutano
  copia/rinomina, peggiorano la prosa) e confermato fuori:
  [HackMD](https://hackmd.io/ODXuOQNzSiyUITz7g9mtBw) misura −39% con `ngram-mod` aggressivo su
  Qwen3.6-35B-A3B + 3090. Il nostro caso d'uso e' prosa e codice nuovo.
- **Drafter esterni piccoli** (Qwen3.5-0.8B & co.). Stessa fonte: −54…−60%. E su ktransformers un
  35B-A3B con drafter piccolo va **da 17 a 11 t/s** a 65% di accettazione su poca VRAM. La testa
  nativa e' la scelta giusta; per di piu' un drafter **residente su GPU azzera i colpi** della cache
  esperti ([RFC #24528](https://github.com/ggml-org/llama.cpp/discussions/24528)).
- **La testa non condivisa** e **la testa BF16**. Misura nostra: 0,780 contro 0,785, nessun
  guadagno. Confermato da unsloth: BF16 66,5% contro Q8_0 66,1%, "piu' grande e piu' lenta".
- **Requantizzare la testa** (Q4_K_M). Costa ~2 punti di accettazione (unsloth) e la nostra misura
  dice che la bozza Q4 e' neutra sul tempo: non compra niente.
- **MTP in concorrenza** (`-np > 1`). unsloth misura **0,81-0,87x** a concorrenza 8, e la ricetta
  vLLM del nostro modello misura peggioramenti a ogni concorrenza. Noi giriamo `-np 1`: irrilevante.
- **`draft-dspark`**. [Jetson AI Lab](https://www.jetson-ai-lab.com/tutorials/speculative-decoding/):
  "llama.cpp non supporta ancora DSpark". E non esiste una testa DSpark per Flash-Next.
- **DFlash2 / EAGLE-3 / HASS / Medusa per il nostro modello**: **non esistono**. Ci sono per
  Qwen3.8-**27B** e per Qwen3.6-27B, non per Flash-Next. Adattarli richiederebbe addestramento su
  un'architettura diversa.
- **Forzare MMQ sul percorso `MUL_MAT_ID`** per abbassare i +6,6 ms di mmvq. A monte l'hanno
  misurato: **−38/−62% su Qwen3-30B**, ed e' per questo che
  [PR #26079](https://github.com/ggml-org/llama.cpp/pull/26079) ha escluso il MoE dalla tabella e ha
  rimosso l'env var. Resta pero' **un controllo da fare** (non una leva): verificare cosa restituisce
  `get_mmvq_mmid_max_batch()` per **IQ2_S** e **IQ4_NL** nel nostro albero — se e' basso o −1, il
  MoE cade su dequant-a-F32 + GEMM e i +6,6 ms hanno una causa banale
  ([precedente su tq2_0: 7,2x](https://github.com/stamsam/llama.cpp/issues/2)).
- **Speculative Prefill** ([PR #27692](https://github.com/ggml-org/llama.cpp/pull/27692), presente
  nel fork markldn: TTFT 13,2s→8,1s). Risolve il prefill, non il decode, e a noi il prefill sta gia'
  a 294,95 a 131k. Fuori tema.
- **LayerSkip / auto-speculazione a strati saltati**. Richiede layer-dropout in addestramento
  (LayerSkip) o comunque riduce **calcolo**, non **byte**: noi siamo al muro del bus. Le varianti
  senza addestramento (CLaSp, KnapSpec) restano da tenere d'occhio ma partono col regime sbagliato.

---

## Avvertenze di metodo raccolte per strada (da usare nel prossimo banco)

1. **Accettazione per finestra, non media.** vLLM #55357 documenta crolli episodici a **0,000%**
   che durano ore su *questo modello*, invisibili in una media di vita (20%).
2. **Accettazione alla profondita' d'uso.** vLLM #47602 e il crollo a 26k di EngramHalo
   (38,5 t/s a 3,4k → 15,0 a 26k, **sotto** il baseline 15,5): misurare a 32k e 131k, non a 2k.
3. **Il combiner per flusso di iper-connessione.** PR #27836 avverte che il mean pooling fa crollare
   l'accettazione. Se la nostra accettazione fosse sotto attesa, e' il primo posto dove guardare.
4. **Grafi CUDA e speculazione.** `GGML_CUDA_DISABLE_GRAPHS=1` e' citato a monte come workaround per
   corruzione di output ai rollback (PR #27836) — e nel nostro ledger c'e' gia' il verdetto opposto
   (`GGML_CUDA_DISABLE_GRAPHS=0`). Da ri-dirimere prima di attribuire guadagni.
5. **`--load-mode none` e' una precondizione del drafting con cache MoE**, non un'opzione
   (wiki GenerelSchwerz): con mmap si ricade sul percorso cached lento.
