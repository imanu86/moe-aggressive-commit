# 35 — `patch_acceptmoe.diff` rifusa sull'albero del 10 agosto

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, HEAD
`f8df4de8a`. **Niente compilato, niente eseguito** (la macchina stava
misurando). Consegna: le modifiche sono **sull'albero, non committate**.

Stato: 13 file su 13 della patch applicati, **più un quattordicesimo che la
patch aveva dimenticato** (`ggml/include/ggml-rpc.h`, §4). Tre dei quattro
conflitti segnalati da `git apply --check` erano **fine-riga, non semantica**;
uno solo era vero.

---

## 1. Il meccanismo, in due frasi

Due op nuove (`GGML_OP_ACCEPTMOE_IDS`, `GGML_OP_ACCEPTMOE_PESI`) si infilano fra
il router e i `MUL_MAT_ID` e **riscrivono i valori — mai le forme — di id e pesi
degli esperti**: per le sole righe `t >= n_esatte` del batch di verifica, gli
esperti non residenti nella cache VRAM vengono rimpiazzati da un duplicato del
miglior residente della riga con peso 0, e i superstiti rinormalizzati di
`Σtot/Σtenuti`, così che la verifica delle posizioni oltre la prima non chieda
**nessun** trasporto H2D.

Quali righe mascherare viaggia in un **tensore di input** `I32[4] {attivo,
n_esatte}` — lo stesso canale per-forward di token e posizioni, quindi le forme
restano congelate e i CUDA graph non si accorgono di niente — pubblicato dal
server, che arma one-shot solo quando la vista è esattamente `[token campionato
+ bozza]` di un solo slot e **non** è un replay da checkpoint.

---

## 2. I quattro conflitti, e come li ho risolti

`git apply --check` ne segnalava **quattro**, non tre: oltre ai tre del mandato
c'era anche `tools/server/server-context.cpp`. La causa vera li accomuna quasi
tutti.

### La diagnosi: la patch è a fine-riga MISTO

`patch_acceptmoe.diff` non è né LF né CRLF: è mista, sezione per sezione.

| sezione della patch | righe LF | righe CRLF | il file su disco | esito |
|---|---:|---:|---|---|
| `ggml/include/ggml.h` | 5 | **44** | LF | **falliva** |
| `ggml/src/ggml.c` | 6 | **90** | LF | **falliva** |
| `ggml/src/ggml-cpu/ggml-cpu.cpp` | 4 | 10 | *(vedi §5)* | passava |
| `include/llama.h` | 4 | 20 | *(vedi §5)* | passava |
| `src/llama-cparams.h` | 4 | **10** | LF | **falliva** |
| `tools/server/server-context.cpp` | 5 | **32** | LF | **falliva** |
| gli altri 7 | 556 | 0 | LF | passavano |

I quattro che fallivano sono **esattamente** i quattro con corpo CRLF su file
LF. `git apply` non fa fuzzing sul CR: una riga di contesto `...\r\n` non
combacia con `...\n`, e l'hunk viene rifiutato anche quando il testo è
identico. Verificato in isolamento (repo di prova nello scratchpad: blob LF di
`llama.h` + hunk CRLF ⇒ `patch does not apply`, deterministico).

### Conflitto 1 — `src/llama-cparams.h`: **fine-riga soltanto**

Risolto normalizzando la sezione a LF e applicandola con `git apply`.
Il contesto (`cb_eval_user_data` / `ctx_other` / `};`) è **immutato** dalla
fusione hyper-connection: quella ha aggiunto `fused_dsv4_hc_pre/comb/post` e
`auto_fhc` **sopra**, a riga 44-47, spostando solo gli offset.
**Semantica invariata rispetto all'intento originale.** Nessuna scelta fatta da
me: è la patch, byte per byte.

### Conflitto 2 — `tools/server/server-context.cpp`: **fine-riga soltanto**

Idem. L'ancora (`n_empty_consecutive = 0; }` … `const int ret =
llama_decode(ctx_tgt, batch_view);`) è intatta, solo scivolata da riga 3608 a
3627. **Semantica invariata.**

### Conflitto 3 — `ggml/include/ggml.h`: **fine-riga soltanto**

Entrambi gli hunk (i due enumeratori in coda all'enum, e le due dichiarazioni
`GGML_API` prima di `ggml_dsv4_kv_ring_store`) hanno contesto immutato: la
fusione HC ha inserito `GGML_OP_DSV4_HC_COMB/PRE/POST` a riga 573-575, molto
**sopra** il punto d'inserimento. **Semantica invariata.**

Verificato che i due nuovi op restano **gli ultimi due prima di
`GGML_OP_COUNT`** (righe 605-606, `COUNT` a 608): nessun op preesistente cambia
valore numerico, quindi nessuna serializzazione e nessuna tabella indicizzata
per op si sposta.

### Conflitto 4 — `ggml/src/ggml.c`: **l'unico conflitto VERO**

Qui la fusione HC morde davvero. La patch faceva `100 → 102`; l'albero di oggi
è a **103** (i tre op HC). Risolto **a mano** con `Edit`, tre punti:

1. `GGML_OP_NAME[]` (riga 1101-1106): aggiunti `"ACCEPTMOE_IDS"`,
   `"ACCEPTMOE_PESI"` **in coda**, dopo `"DSV4_KV_RING"`, e
   `static_assert(GGML_OP_COUNT == 103)` → **`== 105`**.
2. `GGML_OP_SYMBOL[]` (riga 1219-1227): idem con
   `"acceptmoe_ids(sel,pesi,stato)"` / `"acceptmoe_pesi(pesi,sel,stato)"`, e il
   secondo `static_assert` → **`== 105`**.
3. I due costruttori `ggml_acceptmoe_ids` / `ggml_acceptmoe_pesi`, copiati
   **carattere per carattere** dalla patch, inseriti dove la patch li voleva:
   dopo `ggml_cache_esperti_partiziona`, prima di `ggml_dsv4_kv_ring_store`.

**La risoluzione NON cambia la semantica dell'intento.** L'unico grado di
libertà era *dove* mettere i due nomi negli array, e la risposta è forzata:
l'array è indicizzato per valore dell'enum, i due op sono in coda all'enum,
quindi i due nomi vanno in coda agli array. Ho verificato che l'ordine
enum ↔ nomi combacia anche per gli op HC preesistenti (`COMB, PRE, POST` in
entrambi: nessun disallineamento ereditato da correggere di straforo).

Il `103 → 105` non è una scelta: è aritmetica. I due `static_assert` sono
proprio il meccanismo che urla se sbaglio, ed è il motivo per cui questo
conflitto era rumoroso invece che silenzioso — il caso fortunato.

---

## 3. Il quattordicesimo file: la patch originale era INCOMPLETA

`ggml/include/ggml-rpc.h:14` porta un terzo controllo sul conteggio:

```c
#define RPC_PROTO_PATCH_VERSION    3
static_assert(GGML_OP_COUNT == 103, "GGML_OP_COUNT has changed - update RPC_PROTO_PATCH_VERSION");
```

**La patch originale non lo tocca.** Portava `GGML_OP_COUNT` da 100 a 102
lasciando lì un `== 100`: sul suo stesso albero, con `GGML_RPC=ON`, **non
avrebbe compilato**. Non è emerso perché `git apply --check` non compila e
perché in questo build `GGML_RPC:BOOL=OFF` (`build/CMakeCache.txt:776`), quindi
l'header non viene mai incluso.

Ho allineato a `== 105` e bumpato `RPC_PROTO_PATCH_VERSION` a **4**, che è
esattamente ciò che avevano fatto le due porte precedenti su questo stesso
albero (`patch_fusioni.diff` 98→101 con patch 2→3, `patch_sinkhorn.diff`
100→103 con patch 2→3). **Effetto sul binario di oggi: zero** (RPC spento).
È l'unica riga che ho scritto senza un mandato diretto dalla patch: se preferisci
un albero fedele alla lettera, questo è il file da revertire — ma allora resta
una mina per chiunque accenda RPC.

Controllato che non ci siano altre tabelle da estendere: gli unici array
`[GGML_OP_COUNT]` sono i due di `ggml.c` (fatti) e `fuse_cnt[GGML_OP_COUNT]` in
`ggml-metal-context.m`, che si dimensiona da solo e non è compilato qui.

---

## 4. `git diff --numstat`, commentato file per file

Sono **identici alla patch originale su tutti e 13 i file**. Il
quattordicesimo è mio.

```
2	2	ggml/include/ggml-rpc.h          <-- NON nella patch: vedi §3
32	0	ggml/include/ggml.h
3	1	ggml/src/ggml-cpu/ggml-cpu.cpp
146	0	ggml/src/ggml-cuda/cache-esperti.cu
26	0	ggml/src/ggml-cuda/cache-esperti.cuh
37	0	ggml/src/ggml-cuda/ggml-cuda.cu
66	2	ggml/src/ggml.c
14	0	include/llama.h
48	0	src/llama-context.cpp
10	0	src/llama-context.h
6	0	src/llama-cparams.h
67	0	src/llama-graph.cpp
31	0	src/llama-graph.h
26	0	tools/server/server-context.cpp
```

| file | +/− | cosa c'è dentro |
|---|---|---|
| `ggml-rpc.h` | 2/2 | §3: assert 103→105, PATCH_VERSION 3→4. Non compilato (RPC off) |
| `ggml.h` | 32/0 | 2 enumeratori in coda + 2 dichiarazioni `GGML_API` + commenti di contratto |
| `ggml-cpu.cpp` | 3/1 | i 2 op aggiunti alla lista di rifiuto della CPU (la `-1` è la riga `DSV4_KV_RING)` che diventa `||`) |
| `cache-esperti.cu` | 146/0 | `kern_acceptmoe` + lanciatore + `cudaMalloc/Memset/Free` di `am_cont[8]` + riga di dump |
| `cache-esperti.cuh` | 26/0 | campo `am_cont` nella struct + contratto del lanciatore |
| `ggml-cuda.cu` | 37/0 | 2 `case` nel dispatch + 2 in `supports_op` (accettazione esplicita CUDA-only) |
| `ggml.c` | 66/2 | §2 conflitto 4: 2 nomi + 2 simboli + 2 costruttori; le `-2` sono i due `static_assert` riscritti |
| `llama.h` | 14/0 | API `llama_acceptmoe_arma` + l'avvertenza «CAMBIA L'USCITA» |
| `llama-context.cpp` | 48/0 | aggancio di `cparams.acceptmoe_stato`, consumo one-shot dell'arm, pubblicazione dello stato per ubatch, le 2 funzioni dell'API |
| `llama-context.h` | 10/0 | `acceptmoe_armato = -1`, `acceptmoe_stato_host[4]`, dichiarazione del metodo |
| `llama-cparams.h` | 6/0 | il puntatore `acceptmoe_stato` |
| `llama-graph.cpp` | 67/0 | `set_input` dell'input nuovo + il blocco d'inserzione in `build_moe_ffn` |
| `llama-graph.h` | 31/0 | classe `llm_graph_input_acceptmoe` + `t_acceptmoe_stato` mutable |
| `server-context.cpp` | 26/0 | l'arm prima di `llama_decode`, con la guardia `!slot.spec_replay` |

**Fine riga: tutti e 14 i file sono LF puro**, verificato byte per byte
(scansione diretta, non `git diff`). Nessun numero gonfiato.

---

## 5. Quello che NON mi torna — e che ho trovato per strada

### 5a. Due file erano GIÀ CRLF nel tuo albero, e `git status` non lo diceva

All'inizio della sessione, **prima di toccare qualsiasi cosa**:

```
ggml/src/ggml-cpu/ggml-cpu.cpp    worktree: LF=0 CRLF=713    blob HEAD: LF=713 CRLF=0
include/llama.h                   worktree: LF=0 CRLF=1614   blob HEAD: LF=1614 CRLF=0
```

…eppure `git status --short` e `git diff --stat` li davano **puliti**. La cache
di stat dell'index li stava nascondendo: `git update-index --really-refresh` li
ha fatti emergere subito.

**Non sono stato io**: l'esperimento in isolamento (§2) prova che `git apply`
*rifiuta* un hunk CRLF su un file LF. Quelle due sezioni della patch sono CRLF e
sono passate ⇒ i file erano già CRLF sul disco. Erano l'unico motivo per cui
quei due file non comparivano fra i conflitti.

Li ho **normalizzati a LF**, che è la convenzione dell'albero (`core.autocrlf
false`, nessun `.gitattributes`, blob HEAD tutti LF). Senza questo,
`git diff --numstat` diceva `715/713` e `1628/1614` invece di `3/1` e `14/0` —
la nottata di cui parlavi. È una correzione a danno preesistente, non alla
patch: **dillo pure che l'ho fatta**, perché tocca due file oltre le mie righe.

`ggml/src/ggml-cuda/CMakeLists.txt` risulta `M` in `git status` ma ha diff
vuoto: è solo stat-dirty (mtime di un build). Non l'ho toccato.

### 5b. La riga di dump esce ANCHE a leva spenta — `ACCEPTMOE.md` §C0 va corretto

La guardia della riga nuova nel dump è `if (runtime->cache.am_cont)`, e
`am_cont` viene allocato **incondizionatamente** in
`ggml_cuda_cache_esperti_init`. Quindi con cache esperti attiva e **tutte le
leve spente** il dump stampa comunque:

```
cache-esperti: acceptmoe -> lanci=0, righe mascherate=0, esperti scartati=0, ...
```

`audit/ACCEPTMOE.md` §"Il cancello" scrive per C0 «nessuna riga nuova nel log».
**È sbagliato, e va corretto lì**: se domani leggi quella riga e la chiami
fallimento di C0, fermi la campagna per niente. Il criterio giusto è: riga
presente, **tutti gli otto contatori a zero**.

### 5c. Cosa cambia sul cammino normale a leve spente (l'elenco onesto)

Hai chiesto di dirlo anche se è un dettaglio. Con nessuna delle quattro leve
impostata, **niente cambia numericamente** — nessun nodo nel grafo, nessun
kernel lanciato, nessuna riordinata di operazioni esistenti (tutti i blocchi
nuovi sono *inseriti fra* statement, non spostano nulla). Ma queste tre cose
non sono a costo zero assoluto:

1. **64 byte di VRAM allocati sempre.** `cudaMalloc(&am_cont, 8*sizeof(uint64_t))`
   + `cudaMemset` in `init`, `cudaFree` in `free`, incondizionati. Una
   `cudaMalloc` in più sposta gli indirizzi delle allocazioni successive.
   Numericamente irrilevante, ma su questa macchina la VRAM libera è una
   scogliera nota (muro ~540 MiB): 64 byte non la muovono, però **non è "zero"**.
2. **Una `cudaMemcpy` D2H di 64 byte + una `fprintf` a ogni dump** (§5b).
   Fuori dal cammino di decode.
3. **Due confronti interi in più** in `ggml_backend_cpu_device_supports_op` per
   ogni op che non è una delle cinque della lista, e **due `int32_t` scritti per
   ubatch** in `llama_context::decode` (`acceptmoe_stato_host[0..1] = 0`).
   Rumore sotto il pavimento di misura.

Nessuna di queste tocca un tensore. **Il cancello SHA deve reggere.** Se non
regge, il colpevole non è in questa lista e va cercato: è un difetto, non un
dettaglio.

### 5d. Un punto da tenere d'occhio quando la leva sarà accesa

`llama_context::decode` legge `ubatch.seq_id[i][0]` nel test di sequenza
singola. Ci arriva **solo** se `acceptmoe_spec > 0`, cioè solo dopo un arm del
server, che a sua volta arma solo su viste di slot generanti. Non l'ho
verificato eseguendo: se a C2 comparisse un crash lì, è quello.

---

## 6. La sequenza di cancelli per domani

Base di riferimento **nuova** (post-fusione HC): SHA `CF2DEEA06E90`,
**12,83-12,92 t/s**. Attenzione: `ACCEPTMOE.md` cita ancora
`B396AB2137B2080A` / 10,40-10,47 — è la base *pre*-fusione, morta.

Invariante di ogni corsa con cancello SHA: `LLAMA_SPEC_DRAFT_TOPK=1`
(senza, la bozza estrae a sorte fra i primi dieci e lo SHA non è riproducibile).

Fermarsi al primo che fallisce.

| # | configurazione | cosa deve uscire | cosa falsifica |
|---|---|---|---|
| **C0** | binario nuovo, **nessuna env ACCEPTMOE**. Configurazione dello SHA. n=3 | **SHA `CF2DEEA06E90`**, 12,83-12,92 t/s. Dump: la riga `acceptmoe` c'è ma **tutti i contatori a 0** (§5b) | SHA diverso ⇒ la patch tocca qualcosa che dichiara di non toccare. Fermare tutto |
| **C1a** | `LLAMA_ACCEPTMOE=1`, **spec OFF**, `K=0` | **stesso SHA**. Dump: `lanci>0`, `righe mascherate=0` | le op sono nel grafo e girano in modalità identità: se lo SHA si muove qui, il kernel non è una copia esatta |
| **C1b** | `LLAMA_ACCEPTMOE=1`, **spec ON** (n-max 1), **`LLAMA_ACCEPTMOE_ESATTE=99`** | **stesso SHA `CF2DEEA06E90`**. Dump: `lanci>0`, `righe mascherate=0`, `righe senza residenti=0` | **è il cancello che separa «il codice nuovo gira» da «il codice nuovo cambia il risultato»**: arm, input, kernel, tutto acceso, ma `n_esatte=99 > n_tok` ⇒ nessuna riga è candidata. Se qui lo SHA diverge, il difetto è nel plumbing, non nella maschera. Accendere anche `LLAMA_OVERLAP_VERIFICA=1` |
| **C2** | n-max 1, `ACCEPTMOE=1`, `ESATTE=1`, `SOGLIA=0` | **SHA DIVERGE per costruzione.** Misure: p1, mean_len, t/s, e dal dump `righe mascherate` ≈ cicli armati, `esperti scartati`/riga ~2,5-3 | non-regressione: t/s sotto ~12,6 (banda attesa −0,5%…+2,5%) chiude la via a n-max 1. Guardia: un braccio a solo prompt lungo deve dare `righe mascherate=0` — il prefill non si maschera mai |
| **C3** | **n-max 2**, `ACCEPTMOE=1`, **e `LLAMA_OVERLAP_BATCH_MAX=3`** | **IL test.** Confronto contro **12,83-12,92**, non contro 10,01. Break-even: `1+p1'+p1'·p2' ≥ 12,83 × ciclo/1000`; a ciclo ~178 ms serve **p2' ≥ 0,45-0,60** | p2' mascherato < 0,45 **oppure** testo degradato a occhio ⇒ via chiusa. Margine misurato pulito: p2 = 0,706-0,755 (audit 32), quindi 0,15-0,35 di degrado concesso |
| **C4** | spazzata `SOGLIA` {0; 0,3; 0,5} × `K` {1; 2} sul vincitore di C3 | la frontiera p1 ↔ trasporto | — |

Due trappole da non ripetere, entrambe già pagate:

- **`LLAMA_OVERLAP_BATCH_MAX` a C3.** Il difetto è 1: con n-max 2 il batch di
  verifica ha 3 token, sfonda il cancello e **il ramo CPU muore in silenzio**
  (+50% domande per posizione). È l'errore di `campagna3.ps1:92`. Va messo a
  `n-max + 1` = 3.
- **Mai leggere la *percentuale* di colpi a leva accesa.** I duplicati residenti
  contano come colpi e la gonfiano. La metrica sono i **buchi ASSOLUTI per
  token** dal dump.

`LLAMA_ACCEPTMOE_BATCH_MAX` non serve toccarlo: difetto 8, e `TOK_MAX` del
kernel è 32, quindi l'abort del lanciatore non può scattare né a n-max 2 né a
n-max 5.

---

## Cosa resta aperto

1. La riga di C0 in `audit/ACCEPTMOE.md` §"Il cancello" è da correggere (§5b).
2. `ggml-rpc.h` è mio, non della patch (§3): revertibile in due righe se vuoi
   l'albero fedele alla lettera.
3. Il rilevatore di replay stantio **non copre le due op nuove** (debito già
   dichiarato in `ACCEPTMOE.md` §"Cosa NON risolve" punto 6): sorveglia la
   partizione adiacente, che gira con lo stesso `n_tok`.
4. Niente di tutto questo è compilato. Il primo fatto nuovo arriva da C0.
