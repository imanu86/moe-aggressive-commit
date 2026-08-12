# INDEXERZC — indexer zero-copy da RAM pinnata: byte TOCCATI misurati (densi), flag consegnato

Data: 2026-07-29. Nessuna compilazione, nessun server, `D:\` mai toccato,
nessun file del tree modificato (deliverable solo in `.microbench/indexerzc/`).

Mandato: **FATTO 1** — determinare dai kernel i byte dell'indexer LETTI per
token dal percorso di scoring a ctx>2048 (byte toccati, non byte copiati),
verificando se il "100% riletto" di pin2 misurava la cosa giusta. **FATTO 2** —
consegnare comunque `DS4_CUDA_INDEXER_HOST_ZEROCOPY=1` dietro flag, fail-open,
perche' il bilancio si decide a banco.

## Esito in breve

- **FATTO 1: l'accesso intrinseco dei kernel E' DENSO. Il verdetto di pin2
  misurava gia' i byte TOCCATI** (derivazione dal sorgente dei kernel, non
  contatori di copia: pin2 §1.3) **e resta valido sul tree corrente**:
  `indexer_f16` = **363.331.584 B/token, 100% della residenza, ogni token con
  pos >= 2051, ctx-indipendente**. La distinzione copiati/toccati cambia i
  numeri solo per la parte NON-pesi (K-cache dell'indexer: anch'essa toccata
  al 100% del visibile, e CRESCE col contesto — §1.3). La speranza "accesso
  sparso" e' falsificata alla riga di kernel: la sparsita' della DS4-attention
  nasce DOPO il top-k sugli score; nessun ramo legge un sottoinsieme di righe.
- **FATTO 2: CONSEGNATO.** `indexerzc.patch` (+165/-0, solo
  `ds4-p4a/ds4_cuda.cu`), `git apply --check` pulito sul tree CORRENTE
  (che ha gia' pin2 applicato: base = `DD1E4CD8...`, il "dopo" di pin2).
  Flag `DS4_CUDA_INDEXER_HOST_ZEROCOPY=1`, default 0 = percorso attuale.
  Zero copie per token, zero staging/arena, fail-open a UNA riga, UNA riga
  all'attivazione con byte pinnati + previsione di tocco.
- **Bilancio su carta (da verificare a banco): NEGATIVO, ~-7/-13 ms/token**
  (§1.4). Il flag esiste per decidere coi numeri del banco, come prescritto.

---

## 1. FATTO 1 — i byte toccati per token dal percorso di scoring

### 1.1 Copiati vs toccati: cosa misurava pin2

La verifica richiesta dal mandato: pin2 §1.3 NON contava i byte copiati
dall'implementazione (la fd-cache copia ogni tensore UNA volta, 346,5 MiB
one-shot) ma derivava dal corpo dei kernel i byte letti per token. E' la
misura giusta ed e' stata ri-derivata sul tree corrente (righe sotto). La
conclusione non cambia col cambio di lente: il GEMV e' denso.

### 1.2 Il percorso di scoring per token (decode, pos >= 2051) — tree corrente

Guardia di attivazione: `ds4.c:13591` (`layer_n_comp[il] > decode_top_k`,
top_k=512 da `ds4.c:124`) -> pos >= 2051. Layer con indexer: `ratio == 4`
-> `ds4_layer_compress_ratio` (`ds4.c:452-456`): il pari da 2 a 42 = **21
layer**. Per ciascuno, per token:

| # | passo | file:riga (chiamata) | kernel (corpo) | byte toccati/token/layer |
|---|---|---|---|---:|
| 1 | GEMV `indexer.attn_q_b` (F16 1024x8192) | `ds4.c:13607-13611` | `matmul_f16_ordered_chunks_kernel` `ds4_cuda.cu:17922-17952` (lancio `:22889-22891`, n_tok=1 default) | 16.777.216 (100%) |
| 2 | GEMV `indexer.proj` (F16 4096x64) | `ds4.c:13625-13629` | idem | 524.288 (100%) |
| 3 | score vs K-cache indexer | `ds4.c:13639-13646` | `indexer_score_one_direct_kernel` `ds4_cuda.cu:20874-20915` (lancio `:22272-22280`) | 512 x n_index_comp (100% del visibile) |
| 4 | top-k sugli score | `ds4.c:13655-13659` | `indexer_topk_*` `ds4_cuda.cu:21093-21344` | 4 x n_index_comp (dato calcolato) |

Prova di densita' (passi 1-2): `matmul_f16_tensor_labeled` prende il puntatore
all'INTERO tensore (`weight_bytes = out_dim*in_dim*2`, `ds4_cuda.cu:22836-22842`)
e ogni blocco del kernel legge `wr[i]` per l'intera riga (thread t copre il
chunk contiguo `[t*chunk, (t+1)*chunk)`, unione = in_dim; blocchi = out_dim
righe): ogni byte letto esattamente una volta per token. Identico per i rami
`matmul_f16_kernel` (`:17874-17900`), seriale (`:17902-17920`) e cublas
(prefill n_tok>1, `:22855-22883`). Il top-k avviene sugli SCORE (passo 4),
mai sui pesi. Prova (passo 3): blocco per riga `c in [0, n_comp)`, lettura
`index_comp[c*128 .. +128]` (`:20899`), righe oltre `visible=(pos+1)/ratio`
solo azzerate: toccato il 100% delle righe visibili, che a decode ~= tutte.

### 1.3 I numeri (formula e valori)

- **Pesi `indexer_f16`** (i soli file-backed, cio' che il flag sposta):
  21 x (16.777.216 + 524.288) = **363.331.584 B/token = 346,5 MiB, fissi**.
- **K-cache indexer** (`layer_index_comp_cache`, f32 128/riga):
  21 x 512 x n_index_comp ~= **2.688 x pos B/token** -> 5,5 MB a pos 2051,
  22 MB a 8k, 88 MB a 32k, **403 MB a 150k**. Alloc UPFRONT a
  `ctx/4+2` righe (`ds4.c:12845`, `:12778`; a cap hard-fail `ds4.c:13539-13542`):
  la sua VRAM e' COSTANTE dall'avvio; cio' che "si allarga" a pos>=2051 e' la
  residenza dei PESI nella fd-cache (il cliff). Dei ~536 MiB del mandato,
  solo 346,5 MiB sono spostabili con un flag di residenza pesi; il resto e'
  dato calcolato (gia' indirizzabile con DS4_CUDA_KV_MANAGED/KV_STAGED_RING,
  toccato anch'esso al 100% -> stessa economia negativa, peggiore a ctx alto).
- **Score/top-k**: ~21 x pos B/token (3,2 MB a 150k) — trascurabile.

### 1.4 Il bilancio quantificato (numeri misurati del repo, non stime nuove)

| voce | valore | fonte |
|---|---:|---|
| costo zero-copy pesi (25,86 GB/s S2a, caso migliore) | +14,1 ms/token | `.microbench/zerocopy/results.txt` |
| costo con i 18 GB/s del mandato | +20,2 ms/token | mandato (536->346,5 MiB corretti) |
| oggi da VRAM (89,4 GB/s S1) | 4,1 ms/token | idem |
| **delta costo permanente** | **>= +10 ms/token** | (e il pattern `ordered_chunks`, 32 thread x 2 B stride 64 B, rende il caso migliore ottimista: il bench era coalescente a 256 thread) |
| VRAM liberata | 346,5 MiB = **+51 slot** (7.077.888 B/slot), cache 140->191 | aritmetica |
| hit atteso (curva 140=26%, 258=34%) | +3,5 pp -> ~8,3 miss/token in meno | curva capacita' misurata |
| risparmio H2D esperti (7,08 MB x 8,3 a 17,6-19,8 GB/s S3) | -3,0/-3,3 ms/token | zerocopy results S3a/S3b |
| **netto su carta** | **~ -7/-13 ms/token (PERDITA)** | |
| recuperabile a banco | hot-reserve 256 MB non piu' necessaria (costo documentato +34% POST/PRE) | braccio B3 §4 |

---

## 2. FATTO 2 — il flag consegnato

`DS4_CUDA_INDEXER_HOST_ZEROCOPY=1` (default assente/0 = percorso attuale).
Righe «:N» = file DOPO la patch.

### 2.1 Disegno

- **Intercetta** in `cuda_model_range_ptr` (`:4113-4123`), DOPO il lookup dei
  range esistenti e PRIMA della fd-cache: solo etichetta `indexer_f16`
  (costruita unicamente da `ds4_gpu_matmul_f16_indexer_tensor`, `:23076-23088`).
- **Acquisizione una-tantum per tensore** (`cuda_indexer_zerocopy_range_ptr`,
  `:3978-4054`): `cudaHostAlloc(cudaHostAllocMapped)` + UNA lettura dal file
  col lettore di produzione `cuda_model_stage_read` (gestisce O_DIRECT/align;
  slack 2x`g_model_direct_align`, il device pointer viene spostato del delta
  del payload) + `cudaHostGetDevicePointer` (UVA). Poi SOLO hit di registro
  (<=42 voci, richieste whole-tensor identiche): **nessuna copia per token,
  nessun transito da arena/staging, i kernel leggono sul posto via PCIe**.
  Idiomi riusati dal percorso `DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB`:
  stesso tetto host-pin (`cuda_host_register_budget_bytes`) e stesso
  accumulatore WDDM `g_model_registered_range_bytes` (`:4052`) — il pin
  cudaHostAlloc consuma lo stesso budget fisico dei cudaHostRegister.
- **Fail-open dichiarato** (`cuda_indexer_zerocopy_failopen`, `:3967-3976`):
  al primo fallimento (file non leggibile, budget, cudaHostAlloc, lettura,
  map) UNA riga `[indexer-zc] pin_failed reason=... action=fail-open` +
  latch: i tensori gia' pinnati restano zero-copy (dati validi), i successivi
  proseguono sul percorso fd-cache ODIERNO (la chiamata torna NULL e il
  flusso continua nel blocco fd-cache sottostante, non nel legacy VRAM-copy).
- **UNA riga all'attivazione** (`:3987-4005`): emessa al PRIMO RIUSO di una
  voce (= il working set indexer del primo passaggio e' completo, totali
  veri): `active=1 tensors=N pinned_bytes=B (MiB, alloc) mode=hostalloc+
  fd-read+uva predicted_touch_per_token=B bytes (100% dei pinnati: GEMV
  denso, ctx-indipendente)` — la previsione e' il FATTO 1.
- **Ciclo di vita**: rilascio in `cuda_model_range_release_all` (`:8985-8988`),
  quindi sia a `ds4_gpu_cleanup` sia a `ds4_gpu_set_model_map` (reload);
  liberazione con `cudaFreeHost`, azzeramento latch/annuncio.
- **Invisibile allo sfratto**: le voci vivono FUORI da `g_model_ranges` ->
  `cuda_model_pick_victim` non puo' designarle (scarta gia' i non-streamed),
  `span_release`/`range_bytes`/probe del picco non le contano (niente VRAM),
  la fd-cache non registra load per l'indexer. `DS4_CUDA_STREAM_HOT_RESERVE_MB`
  resta inerte per l'indexer a flag ON (nessuna stream_alloc da riservare).
- Nota configurazioni: se una configurazione pre-carica gli span del modello
  in VRAM al load (label `tensor-span:N`), il lookup dei range vince e il
  flag e' un no-op silenzioso — corretto: li' non c'e' cliff da curare. Nel
  config di campagna gli span oltre finestra sono deferiti (documentato dal
  cliff `fd-cache load` a pos 2051) e il gate scatta alla prima richiesta.

### 2.2 Cosa vedono i contatori (dichiarazione richiesta dal mandato)

- **Transport ledger** (`DS4_CUDA_TRANSPORT_LEDGER`, `:28209+`): e' un ledger
  per coppia (layer, esperto) MoE — **non vede i byte dell'indexer OGGI e non
  li vede col flag ON**. Non e' un buco NUOVO: e' fuori dal suo dominio per
  costruzione. Dichiarato qui, nessuna pretesa che li conti.
- **Worker-prof** (`WP_READ_BYTES` ecc.): conta le letture del route worker
  esperti — **le mie letture one-shot (decode thread, `cuda_model_stage_read`)
  non ci passano e non vengono contate**. Dichiarato.
- **I byte zero-copy per token NON sono osservabili da NESSUN contatore host
  esistente**: sono traffico PCIe generato dai kernel (BAR/UVA), senza evento
  host da agganciare. Il sostituto dichiarato e' la riga di attivazione:
  `predicted_touch_per_token` = byte pinnati (100%, FATTO 1). A banco la
  verita' la dicono Nsight/contatori PCIe, non il runtime.
- **Cosa si vede comunque nei log esistenti** (segnatura del flag che lavora):
  a pos 2051 SPARISCONO i `fd-cache load` dell'indexer e gli sfratti da
  pressione `indexer_f16` (righe ANOMALY/PIN di pin2 con `requester=
  indexer_f16` -> assenti); `[vram-prio]` e `nvidia-smi` mostrano ~346,5 MiB
  in meno di pressione VRAM; +51 slot alzabili sulla cache esperti.

### 2.3 Neutralita' a flag spento

- Gate: `cuda_indexer_host_zerocopy_enabled()` = int memoizzato (getenv una
  volta a processo, idioma `ds4_gpu_graph_tensor_device_requested`); a OFF il
  corto circuito salta anche lo `strcmp` -> percorso IDENTICO (il blocco
  fd-cache sottostante fa gia' un getenv per chiamata: il gate costa meno di
  cio' che lo segue).
- Nessuna struct condivisa toccata: struct + vector + 4 interi NUOVI, static
  file-local (stesso pattern accettato di pin2); mutazioni sul thread di
  decode/prefill come `g_model_ranges`.
- Nessuna riga di log nuova a OFF (neanche campi a zero: il controllo resta
  byte-identico anche nei log, piu' stretto di pin2).
- Hook di release: itera un vector vuoto e azzera zeri — nessun effetto.
- Zone vietate: ZERO hunk su shared1 (`ds4_gpu_model_span_release`, `:8623`),
  pin2 (pick_victim `:8481`, ciclo di sfratto con shed `:8665-8781`, prepare,
  launch_impl), drain4+fix, dspark1, dspark2+fix2+fix3, logids, lane, econ,
  precheck route worker (`:42193-42286` del file base, slittato a `:42358+`
  dopo la patch, mai toccato), Q1. Hunks: `:3907-4055` (blocco nuovo),
  `:4113-4123` (gate), `:8986-8988` (release). `ds4.c` non toccato.

---

## 3. Bracci minimi per giudicare a banco

1. **Controllo** (OFF): log byte-identici a oggi (nessun campo nuovo).
2. **B1 ON, cache 140, hot-reserve invariata**: attesi la riga `[indexer-zc]
   active=1 tensors=42 pinned_bytes=363331584`, `fd-cache load` piatto a
   pos 2051, sfratti da indexer assenti; misurare il delta ms/token POST
   (qui si paga il PCIe denso: e' il numero che decide).
3. **B2 ON + cache alzata a ~191** (i +51 slot incassati): l'unico braccio
   in cui il flag puo' vincere; confrontare con controllo a parita' di token.
4. **B3 = B2 senza `DS4_CUDA_STREAM_HOT_RESERVE_MB`**: recupero del +34%
   POST/PRE della riserva, che a flag ON non serve piu' all'indexer.
   Fail-fast: se B1 degenera oltre il bilancio di §1.4, stop (regola utente).

## 4. Applicabilita' e hash

```text
base:  ds4-p4a/ds4_cuda.cu (tree corrente = pin2 applicato, NON modificato)
       SHA-256 DD1E4CD8B3B2D93C4414B6A80A2DFE153FD0BD20A11125DECECE4ADDDA14AD71
dopo:  ds4-p4a/ds4_cuda.cu + indexerzc.patch
       SHA-256 23FF1A3BAAA262D508C19A0C44CCC950FE54888D493EED4EE39BACE344448124
patch: .microbench/indexerzc/indexerzc.patch
       SHA-256 ADD4F7180551BE0D58D3C62CD2C409594564000B08F63A68D25F99512F99D4CC

git apply --check .microbench/indexerzc/indexerzc.patch -> OK (tree corrente)
git apply --numstat -> +165 -0, solo ds4-p4a/ds4_cuda.cu
roundtrip base+patch -> byte-identico al file di lavoro
bilanciamento ()/{}[] -> identico alla base; fprintf nuove verificate 1:1
```

Verifica FATTO 1 condotta su: `ds4-p4a/ds4.c` (124, 452-456, 12770-12862,
13539-13542, 13591-13682, 16135-16157), `ds4-p4a/ds4_cuda.cu` base
(17874-17952, 20874-20961, 22235-22301, 22824-22923, 8622-8720, 3907-4025,
8319-8348, 9115-9181), `.microbench/pin2/NOTA.md`,
`.microbench/zerocopy/results.txt`. Nessuno di questi file modificato.
