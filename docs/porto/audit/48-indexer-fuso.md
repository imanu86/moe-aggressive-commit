# 48 — L'op indexer fusa: portata, dietro leva, mai compilata

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, HEAD `f4ea55518`.
**Niente compilato, nessun server toccato, niente committato.** Il codice e'
sull'albero e basta.

Strumenti: l'albero upstream **in locale** (`upstream/master` =
`936918514`), letto direttamente con `git show` — non le pagine web delle PR.
Questo conta: quello che segue e' il codice che gira upstream oggi, non la
descrizione di una PR. Marcatura: [MISURATO] = letto nel codice o numero di
casa; [DEDOTTO] = aritmetica; [IPOTESI] = da falsificare col cancello indicato.

---

## 1. Il meccanismo, in tre frasi

1. `GGML_OP_LIGHTNING_INDEXER` prende `q`, `k`, i pesi **gia' scalati** e la
   maschera **in f16**, e per ogni coppia (posizione KV, token) calcola in un
   solo kernel `sum_h relu(q_h · k) * w_h + maschera`, tenendo i 64 punteggi
   per-testa nei registri e nella memoria condivisa.
2. Non materializza nessuna intermedia: **scrive solo il risultato finale
   `[n_kv, n_batch]` f32**, dove la catena non fusa scriveva e rileggeva tre
   volte un tensore `[n_kv × 64 teste × n_tok]`.
3. Sulla 3060 (Ampere, `turing_mma_available`) con K in f16 entra il ramo
   **wmma** (frammenti 8×32×16, K in shared, Q in doppio buffer); il ramo
   vettoriale resta per F32/BF16 e per le schede senza mma.

### Cosa cambia nella forma dei tensori

La forma degli **ingressi** e delle **uscite** non cambia. Cambia che le forme
intermedie **spariscono**.

| | catena non fusa | op fusa |
|---|---|---|
| `q` | `[128, 64, nt, ns]` → permute → `[128, nt, 64, ns]` | `[128, 64, nt, ns]` **senza permute** |
| `k` | `[128, 1, n_kv, ns]` → permute → `[128, n_kv, 1, ns]` | `[128, 1, n_kv, ns]` **senza permute** |
| pesi | `[64, nt, 1, ns]` | `[64, nt, 1, ns]` — identici, gia' scalati |
| maschera | `[n_kv, nt, 1, ns]` **f32** | `[n_kv, nt, 1, ns]` **f16** ← unica forma che cambia |
| **intermedia 1** | `mul_mat` → **`[n_kv, nt, 64, ns]` f32** | — |
| **intermedia 2** | `cont(permute)` → **`[64, nt, n_kv, ns]` f32** | — |
| intermedie 3-4 | `relu`, `mul` (stessa taglia, riuso in-place) | — |
| intermedia 5 | `sum_rows` → `[1, nt, n_kv, ns]` | — |
| uscita | `[n_kv, nt, 1, ns]` f32 | `[n_kv, nt, 1, ns]` f32 — **stessa** |

Le due intermedie in grassetto sono tutto il fronte. **11 nodi → 1.**

Il contratto dell'op (dal commento upstream in `ggml.h`, portato verbatim):
`weights` "!! prescaled !!" e `mask` "!! f16 !!". Il primo lo soddisfiamo gia'
— lo `ggml_scale(1/sqrt(128*64))` c'era. Il secondo **no**: e' l'unica cosa
che il porto deve cambiare fuori dalla catena.

---

## 2. Confronto con la nostra catena — verificato, non assunto

L'audit 45 diceva "identica riga per riga alla loro non-fusa". **Ho verificato
con un diff testuale** fra il nostro `build_lid_top_k` a HEAD e quello upstream
(`deepseek4.cpp:589-680` contro `:612-710` upstream), normalizzando gli spazi.

**L'audit 45 aveva ragione con UNA eccezione, ed e' quella che rende il porto
non del tutto meccanico** [MISURATO]:

```
  noi:       ggml_tensor * indexer_k = inp_dsv4->mctx->get_lid()->ring_enabled()
                     ? inp_dsv4->mctx->get_lid()->materialize(
                             ctx0, n_lid, il, nt, dsv4_ring_accounts_tokens(hparams, il))
                     : inp_dsv4->mctx->get_lid()->get_k(ctx0, il);

  upstream:  ggml_tensor * indexer_k = inp_dsv4->mctx->get_lid()->get_k(ctx0, il);
```

Tutto il resto — proiezione q_b, rope, concat, hadamard, `indexer_proj`, lo
`ggml_scale`, le due `view_4d` di stream, i due permute, `mul_mat`, `cont`,
`relu`, `mul`, `sum_rows`, `cont`, `add` con la maschera, `top_k` — coincide
carattere per carattere a meno degli spazi.

**Perche' l'eccezione e' benigna** [MISURATO]: `ggml_dsv4_kv_ring`
(`ggml.c:5483-5484`) alloca `ggml_new_tensor_4d(host->type, head_dim, n_head,
n_kv, ns)` = `[128, 1, n_kv, 1]` **contiguo**, che e' esattamente la forma che
l'op pretende per `k`. I passi (`nb1=256`, `nb2=256`, `nb3=256·n_kv`) passano
tutti il controllo di allineamento `nb[i] % 16 == 0` di
`ggml_cuda_lightning_indexer_supported`. Sul ramo senza anello, `get_k()` da'
una vista dentro la cache: se i passi non reggessero, `supports_op` dice no e
il probe **spegne la leva ad alta voce** invece di sbagliare in silenzio.

Le nostre hparams sono nel punto dolce del kernel: **indexer 64 teste × 128**
(audit 30, `:81`), e il kernel supporta solo `n_embd == 128` e
`n_head ∈ {32, 64}`. Fuori da li' aborta — ma non ci arriva mai, perche'
`supports_op` filtra prima.

---

## 3. Il codice sull'albero

`git diff --numstat`, commentato:

```
   1     1  ggml/include/ggml-rpc.h            static_assert 105 -> 106 (la terza guardia,
                                              quella che una patch precedente aveva scordato)
  19     0  ggml/include/ggml.h                enum GGML_OP_LIGHTNING_INDEXER nella POSIZIONE
                                              upstream (dopo GATED_DELTA_NET) + firma e contratto
  40     2  ggml/src/ggml.c                    2 tabelle ordinate (NAME, SYMBOL), 2 static_assert,
                                              ggml_lightning_indexer() con le 14 GGML_ASSERT
  11     0  ggml/src/ggml-cpu/ggml-cpu.c       dispatch + n_tasks + wdata per la dequantizzazione K
  84     0  ggml/src/ggml-cpu/ops.cpp          ggml_compute_forward_lightning_indexer -- IL RIFERIMENTO
   1     0  ggml/src/ggml-cpu/ops.h            dichiarazione
   6     0  ggml/src/ggml-cuda/ggml-cuda.cu    include + dispatch + supports_op
 588     0  ggml/src/ggml-cuda/lightning-indexer.cu   VERBATIM da upstream (verificato: identico)
   4     0  ggml/src/ggml-cuda/lightning-indexer.cuh  VERBATIM
  33     0  src/llama-context.cpp              probe + LEVA LLAMA_DSV4_INDEXER_FUSO
   2     0  src/llama-cparams.h                fused_lid, auto_flid
  44    16  src/llama-graph.cpp                maschera lid f16 alla nascita SE leva accesa;
                                              dsv4_set_kq_mask scrive f16; can_reuse controlla il TIPO
   1     0  src/llama-graph.h                  LLM_FUSED_OP_LIGHTNING_INDEXER
  35    15  src/models/deepseek4.cpp           il ramo: if (cparams.fused_lid && il >= 0)
  94     0  tests/test-backend-ops.cpp         test_lightning_indexer + registrazione eval e perf
```

Tre cose da sapere su come e' fatto:

- **La leva e' `LLAMA_DSV4_INDEXER_FUSO`, spenta di difetto**, modellata sulla
  gia' esistente `LLAMA_DSV4_HC_FUSO`. Accende `cparams.fused_lid` **e**
  `auto_flid`, cosi' il probe di `resolve_fused_ops` gira solo quando la leva
  e' accesa: **a leva spenta non si costruisce nemmeno il grafo di prova.**
- **`GGML_OP_COUNT` va a 106**, e le **tre** guardie sono tutte aggiornate
  (`ggml.c:1110`, `ggml.c:1232`, `ggml-rpc.h:14`). Ho messo l'enum nella
  posizione upstream (fra `GATED_DELTA_NET` e `DSV4_HC_COMB`) e non in coda:
  costa lo spostamento di 3 valori, ma i prossimi rebase non litigano. Le sole
  due tabelle dimensionate `[GGML_OP_COUNT]` sono in `ggml.c` e sono entrambe
  aggiornate; tutti gli altri backend (Vulkan, SYCL, OpenCL, Metal, BLAS, RPC)
  hanno `default:` nei loro switch sull'op — **verificato, nessuno si rompe**.
- **Ho portato anche l'implementazione CPU.** Non e' per girare su CPU: e'
  perche' **`test-backend-ops` confronta la CUDA contro la CPU**, e senza la
  CPU il secondo cancello non esisterebbe.

### Fine riga

Nessuno dei 15 file toccati e' fra i quattro della trappola armata
(`ggml-alloc.c/.h`, `ggml-backend.cpp/.h`): quelli restano CRLF nel working
tree e LF nell'indice, **non li ho toccati**. Scansione byte su tutti i 15
file dopo le modifiche: **LF puro, zero CRLF, zero BOM**. I due file CUDA nuovi
sono stati normalizzati a LF prima di scriverli e verificati identici al blob
upstream a meno del newline finale.

---

## 4. La sequenza dei cancelli

### Cancello 1 — identita' a leva spenta (il primo, sempre)

`LLAMA_DSV4_INDEXER_FUSO` assente o `0`, **spec off e K=0**:
**SHA `33D76723EB8D`, 13,19-13,26 t/s.**

Perche' deve passare per costruzione: a leva spenta `cparams.fused_lid` e'
`false`, quindi (a) la maschera lid nasce `GGML_TYPE_F32` come sempre, (b)
`build_lid_top_k` prende il ramo `else` che e' il codice di prima parola per
parola, (c) `auto_flid` e' `false` quindi il probe non gira e non si costruisce
nessun grafo in piu'. L'unica cosa che si e' mossa nel binario e' un valore
d'enum e due voci di tabella.

**Se questo cancello fallisce, fermarsi**: vuol dire che lo spostamento
dell'enum ha rotto qualcosa che non ho visto, e nessun'altra misura vale.

### Cancello 2 — separare «l'op gira» da «l'op cambia il risultato»

Questo e' il cancello che il mandato chiede, e ha **due battenti distinti**.

**2a — l'op e' CORRETTA** (non serve il modello, non serve il server):

```
test-backend-ops -o LIGHTNING_INDEXER
```

Confronta la CUDA contro la **CPU** su 156 casi: kv ∈ {1,7,8,63,64,65,256}
(i bordi non multipli di 32 e 64 sono la' apposta), nh ∈ {32,64}, batch 1 e
512, 4 stream, 9 tipi di K. Soglia `max_nmse_err = 1e-6`. **Verde qui = l'op
calcola la cosa giusta.** Rosso qui e tutto il resto e' rumore.

**2b — l'op e' INNESTATA giusta**, cioe' gira davvero e sul device giusto.
Due spie, entrambe gratis:

- nel log: `resolve_fused_ops: Lightning Indexer enabled`. Se invece esce
  `... not supported, set to disabled`, l'op c'e' ma il grafo l'ha messa
  altrove — la leva si e' spenta da sola e ogni misura successiva e' quella di
  sempre travestita.
- **conteggio nodi**: la catena non fusa e' 11 nodi (permute, permute,
  mul_mat, permute, cont, relu, mul, sum_rows, permute, cont, add) → 1.
  Su 21 strati CSA: **atteso −210 nodi**, da 10.507 a **~10.297**.
  Se il log ne toglie ~210, l'op gira su tutti gli strati. Se ne toglie 10,
  gira su uno solo. Se ne toglie 0, non gira.

E la cosa **onesta** da dire sul decode a contesto corto: −210 nodi con la
calibrazione di casa (+16,5% per 24.000 nodi = 0,000687%/nodo) vale
**+0,14%** [DEDOTTO]. Il pavimento di rumore e' ±1,6%. **A contesto corto
questo porto NON e' misurabile sul t/s, e chiedere il t/s li' produrra' solo
un numero che non vuol dire niente.** Il conteggio nodi e' l'unica cosa
leggibile a contesto corto.

### Cancello 3 — IL NUMERO: il buffer di calcolo

Questo e' il cancello che decide se il porto e' servito a qualcosa.

**Il modello, ricavato dalle DUE misure di stamattina.** Con `n_lid` =
`GGML_PAD(ceil(ctx/4), 256)` (ratio CSA 4, `llama-kv-cache-dsv4.cpp:29-31`) —
che a ctx 10.000 fa **2.560**, ed e' esattamente la LID che l'audit 30 aveva
gia' misurato:

```
    A(ctx) = n_lid × ub × 64 teste × 4 B      (l'intermedia)
    B(ctx) = n_lid × ub × 4 B                 (i tensori piatti: score, maschere, top-k)

    ctx  10.000  ->  n_lid =  2.560  ->  A =   320,00 MiB   B =  5,00 MiB
    ctx 104.000  ->  n_lid = 26.112  ->  A = 3.264,00 MiB   B = 51,00 MiB
```

Adattando `buffer = a·A + b·B + c` alle due misure (859,68 e 6.960,93 MiB):

```
    a = 1  ->  b = 68,6    fisicamente assurdo (68 tensori piatti vivi)
    a = 2  ->  b = 4,64    c = 196,50 MiB      <-- l'unica soluzione fisica
    a = 3  ->  b < 0       impossibile
```

**`a = 2` e' forzato dall'aritmetica**: ci sono esattamente **due copie vive**
dell'intermedia — l'uscita di `mul_mat` e l'uscita di `cont(permute)`. `relu` e
`mul` li riusa l'allocatore in-place. Il termine costante, 196,5 MiB, e' tutto
il resto del grafo.

**Quindi, con la leva accesa a ctx 104.000 e ub 512, il termine `2·A = 6.528
MiB` va a ZERO** — l'op non materializza niente. Resta `b·B + c`:

> ### Il buffer di calcolo deve scendere da **6.960,93 MiB** a **~430 MiB**.
> Intervallo atteso **330-435 MiB** [DEDOTTO]: 435 se restano vivi tutti i
> tensori piatti di adesso, ~330 se l'op ne toglie anche due o tre
> (`sum_rows`, il `cont`, l'`add`). **Riduzione ~16×.**

E le tre letture che falsificano, in ordine di gravita':

| il numero che esce | cosa vuol dire |
|---|---|
| **330-435 MiB** | il porto funziona. `ub 512` a 104k e' libero: 4,2 GiB disponibili contro 0,43 richiesti |
| **~3.700 MiB** | e' sparita **una sola** delle due copie. L'op c'e' ma la catena vecchia e' ancora nel grafo su una parte degli strati — guardare il conteggio nodi del cancello 2b |
| **6.960,93 invariato** | la leva non e' mai scattata. Guardare il log del probe |
| **qualsiasi altro** | il modello a due termini e' sbagliato e va rifatto **prima** di trarre conclusioni |

**Il braccio da fare per primo e' pero' a ctx 10.000, non a 104.000**, perche'
costa un minuto e usa lo stesso modello: **atteso 859,68 → ~220 MiB**
(`4,64 × 5 + 196,5 = 219,7`). Se a 10k il numero non e' ~220, il braccio da 104k
e' sprecato.

### Cancello 4 — solo dopo i primi tre: `ub` a contesto lungo

`ub 64`, poi `128`, poi `256`, poi `512` a ctx 104.000. **Questo e' l'unico
punto in cui il porto puo' pagare quanto promesso**: prefill da **22,6 t/s**
(obbligati a `ub` basso) verso i **72,9** di `ub 512`. Un prompt da 96.000
token: da 71 minuti a 22.

Al decode a 105k il guadagno atteso e' **3-5 ms/posizione** [DEDOTTO, audit 45].
Conferma indipendente per aritmetica di banda: a nt=2 e n_lid=26.112,
l'intermedia e' 12,75 MiB/strato scritta una volta e riletta tre → ~1.071
MiB/forward su 21 strati; a ~300 GB/s effettivi sono **3,4 ms**. I due conti
si toccano, il che e' una ragione in piu' per crederci.

### Avvertenza che vale un cancello a sé: il replay del grafo CUDA

L'op fusa **deriva la griglia da `n_kv`** (`lightning-indexer.cu:457,477`:
`num_kv_blocks = ceil(n_kv / K_VECS_PER_BLOCK)`). E' esattamente la classe di
op che l'audit 11 aveva schedato come esposta: **stesso `uid`, stesso numero di
nodi, `ne` diverso ⇒ replay con griglia stantia**, senza crash. A contesto
lungo `n_kv` cresce a ogni ubatch mentre il numero di nodi resta fisso: e' il
caso peggiore per costruzione.

**La prima corsa a contesto lungo con la leva accesa va fatta con
`LLAMA_GRAPH_REUSE_DISABLE=1`** (`llama-context.cpp:328`). Il sintomo se si
sbaglia non e' un crash: e' una selezione top-512 sbagliata, cioe' p1 e
accettazione che scendono senza che niente si lamenti.

E il promemoria di casa: **lo SHA DIVERGERA' a leva accesa, ed e' legittimo.**
Il kernel accumula le 64 teste in ordine diverso da `sum_rows` (riduzione per
warp con `i_lane == 0`, non riduzione per righe). Il cancello SHA vale solo a
leva spenta.

---

## 5. Cosa ho lasciato indietro, e perche'

1. **#25370, la parte viva** (maschere CSA/HCA nate f16 con la FA accesa).
   Ho reso f16 **solo** la maschera lid, e **solo** a leva accesa, perche' e'
   l'op che la esige. Le maschere CSA/HCA restano f32 e vengono ancora castate
   per strato ogni forward — quel fronte (audit 45 §1.1: ~1,7 GiB di traffico
   cast per ubatch a ub 512 su 105k, ~1 s sul prefill) e' **intatto e
   separabile**. Non l'ho fatto perche' avrebbe cambiato il cammino a leva
   spenta, e il cancello 1 sarebbe morto.
2. **#25702** (`prev_idxs`/`cur_idxs` → `get_rows` unica, il nostro pre-fix e'
   a `deepseek4.cpp:531-539`) e **#25896** (`sqrt_softplus` in `topk-moe.cu`).
   Sono gli altri due pezzi del "lotto 1" dell'audit 45. Indipendenti da
   questo, e nessuno dei due tocca il buffer di calcolo.
3. **SYCL, Metal, Vulkan, OpenCL**: non portati. Upstream ha SYCL (#26568) e
   Metal (#25893); a noi non servono e sarebbero 800 righe di codice che non
   compiliamo mai. `supports_op` di quei backend ha `default:` — restituiscono
   false e basta.
4. **Nessun flag CLI**: la leva e' solo d'ambiente, come `LLAMA_DSV4_HC_FUSO`.
   Se serve in `common/arg.cpp` e' una riga, ma non ha senso prima che il
   cancello 3 abbia parlato.
5. **#24776** (top_k/argsort a blocchi ≤ 64 MiB) — **e questo diventa piu'
   interessante DOPO**, non prima. Tolta l'intermedia da 3.264 MiB, il termine
   piu' grosso rimasto e' `b·B` ≈ 236 MiB, e dentro c'e' il `ggml_top_k` su
   righe da 26.112. Il prossimo soffitto e' li'.

---

## 6. Dove correggo la domanda

Il permesso e' accordato, e ho **due** correzioni. La seconda e' quella che
conta.

**(a) "Otto volte, a parita' di ubatch. Il buffer scala con `ub × contesto`."**
Vero ma incompleto, e l'incompletezza e' il punto: scala con
**`ub × n_kv × n_teste`**, e **il moltiplicatore grosso e' 64, non il
contesto**. E' il fattore 64 che porta 51 MiB a 3.264. Detto altrimenti: non
stiamo pagando il contesto lungo, stiamo pagando **64 teste × il contesto
lungo**, e l'op fusa attacca proprio quel 64 — per questo la riduzione e' 16×
e non 2×.

**(b) "L'op fusa e' l'unica cosa che sblocca quel fronte."**
Dell'aritmetica del §4 esce che **toglie il 93,8% del buffer** (6.528 su
6.960,93). Non e' tutto: restano ~433 MiB, di cui **~236 crescono ancora
linearmente col contesto**. A 104k va benissimo — 0,43 GiB contro 4,2
disponibili. Ma la frase "sblocca il fronte" e' vera per **questo** contesto,
non per sempre: a 400k lo stesso conto da' ~1,1 GiB, e a quel punto il
soffitto e' il `top_k` (§5.5), non piu' l'indexer. **Vale la pena scriverlo
adesso perche' il fronte deciso dall'utente e' "prefill 10-100×", e 100× su
104k vuol dire guardare oltre 104k.**

E una terza cosa che non e' una correzione ma un avvertimento sul metodo:
**questo porto non si misura col t/s a contesto corto.** Vale +0,14% li',
dentro il rumore. Chi lo misura a contesto corto ottiene un numero, e il
numero non vorra' dire niente. Il metro e' il **buffer di calcolo**, ed e' un
numero che il log stampa gratis.

---

## 7. Fonti

Codice upstream letto in locale a `upstream/master` = `936918514`:
`ggml/include/ggml.h`, `ggml/src/ggml.c`,
`ggml/src/ggml-cuda/lightning-indexer.cu` (589 righe, portate verbatim),
`ggml/src/ggml-cpu/ops.cpp:11922-12004`, `ggml/src/ggml-cpu/ggml-cpu.c`,
`src/llama-graph.cpp:732-774,925-953`, `src/llama-context.cpp:34-62,564`,
`src/models/deepseek4.cpp:612-710`, `tests/test-backend-ops.cpp:7300-7359`.
Codice nostro a HEAD `f4ea55518`. Numeri di casa: le due misure del buffer
(859,68 / 6.960,93 MiB) dal mandato; audit 30 (indexer 64×128, top_k 512, LID
2560, 651 nodi/forward), audit 45 (il candidato e la sua aritmetica), audit 11
(replay a taglia stantia), PAVIMENTO (calibrazione nodi→t/s), memoria di
progetto (pavimento di rumore ±1,6%, prefill 22,6 / 72,9 t/s).
