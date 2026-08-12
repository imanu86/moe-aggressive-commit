# UP_D — SCHEDULER E CAMMINO SPECULATIVO

Audit del delta upstream sulla fetta D: `ggml/src/ggml-backend.cpp`, `ggml-backend-impl.h`,
`ggml/src/ggml.c`, `ggml/include/ggml.h`, `ggml/src/ggml-alloc.c`, `common/speculative.cpp`,
`tools/server/`.

- repo: `D:\llama-overlap`, ramo `overlap`, HEAD `9b7f9eea7`
- base comune: `git merge-base HEAD upstream/master` = `5c3a58686` (9 luglio)
- upstream avanti di **436** commit; il nostro ramo ha **133** commit propri sopra la base
- **niente compilato, niente avviato, niente applicato, nessun cherry-pick.** Solo lettura di diff.

> **Il reperto piu' importante di questo audit non e' un commit da portare.** E' al §1, e spiega
> perche' allargare la finestra ha reso +4% invece di +50%. Il resto viene dopo.

---

## 0. Superficie effettiva (contata, non stimata)

```
ggml-backend.cpp + ggml-backend-impl.h + ggml-backend.h ....  3 commit
ggml.c + ggml.h ............................................  6 commit
ggml-alloc.c / ggml-alloc.h ................................  0 commit   <- ZERO
common/speculative.{cpp,h} .................................  9 commit
tools/server/ .............................................. 59 commit
```

Lo scheduler in un mese ha preso **tre** commit, e uno dei tre (`153d324bc`) tocca solo
l'header, non il `.cpp`. **Nessuno dei tre tocca la sovrapposizione fra backend, il join, o
l'ordine di esecuzione degli split.** Non c'e' nessun lavoro upstream sul numero grosso —
perche' upstream l'ha gia' fatto **prima** della nostra base, e l'ha buttato. Vedi §1.

---

## 1. IL REPERTO — `#20793` e il suo revert, e perche' +4% invece di +50%

### 1.1 I due commit, e dove stanno rispetto a noi

```
3fc4e1052  2026-06-26  sched : reintroduce less synchronizations during split compute (#20793)
                       Andreas Kieslinger
86b94708f  2026-06-30  Revert "sched : reintroduce less synchronizations..." (#25138)
                       Oliver Simons  <osimons@nvidia.com>     <-- NVIDIA, non AMD
```

**Verificato: entrambi sono ANTENATI della nostra base `5c3a58686`.**

```
git merge-base --is-ancestor 3fc4e1052 5c3a58686  -> True
git merge-base --is-ancestor 86b94708f 5c3a58686  -> True
```

Cioe': **non e' un commit da valutare, e' un pezzo di storia che abbiamo gia' ereditato — dal
lato del revert.** Il nostro `ggml-backend.cpp` di oggi contiene la versione **stretta**, quella
con tutte le sincronizzazioni. Quattro giorni di vita, revertito da un ingegnere **NVIDIA**.

### 1.2 Che cosa aveva provato a fare — letto nel diff

Quattro modifiche, due in `ggml-backend.cpp` e due in `ggml-cuda.cu`:

*(a)* Un `ggml_backend_synchronize(split_backend)` **una volta sola** in cima all'iterazione di
split, e uno prima di `graph_compute_async` — il pattern che il messaggio chiama `saaasg`
(sync, async, async, async, sync, graph).

*(b)* La sincronizzazione **per ingresso** diventa condizionale:
```c
-                } else {
+                } else if (!split_backend->iface.cpy_tensor_async) {
                     ggml_backend_synchronize(split_backend);
                 }
-                ggml_backend_tensor_copy(input, input_cpy);
+                ggml_backend_tensor_copy_async(input_backend, split_backend, input, input_cpy);
```
Su entrambi i rami (ingresso utente e ingresso interno).

*(c)* In CUDA, `ggml_backend_cuda_cpy_tensor_async` viene esteso a **host→device**, non piu'
solo device→device:
```c
const bool copy_from_host = ggml_backend_buffer_is_host(buf_src) &&
                            ggml_backend_dev_type(backend_src->device) == GGML_BACKEND_DEVICE_TYPE_CPU;
...
if (copy_from_host) {
    CUDA_CHECK(cudaMemcpyAsync(dst->data, src->data, ggml_nbytes(dst),
                               cudaMemcpyHostToDevice, cuda_ctx_dst->stream()));
}
```

*(d)* **Ma con HIP e MUSA esclusi da `copy_from_host` per precauzione:**
```c
#if defined(GGML_USE_HIP) || defined(GGML_USE_MUSA)
    const bool copy_from_host = false;
#else
    const bool copy_from_host = ...;
#endif
```

### 1.3 Che cosa e' andato storto — e non e' l'hardware

Il messaggio del commit e' gia' un verbale di tre cure prima ancora di atterrare: *«Adds
single-GPU synchronizations to multi-GPU settings to fix hip backend pipeline parallel bugs»*,
*«Scheduler Hardening: Exclude hip/MUSA from copy_from_host»*, *«Scheduler Hardening: Re-adding
original additional synchronizations for non-async backends»*.

Il difetto e' leggibile mettendo insieme *(b)* e *(d)* con il fallback di
`ggml_backend_tensor_copy_async` (`ggml-backend.cpp:504-523`, letto nel nostro albero):

```c
if (backend_dst->iface.cpy_tensor_async != NULL) {
    if (backend_dst->iface.cpy_tensor_async(backend_src, backend_dst, src, dst)) {
        return;
    }
}
// to simulate the same behavior, we need to synchronize both backends first, and do a blocking copy
ggml_backend_synchronize(backend_src);
ggml_backend_synchronize(backend_dst);
ggml_backend_tensor_copy(src, dst);
```

**Su HIP, con #20793 dentro:**

1. `split_backend->iface.cpy_tensor_async != NULL` — vero, HIP compila la stessa funzione
   → la guardia *(b)* **salta la sync**;
2. dentro la funzione, `copy_from_host` e' forzato `false` dal `#if` *(d)*, e la sorgente e'
   un buffer host → **`return false`**;
3. → si cade nel fallback: **`synchronize(src)` + `synchronize(dst)` + copia bloccante**.

Cioe': **due sincronizzazioni per ingresso invece di una.** Non un rallentamento marginale:
un raddoppio secco sul cammino che l'offload MoE martella. Un −50% e' perfettamente coerente
con questo, e **non serve invocare nessuna proprieta' del silicio AMD per spiegarlo.**

**LA CAUSA E' UNA PROPRIETA' DEL MODELLO DI SINCRONIZZAZIONE, NON DELL'HARDWARE.** La guardia
che decide **se saltare la sync** (`iface.cpy_tensor_async != NULL`, una *dichiarazione di
capacita'*) **non e' la stessa guardia** che decide **se la copia e' davvero asincrona**
(`copy_from_host`, una *macro di build*). Due condizioni diverse su due siti diversi per un
solo invariante.

E' la regola che ci e' gia' costata un kernel impiccato:
> **le barriere devono stare sullo STESSO SITO** — non basta il conteggio bilanciato: stessa
> chiamata sotto condizione uniforme.

Che il revert sia firmato **NVIDIA** chiude il cerchio: non e' stato AMD a farsi restituire il
proprio regime. E' stato chi guadagnava l'1% a decidere che l'1% non valeva un invariante rotto.

**Per noi, quindi:** la ragione del revert **non ci esenta** (non e' «e' roba AMD»), ma **non ci
condanna** neanche (non e' «l'asincronia sugli ingressi non funziona»). Ci dice: *l'idea e'
buona, il modo in cui e' stata cancellata la sincronizzazione era sbagliato, e il modo giusto e'
una condizione sola.*

### 1.4 PERCHE' +4% INVECE DI +50% — la risposta, e non e' la finestra

Il nostro albero e' post-revert. Leggo `ggml_backend_sched_compute_splits` cosi' com'e' oggi:

```
ggml-backend.cpp:2019   if (input->flags & GGML_TENSOR_FLAG_INPUT) {
ggml-backend.cpp:2024       else -> sync_profilato(split_backend);      <- BLOCCANTE
ggml-backend.cpp:2026       ggml_backend_tensor_copy(input, input_cpy); <- BLOCCANTE
ggml-backend.cpp:2027   } else if (copia_join_async) {                  <- l'unico ramo SENZA sync
ggml-backend.cpp:2034   } else {
ggml-backend.cpp:2039       else -> sync_profilato(split_backend);      <- BLOCCANTE
ggml-backend.cpp:2054       sync_profilato(input_backend);              <- cammino esperti MoE
ggml-backend.cpp:2073       sync_profilato(ids_backend);                <- cammino esperti MoE
```

E cosa fa `ggml_backend_synchronize` su CUDA (`ggml-cuda.cu:3164-3168`):

```c
CUDA_CHECK(cudaStreamSynchronize(cuda_ctx->stream()));
```

**Drena lo stream. Tutto.**

Quindi: **ogni ingresso di ogni split apre con una barriera di device.** Con 35,2 split per
grafo, il ciclo degli split non e' «accoda tutto e poi aspetta» — e'
**accoda / drena / accoda / drena**, decine di volte per grafo.

**La conseguenza distrugge l'aritmetica con cui abbiamo aperto il cantiere.** L'aritmetica
diceva:
```
lavoro GPU per split   ~33 ms / 130,7 = 0,25 ms
lavoro CPU da coprire   29,5 ms / 42  = 0,70 ms
```
e concludeva: *la finestra e' larga uno split, tre volte troppo stretta — allarghiamola a N e
copriamo il lavoro CPU.* L'assunto implicito era: **con `finestra = 4` la GPU ha 4 × 0,25 = 1,00 ms
di lavoro in volo.**

**Non ce l'ha.** La barriera a ogni confine impedisce alla coda di riempirsi. Con `finestra = 4`
l'host **emette** 4 split, ma li emette **drenando fra l'uno e l'altro**: 0,25 ms in volo,
quattro volte di seguito, non 1,00 ms in volo una volta. Il worker, che aspetta un evento
registrato in fondo a quella coda, non lo vede arrivare prima. **La finestra in numero di split
non era il vincolo. Il vincolo e' che ogni confine di split e' una barriera di device.**

**La corroborazione, dai numeri del profilo.** `us_sync = 2,200 ms` per grafo su 35,2 split:

```
2.200 us / 35,2 split = 62,5 us bloccati per confine
```

Sessantadue microsecondi. **A ogni barriera l'host trova la GPU praticamente gia' ferma.** Se
la coda fosse profonda 0,25 ms per split, l'host aspetterebbe 250 us per confine, non 62. La
misura dice che **la coda e' quasi sempre vuota**: host e GPU camminano in lockstep, e il
lockstep e' scritto nel codice, non nell'hardware.

Con 4 confini: `4 × 62,5 = 250 us` di lavoro GPU accumulabile, contro **700 us** di lavoro CPU
da coprire. Copertura massima teorica ~36%. **E' li' che la leva satura, ed e' li' che finisce
il +4%.**

> *(Marcatura: `us_sync = 2,200 ms/grafo` e `35,2 split` sono **misurati**; `62,5 us/confine` e'
> una **divisione** dei due; la catena «barriera → coda vuota → finestra inefficace» e' **dedotta**
> dalla lettura del codice, e la divisione la corrobora. Il modo di falsificarla e' al §1.5.)*

### 1.5 Che cosa fare — e la leva ce l'abbiamo gia', SPENTA

**Non c'e' niente da portare.** #20793 e' gia' passato e gia' revertito nella nostra storia.
Ma la sua idea, scritta **con una condizione sola**, e' esattamente cio' che il nostro albero
gia' contiene in forma stretta:

```c
ggml-backend.cpp:2014-2017
const bool copia_join_async = prodotto_dallo_split_unito &&
        ggml_backend_dev_type(ggml_backend_get_device(input_backend)) == GGML_BACKEND_DEVICE_TYPE_CPU &&
        input_buffer != NULL && ggml_backend_buffer_is_host(input_buffer) &&
        split_backend->iface.set_tensor_async != NULL;      // <-- LA STESSA condizione
...
ggml-backend.cpp:2030
ggml_backend_tensor_set_async(split_backend, input_cpy, input->data, 0, ggml_nbytes(input));
```

**Questa e' #20793 fatta bene**: la guardia che salta la barriera (`set_tensor_async != NULL`)
e' **la stessa** che rende la copia asincrona, perche' e' la funzione che viene poi chiamata.
Nessuna macro di build in mezzo. Il difetto di #20793 qui non puo' esistere per costruzione.

**Ed e' spenta di difetto** (`ggml-backend.cpp:1823-1831`):
```c
// LLAMA_OVERLAP_JOIN_ASYNC: accoda il ritorno del worker sullo stream della
// coda GPU. Spento per difetto per mantenere un controllo d'identita' diretto.
```

**Le tre mosse, in ordine, e il numero di ognuna:**

1. **`LLAMA_OVERLAP_JOIN_ASYNC=1`, un braccio.** Numero da guardare: **`us_sync`** (oggi 2,200 ms/grafo)
   e **`n_join_async`** (il contatore delle copie accodate, gia' stampato a `:2286`). Se
   `n_join_async` e' ~0, la condizione non e' soddisfatta e la leva e' irraggiungibile — e
   allora il primo lavoro e' capire perche'. Costo: zero righe, una corsa.
2. **La falsifica del §1.4.** Se la catena e' giusta, `us_sync` deve **scalare con il numero di
   confini** e non con la profondita' della finestra. Prova: `LLAMA_OVERLAP_FINESTRA` da 1 a 4
   con `GGML_SCHED_PROFILO=1` e guardare `us_sync` — se resta piatto a 2,2 ms mentre il join
   cala solo del 4%, la diagnosi e' confermata. Se `us_sync` cala, e' sbagliata.
3. **Solo dopo**, ed e' un cantiere nostro non un porto: estendere il ramo `copia_join_async`
   a **tutti** gli ingressi host→GPU, non solo a quelli prodotti dal worker. E' letteralmente
   la parte *(c)* di #20793, ma scritta con l'unica condizione che il nostro ramo gia' usa.
   **La macro `#if defined(GGML_USE_HIP)` non va replicata: e' quella che ha ucciso #20793.**
   Numero: `us_sync` 2,200 → verso zero, cioe' **6,7% del tempo di parete** in palio direttamente,
   piu' — se il §1.4 e' giusto — la finestra che comincia a valere davvero.

**Ammonizione, dal loro stesso verbale:** #20793 ha avuto bisogno di **tre** cure di correttezza
prima di atterrare, e la quarta e' arrivata come revert. Ogni ramo che salta una barriera va
scritto con la condizione che rende la barriera inutile, **nello stesso `if`**.

---

## 2. LE DUE COSE CHIESTE — giudizio indipendente

### 2.1 `c8e03ce81` — PR #26649 — `ggml_build_forward_order`

**VERDETTO: NON SERVE al join. Non allarga la finestra. Non porta, e non riscrivere le 5 righe.**

**Prima la domanda che mi e' arrivata dopo: e' un pezzo della strada gia' fallita?**
**No — e non e' nemmeno su quella strada.** #20793 vive in
`ggml_backend_sched_compute_splits`, cioe' **al momento dell'esecuzione**, e riguarda quando
l'host si blocca. `ggml_build_forward_order` vive in `ggml_build_forward_impl`, cioe' **al
momento della costruzione del grafo**, e riguarda quale flag ha un nodo. Non si toccano.

Il che rende la risposta alla domanda originale **piu' netta, non meno**: dopo il §1 sappiamo
che il collo e' una barriera per confine di split. `_order` non toglie barriere, non toglie
confini, non sposta lavoro. **E' fuori dal cammino critico per costruzione.**

**Cosa cambia, letto nel diff.** Quattro righe in `ggml/src/ggml.c` piu' sei nell'header:
```c
void ggml_build_forward_order(struct ggml_cgraph * cgraph, struct ggml_tensor * tensor) {
    ggml_build_forward_impl(cgraph, tensor, true, false);
}
```
Cioe' letteralmente `_expand` con `compute=false`. Piu' tre chiamate in `tools/mtmd/clip.cpp`
(q/k/v dell'encoder). **Zero** chiamanti fuori da mtmd, in tutto upstream. Noi abbiamo gia'
`ggml_build_forward_impl(..., bool expand, bool compute)` (`ggml.c:7304`) e
`ggml_build_forward_select` (`:7323`): la riscrittura sarebbe banale. **Il problema non e'
scriverla, e' che non muove niente.**

**Perche' NON allarga la finestra — il meccanismo.** `GGML_TENSOR_FLAG_COMPUTE` fa una cosa
sola: ogni backend, in `graph_compute`, **salta** i nodi che non ce l'hanno (verificato uno per
uno: `ggml-cuda.cu:4772`, `ggml-cpu.c:3089`, vulkan, metal, sycl, opencl, blas, zdnn, cann,
webgpu, hexagon). Ma la differenza fra `_order` e `_expand` **sparisce** per qualunque nodo che
finisce comunque calcolato, per via di `ggml_visit_parents_graph` (`ggml.c:7247-7255`): quando
un nodo gia' visitato viene raggiunto con `compute=true`, il flag viene **risalito e riacceso**
su tutti gli antenati che non ce l'hanno.

> `_order(gf, X)` seguito da un `_expand` che raggiunge `X` produce **lo stesso identico grafo**
> di `_expand(gf, X)` fatto subito. Stessa posizione topologica, stesso flag, stessi split.

Nel nostro grafo di decode **tutti i nodi dei due rami sono calcolati**. E il controllo
dell'ordine ce l'abbiamo gia' e lo usiamo gia' (`64745aced`, «l'ordine di esecuzione e' del
grafo, non del sorgente — expand esplicito del ramo GPU»).

**Il bug che #26649 risolve non e' il nostro.** Serve a `ggml_build_forward_select`, dove un
ramo **non selezionato** non deve girare: usare `_expand` come suggerimento d'ordine lo forzava
a girare con input mai caricati (`get_rows` fuori dai bordi nel grafo audio di mtmd). E' una
**cura di correttezza per `_select`**, non una primitiva di scheduling.

**E se qualcuno propone di usarlo per mettere in grafo un ramo che non deve girare** (per
esempio: il cammino tutto-su-GPU e l'ibrido nello stesso grafo, a numero di nodi costante),
va detto che i nodi **senza** `FLAG_COMPUTE`:
1. **prendono comunque un backend** — `ggml_backend_sched_split_graph` non guarda mai
   `FLAG_COMPUTE` (l'unica occorrenza in `ggml-backend.cpp` e' la riga 1192, una **stampa di
   debug**);
2. **creano comunque confini di split** nel passo 5 (`:1487-1562`) — e dopo il §1 sappiamo che
   ogni confine costa **62,5 us di barriera**;
3. **vengono comunque allocati** — `ggml-alloc.c` non contiene la stringa `FLAG_COMPUTE`.

Il ramo morto costerebbe barriere e VRAM e non calcolerebbe niente. **Sfonda il cancello dei
35,2 split per costruzione, e adesso sappiamo anche a quanto al pezzo.**

**Rischio di conflitto:** nullo (funzione nuova, nessun chiamante).
**Numero che dovrebbe muoversi:** nessuno. `join (sched)` resta 24 ms, `us_sync` resta 2,2 ms.

### 2.2 `dbadb68ee` — PR #22789 — allocazione dinamica per gli ingressi degli split

**VERDETTO: NON PORTARE. Corregge un crash irraggiungibile nel nostro assetto, e il suo unico
effetto misurabile vale 30 KB.**

**Cosa cambia, letto nel diff.** Cinque cose:
1. `split->inputs[GGML_SCHED_MAX_SPLIT_INPUTS]` (30 fissi) → `struct ggml_tensor **` con
   `inputs_capacity` e raddoppio a domanda; idem `sched->graph_inputs`.
2. `if (split->n_inputs == GGML_SCHED_MAX_SPLIT_INPUTS)` → `>= split->inputs_capacity` —
   **questa hunk cade a `ggml-backend.cpp:1517`, dodici righe sopra `confine_partizione`
   (`:1529-1548`)**.
3. I due `GGML_ASSERT` (`:1592`, `:1612` da noi) → chiamate di crescita.
4. `memset` sugli slot nuovi dopo il `realloc` degli split (`:1550-1554` da noi).
5. Nuova formula di `graph_size`.

**Perche' il crash non ci riguarda — due cancelli, entrambi chiusi.**

*Cancello A — `sched->graph_inputs`.* E' il percorso che in #22789 fa il botto (l'`ASSERT` senza
via d'uscita). Da noi e' **codice morto**: l'unico posto che lo riempie e' `:1575`, sotto
`if (src->flags & GGML_TENSOR_FLAG_INPUT && sched->n_copies > 1)`, e `n_copies` nasce a `:2324`
come `parallel ? GGML_SCHED_MAX_COPIES : 1` con `parallel = cparams.pipeline_parallel`
(`llama-context.cpp:712`). Il fork e' single-device: **`n_copies == 1`, sempre.** *(Una leva
esiste solo se il suo ramo e' raggiungibile.)*

*Cancello B — `split->inputs`.* L'`ASSERT` a 30 non scatta mai perche' la condizione di
`need_new_split` (`:1515-1525`) e quella che **aggiunge** un ingresso (`:1597-1614`) sono **la
stessa condizione**: `src_backend_id != cur_backend_id && tensor_id_copy(...) == NULL && !supported`.
A 30 ingressi il confine si apre **prima** dell'inserimento. Il 31esimo non esiste.

**Il premio, misurato.** Resta solo `graph_size`:
```
vecchia:  10.507 + 35,2 * 30 * 2 * 1  =  12.619 slot
nuova:    10.507 + Σ ingressi * 2     ≈  ~10.700 slot   (a 2-3 ingressi/split)
```
~1.900 puntatori su due array = **~30 KB**. E `sched->graph.size` **cresce e basta** (`:1644`),
quindi non e' nemmeno una riallocazione ricorrente. La formula nuova e' corretta e stretta
(verificato il conteggio: per split servono `2*n_inputs + (i_end - i_start)` nodi, la somma
torna) — ma essere stretta qui non compra niente.

**Il cancello dei 35,2 split lo passerebbe:** con `capacity` inizializzata a 30 e mai cresciuta
(cancello B), `>= capacity` e' **identica bit-per-bit** a `== 30`. Gli split resterebbero 35,2.
Ma un cancello passato non e' un premio.

**Rischio di conflitto: ALTO e sproporzionato.** Tre hunk su cinque cadono dentro o accanto al
nostro codice: la 2 a dodici righe da `confine_partizione`; la 4 dentro il blocco dove
scriviamo `split->overlap_produttori` (`:1548`, `:1560`); la 3 nel ciclo che
`ggml_sched_split_dipende_dal_worker` (`:1883-1899`) legge — quella funzione **itera
`split->inputs[i]`** e andrebbe riletta per niente.

**Numero: nessuno.** Split 35,2 → 35,2, t/s invariato, 30 KB in meno.

*(La hunk 4, il `memset`, non chiude un bug da noi: ogni campo di uno split nuovo e' scritto a
`:1556-1561`, incluso `overlap_produttori`.)*

---

## 3. DOMANDA 1 — che cosa e' cambiato nello scheduler in un mese

Tre commit. Uno e' un no-op sul `.cpp`. Gli altri due sono al §2. Ma c'e' un quarto commit che
**non e' nella mia fetta di file e invece e' la risposta vera**, perche' cambia l'assegnazione
dei nodi ai backend sul nostro modello — e dopo il §1 sappiamo che ogni confine tolto vale
**62,5 us di barriera** oltre allo 0,94 ms/confine gia' a ledger.

### 3.1 `dee2a846b` — PR #25832 — «adjust logic for offloading ops to weight's backend»
**RACCOMANDATO — l'unico commit del mese che puo' muovere i 35,2 split.**

**Cosa cambia, letto nel diff.** Tre pezzi indipendenti:

*(a) `ggml-backend.cpp` (43 righe, `ggml_backend_sched_backend_id_from_cur`).* La lista delle op
che **non** scelgono il backend dal loro peso passa da `{ROPE}` a `{ROPE, FLASH_ATTN_EXT}`
(«the sinks tensor is too small to choose a backend based on it»), riscritta come flag `allow`.
Per DSV4 e' **probabilmente inerte** (la MLA non ha `sinks`; q/k/v/mask non sono buffer con
`usage == WEIGHTS`), ma e' una riga e va col resto.

*(b) `src/llama-context.cpp`.* Il pin del nodo di fine strato sul device dello strato si estende
da `norm` a `norm || l_last`:
```c
if (ubatch.n_tokens < 32 || full_offload) {
    if (il != -1 && (strcmp(name, "norm") == 0 || strcmp(name, "l_last") == 0)) {
```
*«force the last op of the layer on the specified backend to avoid running it on the backend of
the next layer due to scheduling».*

*(c) `src/models/deepseek4.cpp`.* `cb(inpL, "l_out", il)` → `cb(inpL, "l_last", il)`, e prima
del `ffn_norm` arrivano tre `ggml_build_forward_expand` espliciti su `residual`, `post`, `comb`
— i tre tensori della **hyper-connection**.

**Perche' dovrebbe pagare, agganciato a un numero.** Il gate `ubatch.n_tokens < 32` **e'
raggiungibile**: il decode speculativo gira a 2 token (`--spec-draft-n-max 1`), 2 < 32. La
condizione esiste gia' da noi in forma vecchia (`llama-context.cpp:3016-3017`) e il nostro
`deepseek4.cpp:1455` nomina ancora `l_out`. Effetto: l'ultima op di **ognuno dei 43 strati**
smette di poter finire sul backend dello strato successivo. Ogni volta che oggi ci finisce,
paga un'alternanza di backend = **un confine di split = 62,5 us di barriera** (misurato al §1)
oltre agli 0,94 ms/confine del ledger.

Il pezzo (c) e' ancora piu' interessante: i tre `_expand` espliciti fissano la posizione
topologica di `residual`/`post`/`comb`, **esattamente i tensori della nostra fusione HC**
(`0adb16c64`, +16,5%). Upstream ha scoperto in autonomia che l'ordine di quei tre conta per lo
scheduling.

**Rischio di conflitto: MEDIO.** (a) e (b) applicano puliti. (c) **no**: il nostro
`deepseek4.cpp` e' divergente per la fusione HC (`build_hc_post` a 1310 e 1453, `hc_ffn_pre` a
1319). Il rename e' una riga; i tre `_expand` vanno riposizionati **capendoli**, perche' un
`_expand` nel punto sbagliato sposta l'ordine di esecuzione (lezione gia' pagata: `64745aced`).

**Numero che deve muoversi: `35,2 split per grafo`, e con lui `us_sync`.** Se non si muove, il
commit e' inerte e si butta. Se scende di k, il premio atteso e' `k × 62,5 us` su `us_sync`
piu' quello che il ledger prezza a 0,94 ms/confine. Se **sale**, si butta subito.
`GGML_SCHED_PROFILO=1` stampa gia' `n_splits/n_graphs` e `us_sync`: un braccio, mediana,
`QUIETE=300`.

### 3.2 `153d324bc` — PR #26081 — load-mode auto (no mmap su iGPU)
**NON PORTARE.** Non tocca `ggml-backend.cpp`. Aggiunge `bool mmap_support` alla struct delle
proprieta' del device in `ggml/include/ggml-backend.h`, piu' una riga in **18 backend** e la
logica `load-mode auto` in `llama-model.cpp` — 33 file. Cambia il **default** di mmap, cioe' la
leva sotto `LLAMA_MAPPED_IBRIDO` e la condizione `is_host` che ci e' gia' costata 221.963
`cudaMemcpyAsync` dal fallback dello scheduler. Risolve un problema di iGPU non-Metal.
**Rischio: altissimo. Numero: nessuno.**

### 3.3 Il buco che nessuno tappera'
`ggml-alloc.c`: **zero commit in un mese**. L'esposizione dichiarata di `LLAMA_OVERLAP_FINESTRA`
— «l'allocatore calcola la vita dei tensori assumendo esecuzione SEQUENZIALE» — **non verra'
mai chiusa da upstream**, perche' upstream non esegue mai due split in parallelo. Quel rischio
e' nostro e resta nostro. L'unica riga upstream che ci da' una mano e' al §6.

---

## 4. DOMANDA 2 — cammino speculativo

Nove commit. **Nessuno riduce il costo di verificare 2 token.** Uno solo, in teoria, potrebbe —
ed e' proprio quello che inciampa nella regola gia' pagata due volte.

### 4.1 `dd1ea5243` — PR #25532 — «llama : support multi-output backend sampling»
**LA SOLA LEVA VERA DEL MESE, E LA SCONSIGLIO.**

**Cosa cambia.** +1.282 / −368 righe su 24 file. Nasce `n_outputs_max_per_seq` accanto a
`n_outputs_max` (che abbiamo gia' dalla base; **il `_per_seq` no, verificato**). Il campionatore
di backend — quello che campiona **dentro il grafo, sulla GPU** — gestiva un solo output per
sequenza; ora ne gestisce N. Prima riga del messaggio: *«Enable backend sampling with token
speculation»*. `llama-sampler.cpp` +443, `llama-context.cpp` +309, `llama-graph.cpp` +152.

**Perche' dovrebbe pagare, agganciato a un numero.** I logits tornano oggi sull'host:
`2 × n_vocab × 4 B` per passo. Col campionamento sul backend il token esce gia' campionato dal
grafo e la D2H sparisce: ~1 MB su un canale misurato a 24 GiB/s = **~40 us**, contro 67,7 ms/token.
**Sotto lo 0,1%**, cioe' sotto la deriva del banco (2,4%). Non e' misurabile.

**Perche' lo sconsiglio.** Il campionamento passa da CPU a GPU, e **CPU e GPU arrotondano
diverso** — e' la ragione per cui il cancello SHA vale solo con spec off e `K=0`. Cambia il
token campionato → cambia l'accordo bozza-bersaglio → **cambia p1**. La regola e' esplicita:
*qualunque cosa cambi come il bersaglio ricostruisce il suo stato degrada la bozza — due leve
indipendenti ci sono inciampate la stessa notte.* Qui la leva **e'** quel cambiamento, in forma pura.

**Rischio: MASSIMO** (`llama-sampler.cpp`, `llama-context.cpp`, `llama-graph.cpp`,
`common/speculative.cpp` sono tutti file che abbiamo riscritto).
**Numero che dovrebbe muoversi: `p1` — cioe' il numero che NON deve muoversi.** Costo: giorni.
Premio: 40 us su 67.700. **NON PORTARE.**

### 4.2 `f785fc9ea` — PR #26904 — «spec : update speculative-simple»
**NON PORTARE.** Rimuove i virtuali `need_embd()` / `need_embd_nextn()` e le due funzioni
pubbliche `common_speculative_need_embd[_nextn]()`, piu' `server_slot::need_embd_nextn()`.

Sembra pericoloso — l'unico impl che tornava `need_embd_nextn() == true` era MTP, e il nostro
`draft-dspark` e' un ramo dell'impl MTP (`speculative.cpp:928-1730`). **Ma non lo e':** sia noi
sia upstream chiamiamo gia' `llama_set_embeddings_nextn(ctx_tgt, true, false)` nell'`init`
dell'impl (nostro `:1379`, upstream `:1332`). Il virtuale era un **secondo percorso ridondante**,
e da noi e' gia' **morto**: nessun chiamante di `need_embd_nextn` in `tools/server/`.
Rimozione di codice morto in un file caldo: rapporto rischio/premio peggiore possibile.
Ne salvo **una riga**, al §4.4. **Numero: nessuno.**

### 4.3 `7bd8282c3` — PR #26510 — refactor di `common_speculative_init`
**NON PORTARE.** 16 righe aggiunte, 45 tolte: dieci `if (has_X)` diventano una lambda
`add_config_if_enabled`. **Comportamento identico** (letto riga per riga: stessa lista, stesso
ordine di priorita', stessi gate `ctx_dft != nullptr`). Cade su `speculative.cpp:2435-2480`,
dove c'e' `has_draft_dspark`. Churn puro. **Numero: nessuno.**

### 4.4 `956973c76` — PR #25720 — «Fix crash with draft-simple»
**PORTARE — 3 righe, correttezza, premio zero sul t/s.**
```c
-const int ret = llama_decode(ctx_dft, batch);
+llama_batch batch_dft = batch;
+batch_dft.logits = nullptr;
+const int ret = llama_decode(ctx_dft, batch_dft);
```
Il batch del bersaglio arrivava al contesto bozza con la sua maschera `logits`, che indicizza
posizioni inesistenti li'. Da noi `speculative.cpp:272` ha ancora la riga vecchia. **Non ci
tocca in produzione** (`--spec-type draft-dspark`), ma e' un crash latente in un braccio di
confronto. Insieme, dallo stesso ambito, la guardia di `f785fc9ea`:
```c
if (!ctx_dft) { throw std::runtime_error("draft-simple requires a draft context"); }
```
**Igiene di banco: un crash in mezzo a una campagna costa piu' di tre righe. Rischio nullo.
Numero: nessuno — e' una rete, non una leva.**

### 4.5 Gli altri cinque
- `596a5795b` #25784 «DeepseekV4 MTP + DSpark» — **gia' guardato**: `c91bb3678` ne ha portato
  la riga utile (`n_embd_out` sul bersaglio) e l'ha marcata **INERTE**.
- `84075273c` #25173 «spec: add DSpark» — base del nostro `draft-dspark`, gia' presente e gia'
  divergente.
- `f87067841` #25794 eagle3-v3 per gpt-oss / `62bf73d25` #26841 Muse Glimmer — altri modelli.
- `ddfc2288e` #26165 precedenza di `-md` sui sidecar HF — passiamo percorsi locali. Inerte.

---

## 5. DOMANDA 3 — `a035a8887` #26389, contatori spec-decode in `/metrics`

**VERDETTO: PORTABILE a costo quasi zero, ma NON abbassa il costo di misura. Prenderlo solo se
e quando si tocca il server per altro.**

**Cosa cambia.** 58 righe, tutte additive, su 4 file: quattro accumulatori in `server_metrics`,
la somma in `on_decoded`, il passaggio nel `server_task_result_metrics`, e l'esposizione su
`/metrics` con nomi allineati a vLLM (`spec_decode_num_draft_tokens_total`,
`..._num_accepted_tokens_total`, `..._num_drafts_total`) piu' una serie etichettata per
posizione della bozza.

**I campi di slot su cui poggia li abbiamo gia' tutti, e ne abbiamo di piu':**
```
server-context.cpp:328-331   n_draft_total, n_draft_accepted, n_draft_verif_steps, n_accepted_per_pos
server-context.cpp:315-316   n_draft_accepted_last, n_draft_verif_steps_last   <- NOSTRI
server-context.cpp:636       n_p1_accepted = n_accepted_per_pos[0]             <- NOSTRO, p1 A FINESTRA
```
Il porto sarebbe **puramente additivo**, senza conflitti.

**Perche' NON abbassa il costo di misura**, in ordine di peso:
1. **Stampiamo gia' p1 a finestra** (`:636-681`); upstream espone solo **cumulativi** da inizio
   processo. Un cumulativo su 300 s non separa il regime — *misura il regime, non la media*.
   Il nostro contatore e' **piu' informativo** di quello che il commit aggiunge.
2. Una lettura di `/metrics` e' una **task che passa dalla coda del server**, cioe' si inserisce
   nel ciclo di decode. Su 67,7 ms/token con deriva del 2,4%, uno scrape periodico e' un
   disturbo che il log non ha.
3. Il riferimento **si legge dal LOG**, ed e' gia' a registro. Cambiare sorgente di verita' a
   meta' campagna e' il modo di produrre un altro «+3,8% non attribuito».

**Dove paga davvero, ed e' piccolo:** il cumulativo di fine corsa in forma strutturata evita di
riparsare N log per il ledger. Non retroattivo sulle 349 corse; comodo per le prossime.
**Rischio: nullo. Numero: nessuno — e' uno strumento, non una leva.**

**Un allarme che vale piu' del commit.** `000547513` #26320 corregge un **conteggio gonfiato di
p1** nel replay della bozza scalando `n_accepted` di uno. **Noi abbiamo gia' una cura, ed e'
piu' stretta** (`server-context.cpp:4195-4201`):
```c
// already accepted, so it is accepted 100% by construction -- counting it would report the
// acceptance of the re-evaluation, not of the draft.
if (!slot.spec_replay) {
    slot.update_spec_stats(ids.size() - 1, common_speculative_n_max(...));
}
```
Noi escludiamo **l'intero passo**, denominatore compreso; loro tolgono un token e tengono il
passo. **Definizioni di p1 diverse.** Sovrapporle farebbe muovere p1 **per ragioni contabili**.
→ **NON PORTARE, e nemmeno «per allinearsi».**

---

## 6. DOMANDA 4 — la porta

**`0b14b87d7` #26508 NON cambia la porta. Nessuno script va toccato.**

Il diff e' **sette righe**, tutte in `tools/server/server.cpp`, e sono un avviso:
```c
// TODO: remove this in the future
// check the string to also handle the .sock case
if (string_ends_with(ctx_http.listening_address, ":8080")) {
    SRV_WRN("%s", "NOTICE: server default port will be changed to :9931 in a future release\n");
    SRV_WRN("%s", "        ref: https://github.com/ggml-org/llama.cpp/pull/26508\n");
}
```
Il default e' ancora **8080**. Il cambio e' annunciato «in a future release» e non e' in questi
436 commit.

**Adesso:** niente. **Da NON fare:** portare il commit — aggiungerebbe due `SRV_WRN` in cima a
ogni `server.out`, rumore per un evento che non e' successo.

**La tripwire da mettere:** al prossimo `fetch`, prima di qualunque porto,
`git log upstream/master -- common/arg.cpp | grep -i port`. Se il default si muove davvero, la
porta e' cablata nei nostri script e la corsa **fallira' su un'altra porta** — la stessa classe
di guasto dell'invio ISO-8859-1 (la corsa riesce, sul carico sbagliato).

---

## 7. UNA RIGA FUORI LISTA CHE PAGA — `da5b44862` #25729

**«ggml : set output of view src» — 3 righe in `ggml.c`, e tocca la nostra esposizione vera.**

```c
 void ggml_set_output(struct ggml_tensor * tensor) {
-    tensor->flags |= GGML_TENSOR_FLAG_OUTPUT;
+    for (struct ggml_tensor * cur = tensor; cur != NULL; cur = cur->view_src) {
+        cur->flags |= GGML_TENSOR_FLAG_OUTPUT;
+    }
 }
```
Il nostro `ggml.c:7994` ha ancora la versione a una riga.

**Perche' ci riguarda.** In `ggml-alloc.c`, `FLAG_OUTPUT` significa **«non riusare, non liberare
mai»**: `:645` (riuso) e `:692` (liberazione). Il controllo sul riuso guarda **gia'** anche
`parent->view_src->flags`; quello sulla liberazione guarda **solo** `node->flags`. Una vista
marcata OUTPUT non protegge il suo `view_src`. Questa patch chiude il buco alla sorgente.

E' **il pin di cui ha bisogno `LLAMA_OVERLAP_FINESTRA`**: marcare OUTPUT le uscite dello split
del worker le inchioda per tutto il grafo, ed e' l'unico modo che ggml offre di dirlo — ma
funziona solo se copre i `view_src`, e le uscite del ramo esperti sono viste.

**Il costo, che va detto.** Piu' tensori OUTPUT = meno riuso = **buffer di calcolo piu' grande**,
su 12 GB gia' contesi. Upstream ha dovuto pagare il conto altrove (`llama-sampler.cpp` +57
righe per **evitare** viste negli output).

**Rischio: basso** sulla hunk `ggml.c` (3 righe), ma cambia comportamento a tutti i chiamanti.
**Numero: il buffer di calcolo in MiB deve restare fermo**, e poi `LLAMA_OVERLAP_FINESTRA` deve
poter salire sopra 4 senza corruzione. Dopo il §1 sappiamo pero' che la finestra satura per
**barriere**, non per memoria — quindi questo va misurato **dopo** le mosse del §1.5, non prima.

---

## 8. CLASSIFICA

| # | cosa | premio | rischio | numero che deve muoversi |
|---|------|--------|---------|--------------------------|
| **0** | **`LLAMA_OVERLAP_JOIN_ASYNC=1` + la falsifica del §1.5** — **non e' un porto, e' una leva che abbiamo gia' e che e' spenta** | l'unica cosa in questo audit agganciata al numero grosso | zero righe, una corsa | **`us_sync`** 2,200 ms/grafo (6,7% del parete) e **`n_join_async`**; poi `us_sync` piatto da finestra 1 a 4 = diagnosi §1.4 confermata |
| 1 | `dee2a846b` #25832 | l'unico commit del mese che puo' togliere confini, a **62,5 us di barriera** l'uno (+ 0,94 ms/confine a ledger) su 43 strati | medio — il pezzo `deepseek4.cpp` va rifatto a mano sulla fusione HC | **35,2 split/grafo**; se non scende, si butta |
| 2 | `956973c76` #25720 + guardia `!ctx_dft` di `f785fc9ea` | zero t/s, toglie un crash latente in `draft-simple` | nullo (3 righe) | nessuno — e' una rete |
| 3 | `a035a8887` #26389 | ledger strutturato per le prossime campagne | nullo (58 righe additive) | nessuno — il riferimento resta il LOG |
| 4 | `da5b44862` #25729 (sola hunk `ggml.c`) | chiude il buco del pin per la finestra | basso sul codice, **reale sulla VRAM** | buffer di calcolo fermo, **e solo dopo il §1.5** |

Sotto la #4 non c'e' niente che valga una compilazione.

---

## 9. NON PORTARE — con la ragione

| commit | PR | ragione |
|--------|-----|---------|
| `3fc4e1052` | #20793 | **Gia' nella nostra storia, e gia' revertito** (`86b94708f`, entrambi antenati della base). L'idea e' giusta e vale `us_sync`; l'implementazione era rotta: la guardia che salta la barriera (`iface.cpy_tensor_async != NULL`, capacita') non era la stessa che rende la copia asincrona (`copy_from_host`, macro di build) → su HIP si finiva nel fallback a **due** sync per ingresso. **Da rifare nostra, con una condizione sola** (§1.5), non da ripescare. |
| `c8e03ce81` | #26649 | `_order` = `_expand` con `compute=false`. Per un nodo che finisce calcolato il flag viene **riacceso** (`ggml.c:7247-7255`): grafo identico, split identici. Unico chiamante upstream = `mtmd/clip.cpp`. Non e' nemmeno sulla strada di #20793: quella e' l'esecuzione, questa e' la costruzione. E i nodi senza `FLAG_COMPUTE` **creano confini lo stesso** (`split_graph` non legge quel flag) e **vengono allocati lo stesso** (`ggml-alloc.c` non lo nomina): usarlo per un ramo morto costa 62,5 us a confine per zero calcolo. |
| `dbadb68ee` | #22789 | Crash irraggiungibile: `graph_inputs` e' sotto `n_copies > 1` e siamo single-device (`n_copies = 1`, `:2324`); `split->inputs` e' protetto perche' `need_new_split` ha **la stessa condizione** dell'inserimento. Premio residuo = `graph_size`, ~30 KB. Tre hunk su cinque dentro `confine_partizione` e il ciclo che il join legge. |
| `153d324bc` | #26081 | Cambia il **default** di mmap, cioe' la leva sotto `LLAMA_MAPPED_IBRIDO` e `is_host`. ABI della struct device, 18 backend, 33 file, per un problema di iGPU non-Metal. |
| `dd1ea5243` | #25532 | Sposta il campionamento da CPU a GPU con la speculazione accesa. CPU e GPU **arrotondano diverso** → cambia i token accettati → **degrada la bozza**: la regola gia' pagata due volte, in forma pura. Premio aritmetico ~40 us su 67.700, sotto la deriva del banco. 1.282 righe su tre file riscritti da noi. |
| `f785fc9ea` | #26904 | Rimozione di codice **gia' morto da noi** (nessun chiamante di `need_embd_nextn` in `tools/server/`; il meccanismo vero e' `llama_set_embeddings_nextn` all'init, che gia' condividiamo). Conflitto garantito su `common/speculative.cpp`. Ne salvo solo la guardia `!ctx_dft`. |
| `7bd8282c3` | #26510 | Refactor a comportamento **identico** (letto riga per riga). Cade su `has_draft_dspark`. |
| `000547513` | #26320 | **Attivamente dannoso.** Abbiamo gia' una cura **piu' stretta** (`server-context.cpp:4195-4201`: escludiamo l'intero passo di replay, denominatore compreso). Sovrapporle cambia la **definizione** di p1 e fa muovere il numero per contabilita'. |
| `0b14b87d7` | #26508 | **Non cambia la porta.** Sette righe di `SRV_WRN` quando l'indirizzo finisce in `:8080`. Aggiungerebbe rumore a ogni avvio. |
| `f87067841`, `62bf73d25`, `ddfc2288e` | #25794, #26841, #26165 | Altri modelli / download automatico dei sidecar HF. Inerti: passiamo percorsi locali. |
| `0c4fa7a98` | #25472 | Cambia la ritenzione dei checkpoint (`id_task`, sfratto dei troppo vicini, `near_prompt_end`). Tocca `checkpoint_min_step`, la manopola di `-cms 32` (288 s → 2,7 s). Il nostro cammino e' gia' divergente (`:3668`, `:3722`). **Non entrare senza un banco di prefill dedicato.** |

---

## 10. LE QUATTRO COSE DA RICORDARE

1. **Il collo non e' la finestra, sono le barriere.** Ogni ingresso di ogni split apre con un
   `cudaStreamSynchronize` (`:2024`, `:2039`, `:2054`, `:2073` → `ggml-cuda.cu:3167`). Con 35,2
   split, host e GPU camminano in **lockstep**, e la misura lo conferma: `2.200 us / 35,2 = 62,5 us`
   di attesa per confine, cioe' **la coda GPU e' quasi sempre vuota**. `finestra = 4` non mette
   1,00 ms di lavoro in volo: ne mette 0,25 ms, quattro volte di seguito. **Ecco il +4%.**
2. **Upstream ha gia' provato a togliere quelle barriere (#20793) e l'ha buttato in quattro
   giorni — ma per un difetto di scrittura, non di hardware.** La guardia che salta la sync non
   era la stessa che rende la copia asincrona. Da noi quella scrittura corretta **esiste gia'**
   (`copia_join_async`, `:2014-2033`) **ed e' spenta di difetto.**
3. **Il numero da tenere davanti mentre si porta qualunque cosa di questa fetta e' `35,2 split
   per grafo`**, e adesso ha un prezzo: **62,5 us di barriera a confine**, oltre agli 0,94 ms
   che il ledger gia' gli attribuisce. L'unico commit del mese che puo' muoverlo e' `dee2a846b`
   — nella parte che **non** e' in `ggml-backend.cpp`.
4. **`ggml-alloc.c`: zero commit in un mese.** L'esposizione della finestra sull'allocatore non
   verra' mai chiusa da upstream, perche' upstream non esegue mai due split in parallelo.

---

*Nessun binario compilato, nessun server avviato, nessuna patch applicata, nessun cherry-pick.
Tutte le righe citate sono state lette nel diff di upstream o nel sorgente in `D:\llama-overlap`.*
