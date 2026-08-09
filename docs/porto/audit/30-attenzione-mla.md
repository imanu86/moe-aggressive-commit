# 30 — ATTENZIONE E MLA COMPRESSA: dopo la fusione HC il grafo dell'attenzione non ha un secondo Sinkhorn; ha mezzo Sinkhorn di contorni, e 4,55 GiB di proiezioni per forward che il mandato contava sotto "densi"

Data: 10 agosto 2026, notte. Solo lettura. Ramo `overlap` (`1e07e003b` + working tree
con la fusione HC applicata). File letti per intero: `src/models/deepseek4.cpp`
(1.447 righe, versione FUSA), `ggml/src/ggml-cuda/dsv4-hc.cu`,
`ggml/src/ggml-cuda/softmax.cu` (launcher e kernel), `common.cuh:540-650`,
`fattn.cu:340-520`; per le parti citate: `llama-graph.cpp` (input DSV4, attn_mha,
moe_ffn, moe_ffn_overlap), `llama-kv-cache-dsv4.cpp` (ring, materialize, plan),
`llama-kv-cache.cpp` (get_k/cpy_k), `ggml.c` (op fuse e custom), `llama-impl.h`
(hadamard). Log: `D:\ds4_work\llama_run\fu7_k2.server.log` (fuso, 10.507 nodi) e
`fu0_k2.server.log` (non fuso, 34.329). Rapporti a monte: PAVIMENTO.md,
SINKHORN.md, UPSTREAM_390.md. Nessuna compilazione, nessuna corsa.

Marcatura: [MISURATO] = log/file di risultati; [CONTATO] = conteggio statico dal
sorgente, calibrato (§0b); [DEDOTTO] = aritmetica su misure; [IPOTESI] = da
falsificare con la misura indicata.

**Esito in tre righe.** (1) L'attribuzione per famiglia dei 10.507 nodi è fatta e
chiude al 2,7%: l'attenzione in senso stretto è ~2.760 nodi (26%), la macchineria
HC residua 1.978 (19%), lo **stato dei compressori CSA/LID/HCA ~3.200 (30%, la
voce singola più grossa)**, il MoE ~2.530 (24%). (2) Non c'è un secondo Sinkhorn:
il più vicino sono le **affini+sigmoidi pre/post ancora fuori dall'op fusa**
(1.204 nodi/forward, patch piccola su un kernel che già esiste, +0,5÷1%) e il
**blocco di stato dei compressori** (~129 nodi/strato CSA a ogni chiusura,
+0,3÷0,8%, patch media). (3) Il costo vero dell'attenzione non sono i nodi: sono
**4,55 GiB/forward di proiezioni q8_0 (wq_b, wo_a, wo_b)** — il 70% della voce
"densi" di PAVIMENTO è attenzione-MLA, già vicina al tetto del formato — più una
matrice indexer **f16 da 336 MiB/forward** che è l'unico byte comprimibile
rimasto nel perimetro.

---

## 0. Ancoraggio e calibrazione

### 0a. I numeri di partenza [MISURATO]

    fu0 (HC non fusa):  34.329 nodi bs=1 | 33.813 bs=64 | bozza 2.094 | 10,86 t/s
    fu7 (HC fusa):      10.507 nodi bs=1 |  9.991 bs=64 | bozza   432 | 12,66 t/s
    seconda reserve fu7 (dopo il drafter): 10.519 — i +12 sono la cattura
    t_layer_inp per DSpark: 3 tap × 4 nodi (permute+cont+mean+reshape),
    deepseek4.cpp:1260-1269
    flash_attn = auto → "resolve_fused_ops: Flash Attention enabled" (riga 226)
    fused DSV4 HC pre/comb/post: enabled (righe 231-233) — anche per la bozza (415-417)
    kv_unified = false, n_seq_max = 1 → n_stream = 1
    SWA raw 256 celle | CSA 2560 (pad → ring 512) | HCA 80 (pad → 256) | LID 2560 (ring 512)

### 0b. Il fattore di conversione, misurato stanotte e non stimato

La fusione HC è l'esperimento di calibrazione più pulito che abbiamo: −23.822
nodi sul bersaglio, −1.662 sulla bozza, e −13,09 ms/token misurati (92,08 →
78,99). Contando le chiamate bozza per ciclo e ÷1,85 accettati, i nodi tolti per
token sono ~18.000 [DEDOTTO]:

    ~0,73 µs per NODO tolto (viste comprese)  |  ~1,1 µs per KERNEL tolto

Uso questo fattore per tutte le leve di lanci qui sotto, ed è il motivo per cui
le stime sono più basse dei "1,5-3 µs/nodo" ipotizzati in PAVIMENTO §2b: il
misurato sta sulla metà bassa della forbice. Vale per famiglie lancio-dominate
(eltwise piccoli, viste, riduzioni minuscole); NON vale per mul_mat/MMVQ, dove
domina il lavoro. Verifica incrociata del metodo: il mio conteggio statico del
loop HC non fuso dà −276 nodi/blocco × 86 blocchi = −23.736 contro i −23.822
misurati (**scarto 0,4%**). Lo stesso metodo applicato al grafo fuso dà 10.793
contro 10.507 misurati (**+2,7%**): tutte le voci di §2 ereditano quell'errore.

---

## 1. La MLA compressa: che cos'è nel codice, e cosa costa

### 1a. Le hparams e il loro ruolo (file:riga)

| chiave | valore | ruolo | dove |
|---|---|---|---|
| `n_head` / `n_head_kv` | 64 / 1 | MQA assorbita: un solo K=V da 512, 64 teste Q | log 99-108 |
| `n_embd_head_k` | 512 | testa da 512 = 448 nope + 64 rope | `deepseek4.cpp:890-954` |
| `n_lora_q` | 1024 | wq_a 4096→1024 → wq_b 1024→32768 | `:116-118` |
| `dsv4_o_lora_rank` | 1024 | uscita fattorizzata wo_a→wo_b | `:121-122`, `llama-hparams.h:232` |
| `dsv4_o_group_count` | 8 | wo_a per GRUPPI di 8 teste: mul_mat 3D [4096,1024,8] | `:975-999` |
| `dsv4_compress_rope_base` | 160000 | base rope degli strati compressi (raw: 10000, senza yarn) | `:1024-1030` |
| `dsv4_compress_ratios` | [0,0,4,128,4,128,…] | 2 raw + 21 CSA (ratio 4) + 20 HCA (ratio 128) | `:68-73`, `llama-arch.cpp` |
| `n_swa` | 128 | finestra raw; cache SWA 256 celle | log 102, 180 |
| indexer | 64 teste × 128, top_k 512 | lightning indexer degli strati CSA | `:33-35` |

Il caricatore rifiuta ratio ∉ {0,4,128} (`:150-152`) e pretende
`sqrtsoftplus` (`:76-78`). `LLM_KV_ATTENTION_COMPRESS_RATIOS` arriva come
array da 44 (GGUF kv 29) e viene letto in `dsv4_compress_ratios` (`:68-73`).

### 1b. Il forward dell'attenzione per strato (il=2..42)

`build_attention` (`deepseek4.cpp:1007-1240`): wq_a+norm → `build_mla_qkv`
(`:890-954`: q = wq_b→rms→split nope/pe→rope(pe)→concat; kv = wkv→rms→split→
rope→concat, UN solo head) → uno dei tre percorsi:

- **raw** (il 0-1): SWA pura a 128 celle — `build_raw_attention` (`:852-888`);
- **CSA+LID** (il pari, 21 strati): `build_csa_lid_attention` (`:711-782`) —
  l'indexer (`build_lid_top_k`, `:589-680`) sceglie 512 celle su 2560, la
  maschera top-k si costruisce con fill+set_rows+add (`build_top_k_mask`,
  `:682-709`), poi K = concat(raw SWA, CSA compressa) e una sola
  flash-attention;
- **HCA** (il dispari, 20 strati): `build_hca_attention` (`:784-850`) —
  K = concat(raw, HCA compressa a ratio 128), flash-attention.

Chiusura comune: `build_mla_o` (`:956-1005`) che **de-ruota** l'uscita
(`ggml_rope_ext_back`, `:989` — wo_a è addestrata nello spazio non ruotato) e
applica wo_a per gruppi + wo_b.

**Nodi per strato [CONTATO]** (fuso, bs=1, senza chiusure di blocco):

| pezzo | nodi | di cui kernel |
|---|---|---|
| comune MLA (wq_a, norm, qkv, mla_o) | 30 | 17 |
| percorso raw (il 0-1) | 9 | 3 |
| percorso CSA+LID | 54 (di cui **31 il solo indexer**) | 26 |
| percorso HCA | 16 | 6 |
| + macchineria HC di strato (2 blocchi, §3) | 46 | 28 |
| + stato compressori ALLA CHIUSURA (§4b) | CSA+LID 129, HCA 39 | ~88 / ~27 |

### 1c. I BYTE: il costo vero della MLA sta qui, non nei nodi

Le 5 proiezioni per strato sono q8_0 [MISURATO log: 345 tensori q8_0 = 8/strato
+ testa]:

    wq_a  4096×1024  =  4,25 MiB     wq_b  1024×32768 = 34 MiB
    wkv   4096×512   =  2,12 MiB     wo_a  4096×8192  = 34 MiB
    wo_b  8192×4096  = 34 MiB        totale 108,4 MiB/strato → 4,551 GiB × 43

**4,55 GiB letti per forward** (una volta, servono 2 posizioni) → a 200-250 GB/s
reali = **18-23 ms/forward = 9-11,5 ms/posizione** [DEDOTTO]. È il 70% della
voce "densi q8_0" di PAVIMENTO §2a (6,6 GB): quella voce è in massima parte
QUESTA attenzione. Il formato è quello buono della famiglia (blocchi 34 B
allineati); non c'è leva di grafo che tocchi questo numero, solo M1/M2 possono
dire se il kernel q8_0 è al suo tetto.

Al confronto, tutto il resto del perimetro attn:

    f16 sempre letti: indexer_attn_q_b 16 MiB × 21 strati = 336 MiB/forward
                      + hc_fn 0,75×86 + indexer_proj ≈ 75 MiB
    f16 a chiusura:   compressori CSA/LID ~420 MiB ammortizzati ≈ 210 MiB/fwd
    KV letti:         raw 0,25×43 + CSA 2,75×21 + HCA 0,5×20 + LID 0,63×21 ≈ 85 MiB
    → attn non-q8_0 ≈ 0,6-0,7 GiB/forward ≈ 2,5-4 ms/forward

e i LANCI dell'intero perimetro attn (§2): ~1.400 kernel ≈ 1,5 ms/forward.
La stima storica "attenzione ~1-2 ms/posizione" era giusta SOLO come lanci+KV;
come byte di pesi il perimetro attn vale ~10-13 ms/posizione, già contati
altrove. Nessun doppio conteggio da aggiungere al bilancio di PAVIMENTO: è una
RIATTRIBUZIONE (la voce "densi" era per il 70% attenzione).

---

## 2. L'attribuzione dei 10.507 nodi per famiglia [CONTATO, errore ±3%]

Topologia della reserve bs=1 (che INCLUDE i rami di stato: senza, il conto si
ferma a ~7.300 — la differenza misura proprio lo stato):

| famiglia | nodi | % | kernel veri | dove |
|---|---|---|---|---|
| **stato compressori CSA/LID/HCA** | ~3.200 | 30,5% | ~2.200 | `deepseek4.cpp:1064-1217`, `:449-587` |
| **attenzione** (proiezioni+rope+percorsi+fattn) | ~2.760 | 26,3% | ~1.400 | `:890-1005`, `:589-888` |
| **MoE** (router+overlap K2+shexp+predittore) | ~2.530 | 24,1% | ~1.900 | `llama-graph.cpp:1773-2400`, `deepseek4.cpp:1304-1416` |
| **hyper-connection residue + norm di strato** | ~1.980 | 18,8% | ~1.200 | `deepseek4.cpp:328-447` |
| testa + embedding + out_ids | ~35 | 0,3% | ~20 | `:1242-1446` |

Tre letture operative:

1. **Nel regime il primo posto cambia**: lo stato CSA/LID compare solo quando un
   blocco da 4 si chiude (≈metà dei forward a batch 2), l'HCA ogni 128 →
   ammortizzato lo stato vale ~1.400 nodi/forward e l'**attenzione diventa la
   famiglia più numerosa del grafo di regime (~26-30%)**.
2. Dei 2.760 nodi di attenzione, 651 (31×21) sono il SOLO indexer LID: la
   selezione delle 512 celle costa più nodi della flash-attention che la usa
   (6 nodi, 1 kernel).
3. I 45 split del grafo non nascono qui: sono la lane CPU del MoE (K=2), uno
   per strato + testa/coda [MISURATO log 237].

Verifica proposta (gratis, alla prossima corsa): `GGML_SCHED_PROFILO=1` +
`LLAMA_DSV4_COMPRESS_DEBUG=1` stampano piani e battiti; il dump nodi con
`GGML_SCHED_DEBUG=2` su UN forward chiude l'attribuzione all'unità se serve.

---

## 3. I cicli residui che generano nodi su tensori piccoli (il "prossimo Sinkhorn", in ordine di massa)

### 3a. Le affini+sigmoidi pre/post di `build_hc_pre` — 1.204 nodi/forward, la leva n. 1

`deepseek4.cpp:344-365`: per OGNI blocco HC (2×43), DOPO la fusione restano
fuori dall'op `ggml_dsv4_hc_comb`:

    reshape + rms_norm + mul_mat(hc_fn 16384×24)            ← 3 nodi, lavoro vero
    4 view_1d su scale/base                                 ← 4 viste
    pre:  view + mul + add + sigmoid + scale_bias           ← 5 nodi su [4,nt]
    post: view + mul + add + sigmoid + scale                ← 5 nodi su [4,nt]

cioè **14 nodi (10 kernel) per blocco su 8-16 float** — lo stesso disegno del
Sinkhorn, un ordine di grandezza più piccolo. Il kernel fuso LEGGE GIÀ `mixes`,
`scale`, `base` (`dsv4-hc.cu:36-101` prende le colonne comb 8..23): estenderlo a
emettere anche `pre` [4,nt] e `post` [4,nt] (colonne 0..7) è la patch più
piccola possibile — un'uscita in più, niente numerica nuova, bit-uguale
possibile (sigmoide f32 seriale).

- **Risparmio**: 14×86 = 1.204 nodi/forward bersaglio + 84/chiamata bozza ≈
  ~910 nodi/token → **−0,6÷0,7 ms/token → +0,5÷1,0% t/s** [CONTATO×0b].
- **Verifica**: conteggio nodi dal log (atteso ~9.300 bs=1); SHA della risposta
  identico a fu7 con spec off e K=0 (il cancello vale: stessa aritmetica);
  accettazione 0,863 invariata; t/s mediana su 3.

### 3b. Il blocco di stato dei compressori — 129 nodi/strato CSA a ogni chiusura

`build_overlap_compressed_kv_from_state` (`:507-587`) + il gemello HCA
(`:449-505`) + la coreografia attorno (`:1064-1217`). Per UNA chiusura CSA:
43 nodi il compressore + 43 il gemello LID + 4+4 le proiezioni/APE + 2+2 le
concat con lo stato + 2+2 ring-store + **6+6 gli `dsv4_with_zero_dep`** + 2+2 i
persist + 4+4 le set_rows di stato = **129 nodi** su tensori [512,8] e [128,8].
Dentro ci sono i pattern da manuale del mandato:

- `dsv4_append_zero_row` (`:194-200`): 4 nodi (view+scale+reshape+concat) per
  APPENDERE UNA RIGA DI ZERI — due volte per compressore;
- `dsv4_with_zero_dep` (`:202-209`): sum+scale+add = 3 kernel il cui UNICO
  scopo è ordinare l'esecuzione (dipendenza fittizia) — sei volte per strato
  CSA alla chiusura;
- 4× (get_rows+cont+view+reshape) per separare prev/cur (`:534-552`).

Ammortizzato (≈½ dei forward per CSA/LID, 1/64 per HCA): ~1.400 nodi/forward
medio. Fonderlo in un'op per compressore (gather+softmax+pesatura+rms+rope su
[512×8], un warp per blocco) toglierebbe ~110 nodi/chiusura/strato →
**−0,4÷0,6 ms/token → +0,3÷0,8%** [IPOTESI, banda larga perché la frequenza
di chiusura a batch 2 va misurata]. Patch MEDIA (rope e rms dentro il kernel);
il rendimento/rischio è peggiore di 3a: seconda in coda, non prima.
- **Verifica**: `LLAMA_DSV4_COMPRESS_DEBUG=1` per contare le chiusure vere nel
  metro; poi test-backend-ops per l'op nuova contro la catena attuale.

### 3c. La riduzione finale del MoE — 11 nodi/strato

`build_moe_ffn_overlap` (`llama-graph.cpp:1937-1949`) e il percorso classico
(`:2360+`): 6 viste + 5 add sequenziali su [4096,nt] per sommare i 6 esperti.
Un'op di riduzione (o un `add` a 6 vie) = **−10 nodi/strato ×43 = −430/fwd**
(+ bozza) → **−0,2÷0,3 ms/token → +0,25÷0,4%**. Tocca il MoE, non l'attn: la
segnalo perché cade nello stesso stampo e la patch è piccola; ATTENZIONE
all'ordine di somma (bit-exact da preservare: somma seriale nello stesso
ordine 0..5).

### 3d. `build_top_k_mask` — 7 nodi/strato CSA

`deepseek4.cpp:682-709`: fill(-INF) + 2 viste + fill(0) + set_rows + vista +
add per trasformare il top-k in maschera additiva: 3-4 kernel × 21 strati.
Fondibile in uno scatter singolo: −60 kernel/fwd → +0,05÷0,1%. Spicciolo: solo
in coda a un'altra patch.

### 3e. L'indexer LID per intero — 31 nodi/strato, 651/forward

`build_lid_top_k` (`:589-680`): mm q_b → rope → concat → hadamard → mm proj →
scale → ring → 2 permute+cont → relu·w·sum_rows → add mask → argsort. La catena
relu+mul+sum_rows+cont (4 kernel su [512,64,nt]) è fondibile in un solo kernel
"score": −4 kernel/strato. Ma il costo VERO dell'indexer non sono i lanci: è la
**matrice f16 `indexer_attn_q_b` da 16 MiB/strato = 336 MiB/forward** (§5).

### 3f. Già ottimale (perimetro pulito, nessuna azione)

- **I tre kernel fusi HC** (`dsv4-hc.cu`): un lancio l'uno, Sinkhorn a 20
  iterazioni in registri, un thread per token; per il decode non c'è niente da
  limare.
- **La flash-attention**: 1 kernel per strato, percorso mma_f16 DKQ=DV=512
  (`fattn.cu:179-181`, `:484`), gqa_ratio 64 sfruttato (ncols2=8).
- **`build_attn_mha`**: 6 nodi di cui 5 viste, zero copie.
- **La cache raw SWA**: 256 celle, cpy_k = view+set_rows, K letto 0,25
  MiB/strato: il ring SWA è già minimo.
- **`build_mla_qkv`**: 15 nodi per q+kv con 2 soli concat da 256 KB — è il
  pattern MLA upstream, niente da togliere.

---

## 4. RoPE e SWA: com'è implementato, cosa costa

- **Due regimi di rope** (`:1024-1030`): strati compressi → base 160000 con
  yarn (freq_scale 0,0625, ctx_orig 65536); strati raw → base 10000, yarn
  SPENTO (freq_scale 1, ext 0). `dsv4_rope_attn_factor` (`:11-17`) compensa il
  fattore d'attenzione yarn.
- **Lanci rope per forward** [CONTATO]: 2/strato (q_pe [64,64,nt], kv_pe
  [64,1,nt]) ×43 + 1 de-rope/strato (`ggml_rope_ext_back`, `:989`) ×43 +
  1 indexer/strato CSA ×21 + i rope di stato alle chiusure ≈ **150-170
  lanci/forward ≈ 0,15-0,2 ms** al fattore 0b. Il de-rope NON è rimovibile
  (wo_a vive nello spazio de-ruotato — è architettura, non zavorra); q+kv dello
  stesso strato sono fondibili in un lancio ma vale <0,05 ms: solo in coda.
- **SWA**: `n_swa=128`, `LLAMA_SWA_TYPE_STANDARD` su TUTTI gli strati
  (`set_swa_pattern(0)`, `:79-80`); cache raw da 256 celle [MISURATO log 180].
  Il costo è irrisorio per costruzione (0,25 MiB/strato letti). Unica cosa da
  sapere: la raw entra in OGNI percorso via `ggml_concat(raw_k, comp_k, 2)`
  (`:758,826`) — la concat NON copia la cache, produce il K unito per la fattn;
  è il disegno giusto finché la fattn accetta un solo tensore K.

---

## 5. Op ridondanti e zavorra (#25370 e oltre)

1. **`dsv4_repeat_streams` e `dsv4_build_kq_zero_bias` sono ancora nel file MA
   sono INERTI nella configurazione di produzione** [CONTATO]: con
   `kv_unified=false` e `n_seq_max=1` → `n_stream=1`, il repeat esce al primo
   ramo (`:214-216`) e il bias esce su `!cparams.kv_unified` (`:227-229`):
   **zero nodi generati**. La rimozione upstream (#25370, censita in
   UPSTREAM_390 §riga 82) da noi vale igiene e multi-sequenza, NON pavimento:
   la voce "zavorra nel 49%" di UPSTREAM_390 va corretta — nel grafo fu7 quei
   nodi non ci sono. Righe attuali: `:213-220`, `:222-235`, usi a
   `:756,774,824,842,878,880`.
2. **Le maschere dei compressori nascono F32 e vengono castate F16 a OGNI
   strato** [CONTATO]: `dsv4_build_comp_inputs` crea `kq_mask` F32 fisso
   (`llama-graph.cpp:858`) mentre la maschera raw segue la FA
   (`:710`, F16). Il costruttore poi casta per strato (`deepseek4.cpp:764-769`
   CSA, `:832-837` HCA): **41 kernel cast/forward**. Cura: creare la comp mask
   col tipo della raw + scrivere fp16 in `dsv4_set_kq_mask`. −41 kernel
   (+0,03-0,05%): spicciolo ma è UNA riga più il writer, e cade da sola
   nell'eventuale patch 3a.
3. **`dsv4_with_zero_dep` / `dsv4_append_zero_row`**: 3 e 4 nodi l'uno per
   fabbricare dipendenze e righe-zero (§3b): non rimovibili da soli (ordinano
   le scritture del ring), spariscono SOLO dentro la fusione del compressore.
4. **L'eps del Sinkhorn come tensore+fill** (`:300-303`): vivo solo nel
   percorso NON fuso; con `fused_dsv4_hc_comb` attivo non entra nel grafo.
   Idem `build_hc_head` che resta sul cammino storico (loop `:279-288`): 15
   nodi UNA volta per forward — non vale una riga di patch.
5. **Il predittore `cache_pf`** (`:1371-1409`): 8 nodi/strato ×~39 strati nel
   decode. Non è zavorra (è il prefetch della cache esperti) ma è nel conto MoE
   di §2 — lo dico perché chi confronta i nodi con upstream se lo ritrova.

---

## 6. Flash attention: attiva, su quale kernel, e il filo a cui è appesa

- **Attiva** [MISURATO]: `flash_attn=auto` → "Flash Attention enabled"
  (fu7 righe 167, 226; anche la bozza, 410).
- **Kernel**: per K=V=512 il dispatch esige `gqa_opt_applies` (`fattn.cu:
  424-431`), cioè maschera presente, no ALiBi e **KV multiplo di
  FATTN_KQ_STRIDE=256**; su Ampere (cc 8.6, `turing_mma_available`) il vec è
  escluso (`Q->ne[0]=512 > 256`, `:460`) → **BEST_FATTN_KERNEL_MMA_F16**
  (`:484`) con ncols2 da gqa 64. Un lancio per strato.
- **Il filo**: il multiplo di 256 lo garantisce SOLO `plan.n_kv =
  GGML_PAD(plan.n_kv, 256u)` (`llama-kv-cache-dsv4.cpp:617`) più le cache comp
  allocate a multipli di 256 (`:1105-1114`; per questo la HCA da 80 celle
  logiche ne alloca 256 [MISURATO log 194]). Chi tocca quel padding spegne la
  FA **in silenzio** (auto → fallback softmax) e riporta in gioco la race del
  punto sotto su TUTTI gli strati. Da proteggere con un assert o un log alla
  reserve.
- **Cosa costerebbe non averla**: percorso esplicito = kq mul_mat [512]×[celle]
  + soft_max + kqv per 64 teste — a queste taglie ~3-5 nodi in più per strato e
  qualche ms, ma soprattutto la soft_max non-FA passerebbe da `block_reduce`.

### 6a. La race #26385 è nel nostro albero, e il punto d'innesco vivo è lo stato HCA

`common.cuh:620-640`: fra la `__syncthreads()` (`:631`) e la lettura di
`shared_vals[lane_id]` (`:634`) non c'è barriera d'uscita: una SECONDA chiamata
a `block_reduce` sullo stesso buffer (il pattern max→sum di `soft_max_f32`,
`softmax.cu:102` e `:120`; doppio in `:174/189` e `:212/226`; e le due SUM di
`group_norm_f32`, `norm.cu:56/67`) può sovrascrivere ciò che i warp lenti non
hanno ancora letto. Serve `block_size > 32`, cioè **ncols > 32** (launcher:
`nth` raddoppia da 32, `softmax.cu:327-331`).

Nel NOSTRO decode fuso [CONTATO]: l'attn principale è FA (non passa di lì); i
softmax vivi sono quelli dei compressori — CSA/LID a ncols=8 → 32 thread →
salvi; **HCA a ncols=128 → 4 warp → esposta**, una volta ogni 128 posizioni per
strato HCA. La cosa seria non è la frequenza: l'output di quel softmax viene
**scritto nel ring HCA e persiste** (`:1195-1196`) — un innesco corrompe la
cache compressa per il resto della sessione, non un token solo. Con FA spenta
(o il filo di §6 rotto) l'esposizione diventa ogni-strato-ogni-forward. La fix
upstream (`9bd4c09ea`) è due `__syncthreads()`: UPSTREAM_390 la scheda già
(pick 3); qui aggiungo solo il punto d'innesco vivo e la persistenza. Nessun
guadagno di velocità: è fiducia nelle misure.

---

## 7. Le leve, in ordine di nodi risparmiabili (stime BASSE, fattore §0b dichiarato)

| # | leva | nodi/fwd | ms/token | t/s | patch | cancello |
|---|---|---|---|---|---|---|
| 1 | **pre/post dentro l'op comb** (§3a) | −1.204 (+bozza) | −0,6÷0,7 | **+0,5÷1,0%** | piccola (estendere `dsv4-hc.cu`) | nodi ~9.300; SHA=fu7 a spec off K=0; acc 0,863 |
| 2 | **compressore di stato fuso** (§3b) | −1.100÷1.400 ammort. | −0,4÷0,6 | +0,3÷0,8% | media | conteggio chiusure con COMPRESS_DEBUG, poi test-backend-ops |
| 3 | **riduzione MoE a 6 vie** (§3c) | −430 (+bozza) | −0,2÷0,3 | +0,25÷0,4% | piccola | bit-exact sull'ordine di somma |
| 4 | **indexer_attn_q_b f16→q8_0** (§5 byte) | 0 | −0,3÷0,4 | +0,4÷0,5% [IPOTESI] | riconversione GGUF, zero codice | qualità: acc e p1 invariati (la selezione top-512 deve reggere il rumore di quantizzazione — NON bit-garantito) |
| 5 | maschere comp F16 + top_k_mask scatter + rope q&kv (§5.2, 3d) | −150 kernel | −0,1 | +0,1÷0,15% | spiccioli | solo in coda a 1-2 |
| — | fix race #26385 (§6a) | 0 | 0 | 0 (fiducia) | 2 righe | 3 SHA identici restano identici |

Composito onesto delle leve di grafo (1+2+3+5): **+1,1÷2,3% t/s** — un decimo
della fusione di stanotte, ed è giusto così: il grafo dell'attenzione dopo la
fusione è per due terzi lavoro vero. La leva 4 è l'unica a byte e va trattata
da esperimento di qualità, non da ottimizzazione.

**Perché queste stime sono basse e quella HC era bassa di 3-10×**: la fusione HC
ha tolto il 69% dei NODI del grafo, accorciando la cattura CUDA e i buchi di
sottomissione oltre il costo contabile dei lanci — un effetto di soglia che non
si ripete togliendo il 10%. Il fattore 0b (0,73 µs/nodo) è GIÀ il fattore
post-soglia misurato, non un ms-contabile da scontare con lo 0,08-0,43: per
lanci residui su un grafo già corto è la scelta prudente coerente coi dati di
stanotte.

---

## 8. Cosa NON si ottiene senza eseguire (elenco richiesto)

1. **Attribuzione al nodo esatto**: un forward con `GGML_SCHED_DEBUG=2` (o la
   sonda nodi) chiude le bande ±3% di §2.
2. **Frequenza vera delle chiusure CSA/LID a batch 2** (decide metà della leva
   2): `LLAMA_DSV4_COMPRESS_DEBUG=1` sul metro, gratis.
3. **µs/nodo per famiglia** (valida il fattore 0b fuori dalla famiglia HC):
   nsys su ~20 forward (M1 di PAVIMENTO, mai eseguita).
4. **Kernel FA effettivo a runtime** (la deduzione statica dice MMA_F16;
   conferma con nsys o un printf nel dispatch).
5. **GB/s reali di wq_b/wo_a/wo_b q8_0 alle forme vere** (decide se i 18-23
   ms/forward di §1c hanno margine): `test-backend-ops perf -o MUL_MAT` q8_0
   4096×32768 ne1=2 — è la M2 di PAVIMENTO estesa ai densi.
6. **Innesco della race HCA**: loop di `test-backend-ops -o SOFT_MAX` ncols=128
   su sm86, oppure due run col fix e senza: divergenza = innesco.

## 9. Sintesi in tre righe

Dopo la fusione di stanotte l'attenzione è la famiglia più numerosa del grafo di
regime (~26-30% dei nodi) ma non contiene un secondo Sinkhorn: contiene le
affini pre/post rimaste fuori dal kernel fuso (1.204 nodi, patch piccola su un
kernel esistente, +0,5-1%), il blocco di stato dei compressori (~129 nodi/strato
a chiusura, +0,3-0,8%, patch media) e spiccioli censiti — in tutto +1,1-2,3%,
non un altro +16%. Il costo VERO della MLA sono i byte: 4,55 GiB/forward di
wq_b/wo_a/wo_b q8_0 (il 70% della voce "densi" di PAVIMENTO era attenzione) più
336 MiB di indexer f16, l'unico byte comprimibile rimasto (+0,4-0,5%, cancello
di qualità). La flash-attention c'è, è mma a un lancio per strato, ed è appesa
al `GGML_PAD(n_kv, 256)` del piano: proteggerlo, e importare il fix della race
`block_reduce` (#26385) che oggi ha un punto d'innesco vivo nel softmax dello
stato HCA — corrompe cache persistente, non un token.
