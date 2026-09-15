# P11 cella 2 · le tre maschere del prefill a 131k: che cosa sono davvero, e perché toglierle dal picco non basta — 15 settembre 2026

Cella dell'apertura **A1** di P11: *togliere il muro di VRAM del batch nel prefill a 131k
non materializzando le maschere dense quando la sparse FA è accesa*, per portare il
prefill oltre i 400 t/s. Punto operativo dell'utente: prompt freddo di 131.072 token,
KV 250k (contesto 262.144), MTP spento, 64 slot, greedy, `-np 1`.

**Risposta breve: A1 è falsificata — e il muro del batch si toglie lo stesso, per un'altra
strada. Il prefill a 131k passa da 376,4 (W4) a 396,99 t/s, cioè lo 0,75% sotto i 400.**

---

## 0. In dieci righe

1. **Le «tre maschere F32 `[n_kv, n_batch]`» esistono, ma non sono quelle indicate in
   P11.** Non stanno nell'attenzione (`build_attn_qsa`) — lì le maschere sono **F16 e
   sono due**, perché il `set_rows` restituisce una *vista* e non alloca. Le tre F32 vere
   stanno nell'**indicizzatore** (`build_qsa_top_k`). Misurate nodo per nodo, non dedotte.
2. Per ciascuno dei 12 strati QSA il grafo di prefill riservato contiene **7 tensori di
   taglia `n_kv × n_batch`**, per **20,17 byte a coppia token×cella**; il totale su 12
   strati è **242,00 B/coppia** (84 nodi). Il termine `T·K` della riserva ne vale ~12-13.
3. A 131k, con `n_kv` 147.456 e ubatch 3072, **una** di quelle maschere pesa **1728 MiB**
   (2304 a ubatch 4096). La somma dei 7 nodi di un solo strato è 8640 MiB.
4. **La correzione A1 è stata scritta e misurata: non paga.** Calcolare la selezione
   top-k a fette di 512 token invece che su tutti e 3072 lascia la riserva dov'era
   (**+4,2%**, non −60%) e costa **il 9%** di velocità. A batch 4096 peggiora il crollo
   di W2. **Spenta di default.**
5. **Serviva una cella di controllo e adesso c'è**: X0 = W4 esatta sui binari nuovi,
   **383,315 t/s** contro i 376,351 di W4 sui binari congelati, workspace **identica**
   (6819,42 MiB) e **impronta identica**. Il +1,85% è della build, non di una leva.
6. **Il muro del batch non è la somma dei byte: è il picco**, e il picco non scende
   spezzando quei tensori lungo l'asse dei token.
7. La strada che paga è l'altra metà dell'apertura: **tenere acceso lo staging degli
   esperti fino in fondo**, restringendo l'ubatch in profondità quanto basta a lasciargli
   1,4 GiB liberi. Con la scaletta ricalcolata (X3): **workspace da 6819 a 4659 MiB
   (−31,7%), VRAM libera da 400 a 1656 MiB, staging acceso in 50 blocchi su 50**, e il
   testo **identico** a W4.
8. **Il numero che vale di più non è nel grafo: è `-b`.** Con `-b 12288`, che si divide
   esattamente per 4096, 3072 e 2048, spariscono gli ubatch spaiati e si passa da 389,3 a
   **396,99 t/s** (X4). Un solo argomento, +1,98%.
9. **Un gradino da 6144 in cima non paga** (X5, 387,1): porta la workspace della fascia
   successiva a 5614 MiB e spegne lo staging in 13 blocchi su 38. L'ottimo della scaletta
   è stretto e va rispettato **in ogni fascia**, non in media.
10. Verdetto contro 400 in §8.

---

## 1. Cancello di partenza e stato dei processi

Guardia prima di ogni avvio e prima di ogni build: `netstat -ano | findstr LISTENING |
findstr :8100` vuoto e `tasklist | findstr llama-server` vuoto. **Nessun server non mio è
stato trovato.** Un solo `llama-server` alla volta; `avvia_blocco.ps1` rifiuta l'avvio se
la porta è occupata, se esiste già un `llama-server` o se è in corso una compilazione, e
non termina mai un processo che non ha creato lui.

Non sono stati toccati: `qwen38_clean\bin_prod`, `qwen38_clean\source`,
`qwen38_clean\build\bin`, il lanciatore quotidiano, i modelli, gli snapshot, l'albero P8.
Si è lavorato solo in `D:\ds4_work\p11_work\source` con build in
`D:\ds4_work\p11_work\build`. **Nessun commit.**

---

## 2. Diagnosi: chi alloca che cosa, con file e riga

### 2.1 Il metodo (perché non è una deduzione)

Il modello di costo di P11 (`workspace ≈ cost(T) + 1,1·10⁻⁵·T·K`, cioè ~12 byte per
coppia token×cella) è **giusto nel numero e sbagliato nell'attribuzione**. Per non
ripetere l'errore si è aggiunta una diagnostica che **elenca i nodi del grafo riservato**:
`QWEN_WS_DUMP=N`, in `src/llama-context.cpp` dentro `sched_reserve`, subito dopo la
riserva del grafo di prefill. Stampa i primi N nodi per taglia e **tutti** i nodi il cui
`ne[0]` o `ne[1]` vale `n_kv`, con i byte per coppia. Spenta di default.

*(Nota di metodo: `ggml-alloc.c` ha già una diagnostica del picco — `GGML_ALLOCATOR_DEBUG`
— ma stampa a livello **DEBUG**, e il log del server con `-lv 4` contiene solo righe `I`:
quella diagnostica, accesa, non produce una sola riga. Provato e verificato. Per usarla
servirebbe anche portarla a INFO.)*

### 2.2 Che cosa dice la misura (cella X0, riserva `tokens=3072 kv=16384`)

I sette tensori di taglia `n_kv × n_batch`, per **ciascuno** dei 12 strati QSA. *(I numeri
di riga sono quelli dell'albero **dopo `p11.patch` e prima di `p11_cella2.patch`**, cioè
lo stato su cui la diagnosi è stata fatta.)*

| # | nodo | tipo | forma | B/coppia | dove nasce |
|---|---|---|---|---:|---|
| 1 | `GET_ROWS` | f32 | `[n_batch, n_kv]` | 4,00 | `src/models/qwen4exp.cpp:1056` — espansione del punteggio dai blocchi alle celle |
| 2 | `CONT` «(permuted) (cont)» | f32 | `[n_kv, n_batch]` | 4,00 | `qwen4exp.cpp:1058` — la trasposta che rimette le celle su `ne0` |
| 3 | `CPY` «attn_inp_kq_mask (copy)» | f32 | `[n_kv, n_batch]` | 4,00 | `qwen4exp.cpp:1062` — `ggml_cast` della maschera causale **da F16 a F32** |
| 4 | `ADD` «indexer_score_tokens-il» | f32 | `[n_kv, n_batch]` | 4,00 | `qwen4exp.cpp:1063` — punteggio + maschera |
| 5 | `FILL` | f16 | `[n_kv, n_batch]` | 2,00 | `qwen4exp.cpp:1225` — `kq_mask_all` riempita di −∞ |
| 6 | `ADD` | f16 | `[n_kv, n_batch]` | 2,00 | `qwen4exp.cpp:1248` — somma con `kq_mask` dopo il `set_rows` |
| 7 | (minore) | — | — | 0,17 | — |
| | **per strato** | | | **20,17** | |
| | **totale, 12 strati, 84 nodi** | | | **242,00** | riga `ws_kv TOTALE 84 nodi, 11616,00 MiB` a kv 16384 |

Il numero 242,00 B/coppia è **identico** a tutte le profondità misurate (16384, 32768,
49152, 65536, 81920): la struttura non cambia, cambia solo la taglia.

**Tre correzioni al documento di P11:**

- le tre maschere che P11 indica (`kq_mask_all`, il `set_rows` del top-k, la somma con
  `kq_mask`) sono **F16, non F32**, e sono **due allocazioni, non tre**: `ggml_set_rows`
  restituisce `ggml_view_tensor(a)`, cioè una vista di `kq_mask_all`, e una vista non
  alloca niente. In tutto valgono **4 B/coppia**, non 12;
- le **tre F32** vere stanno nell'**indicizzatore**: l'espansione blocchi→celle
  (`GET_ROWS` + `CONT`), la **copia F32 della maschera causale** e la loro somma. È da lì
  che escono i 12 byte a coppia del modello di costo;
- il `ggml_cast` della riga 1062 esiste **perché la flash attention tiene la maschera in
  F16 mentre i punteggi dell'indicizzatore sono F32**. È una conversione di una maschera
  intera per strato: **12 conversioni da `n_kv × n_batch` per ogni ubatch**, cioè a 131k
  con ubatch 3072 circa 12 × 2,6 GB di traffico per blocco di prompt.

### 2.3 Le taglie esatte al punto operativo

Alla riserva più profonda (`n_kv` = 147.456 = `GGML_PAD(131k + coda, 16384)`):

| | ubatch 3072 | ubatch 4096 |
|---|---:|---:|
| una maschera F32 `[n_kv, n_batch]` | **1728,0 MiB** | **2304,0 MiB** |
| una maschera F16 | 864,0 MiB | 1152,0 MiB |
| somma dei 7 nodi di **uno** strato | 8640 MiB | 11.520 MiB |
| somma su 12 strati | 103.680 MiB | 138.240 MiB |
| **termine `T·K` della riserva, misurato** | **~5070 MiB** | **~6510 MiB** |
| riserva totale misurata | 6819 MiB | 8943 MiB |

La somma è **venti volte** il termine che compare nella riserva: l'allocatore riusa, e il
termine `T·K` è il **picco**, cioè quanti di quei tensori sono vivi nello stesso istante —
circa tre F32. Pendenze misurate: **11,49 / 13,19 / 12,70 B/coppia** per ubatch 2048 /
3072 / 4096.

### 2.4 La sparse FA consuma ancora la maschera: non si può semplicemente non costruirla

L'apertura A1 proponeva di «passare `top_k` al backend invece delle tre maschere». Il
codice dice che oggi non è possibile senza toccare il kernel:

- `ggml_cuda_flash_attn_ext_compact_mask` (`ggml/src/ggml-cuda/fattn.cu:92`) **legge la
  maschera F16** e ne ricava l'elenco degli indici con
  `flash_attn_mask_to_sparse_indices` (`fattn.cu:10`): scandisce la riga e tiene le celle
  con valore finito. La sparse FA non salta la maschera: la *comprime*, e la compressione
  parte dalla maschera materializzata;
- gli indici che il kernel vuole sono **in ordine crescente di cella** e **già filtrati
  dalla causalità**; `ggml_top_k` li produce in ordine di punteggio e **senza** quel
  filtro (le celle invisibili hanno punteggio −∞ e vengono scelte lo stesso quando le
  celle visibili sono meno di `width`, cioè per tutti i token con posizione < 2051).
  Passare `top_k` direttamente cambierebbe l'insieme e l'ordine, quindi l'aritmetica.

Quindi «non costruirla» richiede un kernel nuovo, non una modifica di grafo. Resta la
terza strada indicata nel mandato: **costruirla a pezzi**, che è quella provata qui.

---

## 3. La correzione A1: costruire la selezione a fette di token

### 3.1 L'idea, e perché è lossless per costruzione

Ogni **riga di token** dell'indicizzatore è indipendente da tutte le altre: l'espansione
blocchi→celle è un `get_rows` per colonna, la somma con la maschera è elemento per
elemento, il top-k lavora per riga (`ggml_cuda_op_top_k` chiama `top_k_cub` **una riga
alla volta**, `ggml/src/ggml-cuda/top-k.cu:232`). Quindi la stessa selezione si può
calcolare su fette di `n_chunk` token una dopo l'altra: gli stessi kernel, sugli stessi
byte, e il picco dell'allocatore passa da `12·n_kv·n_tps` a `12·n_kv·n_chunk`.

`p11_cella2.patch` introduce:

- **`QWEN4EXP_QSA_TOPK_CHUNK`** = token per fetta (0 = spenta) in `build_qsa_top_k`. La
  fetta del punteggio e la fetta della maschera sono **viste contigue** (entrambi i
  tensori sono contigui e si taglia lungo `ne1`), quindi nessuna copia in più;
- **`QWEN4EXP_QSA_MASK_INPLACE`** = la somma `kq_mask_top_k + kq_mask` di
  `build_attn_qsa` diventa `ggml_add_inplace`: `kq_mask_all` è già un tensore nostro
  (`ggml_fill` lo duplica), quindi scrivere dentro toglie la seconda maschera F16 senza
  cambiare un valore;
- dentro la fetta, anche la somma `punteggio + maschera` è in posto.

Entrambe **spente di default** dopo la misura (erano accese con la sparse FA nel primo
progetto). Con le due variabili a 0 il binario riproduce W4 riga per riga — ed è quello
che la cella X0 verifica: **stessa workspace, stessa impronta**.

### 3.2 Il ramo si accende davvero (controllo, non fiducia)

Il conteggio dei nodi del grafo di prefill lo dice senza ambiguità:

| | nodi a `bs=3072` |
|---|---:|
| A1 spenta (X0, W4, W5) | **8131** |
| A1 accesa (X1) | **8935** |

+804 nodi = **+67 per ciascuno dei 12 strati QSA**, esattamente quanti ne aggiungono sei
fette da 512 token al posto di una da 3072. Il ramo non è codice morto.

### 3.3 Il risultato: il picco non si muove

| | X0 (A1 spenta) | X1 (A1 accesa) | differenza |
|---|---:|---:|---:|
| prefill integrale | **383,315 t/s** | **348,699 t/s** | **−9,03%** |
| tempo del prompt | 342,2 s | 376,2 s | +9,9% |
| workspace max | **6819,42 MiB** | **7107,42 MiB** | **+4,2%** |
| VRAM libera min (prefill) | 400 MiB | 341 MiB | −59 |
| RAM libera min | 6,10 GB | 5,81 GB | −0,29 |
| impronta | `d77a042a3e08` | `c186b3b753c6` | cambia |

Serie della riserva, stessi punti di profondità:

| kv | X0 | X1 | Δ |
|---:|---:|---:|---:|
| 16384 | 1749,42 | 1797,42 | +48 |
| 32768 | 2163,42 | 2387,42 | +224 |
| 49152 | 2787,42 | 2979,42 | +192 |
| 65536 | 3507,42 | 3699,42 | +192 |
| 81920 | 4083,42 | 4403,42 | +320 |
| 98304 | 4659,42 | 5043,42 | +384 |
| 114688 | 5571,42 | 5683,42 | +112 |
| 131072 | 6195,42 | 6451,42 | +256 |
| 147456 | **6819,42** | **7107,42** | **+288** |

La pendenza passa da **13,19** a **13,81** B/coppia: la fetta non ha tolto niente al
termine `T·K`, e ha aggiunto i tensori della catena di `ggml_concat` (la coppia più grande
vale ~48 MiB, che è esattamente il Δ a kv 16384).

### 3.4 Perché non funziona — la lettura

La somma dei byte scende (per strato si passa da ~12 B/coppia vivi a ~2), ma **la riserva
è il picco dell'allocatore sul grafo dopo lo split, non la somma**, e quel picco non è
fissato dalle tre F32 di *uno* strato: se lo fosse, spezzarle lungo i token lo avrebbe
diviso per sei. La misura dice che non lo fa. Restano due spiegazioni compatibili con i
dati raccolti, e **nessuna delle due è stata verificata** (vedi §9, difetto 1):

- il picco cade in un punto del grafo dove sono vivi insieme tensori `n_kv × n_batch` di
  **più strati** (per esempio le maschere F16, che la fetta non tocca), oppure
- la frammentazione dell'arena: 72 allocazioni piccole per strato al posto di 12 grandi
  non permettono all'allocatore di riempire gli stessi buchi (il +4,2% di riserva a parità
  di byte vivi è coerente con questa lettura).

Il costo in tempo (−9%) è invece leggibile subito: 804 nodi in più per ubatch, cioè 804
lanci di kernel in più ogni 3072 token, su kernel che diventano sei volte più piccoli e
perdono occupazione.

**Conseguenza per il mandato: la terza strada di A1 («costruite per blocco invece che
intere») è provata e falsificata sul lato dei token.** Le altre due (non costruirle: serve
un kernel nuovo, §2.4; compattarle a blocchi di KV: il top-k è globale sulla riga, non si
spezza lungo le celle senza cambiare la selezione) restano non percorribili senza toccare
i kernel.

---

## 4. Le celle

Profilo `prefill_131k`: una sola richiesta, prefisso `ctx131k` freddo (`cache_prompt=false`,
`cache_n=0`), risposta di 64 token al massimo. Il prefill t/s è **integrale**
(`prompt_n / prompt_ms` del server: tutto il prompt, non il picco dei primi blocchi).
Tutte e quattro le celle girano sugli **stessi binari ricompilati**; W4 è riportata solo
come riferimento storico (binari congelati).

| cella | che cosa aggiunge a W4 | prefill t/s | tempo prompt | workspace max | VRAM libera min | RAM libera min | impronta | esito |
|---|---|---:|---:|---:|---:|---:|---|---|
| W4 (rif., binari congelati) | — | 376,351 | 348,53 s | 6819,42 | 400 MiB | 6,17 GB | `d77a042a3e08` | riferimento di P11 |
| **X0** (controllo) | niente: A1 dichiarata spenta | **383,315** | 342,20 s | **6819,42** | 400 MiB | 6,10 GB | `d77a042a3e08` | **+1,85% sulla sola build** |
| **X1** | A1 (fetta 512) a batch 3072 | **348,699** | 376,17 s | 7107,42 | 341 MiB | 5,81 GB | `c186b3b753c6` | **−9,03%**: esce |
| **X2** | A1 (fetta 512) a batch 4096 | **219,570** | 597,39 s | **9086,56** | 297 MiB | **3,44 GB** | `9b331a1bb1a4` | **−42,7%**: paginazione, esce |
| **X3** | scaletta dell'ubatch per lo staging (A1 spenta) | **389,267** | 336,97 s | **4659,42** | **1656 MiB** | 6,45 GB | `d77a042a3e08` | **+1,55%** su X0, testo identico |
| **X4** | X3 con `-b 12288`, divisibile per ogni gradino | **396,987** | 330,41 s | **4659,42** | 1649 MiB | 6,43 GB | `58f84ab53ce2` | **+3,57%** su X0 |
| **X5** | X4 con un gradino da 6144 in cima | **387,122** | 338,83 s | 5700,84 | 1511 MiB | 6,48 GB | `d77a042a3e08` | −2,5% su X4: esce |

Staging degli esperti, contato sul log (`qwen_prefetch: staged …` contro
`qwen_prefetch: skipped, insufficient free VRAM`):

| cella | blocchi con staging | blocchi saltati | dove salta |
|---|---:|---:|---|
| W4 | 31 | 13 | ultimi 13 su 44 |
| X0 | 31 | 13 | ultimi 13 su 44 |
| X1 | 27 | 17 | ultimi 17 su 44 |
| X2 | 15 | 18 | da kv ≈ 82k in poi |
| **X3** | **50** | **0** | — |
| **X4** | **46** | **0** | — |
| X5 | 25 | 13 | nella fascia a 4096 (ws 5614 MiB) |

Due letture immediate:

- **X0 è il controllo che mancava.** Stessa workspace al byte (6819,42) e stessa impronta
  di W4: la differenza di velocità (+1,85%) è tutta della macchina dopo una build
  (regola dell'8/9), non di una leva. Tutti i confronti di questa cella sono quindi
  contro **383,315**, non contro 376,351.
- **X2 riproduce il muro di W2 e lo peggiora.** La workspace arriva a **9086,56 MiB**
  contro i 8942,56 di W2 (+144), la VRAM libera scende a 297 MiB e la RAM di sistema a
  **3,44 GB**, sotto la soglia R-RAM di 4 GB: è paginazione WDDM. I due tratti finali
  costano 153,8 s e 174,0 s contro i 59,9 e 53,1 di X0. X2 è più veloce di W2 (219,6
  contro 175,1) solo perché ha anche GDN a tile e staging, che W2 non aveva.

Cadenza per tratto di KV (secondi fra due riserve consecutive della workspace):

| tratto di KV | X0 (3072) | X1 (3072 + A1) | X2 (4096 + A1) |
|---|---:|---:|---:|
| 16k → 32k | 28,6 | 28,8 | **22,2** |
| 32k → 49k | 31,4 | 31,8 | 31,8 |
| 49k → 66k | 33,6 | 34,3 | 34,7 |
| 66k → 82k | 43,3 | 44,3 | 37,5 |
| 82k → 98k | 38,5 | 39,6 | 46,1 |
| 98k → 115k | 40,7 | 47,3 | 48,7 |
| 115k → 131k | 59,9 | 61,8 | **153,8** |
| 131k → 147k | 53,1 | 54,9 | **174,0** |

Il batch 4096 **vince davvero finché c'è VRAM** (−22% nel primo tratto, −13% nel tratto
66k→82k) e perde tutto dopo: è la stessa firma di W2, spostata un po' più in là dallo
staging. Conferma il punto del documento di P11: *il muro è di memoria, non di aritmetica*.
Ma conferma anche che **A1 non sposta quel muro**.

---

## 5. X3 — l'altra metà dell'apertura: la scaletta calcolata sullo staging

Se la workspace non si può togliere, la si può **spendere dove serve**. P11 §7.3 lo dice
già: la scaletta di W5 era stata calcolata sul tetto della VRAM e non sul **fabbisogno
dello staging**, ed è quello che le è costato il guadagno. Qui la si è ricalcolata.

### 5.1 Il conto, fatto prima della corsa

Dal modello tarato sulle riserve misurate (`ws ≈ const(T) + pendenza(T)·K`, MiB):

| ubatch | const | pendenza (MiB/cella) |
|---:|---:|---:|
| 2048 | 1098 | 0,02245 |
| 3072 | 1115 | 0,03868 |
| 4096 | 1619 | 0,04967 |

In X0, con workspace 6819 MiB la VRAM libera è 400: il tetto «workspace + libera» vale
**~7220 MiB**. Lo staging pretende due buffer da ~450 MiB più 512 di riserva, cioè
**~1,4 GiB liberi**: serve `ws ≤ ~5800 MiB` a ogni profondità. Da qui la scaletta

```
-b 4096 -ub 4096   QWEN_PREFILL_UBATCH_DEEP="81920:3072,114688:2048"
```

cioè 4096 fino alla riserva a kv 65536, 3072 a 81920 e 98304, 2048 da 114688 in poi.

### 5.2 Che cosa è successo

| | X0 | X3 |
|---|---:|---:|
| prefill integrale | 383,315 t/s | **389,267 t/s** |
| tempo del prompt | 342,20 s | **336,97 s** |
| **workspace max** | 6819,42 MiB | **4659,42 MiB (−31,7%)** |
| **VRAM libera min** | 400 MiB | **1656 MiB (4,1×)** |
| RAM libera min | 6,10 GB | 6,45 GB |
| **staging** | 31 blocchi su 44, **spento negli ultimi 13** | **50 su 50, mai spento** |
| impronta | `d77a042a3e08` | **`d77a042a3e08`** |

La serie della riserva mostra la leva che fa quello per cui è stata scritta — la
workspace **scende** due volte e non supera mai i 4660 MiB:

```
t=221,8s  ubatch 4096  kv 16384   ws 2432,56 MiB
t=243,8s  ubatch 4096  kv 32768   ws 2862,56       tratto 22,1 s   (X0 a 3072: 28,6)
t=275,2s  ubatch 4096  kv 49152   ws 3758,56       tratto 31,4     (X0: 31,4)
t=309,2s  ubatch 4096  kv 65536   ws 4526,56       tratto 34,0     (X0: 33,6)
t=345,7s  ubatch 3072  kv 81920   ws 4083,42  <-   tratto 36,6     (X0: 43,3)
t=390,7s  ubatch 3072  kv 98304   ws 4659,42       tratto 45,0     (X0: 38,5)
t=438,2s  ubatch 2048  kv 114688  ws 3640,28  <-   tratto 47,5     (X0: 40,7)
t=488,1s  ubatch 2048  kv 131072  ws 4024,28       tratto 49,8     (X0: 59,9)
t=543,4s  ubatch 2048  kv 147456  ws 4408,28       tratto 55,3     (X0: 53,1)
```

**Il testo non cambia**: `d77a042a3e08`, la stessa impronta di W4 e X0. È un risultato
in sé — la scaletta di W5 il testo lo cambiava (`9b331a1bb1a4`), questa no.

### 5.3 Perché il guadagno è solo +1,55%, e che cosa insegna

Lo staging acceso paga dove ci si aspettava (**115k→131k: −16,9%**, 49,8 s contro 59,9),
ma due cose se lo mangiano:

- **due tratti pagano uno split irregolare.** A ubatch 3072 il server manda blocchi da
  `-b 4096`, che la scaletta spezza in `3072 + 1024`: un ubatch pieno e uno lungo un
  terzo. I tratti 82k→98k e 98k→115k costano **45,0 e 47,5 s** contro i **38,5 e 40,7**
  che la cella X0 paga a 3072 con il batch giusto: **+17%, cioè 13,3 s su 337**. È un
  difetto della *configurazione*, non della leva (la cella X4 lo corregge con `-b 12288`,
  che si divide per 4096, 3072 e 2048);
- **l'ubatch piccolo costa traffico di esperti.** Nell'ultimo tratto X3 fa 55,3 s a
  ubatch 2048 **con** staging, contro i 53,1 di X0 a 3072 **senza**: a 2048 ci sono 8
  blocchi per tratto invece di 5,3, e ogni blocco trasferisce gli stessi 45,4 GiB di pesi
  degli esperti. Lo staging sovrappone quel traffico ma non lo toglie. È il conto che la
  scaletta deve fare e che finora nessuno aveva scritto: **restringere l'ubatch compra
  workspace e vende banda del bus**.

---

## 6. X4 e X5 — il blocco divisibile, e un gradino di troppo

### 6.1 X4: `-b 12288`

L'unica differenza con X3 è il **blocco** che il server manda: 12288 token invece di 4096.
12288 = 3×4096 = 4×3072 = 6×2048, quindi **ogni gradino della scaletta lo divide
esattamente** e non esistono più ubatch spaiati. `-ub` resta 4096: il grafo non cambia, e
infatti la **workspace è identica al byte** (4659,42 MiB) e la VRAM libera pure (1649
contro 1656).

| | X3 (`-b 4096`) | X4 (`-b 12288`) |
|---|---:|---:|
| prefill integrale | 389,267 t/s | **396,987 t/s** |
| tempo del prompt | 336,97 s | **330,41 s** |
| workspace max | 4659,42 MiB | 4659,42 MiB |
| VRAM libera min | 1656 MiB | 1649 MiB |
| staging | 50 blocchi su 50 | **46 su 46, mai spento** |
| impronta | `d77a042a3e08` | `58f84ab53ce2` |

**+1,98% per un solo numero**, e il numero non è nel grafo: è il taglio del blocco. Il
testo cambia perché cambia come il prompt viene diviso in ubatch (X3 e X5, che mandano
blocchi da 4096 e 12288 con ubatch che li dividono in modo diverso, tengono l'impronta di
W4; X4 no). È la stessa classe di differenza già documentata il 13/9: aritmetica
identica, raggruppamenti diversi, qualche pareggio fra logit che si ribalta.

### 6.2 X5: il gradino da 6144 non paga

Ipotesi: nella prima fascia il collo non è l'attenzione ma il **traffico degli esperti**,
che scala con il numero di **blocchi** (45,4 GiB per blocco, sempre gli stessi). Salendo
da 4096 a 6144 i blocchi per tratto passano da 4 a 2,67. Il conto della workspace dava
`ws(6144, 49152) ≈ 5500 MiB`, dentro il margine.

Misura: `ws(6144, 49152) = 5700,84 MiB` — e soprattutto **`ws(4096, 81920) = 5614,56`**,
che è oltre la soglia dello staging (il gradino a 4096 arriva più in profondità che in X4,
dove a 81920 si era già a 3072). Risultato: **13 blocchi su 38 senza staging** (25 con) e
**387,122 t/s, −2,5% su X4** — pur con la stessa impronta di W4 (`d77a042a3e08`). I primi due tratti confermano l'ipotesi (21,4 e 22,4 s
contro 22,1 e 23,4 di X4: il 6144 *è* leggermente più veloce), ma il gradino successivo
paga più di quanto il primo guadagni.

**Lettura**: la scaletta ha un ottimo stretto. Non basta stare sotto il tetto della VRAM
(errore di W5) né sopra il fabbisogno dello staging in *media*: va rispettato **in ogni
singola fascia**, e la fascia che conta è quella appena sotto il gradino, dove la
workspace è massima.

### 6.3 Cadenza delle tre celle con la scaletta

| tratto di KV | X0 (3072 fisso) | X3 | X4 | X5 |
|---|---:|---:|---:|---:|
| 16k → 32k | 28,6 | 22,1 | 22,1 | **21,4** |
| 32k → 49k | 31,4 | 31,4 | **23,4** | 22,4 |
| 49k → 66k | 33,6 | 34,0 | **24,9** | 27,5 |
| 66k → 82k | 43,3 | 36,6 | 53,7 | 53,7 |
| 82k → 98k | 38,5 | 45,0 | **30,3** | 33,5 |
| 98k → 115k | 40,7 | 47,5 | **31,7** | 31,7 |
| 115k → 131k | 59,9 | 49,8 | 73,7 | 78,1 |
| 131k → 147k | 53,1 | 55,3 | 55,3 | **48,7** |
| **somma** | **329,1** | **321,7** | **315,1** | **317,0** |
| **prompt intero** | **342,2** | **336,97** | **330,41** | **338,83** |

*I tratti non sono confrontabili uno a uno fra celle con `-b` diverso*: la riserva cade
dentro un blocco e sposta il confine (è il motivo dei 53,7 e 73,7 di X4 e X5, che sono
contabili, non fisici). La riga che conta è **il prompt intero**.

---

## 7. I cancelli sul candidato X4

### 7.1 Qualità: cinque aghi su cinque

Profilo `aghi_131k`, prefisso `aghi131k` (131.313 token, cinque fatti piantati al
5/25/50/75/95% dei caratteri), budget 768 token, greedy. Il primo caso paga il prefill
freddo, i cinque successivi riusano la cache del prompt.

| caso | profondità | stringa attesa | nella risposta finale | token generati | fine |
|---|---:|---|---|---:|---|
| `Q_AGO_05` | 5% | `MANDORLA-417` | **sì** | 104 | stop |
| `Q_AGO_25` | 25% | `VIOLA-CENERE` | **sì** | 114 | stop |
| `Q_AGO_50` | 50% | `Malinverni` | **sì** | 240 | stop |
| `Q_AGO_75` | 75% | `ZR-8842` | **sì** | 68 | stop |
| `Q_AGO_95` | 95% | `TRAMONTANA` | **sì** | 91 | stop |
| `Q_TEC` | — | `--moe-expert-cache` + `--moe-expert-cache-inserts` | **no**: entrambi i termini compaiono nel ragionamento, ma i 768 token finiscono lì dentro e la risposta finale resta vuota | 768 | length |

**5/5 sugli aghi: cancello superato**, come W4 e come il riferimento del 13/9. `Q_TEC`
resta **inconclusiva per budget**, esattamente come nelle due celle precedenti: è il
quarto giorno che consuma il budget nel ragionamento, e va portata a 3072 o tolta dal
profilo.

**Il prefill si conferma su un secondo prompt**: `Q_AGO_05@aghi131k`, 131.313 token,
**396,844 t/s** (contro i 396,987 del profilo di prefill: 0,04% di differenza). Stessa
workspace (4659,42 MiB) e stessa VRAM libera minima (1656 MiB).

### 7.2 Decode: non regredito

Profilo `lungo_131k` sul candidato X4, contro il riferimento V3 (P10 cella 3, media di due
repliche: **27,245 t/s**; cancello −3%, cioè 26,43).

| caso | decode t/s | contro 27,245 |
|---|---:|---:|
| `L01@ctx131k` (dopo prefill freddo) | **27,475** | **+0,84%** |
| `L02@ctx131k` (prompt in cache) | **27,057** | **−0,69%** |

**Cancello superato.** Entrambe le misure sono dentro il rumore del banco; la scaletta non
tocca il decode, che gira a 1-3 token e sta sotto ogni soglia della scaletta.

**E il prefill si conferma su un terzo prompt, che è lo stesso del riferimento P10**:

| prompt | token | prefill t/s | riferimento noto | delta |
|---|---:|---:|---:|---:|
| `PF_131K@ctx131k` | 131.170 | 396,987 | — (X0 = 383,315) | +3,57% |
| `Q_AGO_05@aghi131k` | 131.313 | 396,844 | — | — |
| `L01@ctx131k` | 131.248 | **392,064** | **252,157** (P10 V3, stesso caso) | **+55,5%** |

RAM libera minima sulle tre corse del candidato: **6,43 / 6,73 / 6,44 GB** (soglia R-RAM
4 GB), VRAM libera minima nel prefill **1649-1656 MiB**. Nessun NaN, nessun errore CUDA,
nessun `failed to allocate` nei log. Nessuna firma di paginazione: la RAM resta oltre 6 GB
e i tratti non hanno salti (in X2, che pagina, la RAM scende a 3,44 GB e i tratti passano
da 48 a 154-174 s). *La potenza della GPU non è campionata dalla sonda di carico: le
letture a 63-82 W durante X2 e a 103 W durante X4 vengono da `nvidia-smi` a mano e sono
indicative, non una misura del banco.*

---

## 8. Verdetto contro i 400

| | prefill t/s a 131k | contro 400 | contro il riferimento P10 (252,2) |
|---|---:|---:|---:|
| riferimento V3 (P10, 15/9) | 252,2 | −37,0% | — |
| W4 (candidato di P11) | 376,4 | −5,9% | +49,2% |
| X0 (W4 sui binari nuovi) | 383,3 | −4,2% | +52,0% |
| W5 (scaletta di P11) | 384,4 | −3,9% | +52,4% |
| X3 (scaletta per lo staging) | 389,3 | −2,7% | +54,4% |
| **X4 (X3 + `-b 12288`)** | **397,0** | **−0,75%** | **+57,4%** |
| X4 sul prefisso degli aghi | 396,8 | −0,79% | — |

**I 400 non sono raggiunti: manca lo 0,75%, cioè 2,5 secondi su 330.** Ma il fronte si è
mosso di **+5,5% su W4** e di **+3,6% sul controllo X0**, e i due cancelli tengono.

**Che cosa ha portato il guadagno, e che cosa no:**

- **non** la maschera densa. Era l'ipotesi numero uno del verdetto di P11 («il singolo
  intervento con il rapporto valore/rischio migliore»), è stata implementata nella sola
  forma possibile senza toccare i kernel, ed è **falsificata**: −9% a batch 3072, −43% a
  4096;
- **sì** lo staging tenuto acceso fino in fondo (P11 lo stimava «3-4% del prefill totale»;
  misurato **+1,55%** da solo, in X3, perché l'ubatch più piccolo che lo rende possibile
  si riprende una parte del guadagno in traffico di esperti);
- **sì**, e in modo sproporzionato, **un argomento della riga di comando**: `-b 12288` al
  posto di `-b 4096`, cioè un blocco che tutti i gradini della scaletta dividono
  esattamente. **+1,98%**, zero righe di codice, zero VRAM.

### 8.1 La configurazione, pronta per un preset di produzione

Binari: `D:\ds4_work\p11_work\build\bin` (P8 + P10c2 + P10c3 + `p11.patch` +
`p11_cella2.patch`). La sola patch che serve al candidato è **`p11.patch`** (la scaletta
dell'ubatch); `p11_cella2.patch` aggiunge solo leve spente e diagnostica.

Argomenti che cambiano rispetto al preset V3:

```
-b 12288 -ub 4096
```

Variabili d'ambiente che si aggiungono:

```
QWEN4EXP_SPARSE_FA=1
QWEN_GDN_TILED=1
QWEN_PREFETCH_EXPERTS=1
QWEN_PREFILL_UBATCH_DEEP=81920:3072,114688:2048
```

Tutto il resto è identico a `preset_V3_p10.json`; il preset completo è
`docs/porto/banco_p0/preset_X4_p11.json`. **La promozione nel lanciatore quotidiano resta
una decisione dell'utente**, e richiede i binari ricompilati (a differenza di W4, che
girava sui binari già presenti).

---

## 9. Difetti di questa cella

1. **Non si sa ancora *dove* cade il picco dell'allocatore.** La diagnosi elenca i
   tensori e le loro taglie (certo), ma non il momento in cui il massimo viene raggiunto
   né chi è vivo lì. Due tentativi, entrambi incompleti:
   `GGML_ALLOCATOR_DEBUG` in `ggml/src/ggml-alloc.c` stampa esattamente quello, ma a
   livello **DEBUG**, che il log del server (`-lv 4`) non contiene — acceso non produce
   una riga (provato; per usarlo va portato a INFO, e allora va anche messo dietro una
   variabile d'ambiente perché rallenta la riserva); il simulatore aggiunto a
   `sched_reserve` lavora sul grafo **prima** dello split ed è stato scritto ma non
   validato (la prima versione contava zero perché guardava `data`, che l'allocatore ha
   già riempito quando il dump gira). È la prima cosa da fare per chiunque riprenda A1.
2. **Una sola replica per cella.** Il rumore del banco fra repliche identiche è 0,06-0,2%
   sul prefill, quindi i salti da ±9% in su sono fuori discussione, ma il +1,85% di X0
   su W4 non è distinguibile da una differenza di macchina.
3. **`QWEN4EXP_QSA_MASK_INPLACE` non è mai stata misurata da sola.** Nelle celle X1 e X2
   è accesa insieme alla fetta, quindi il suo effetto (che dovrebbe essere piccolo e
   positivo: −2 B/coppia) non è separabile. Il preset per misurarla esiste già: basta
   accendere solo lei.
4. **La taglia della fetta non è stata esplorata.** 512 è un valore scelto a tavolino.
   Fette più grandi (1024, 1536) costerebbero meno nodi; ma dato che il picco non si è
   mosso per niente, il ritorno atteso è nullo, e la prova non è stata fatta.
5. **La cadenza dei tratti non è una misura del banco**: viene dai tempi del log del
   server fra due riserve di workspace. È robusta ma non ha l'accuratezza dei `timings`.
6. **Il modello di costo della workspace** (`const(T) + pendenza(T)·K`) è tarato su tre
   ubatch e serve qui solo a progettare la scaletta di X3: fuori dai punti misurati non
   è verificato.
7. **Il 250k non è stato misurato**, come in P11: il punto operativo dichiarato è KV 250k
   con prompt ~131k, e si è misurato quello.

---

## 10. Aperture

- **A1-bis — trovare il punto del picco.** Portare `GGML_ALLOCATOR_DEBUG` a INFO dietro
  una variabile d'ambiente e leggere la composizione del massimo. Finché non la si legge,
  ogni intervento sulla workspace è a tentoni: questa cella lo dimostra al costo di tre
  corse.
- **A1-ter — la maschera F32 dell'indicizzatore.** Il `ggml_cast` di `qwen4exp.cpp:1062`
  converte una maschera intera per strato da F16 a F32 solo per poterla sommare ai
  punteggi. Se `ggml_add` accettasse `src1` in F16 (o se la somma avvenisse dentro
  l'espansione), sparirebbero **4 B/coppia di allocazione e ~2,6 GB di traffico per
  blocco**. È una modifica di un kernel elementare, non del kernel di attenzione.
- **A2 — il ring dello staging.** Il documento di P11 propone «buffer da 256 MiB»: il
  codice dice che non si può, perché la taglia del buffer è quella di **un tensore di
  esperti di uno strato** (`max_size` in `ggml-backend.cpp:1729`), non una costante. Le
  due manopole vere sono la **riserva di 512 MiB** (`ggml-backend.cpp:1739`) e il numero
  di corsie; con una sola corsia però non c'è sovrapposizione, cioè la leva si spegne da
  sé. Resta da provare: **riserva più piccola** e un ring che stia in `free − reserve`.
- **A3 — l'anomalia del tratto 66k→82k** con batch 3072 (43,3 s contro i ~36 previsti):
  non indagata, vale ~2% del prefill. In X2 a batch 4096 **non c'è** (37,5 s), il che è
  un indizio nuovo: è legata alla taglia dell'ubatch, non alla profondità.
- **A4 — sparse FA a 250k**, dove la leva vale di più.

---

## 11. Bozza di voce di registro

**Data e fase.** 15 settembre 2026, sera-notte. Fase P11, **cella 2**: l'apertura A1 —
togliere il muro di VRAM del batch nel prefill a 131k non materializzando le maschere
dense quando la sparse FA è accesa.

**Ipotesi.** P11 attribuiva il tetto del batch a «tre maschere F32 `[n_kv, n_batch]` dei
12 strati QSA», 12 byte per coppia token×cella, e stimava che toglierle avrebbe fatto
entrare il batch 4096 in VRAM lasciando spazio allo staging: «463 t/s cumulativi fino a
115k» già dimostrati dalla cella W2.

**File toccati.** `D:\ds4_work\p11_work\source\src\models\qwen4exp.cpp` (le due leve di
A1, entrambe spente di default) e `src\llama-context.cpp` (diagnostica `QWEN_WS_DUMP`,
spenta di default) → `docs/porto/p11_prefill/p11_cella2.patch`.
`docs/porto/banco_p0/preset_X{0,1,2,3,4,5}_p11.json`;
`docs/porto/p11_prefill/` (documento, `genera_preset_cella2.py`, `sonda_workspace_p11.ps1`,
log); `copia_log_p11.py` (aggiunto `ws_dump|ws_kv|graph nodes` alle righe raccolte).
`ggml/src/ggml-alloc.c` è stato modificato per una prova e **riportato allo stato P8**.
**Non toccati e verificati**: `bin_prod`, `qwen38_clean\source`, `qwen38_clean\build\bin`,
lanciatore quotidiano, modelli, snapshot P0, albero P8.

**Configurazioni.** Base = `preset_W4_p11.json` (sparse FA + GDN a tile + staging).
X0 = W4 sui binari nuovi con A1 dichiarata spenta (controllo). X1 = A1 a batch 3072.
X2 = A1 a batch 4096. X3 = scaletta dell'ubatch ricalcolata sul fabbisogno dello staging
(`81920:3072,114688:2048`, `-b/-ub 4096`). X4 = X3 con `-b 12288`. X5 = X4 con `-ub 6144`
e un gradino in più.

**Run validi/invalidi.** Otto corse, tutte valide (`guasto: nessuno`): X0, X1, X2, X3, X4,
X5, cancello aghi, cancello decode. X2 è valida **come misura del crollo**, non come
candidato. Una corsa non è una misura ed è dichiarata tale: la sonda
`sonda_workspace_p11.ps1`, che avvia il server solo per leggere l'elenco dei tensori e lo
chiude. Nessuna corsa interrotta.

**Risultato e limite.** **A1 è falsificata**: la fetta di token lascia la riserva dov'era
(+4,2%) e costa il 9%; a batch 4096 peggiora il crollo di W2 (219,6 t/s, RAM a 3,44 GB).
La diagnosi però **corregge il modello di P11**: le tre F32 stanno nell'indicizzatore, non
nell'attenzione, dove le maschere sono due e F16. Per l'altra strada — la scaletta
calcolata sul fabbisogno dello staging, più un blocco divisibile — il prefill a 131k passa
da **376,4 (W4) / 383,3 (controllo) a 396,99 t/s**, con la workspace da 6819 a 4659 MiB e
lo staging acceso in tutti i blocchi. **I 400 non sono raggiunti: manca lo 0,75%.**
Limite: una replica per cella; il picco dell'allocatore non è stato localizzato (§9.1),
quindi *perché* A1 non paghi resta un'ipotesi (§9, difetto 1);
`QWEN4EXP_QSA_MASK_INPLACE` non è mai stata
misurata da sola; il 250k non è stato misurato.

**Decisione.** **A1 si chiude**: le due leve restano nel codice ma **spente di default**,
perché la forma implementabile senza toccare i kernel è provata e non paga. **X4 si adotta
come candidato di prefill lungo** (5/5 aghi, decode dentro il cancello): supera W4 del
5,5% e il controllo del 3,6%. **Il gradino da 6144 si chiude** (X5, −2,5%). La promozione
nel lanciatore quotidiano resta una decisione dell'utente e richiede i binari
ricompilati.

**Regressioni.** Nessuna misurata: decode **+0,84%** e **−0,69%** contro il riferimento
V3 (cancello −3%), aghi **5/5**, RAM libera minima 6,43-6,73 GB, VRAM libera minima nel
prefill 1649-1656 MiB (quattro volte quella di W4). Il testo del profilo di prefill
cambia rispetto a W4 con `-b 12288` (`58f84ab53ce2`) e **non** cambia con `-b 4096`
(X3 e X5 tengono `d77a042a3e08`): è la stessa classe di differenza già documentata il
13/9, non una direzione sistematica.

**Stato dei processi.** Verificato a fine cella: **nessun `llama-server`, porta 8100
libera, nessuna build in corso, nessun processo residuo.**

**Prossima azione.** Localizzare il picco dell'allocatore (§10, A1-bis): finché non lo si
legge, ogni intervento sulla workspace è a tentoni, e questa cella lo dimostra al costo di
tre corse. Subito dopo, A1-ter: togliere il `ggml_cast` della maschera da F16 a F32
(`qwen4exp.cpp:1062`), che vale 4 B/coppia e ~2,6 GB di traffico per blocco.

---

## 12. Come rifare queste misure

```powershell
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_p0
.\avvia_blocco.ps1 -Preset preset_X0_p11.json -Profilo prefill_131k -Replica 1 -Nota "controllo"
.\avvia_blocco.ps1 -Preset preset_X1_p11.json -Profilo prefill_131k -Replica 1 -Nota "A1 3072"
.\avvia_blocco.ps1 -Preset preset_X2_p11.json -Profilo prefill_131k -Replica 1 -Nota "A1 4096"
.\avvia_blocco.ps1 -Preset preset_X3_p11.json -Profilo prefill_131k -Replica 1 -Nota "scaletta staging"
```

```
cd ..\p11_prefill
python genera_preset_cella2.py
python tabella_p11.py         <cartella_corsa>
python serie_workspace_p11.py <cartella_corsa>\log\server.log
python aghi_p11.py            <cartella_corsa_aghi>
python copia_log_p11.py       X0=<cartella> X1=<cartella> ...
```

La diagnostica dei tensori della workspace si accende con `QWEN_WS_DUMP=25`
nell'ambiente del server (già nei preset X0 e X2).

Corse di questa cella, in `D:\ds4_work\banco_p0_run\`:

| cella | cartella |
|---|---|
| X1 | `20260915_215334_P11_p11_x1_a1_batch3072_r1` |
| X0 (controllo) | `20260915_221144_P11_p11_x0_controllo_binari_nuovi_r1` |
| X2 | `20260915_222210_P11_p11_x2_a1_batch4096_r1` |
| X3 | `20260915_223649_P11_p11_x3_scaletta_per_staging_r1` |
| X4 | `20260915_224723_P11_p11_x4_scaletta_batch_divisibile_r1` |
| X5 | `20260915_225738_P11_p11_x5_scaletta_da_6144_r1` |
| cancello aghi (X4) | `20260915_230714_P11_p11_x4_scaletta_batch_divisibile_r1` |
| cancello decode (X4) | `20260915_231732_P11_p11_x4_scaletta_batch_divisibile_r1` |

Log ripuliti (chiave API redatta) in `docs/porto/p11_prefill/log/`, con il prefisso
`p11_X*`. L'estratto del server di X0 e X2 contiene anche le righe `ws_kv` della
diagnostica.
