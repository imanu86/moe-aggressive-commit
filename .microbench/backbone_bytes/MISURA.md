# MISURA — byte di backbone letti per token di decode (runtime DS4, CUDA)

Data: 2026-07-28. Sorgenti: `ds4-p4a/ds4.c`, `ds4-p4a/ds4_cuda.cu` (commit di riferimento
`877a903`, hash sorgenti in `.codex_runs/p4a_scout/outputs/*/provenance.txt`).
Nessuna compilazione, nessun server avviato, nessun sorgente modificato.

Configurazione presa come riferimento (campagna): `-c 150000 --mtp-draft 1 --cuda`,
`DS4_CUDA_EMBED_ROW_STAGING=1`, `DS4_CUDA_STREAMING_EXPERT_CACHE_N=140`,
`DS4_CUDA_NO_Q8_F16_CACHE=1`, `DS4_G73_OPEN=0`.

---

## 0. Metodo e verifica di chiusura (perche' i numeri sotto sono affidabili)

L'inventario NON e' stimato: e' calcolato dalla geometria fissa del modello
(`ds4.c:104-127`) piu' le regole di layout che il runtime **verifica a fail-fast**
sul GGUF (`weights_validate_layout`, `ds4.c:2848-2917`). Se il file non avesse
esattamente quei dtype e quelle dimensioni, il processo uscirebbe con `exit(1)`;
quindi il fatto che il server parta e' la prova che il layout e' quello.

Chi entra e chi esce dalla startup cache: `accelerator_cache_model_tensor_spans`
(`ds4.c:1728-1808`). Itera su **tutti** i tensori del GGUF ed esclude solo:
- i routed expert, per suffisso `.ffn_gate_exps.weight` / `.ffn_up_exps.weight` /
  `.ffn_down_exps.weight` (`ds4.c:1707-1711`, filtro applicato a `ds4.c:1742`);
- `token_embd.weight` se `DS4_CUDA_EMBED_ROW_STAGING` e' settata (`ds4.c:1713-1716`,
  applicato a `ds4.c:1746`).
Tutto il resto finisce nella cache: quindi "backbone" = **tutto il GGUF meno experts
meno embedding**.

Le tre righe di log si riproducono al byte con questo inventario:

| riga di log | valore loggato | valore calcolato | esito |
|---|---|---|---|
| `startup model cache prepared` | 7.21 GiB | 7 742 326 108 B = **7.2105 GiB** | coincide |
| `startup cache excluded ... routed-expert` | 72.56 GiB | 43 x 1 811 939 328 B = **72.5625 GiB** | coincide |
| `startup cache excluded ... token embedding` | 0.99 GiB | 1 058 969 600 B = **0.9862 GiB** | coincide |
| `[cuda-vram-mark] tracked_vram_mib` | 7383.7 MiB | 7 742 326 108 B = **7383.68 MiB** | coincide |
| somma dei 9 span `fd-cached tensor-span:N` | 7383.66 MiB | idem | coincide |
| somma totale = dimensione file | 86 720 111 488 B | 86 714 686 812 B + header/metadati | delta 5.2 MB (0.006%) |

Log usato: `.codex_runs/p4a_scout/outputs/20260726_211913_.../server.stderr.log:5-17`.

Corollari **provati** da questa chiusura:
- gli experts sono IQ2_XXS su gate/up (66 B/256 elem) e Q2_K su down (84 B/256 elem);
  nessun'altra combinazione da 1.6875 GiB/layer;
- **non esiste alcun tensore MTP nel file** (vedi §2.G): aggiungerne uno porterebbe
  la cache a 7.38 GiB e gli experts a 74.25 GiB, non a 7.21 / 72.56;
- non ci sono tensori "sorpresa" fuori dal binder: l'inventario e' completo entro
  ~0.006% (header GGUF + stringhe del vocabolario).

Geometria (`ds4.c:104-127`): 43 layer, n_embd 4096, vocab 129280, n_head 64,
head_dim 512, lora_q 1024, lora_o 1024, out_group 8, n_expert 256, ff_exp 2048,
hash_layer 3, indexer_head 64 x 128, indexer_top_k 512, hc 4.
Ratio di compressione per layer (`ds4.c:452-456`): layer 0-1 = 0 (nessun compressore),
layer pari >=2 = 4 (21 layer, con indexer), layer dispari >=3 = 128 (20 layer, senza indexer).

Formule byte: F32 = 4n; F16 = 2 x d0 x d1; Q8_0 = d1 x (d0/32) x 34; I32 = 4 x d0 x d1.

---

## 1. INVENTARIO dei 7.21 GiB + verdetto di lettura per token di decode

`letti/token` = byte che i kernel CUDA leggono per **un** token di decode, sommati su
tutte le occorrenze della classe. Contesto lungo (pos >= 2048, quindi ctx 150k della
campagna). Le voci ammortizzate sono marcate.

| # | tensore | dtype | dims | occorrenze | byte in cache | letti / token decode | prova (file:riga) |
|---|---|---|---|---|---|---|---|
| 1 | `blk.*.hc_attn_fn` | F16 | 16384 x 24 | 43 | 33 816 576 | 33 816 576 (100%) | ds4.c:11219 -> ds4_cuda.cu:22503 |
| 2 | `blk.*.hc_attn_scale` | F32 | 3 | 43 | 516 | 516 (100%) | ds4.c:11232 -> ds4_cuda.cu:52014 |
| 3 | `blk.*.hc_attn_base` | F32 | 24 | 43 | 4 128 | 4 128 (100%) | ds4.c:11233 -> ds4_cuda.cu:52016 |
| 4 | `blk.*.attn_norm` | F32 | 4096 | 43 | 704 512 | 704 512 (100%) | ds4.c:11234 / 11261 -> ds4_cuda.cu:22707 |
| 5 | `blk.*.attn_q_a` | Q8_0 | 4096 x 1024 | 43 | 191 627 264 | 191 627 264 (100%) | ds4.c:11267 -> ds4_cuda.cu:22242,22246 |
| 6 | `blk.*.attn_q_a_norm` | F32 | 1024 | 43 | 176 128 | 176 128 (100%) | ds4.c:11286 -> ds4_cuda.cu:22749 |
| 7 | `blk.*.attn_q_b` | Q8_0 | 1024 x 32768 | 43 | 1 533 018 112 | 1 533 018 112 (100%) | ds4.c:11306 -> ds4_cuda.cu:22242 |
| 8 | `blk.*.attn_kv` | Q8_0 | 4096 x 512 | 43 | 95 813 632 | 95 813 632 (100%) | ds4.c:11275 -> ds4_cuda.cu:22242 |
| 9 | `blk.*.attn_kv_a_norm` | F32 | 512 | 43 | 88 064 | 88 064 (100%) | ds4.c:11290 -> ds4_cuda.cu:22751 |
| 10 | `blk.*.attn_sinks` | F32 | 64 | 43 | 11 008 | 11 008 (100%) | ds4.c:11619 / 11646 -> ds4_cuda.cu:23701 / 23349 |
| 11 | `blk.*.attn_output_a` | Q8_0 | 4096 x 8192 | 43 | 1 533 018 112 | 1 533 018 112 (100%) | ds4.c:11682 -> ds4_cuda.cu:24138,24146 |
| 12 | `blk.*.attn_output_b` | Q8_0 | 8192 x 4096 | 43 | 1 533 018 112 | 1 533 018 112 (100%) | ds4.c:11692 -> ds4_cuda.cu:22447 |
| 13 | `blk.*.hc_ffn_fn` | F16 | 16384 x 24 | 43 | 33 816 576 | 33 816 576 (100%) | ds4.c:11733 -> ds4_cuda.cu:22503 |
| 14 | `blk.*.hc_ffn_scale` | F32 | 3 | 43 | 516 | 516 (100%) | ds4.c:11743 |
| 15 | `blk.*.hc_ffn_base` | F32 | 24 | 43 | 4 128 | 4 128 (100%) | ds4.c:11744 |
| 16 | `blk.*.ffn_norm` | F32 | 4096 | 43 | 704 512 | 704 512 (100%) | ds4.c:11745 / 11772 |
| 17 | `blk.*.ffn_gate_inp` (router) | F16 | 4096 x 256 | 43 | 90 177 536 | 90 177 536 (100%) | ds4.c:11784 -> ds4_cuda.cu:22503 |
| 18 | `blk.*.exp_probs_b` (bias router) | F32 | 256 | 43 | 44 032 | **40 960 (93%)** | ds4.c:11789 -> ds4_cuda.cu:24257-24260 |
| 19 | `blk.*.ffn_gate_shexp` | Q8_0 | 4096 x 2048 | 43 | 383 254 528 | 383 254 528 (100%) | ds4.c:11838 / 12009 -> ds4_cuda.cu:22385 |
| 20 | `blk.*.ffn_up_shexp` | Q8_0 | 4096 x 2048 | 43 | 383 254 528 | 383 254 528 (100%) | ds4.c:11839 / 12010 -> ds4_cuda.cu:22386 |
| 21 | `blk.*.ffn_down_shexp` | Q8_0 | 2048 x 4096 | 43 | 383 254 528 | 383 254 528 (100%) | ds4.c:12037 / 12047 -> ds4_cuda.cu:22447 |
| 22 | `blk.{0,1,2}.ffn_gate_tid2eid` | I32 | 6 x 129280 | 3 | 9 308 160 | **72 (0.0008%)** | ds4.c:11790 -> ds4_cuda.cu:20366-20370 |
| 23 | `blk.*.attn_compressor_kv` (r4) | F16 | 4096 x 1024 | 21 | 176 160 768 | 176 160 768 (100%) | ds4.c:11390 -> ds4_cuda.cu:22620 |
| 24 | `blk.*.attn_compressor_gate` (r4) | F16 | 4096 x 1024 | 21 | 176 160 768 | 176 160 768 (100%) | ds4.c:11391 -> ds4_cuda.cu:22620 |
| 25 | `blk.*.attn_compressor_ape` (r4) | F16 | 1024 x 4 | 21 | 172 032 | **43 008 (25%)** | ds4.c:11414 -> ds4_cuda.cu:20034-20038 |
| 26 | `blk.*.attn_compressor_norm` (r4) | F32 | 512 | 21 | 43 008 | **10 752 (25%, ammortizz.)** | ds4.c:11416 -> ds4_cuda.cu:22994,23058 |
| 27 | `blk.*.attn_compressor_kv` (r128) | F16 | 4096 x 512 | 20 | 83 886 080 | 83 886 080 (100%) | ds4.c:11390 -> ds4_cuda.cu:22620 |
| 28 | `blk.*.attn_compressor_gate` (r128) | F16 | 4096 x 512 | 20 | 83 886 080 | 83 886 080 (100%) | ds4.c:11391 |
| 29 | `blk.*.attn_compressor_ape` (r128) | F16 | 512 x 128 | 20 | 2 621 440 | **20 480 (0.78%)** | ds4_cuda.cu:20034-20038 |
| 30 | `blk.*.attn_compressor_norm` (r128) | F32 | 512 | 20 | 40 960 | **320 (0.78%, ammortizz.)** | ds4_cuda.cu:22994,23058 |
| 31 | `blk.*.indexer.attn_q_b` | F16 | 1024 x 8192 | 21 | 352 321 536 | 352 321 536 (100%) **solo se pos>=2048** | ds4.c:11513,11531 |
| 32 | `blk.*.indexer.proj` | F16 | 4096 x 64 | 21 | 11 010 048 | 11 010 048 (100%) **solo se pos>=2048** | ds4.c:11513,11549 |
| 33 | `blk.*.indexer_compressor_kv` | F16 | 4096 x 256 | 21 | 44 040 192 | 44 040 192 (100%) | ds4.c:11470 -> ds4_cuda.cu:22620 |
| 34 | `blk.*.indexer_compressor_gate` | F16 | 4096 x 256 | 21 | 44 040 192 | 44 040 192 (100%) | ds4.c:11471 |
| 35 | `blk.*.indexer_compressor_ape` | F16 | 256 x 4 | 21 | 43 008 | **10 752 (25%)** | ds4.c:11494 -> ds4_cuda.cu:20034-20038 |
| 36 | `blk.*.indexer_compressor_norm` | F32 | 128 | 21 | 10 752 | **2 688 (25%, ammortizz.)** | ds4.c:11496 -> ds4_cuda.cu:23058 |
| 37 | `output_hc_fn` | F16 | 16384 x 4 | 1 | 131 072 | 131 072 (100%) | ds4.c:12111 |
| 38 | `output_hc_scale` | F32 | 1 | 1 | 4 | 4 (100%) | ds4.c:12123 -> ds4_cuda.cu:52060 |
| 39 | `output_hc_base` | F32 | 4 | 1 | 16 | 16 (100%) | ds4.c:12124 -> ds4_cuda.cu:52061 |
| 40 | `output_norm` | F32 | 4096 | 1 | 16 384 | 16 384 (100%) | ds4.c:12142 -> ds4_cuda.cu:22707 |
| 41 | `output` (testa logit) | Q8_0 | 4096 x 129280 | 1 | 562 626 560 | 562 626 560 (100%) | ds4.c:12148-12155 |
| — | `mtp.0.*` (testa MTP) | — | — | **0** | **0** | **0** | ds4.c:19680-19701 (vedi §2.G) |
| | **TOTALE** | | | | **7 742 326 108** | **7 730 171 748** | |

Fuori inventario (escluso dai 7.21 GiB ma letto lo stesso):
`token_embd.weight` F16 4096 x 129280 = 1 058 969 600 B in RAM host, di cui si legge
**una riga = 8 192 B/token** (memcpy host + `cudaMemcpy` H2D), `ds4_cuda.cu:21076-21092`.

---

## 2. Prove per categoria (percorso di decode, non di prefill)

Ingresso decode: `ds4_session_eval_internal` -> `metal_graph_eval_token_raw_swa`
(`ds4.c:20894`, `logits` non-NULL) -> `metal_graph_encode_token_raw_swa` (`ds4.c:13021`),
che fa il loop su tutti i 43 layer (`ds4.c:13074-13100`, `metal_graph_encode_decode_layer`,
corpo a `ds4.c:11163-12098`) e poi la testa di output (`ds4.c:13103-13111`).
Il percorso batch (`*_batch`, `n_tok>1`) e' prefill e non e' stato usato per le prove.

**A. Proiezioni di attenzione (q_a, q_b, kv, output_a, output_b) — LETTE PER INTERO, OGNI TOKEN.**
Tutte passano da `ds4_gpu_matmul_q8_0_tensor` / varianti fuse, che calcolano
`weight_bytes = out_dim * ceil(in_dim/32) * 34` e prendono il puntatore all'intero
tensore (`ds4_cuda.cu:22242-22247`, `22385-22396`, `22447`, `24138-24146`).
In decode `n_tok == 1`, quindi si usa `matmul_q8_0_preq_warp8_kernel`
(`ds4_cuda.cu:22317-22327`): un warp per riga di output, `wr = w + row*blocks*34`
(`ds4_cuda.cu:17873-17886`) -> **ogni byte del tensore letto esattamente una volta**.
Il ramo cuBLAS con cache F16/F32 e' escluso perche' vincolato a `n_tok > 1`
(`ds4_cuda.cu:22248`), oltre che disattivato da `DS4_CUDA_NO_Q8_F16_CACHE=1`.

**B. Norme (attn_norm, ffn_norm, q_a_norm, kv_a_norm, output_norm, hc_scale/base) — LETTE PER INTERO.**
`ds4_gpu_rms_norm_weight_tensor` prende `n * sizeof(float)` (`ds4_cuda.cu:22702-22711`);
la versione fusa QKV prende entrambe le norme (`ds4_cuda.cu:22749-22753`);
`ds4_gpu_hc_split_weighted_sum_norm_tensor` prende scale (12 B), base (96 B) e la norma
del blocco (`ds4_cuda.cu:52014-52016`). Sono vettori piccoli: 100% letto, ma pesano
solo ~1.5 MB/token in totale.

**C. Shared expert (gate/up/down_shexp) — LETTI PER INTERO, OGNI TOKEN, TUTTI E 43 I LAYER.**
`ds4.c:11833-11842` (ramo `overlap_shared`, quello attivo) oppure `ds4.c:12004-12024`;
down a `ds4.c:12033-12050`. Guardie `if (ok && !overlap_shared)` e
`!overlap_shared_full` garantiscono **una sola** lettura per token per tensore: nessun
doppio conteggio. Sono 1.15 GB/token: la seconda voce piu' grossa dopo l'attenzione.

**D. Tabelle posizionali / APE — NON lette per intero: UNA RIGA per token.**
`compressor_store_kernel` (`ds4_cuda.cu:20015-20039`) legge l'APE all'indice
`pos_mod * width + j` con `j < width` e `pos_mod = pos % ratio`
(`ds4_cuda.cu:20034-20038`): quindi `width * 2` byte, cioe' **1/ratio della tabella**.
- APE attn r4: 2 048 B letti su 8 192 (1/4);
- APE attn r128: 1 024 B letti su 131 072 (**1/128**);
- APE indexer: 512 B letti su 2 048 (1/4).

**E. Indexer dell'attenzione sparsa — CONDIZIONALE alla posizione.**
Le due proiezioni pesanti (`indexer.attn_q_b` 16 MiB/layer e `indexer.proj` 0.5 MiB/layer)
sono dentro `if (ok && g->layer_n_comp[il] > decode_top_k)` (`ds4.c:11513`), con
`decode_top_k = DS4_N_INDEXER_TOP_K = 512` (`ds4.c:11023-11026`). `layer_n_comp`
cresce di 1 ogni `ratio`=4 token (`ds4.c:11446`), quindi la soglia scatta a
**pos+1 > 2048**. A ctx 150k (campagna) l'indexer e' **sempre attivo**: +363 331 584 B/token.
Sotto 2048 token di contesto quei 363 MB **non** vengono letti.
I compressori dell'indexer (`indexer_compressor_kv/gate`, 4 MiB/layer) sono invece
**incondizionati** dentro i layer ratio-4 (`ds4.c:11465-11485`).

**F. Compressori di attenzione — LETTI PER INTERO OGNI TOKEN, anche quando non emettono.**
Le due matmul F16 girano a ogni token (`ds4.c:11385-11405`); il flag
`emit = ((pos+1) % ratio) == 0` (`ds4.c:11369`) controlla **solo** se la riga compressa
viene scritta in cache, non se i pesi vengono letti. Unica parte davvero condizionata a
`emit`: la `*_compressor_norm`, letta dentro il ramo `if (!emit) return 1;`
(`ds4_cuda.cu:22994`, poi `23017`/`23058`) -> letta 1 volta ogni `ratio` token.

**G. Testa MTP — ZERO byte. Non e' nemmeno caricata.**
`--mtp-draft 1` imposta solo il numero di draft token (`ds4_server.c:8457`); i pesi MTP
si caricano **solo** con `--mtp <path>` (`ds4_server.c:8455-8456` -> `ds4.c:19680-19701`).
La campagna passa solo `--mtp-draft 1` (`launcher_arguments.txt`, `server_arguments.txt`),
quindi `e->mtp_ready = false`: nessun `model_open` del file MTP, nessun
`mtp_weights_bind`, e nel decode `mtp_should_draft` e' falso (`ds4.c:20878-20880`).
Il log di startup non contiene la riga `MTP support model loaded`. Confermato anche
dall'aritmetica (§0): con i tensori MTP presenti la cache sarebbe 7.38 GiB, non 7.21.
Inoltre, anche con i pesi caricati, `mtp_draft_tokens <= 1` disattiva il loop
speculativo (`ds4.c:20970`).

**H. Testa di output / logit — LETTA PER INTERO, OGNI TOKEN.**
`need_logits = (logits != NULL)` e il decode passa sempre `s->logits`
(`ds4.c:20894-20897`, `15008`), quindi `metal_graph_encode_output_head` gira sempre e
proietta su **tutto** il vocabolario: `vocab_dim = weights->output->dim[1] = 129280`
(`ds4.c:13107`, `12148-12155`). 562 626 560 B/token, cioe' il 7.3% del backbone.
Non esiste in decode una scorciatoia top-k lato pesi: la variante `_top`
(`ds4.c:15053`) fa comunque la proiezione piena e riduce solo dopo, e serve solo al
verificatore speculativo (inattivo).

**I. Tabelle indicizzate per token (tid2eid) — NON lette per intero: 24 BYTE.**
`ds4_gpu_router_select_tensor` prende il puntatore all'intera tabella
(`ds4_cuda.cu:24262-24266`), ma il kernel legge **solo la riga del token**:
`const int32_t *row = hash + tok * 6u;` e poi 6 int32 (`ds4_cuda.cu:20366-20370`).
Sono 24 B per layer, per i soli layer 0-2 (`ds4.c:3205-3207`): **72 B/token su 9.31 MB
residenti**. Nota collaterale: in questi 3 layer il bias `exp_probs_b` non viene
neppure prelevato, perche' `hash_mode` esclude il ramo bias
(`ds4_cuda.cu:24255-24261`, `24274`).

**J. Nessun altro lettore.** RoPE, store KV, `hc_expand*`, `swiglu`, `topk`, `add`
non ricevono `model_map` e non toccano pesi. Il probe SPEX, che rileggerebbe una copia
device del router per layer, e' disattivato: richiede `DS4_SPEX_HIDDEN_GPU_DRY_RUN`
+ file (`ds4.c:9829-9832`, `10064`), assente dal manifest della campagna; le funzioni
escono subito su `!g->spex_active` (`ds4.c:9737`, `10080`).

**K. Il flag `DS4_G73_OPEN` non tocca il backbone.** Governa il trasporto degli expert
selezionati / arena (`ds4_cuda.cu:2293-2305`, `32501-32506`); nessuna delle letture in
tabella e' condizionata da esso. Il valore 0 vs 1 non cambia il numero prodotto qui.

---

## 3. TOTALE

Amortizzato per token di decode (le voci `emit` variano di ~+40 KB nei token in cui
`(pos+1) % ratio == 0`, cioe' ±0.0005%: irrilevante).

| scenario | byte letti / token | GiB / token | % dei 7 742 326 108 B (7.21 GiB) |
|---|---|---|---|
| **ctx 150k (campagna, pos >= 2048) — indexer ATTIVO** | **7 730 171 748** | **7.1992** | **99.843 %** |
| ctx corto (pos < 2048) — indexer non ancora attivo | 7 366 840 164 | 6.8609 | 95.150 % |
| differenza attribuibile all'indexer top-k | 363 331 584 | 0.3384 | 4.693 % |

**Byte del backbone MAI letti (o letti solo in minima parte) a ogni token, a 150k:
12 154 360 B = 11.59 MiB = 0.157 % dei 7.21 GiB.** Dettaglio:

| voce | in cache | non letto / token |
|---|---|---|
| `ffn_gate_tid2eid` (3 layer) | 9 308 160 | 9 308 088 |
| `attn_compressor_ape` r128 (20 layer) | 2 621 440 | 2 600 960 |
| `attn_compressor_ape` r4 (21 layer) | 172 032 | 129 024 |
| `attn_compressor_norm` r128 | 40 960 | 40 640 |
| `attn_compressor_norm` r4 | 43 008 | 32 256 |
| `indexer_compressor_ape` | 43 008 | 32 256 |
| `indexer_compressor_norm` | 10 752 | 8 064 |
| `exp_probs_b` sui 3 layer hash | 3 072 | 3 072 |
| **totale** | | **12 154 360** |

### Verdetto sulla premessa

**La premessa "i 7.21 GiB sono riletti interamente a ogni token" e' CONFERMATA per la
configurazione della campagna (ctx 150k): 99.84 %.** Non si ribalta.
Il residuo non riletto e' 11.6 MiB, praticamente tutto tabelle indicizzate
(`tid2eid`) e tabelle posizionali (`ape` a ratio 128): materiale che occupa VRAM senza
essere quasi mai letto, ma la sua rimozione varrebbe lo 0.157 % — non cambia il conto.

**L'unica clausola che sposta davvero il numero e' la posizione di contesto**, non un
flag: sotto 2048 token l'indexer non parte e il backbone letto scende a 95.15 %
(6.86 GiB). Sopra 2048 token e' 99.84 % e ci resta per tutta la generazione.
La campagna gira a 150k, quindi il numero operativo e' **7 730 171 748 B/token**.

Nota di lettura (non e' una proposta, e' una precisazione di semantica): il numero
sopra e' la **domanda di lettura dei kernel**, indipendente da dove il tensore risiede.
Oggi arriva da VRAM perche' `cuda_model_range_ptr` restituisce il puntatore alla copia
device (`ds4_cuda.cu:3843-3855`); e' la stessa quantita' che attraverserebbe il bus se
la sorgente fosse host.

---

## 4. NON DETERMINABILE dal codice

1. **Presenza effettiva di `exp_probs_b` su ognuno dei 43 layer.** E' un tensore
   opzionale (`tensor_by_namef`, `ds4.c:3197`; `tensor_expect_optional`, `ds4.c:2902`).
   Se mancasse su qualche layer, inventario e letture calano di 1 024 B per layer
   (max 44 032 B = 0.0006%): sotto la risoluzione delle righe di log usate per la
   verifica. Servirebbe un dump dei nomi tensore del GGUF (`gguf-tools`) per chiudere
   la questione; l'impatto sul totale e' comunque nullo.
2. **Byte che attraversano davvero il PCIe per token.** Diverso dalla domanda dei
   kernel: dipende da quanto backbone e' stato sfrattato dalla LRU. Il log mostra che
   accade (`CUDA evicted streamed range`, poi il contatore `fd-cached ... (total ...)`
   che scende da 7.21 a 6.22 GiB durante il prefill, righe 27-45 dello stderr). Il
   runtime ha gia' un gancio, `cuda_vram_prio_note_backbone_reload(offset, bytes)`
   chiamato su ogni ri-stream di un range non-expert (`ds4_cuda.cu:8427`, con
   `is_hot = strncmp(what, "moe_", 4) != 0` a `ds4_cuda.cu:8341`): per avere il numero
   basterebbe leggere/esporre quell'accumulatore per finestra temporale di decode.
   **Non l'ho misurato** (nessun server avviato).
3. **Riuso in cache L2 tra letture dello stesso token.** I conteggi qui sono
   "byte richiesti dai kernel dalla memoria del device". Ogni tensore e' letto una sola
   volta per token e i tensori sono molto piu' grandi della L2 (3 MB su GA106), quindi
   traffico DRAM ~= byte contati; ma la conferma esatta richiederebbe un profilo
   `dram__bytes_read` con Nsight Compute, non ricavabile dal sorgente.
