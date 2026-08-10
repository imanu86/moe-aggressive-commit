# 40 — LA VRAM A FASI: il buffer di calcolo sa gia' crescere da solo, e restringerlo non richiede una riga di ggml

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, HEAD `6e0da6d31`,
working tree. **Niente compilato, niente server avviato, nessuna misura mia**:
codice letto riga per riga, patch scritta e lasciata sull'albero non committata.
Marcatura: [MISURATO] = log/spazzata in cassa, [CONTATO] = codice letto,
[DEDOTTO] = aritmetica su misure, [IPOTESI] = da falsificare con la misura indicata.

> **NON COMPILARE `babd15238`.** Quel commit ha congelato la revisione 2, che
> contiene **due difetti** corretti solo nel working tree: l'ubatch di decode a 8
> (avvelena ogni braccio dell'1,8%) e la formula di capienza che al livello 2
> chiede piu' slot di quanti ce ne stiano. Si compila **l'albero**, non l'HEAD.
> Le due righe incriminate, verificabili in un secondo:
> `git show babd15238:src/llama-context.cpp | grep "atoi(b) : 8"` e
> `git show babd15238:ggml/src/ggml-cuda/cache-esperti.cu | grep "slot_base + (int)"`.

**Revisione 3**, dopo tre giri di calibrazione del coordinatore. Cosa e' cambiato
rispetto alla prima stesura, perche' due delle correzioni erano difetti veri e non
scelte:

1. **L'ubatch di decode era 8, ora e' 64.** Difetto: sotto 64 il decode peggiora
   dell'1,8% [MISURATO], e ogni braccio sarebbe stato avvelenato in silenzio.
2. **La formula di dimensionamento della cache era sbagliata al livello 2.**
   Faceva `slot_base + byte_liberati/byte_slot`; ma al livello 2 quei byte non
   sono un guadagno netto — sono in parte la cache stessa che torna. A `-ub 2048`
   chiedeva 768 slot dove ce ne stanno ~340. Ora si parte dal **libero misurato**
   e **il difetto e' non crescere**: i megabyte restano liberi finche' qualcuno
   non chiede esplicitamente di scommetterli sulla capienza.
3. **Il valore del meccanismo non e' piu' ipotesi**: `-ub 512` costa **1,6% al
   decode** (12,99 contro 13,21) perche' lascia 467 MiB liberi, appena sopra la
   soglia di strozzamento. Il meccanismo recupera quei **2,2 ms/ciclo**, e ora il
   cancello che lo misura ha un bersaglio numerico invece di una speranza.

Aggiunte in questo giro: **ricarica calda** della residenza (idea dell'utente),
dietro la sua leva; l'aggancio per il **transito a gradini**, con scritto cosa
manca; e il **backbone dichiarato fuori portata**, con la ragione.

## L'esito in sette righe

1. **Il cantiere che temevi non esiste.** Il verso "cresci" del buffer di calcolo
   e' gia' automatico e gia' in produzione: quando un grafo non ci sta,
   `ggml_backend_sched_alloc_splits` sincronizza, richiama `ggml_gallocr_reserve_n`
   sul grafo VERO e riprova (`ggml-backend.cpp:1734-1757`) [CONTATO]. E il verso
   "restringi" esiste pure lui, in `llama_context`: `sched_reserve()` ricostruisce
   lo scheduler da zero (`llama-context.cpp:675`) e con lui distrugge il gallocr e
   i suoi buffer. **Zero righe di ggml toccate.** La tua opzione 1 (ri-riservare
   con `ggml_backend_sched_reserve`) non funziona da sola — `ggml-alloc.c:920`
   rialloca se e solo se `new_chunk_size > cur_chunk_size` — ma non serve toccarla.
2. La patch e' **~620 righe aggiunte su 5 file, tutti LF puliti**, dietro
   `LLAMA_VRAM_A_FASI` (difetto 0). A leva spenta: una `getenv` in piu' al primo
   `decode()` e un salto. Nient'altro.
3. **Il valore e' misurato, non ipotizzato**: a `-ub 512` il decode perde l'1,6%
   perche' i 467 MiB liberi sono appena sopra la soglia dei ~400. Il meccanismo
   restituisce ~654 MiB al decode e deve riprendersi quei 2,2 ms/ciclo. **Cancello
   2, con bersaglio 13,15-13,25 contro i 12,99 di oggi.**
4. **Il difetto non scommette.** La cache torna alla sua capienza di sempre e i
   megabyte restano liberi. Al livello 2 questo significa che la fase di decode ha
   **lo stesso buffer, la stessa cache e lo stesso margine del riferimento a
   ub 64** — bit per bit la configurazione di oggi, con in piu' un prefill a ubatch
   grande. Dare quei byte alla capienza e' una scommessa, e si chiede a voce alta.
5. **La separazione capienza/margine resta il cancello che decide**, ed e'
   riscritta per distinguere **tre** esiti. Con un avvertimento nuovo che viene
   dalla tua misura: **il braccio "capienza" NON va girato al pavimento del
   margine**, o confonde capienza e strozzamento — dettaglio in §5.
6. **Ho trovato una bugia dello strumento prima che mordesse**: la transizione
   passa da `sched_reserve()` → `synchronize()`, che CONSUMA `n_queued_tokens` e
   azzera `t_compute_start_us` (`llama-context.cpp:916-935`). Messo il gancio dopo
   i cronometri — dove l'avevo messo io la prima volta — il prompt sarebbe stato
   contato con tempo ~0: **prefill spettacolare e falso**, esattamente sul numero
   che la leva vuole muovere.
7. **Il muro resta C = 5,8-7,3 ms/token**, e dopo questo lavoro e' l'87% del
   prefill. Non lo tocco (e' dell'altro agente): in §7 c'e' quello che il mio fit
   sa e quello che NON sa, perche' gli serve sapere la differenza.

---

## 1. Le tre cose che ho letto e che hanno ridotto il cantiere

### 1a. Il buffer di calcolo cresce GIA' da solo, a runtime [CONTATO]

`ggml_gallocr_alloc_graph` (`ggml-alloc.c:1051`) fallisce se il grafo non entra e
il gallocr ha piu' di un buffer. Il chiamante non lo lascia cadere:

    ggml-backend.cpp:1734-1757
      if (backend_ids_changed || !ggml_gallocr_alloc_graph(...)) {
          for (int i = 0; i < sched->n_backends; i++) ggml_backend_synchronize(...);
          ggml_gallocr_reserve_n(sched->galloc, &sched->graph, ...);   // sul grafo VERO
          if (!ggml_gallocr_alloc_graph(...)) { errore }
      }

**Il caso "arriva un ubatch piu' grande di quanto riservato" e' gia' gestito, con
la sincronizzazione giusta, in produzione, da sempre.** Le tre riserve del
costruttore (`llama-context.cpp:702-743`) esistono per evitarlo, non perche' sia
illegale.

### 1b. Il verso "restringi" non richiede ggml, richiede `sched_reserve()` [CONTATO]

`ggml_gallocr_reserve_n_impl` e' a crescita sola (`ggml-alloc.c:914-924`:
`if (new_chunk_size > cur_chunk_size) realloc = true`), quindi ri-riservare col
grafo di decode — che il costruttore fa gia', riga 724 — non restituisce niente.
Ma `sched_reserve()` fa `sched.reset(ggml_backend_sched_new(...))` (riga 675):
distrugge lo scheduler, quindi il gallocr, quindi i `vbuffer`.

**Da qui la forma della patch**: la fase decide con quale `n_ubatch`
`sched_reserve()` deve riservare, e lo chiama.

### 1c. La cache esperti e' nostra e si ridimensiona senza rischi nuovi [CONTATO]

`ggml_cuda_cache_esperti_free` azzera gia' `cache = {}` e `attiva = false`, ferma
il thread di servizio e libera l'anello (`cache-esperti.cu:632-671`); il registro
delle basi (`runtime->reg`) **sopravvive**, quindi `forse_init` sa rifare tutte le
derivazioni. Il ridimensionamento e': dump → salva mappa → free → nuova capienza →
`forse_init` → ricarica calda.

E il grafo NON cambia forma fra le fasi: `supports_op` guarda
`percorso_gpu_richiesto()` (`ggml-cuda.cu:2009`), che legge solo l'ambiente. Se
cambiasse forma cambierebbero gli split, e il confronto fra bracci sarebbe sporco.

---

## 2. Le quattro trappole che sembravano gratis

| trappola | perche' morde | come e' pagata |
|---|---|---|
| **riuso del grafo** (`can_reuse`) salta `sched_alloc_graph`: i puntatori restano vecchi | i buffer si sono mossi sotto | `sched_reserve()` ricrea `gf_res_prev`: il riuso e' impossibile per costruzione |
| **CUDA graph**: il confronto delle proprieta' e' corto-circuitato dal solo `cgraph->uid` (`ggml-cuda.cu:3145-3150`) | replay con puntatori morti = corruzione muta (audit 11) | `split_graph` riassegna un uid nuovo a **ogni** split (`ggml-backend.cpp:1710`); la ricostruzione lo forza. ~50 ms (audit 34 §5), una volta per richiesta |
| **kernel in volo** mentre si liberano 2,3 GiB | use-after-free su device | `synchronize()` esplicito in testa a `vram_a_fasi()` |
| **i cronometri** | `sched_reserve()` → `synchronize()` consuma `n_queued_tokens` | il gancio sta PRIMA di quelle due righe |

L'ultima l'ho scoperta **sbagliando**: era gia' scritta nel modo che mente.

---

## 3. Il diff, commentato

Il diff sta su **due strati**, perche' la revisione 2 e' stata committata mentre
scrivevo la 3. Cumulativo contro `6e0da6d31`, l'HEAD del mandato — **e' questo il
lavoro**:

```
430  1  ggml/src/ggml-cuda/cache-esperti.cu
 29  0  ggml/src/ggml-cuda/cache-esperti.cuh
 16  0  ggml/src/ggml-cuda/ggml-cuda.cu
188  2  src/llama-context.cpp
 20  0  src/llama-context.h
```

Incrementale contro `babd15238` — **sono le due correzioni piu' la ricarica
calda**, e senza questo strato i cancelli misurano la cosa sbagliata:

```
224 28  ggml/src/ggml-cuda/cache-esperti.cu    (capienza dal libero misurato + ricarica calda)
 11  5  ggml/src/ggml-cuda/cache-esperti.cuh   (contratto delle leve nuove)
 16 11  src/llama-context.cpp                  (ubatch di decode 8 -> 64)
  1  1  src/llama-context.h
398 294 audit/40-vram-a-fasi.md
```

- **`cache-esperti.cu`** — otto campi nuovi nel runtime; `forse_init` legge
  `fase_slot` se e' ≥ 0 e l'ambiente altrimenti (**la riga −1**); `fase_byte_slot`
  registrato PRIMA della `cudaMalloc` della slab, cosi' sopravvive a una init
  fallita; `cache_esperti_zavorra()`; i due kernel della ricarica calda
  (`kern_ricarica` e `kern_ricarica_verifica`) con le funzioni host che li
  guidano; e `ggml_cuda_cache_esperti_fasi()`, che sceglie la capienza dal libero
  misurato, fa dump→salva→free→init→ricarica, ha la rete di ripiego sulla base e
  stampa il ledger. Il grosso delle righe e' commento.
- **`cache-esperti.cuh` (+30/−4)** — la dichiarazione e il contratto delle leve.
- **`ggml-cuda.cu` (+16)** — il wrapper `ggml_backend_cuda_cache_esperti_fasi` (che
  fa `ggml_cuda_set_device` prima di allocare) e la sua voce in `get_proc_address`,
  stesso canale gia' usato da `prepara` e `oracolo_avanza` perche' `src/` non
  linka CUDA.
- **`llama-context.h` (+20)** — cinque membri e la dichiarazione di `vram_a_fasi`.
- **`llama-context.cpp` (+183/−2)** — le **due righe modificate** sono le sole due
  che leggevano `cparams.n_ubatch` per dimensionare una riserva (`sched_reserve()`
  riga 666, `memory_update()` riga 905): ora leggono `n_ubatch_reserve` se e' >0.
  **`cparams.n_ubatch` non viene toccato**, quindi `llama_n_ubatch()` continua a
  dire il valore di riga di comando e il server non vede niente — importante,
  perche' con quel numero decide il rifiuto dei prompt non spezzabili
  (`server-context.cpp:3170`).

**Fine riga**: scansione byte diretta dei cinque file — `CR = 0`, nessun BOM,
`git ls-files --eol` da' `i/lf w/lf`.

**Nota che ti riguarda oltre questo lavoro**: `ggml-alloc.c`, `ggml-alloc.h`,
`ggml-backend.cpp`, `ggml-backend.h` sono **CRLF nel working tree e LF
nell'indice** (`i/lf w/crlf`); `git diff` tace solo per la cache di stat.
**Chiunque tocchi uno di quei quattro file vedra' il file intero nel diff.** E' la
trappola del tuo mandato, gia' armata in albero. Il primo disegno ci passava.

---

## 4. Come funziona, e perche' la soglia e' 64

**Il confine** e' in `decode()`, prima dei cronometri: `n_tokens > soglia` e'
prefill, `<=` e' decode. Solo il bersaglio (`ctx_other == nullptr`), solo causale.

**La soglia e l'ubatch di decode sono lo stesso numero**, e la regola che li unisce
e' una sola: si passa al buffer grande **esattamente quando il prompt
richiederebbe piu' di una passata su quello piccolo**. Col modello a passate del §7
(`T = ceil(N/U)·K(U) + C·N`) si dimostra da sola:

| prompt | a ub 64 | a ub 512 | chi vince |
|---|---|---|---|
| 53 token (turno breve) | 1 passata, K(64) ≈ 2,7 s | 1 passata, K(512) = 4,0 s | **ub 64** |
| 65 token | 2 passate ≈ 5,4 s | 1 passata ≈ 4,0 s | ub 512 |
| 400 token | 7 passate ≈ 21,2 s | 1 passata ≈ 6,4 s | ub 512, di 15 s |

**Il difetto 64 e' misurato** [MISURATO]: `ub 64 → 13,21 t/s` (ms/ciclo 141,0,
colpi 54,2%) contro `ub 2 → 12,88` (143,6, colpi 54,1%). Sotto 64 si perde l'1,8%,
fuori dal rumore (0,8%), e i 59 MiB liberati non arrivano dove servono — **i colpi
non si muovono di un decimo**. *La prima stesura aveva 8: era un difetto.*

| livello | prefill | decode | cosa compra |
|---|---|---|---|
| `0` (difetto) | — | — | il binario di oggi |
| `1` | buffer pieno + cache base | buffer stretto + margine restituito | ~654 MiB al decode: i **2,2 ms/ciclo** di §5 |
| `2` | buffer pieno + cache **spenta** | buffer stretto + margine restituito | +2.288 MiB al prefill → `-ub` fino al tetto della VRAM (~2.700), **e la fase di decode identica al riferimento a ub 64** |

Leve d'appoggio, inerti a difetto: `LLAMA_VRAM_A_FASI_UB` (difetto **64**),
`LLAMA_VRAM_A_FASI_SLOT` (capienza fissata a mano), `LLAMA_VRAM_A_FASI_MARGINE`
(cresci finche' restano tanti MiB liberi; **0 = non crescere**),
`LLAMA_VRAM_A_FASI_SLOT_MAX`, `LLAMA_VRAM_A_FASI_MIN`,
`LLAMA_VRAM_A_FASI_CALDO` (§6), `LLAMA_VRAM_ZAVORRA`.

Il ledger di ogni transizione:

```
vram-a-fasi: fase=decode livello=2  cache 0 -> 339 slot (+339, +2288 MiB)
             riciclati 2897 MiB dal buffer  VRAM libera 1254 MiB  [58,1 ms, cambio n. 3]
vram-a-fasi: ricarica CALDA 331 slot su 331 salvati (2234 MiB dalla RAM bloccata)
             [126,4 ms]  incoerenze dove/chi = 0
llama_context::vram_a_fasi: fase=decode livello=2 ubatch riserva=64
             buffer di calcolo 3001,20 -> 104,30 MiB (-2896,90)  [71,3 ms]
```

Piu' il dump completo della cache **prima** di ogni free: colpi e buchi restano
una serie storica per fase.

---

## 5. IL PREMIO, ora che e' misurato: 2,2 ms/ciclo piu' la domanda sulla capienza

I due riferimenti [MISURATO, coordinatore], prompt lungo, 1.200 token:

| | t/s | ms/ciclo | mean_len | p1 | colpi | VRAM libera |
|---|---|---|---|---|---|---|
| **R64** `-ub 64` | 13,21 | 141,0 | 1,86 | 0,86470 | 54,2% | 1.256 |
| **R512** `-ub 512` | **12,99** | 143,2 | 1,86 | 0,86025 | 53,4% | **467** |

`mean_len` identico e p1 quasi identico: non e' lotteria, **il ciclo si allunga
davvero**. E il colpevole si vede: 467 MiB, appena sopra la soglia dei ~400.

**Quindi il meccanismo ha un bersaglio numerico**: restituire ~654 MiB al decode e
riprendersi quei 2,2 ms/ciclo. Non "forse serve".

### Il quadrato, e un avvertimento che viene dalla tua misura

I tre punti storici, con la VRAM libera ricostruita [DEDOTTO:
`libera = 1.256 − (slot − 339)·6,75` a ub 64]:

| slot | t/s | p1 | VRAM libera |
|---|---|---|---|
| 339 | 12,93 | 0,868 | 1.256 |
| 380 | 12,19 | 0,770 | 979 |
| 448 | 12,76 | 0,885 | **520** |

Non monotona in nessuna colonna. E il dato di stamattina (339 → 354 → 370: colpi
49,4 → 51,9 → 52,1% **monotoni**, ms/ciclo 142,0 → 143,5 → 143,1 **piatti** entro
l'1%) dice che la capienza migliora i colpi e **non si converte in tempo** —
quarto meccanismo della campagna con questa firma, dopo prefetch, AcceptMoE e
rollback.

**L'AVVERTIMENTO, ed e' la correzione che la tua misura di ub 512 impone al mio
disegno precedente.** Avevo proposto il braccio "capienza" a ~448 slot con ~506 MiB
liberi. **Sbagliato**: 506 e' dentro la zona in cui la 3060 si strozza — il braccio
avrebbe confuso *piu' capienza* con *meno margine*, cioe' esattamente l'errore che
il quadrato deve eliminare. Il braccio capienza va girato **sopra la soglia**, e la
spesa di margine va limitata a quel che si puo' spendere restando fuori.

Con ~1.121 MiB liberi dopo la transizione a ub 512 e un pavimento prudente a 800:

| braccio | comando (oltre a `-ub 512`) | slot | VRAM libera |
|---|---|---|---|
| **R512** riferimento | leva spenta | 339 | 467 |
| **A** margine restituito | `LLAMA_VRAM_A_FASI=1` (difetto: non cresce) | 339 | ~1.121 |
| **B** capienza | `LLAMA_VRAM_A_FASI=1 _MARGINE=800` | ~386 | ~800 |
| **C** controllo | `LLAMA_VRAM_A_FASI=1 _SLOT=339 LLAMA_VRAM_ZAVORRA=321` | 339 | ~800 |

- **A contro R512** — **il cancello del valore**: stessa capienza, stesso prefill,
  l'unica variabile sono i 654 MiB restituiti. Atteso **13,15-13,25**, cioe' il
  recupero dei 2,2 ms/ciclo. *Se A resta a 12,99-13,05, il meccanismo non
  consegna il margine e c'e' qualcosa che non ho visto.*
- **B contro C** — stesso margine (~800), **l'unica variabile e' la capienza**
  (339 contro ~386, +14%). E' la misura pulita mai possibile prima.
- **A contro C** — stessa capienza, **l'unica variabile e' il margine**
  (~1.121 contro ~800). Chiude l'altro asse e dice **dove sta il ginocchio**: fra
  467 (che costa 1,6%) e 1.256 (che va bene) oggi non sappiamo niente.

| esito | firma | cosa si fa in produzione |
|---|---|---|
| **paga la capienza** | B > C, A ≈ C | `_MARGINE=<il pavimento vero>`: i MiB alla cache |
| **paga il margine** | A > C, B ≈ C | **il difetto**: i MiB restano liberi. E' gia' questa patch, ed e' l'unica configurazione che oggi non esiste — a `-ub 512` quei 654 MiB sono ostaggio del buffer per tutta la generazione |
| **non paga nessuno** | A ≈ B ≈ C entro ±0,15 t/s **ma A > R512** | il meccanismo vale i 2,2 ms/ciclo e basta: si tiene il difetto e si chiude la domanda sulla capienza. **Quinta conferma che su questa macchina la residenza non e' la leva** |

Il prior onesto: la capienza non si e' mai convertita in tempo, quattro volte su
quattro. **L'esito 3 e' il piu' probabile — ed e' comunque un risultato**, perche'
A > R512 e' gia' quasi garantito dalla fisica del margine che tu stesso hai appena
misurato due volte (467 MiB costano l'1,6%; sesta conferma dello strozzamento).

**Due numeri da guardare alla prima corsa, che sono essi stessi dati:**

1. **Il residuo non recuperato.** Fra ub 64 e ub 512 la VRAM libera cala di 789 MiB
   [MISURATO: 1.256 → 467], ma il buffer del bersaglio ne spiega ~654. **~135 MiB
   scalano con `-ub` da qualche altra parte, e il meccanismo NON li recupera**
   perche' ricostruisce solo lo scheduler del bersaglio. La riga di log da' il
   numero vero. Se e' ~135 e' tollerabile; se cresce piu' che linearmente con `ub`,
   e' quello a fissare il tetto del livello 2, non la cache.
2. **Il costo delle transizioni**, gia' nelle righe di log in millisecondi. Atteso:
   60-150 ms di riserva + ~126 ms di ricarica calda (o ~0 e poi ~339 buchi sparsi
   se la ricarica e' spenta), due volte per richiesta.

---

## 6. La ricarica calda: la mappa, non i byte

**Idea dell'utente, e il pezzo che serve c'era gia'.** I pesi degli esperti non si
muovono mai: vivono nei 74.304 MiB di RAM bloccata, e quello in VRAM e' solo una
copia. Quindi non si salvano i byte, si salva **quali** esperti erano residenti —
`chi[]`, 339 interi, 1,4 KiB — e si ricopiano in blocco dalla stessa RAM:
**2.289 MiB a 18,4 GiB/s = ~124 ms prevedibili** invece di ~339 buchi sparsi sui
primi token della risposta, che e' il momento peggiore per averli.

Dietro `LLAMA_VRAM_A_FASI_CALDO` (difetto **spenta**), cosi' i cancelli 1-3 girano
senza di lei e lei ha il suo. Come funziona:

- **prima della free** (`cache_esperti_salva_mappa`): `chi[]` scende a host; gli
  slot **in transito** si scartano — i loro byte non sono mai atterrati, e
  dichiararli residenti sarebbe una copia che non esiste;
- **dopo la init** (`cache_esperti_ricarica_calda`): le stesse tre
  `cudaMemcpyAsync` per esperto che fa il thread di servizio a ogni buco, poi
  `kern_ricarica` scrive le tabelle **nello stesso ordine con cui `kern_prenota`
  promuove un transito atterrato** (`chi` senza bit di transito, `dove` che punta
  allo slot, `installato = 1`). L'ordine di stream garantisce che nessuna domanda
  veda residente uno slot ancora vuoto.
- `usato = 0` e `ultimo = 0` sono la scelta **conservativa e dichiarata**: si
  ripristina la residenza, non la protezione dallo sfratto. Ripristinarla
  cambierebbe i primi 339 sfratti rispetto a una cache scaldata davvero, e il
  braccio misurerebbe anche quello.

**Il cancello di correttezza e' dentro il codice, non nel rapporto.**
`kern_ricarica_verifica` controlla che per ogni slot ricaricato
`dove[chiave(slot)] == slot`, e stampa il numero di incoerenze. Se non fosse zero,
la cache servirebbe i byte di un esperto per un altro **senza che niente si
lamenti**: e' la classe di difetto peggiore che questo codice possa avere, e ora e'
un numero. *Atteso: `incoerenze dove/chi = 0`. Qualunque altro valore: si spegne
`_CALDO` e si rimisura.*

**Effetto collaterale utile**: al livello 1 la crescita della cache non costa piu'
la residenza. Prima ogni ridimensionamento la buttava; ora il ciclo
salva → free → alloc(N) → ricarica la conserva, e il braccio B non paga piu' una
cache fredda che il braccio C non paga.

### Il transito a gradini: dove sta l'aggancio, e cosa manca

L'aritmetica funziona: una passata di prefill a ub 512 dura ~4 s, la ricarica ne
occupa 124 ms sullo stream DMA mentre la GPU calcola. **Ci sta dentro con un
fattore 30.**

Ho lasciato l'aggancio nella **firma**: `cache_esperti_ricarica_calda(runtime, da,
quanti)`. Oggi c'e' un gradino solo (`0, 0` = tutto); spezzarlo e' un cambio nel
chiamante, non una riscrittura.

**Ma il chiamante non puo' essere `llama_context`, ed e' il pezzo che manca.**
Perche' il gradino funzioni bisogna sapere **quale passata di prefill e'
l'ultima**, e llama_context strutturalmente non lo sa: vede un batch per volta e
non sa quanti altri ne arriveranno per lo stesso prompt. **Lo sa il server**
(`server-context.cpp`: ha `slot.task->n_tokens()` e `slot.prompt.n_tokens()`, e
calcola gia' `near_prompt_end` alla riga 3600). Serve una riga di preavviso da li'
verso il contesto — una funzione pubblica tipo
`llama_vram_a_fasi_preavviso(ctx, n_token_restanti)` — e a quel punto la fase puo'
cominciare a rientrare un gradino per passata. **Non l'ho aggiunta**: tocca l'API
pubblica e il server, ed e' la (c) della tua scala di valore, dopo (a) e (b).

C'e' anche un vincolo fisico da sapere prima di provarci: **al livello 2 la slab
non esiste durante il prefill** (i suoi 2,3 GiB sono nel buffer). Quindi non si
puo' pre-copiare dentro una slab che non c'e': il gradino vero e' *l'ultima passata
a ubatch ridotto*, che libera lo spazio e lascia i 4 secondi di calcolo su cui
nascondere la DMA. E' fattibile, ma e' un disegno, non un parametro.

---

## 7. Il modello a passate, e dove sta il muro

I quattro punti della spazzata, in ms/token [MISURATO]:

    ub  64 → 44,3    ub 128 → 33,5    ub 256 → 21,6    ub 512 → 13,7

Il modello e' `T = ceil(N/U)·K(U) + C·N`, con `K` costante solo dove l'unione e'
satura (U(256)≈255, U(512)=256; a ub 64 U vale ~130-205 e la legge 1/ub non vale
ancora). Sui due punti saturi:

    K/256 − K/512 = 21,6 − 13,7   →   K = 4.045 ms per passata   →   C = 5,8 ms/token

**K si convalida da solo**: `74.304 MiB / K = 18,4 GiB/s`, la banda zero-copy che
crediamo di avere. E il modello **predice una misura che non e' stata usata per
costruirlo**: 6.510 token a ub 512 → 13 passate → 90,4 s previsti contro 89,3
misurati, **1,2% di scarto** [convalida del coordinatore]. Con banda 20-22,5 GiB/s,
C ∈ **[5,8; 7,3] ms/token**.

Sul carico vero — un follow-up da 10.000 token, cioe' modificare una pagina HTML
appena scritta, dove il delta del turno include la risposta precedente:

| ub | passate | tempo | t/s | di cui C |
|---|---|---|---|---|
| 512 | 20 | 139 s | 72 | 58 s |
| 2.700 (cache evacuata) | 4 | 74 s | 135 | 58 s |
| 7.700 (anche backbone) | 2 | 67 s | 149 | **58 s = 87%** |

**Il muro non e' la VRAM, e' C.** E dopo il livello 2 diventa l'87% del tempo di
prefill.

### Per l'agente che scompone C: cosa il mio fit dice e cosa NON dice

- **Dice**: esiste un termine per token, indipendente da `ub`, di 5,8-7,3 ms, e la
  sua stima e' *residuale* — e' tutto cio' che non e' trasporto degli esperti.
- **NON dice di cosa e' fatto.** I candidati con la loro aritmetica sono in
  audit 38 §2 (densi in VRAM ~0,6-1,0 ms/token; attenzione ~0,9-1,5; chiusure
  CSA/LID/HCA + quantize q8_1 + mm_ids_helper ~0,3-1,0; sottomissione WDDM
  ~0,3-0,8): **sommano a 2,1-4,3, cioe' meta' o due terzi di C.** Il resto non ha
  ancora un nome, ed e' li' che c'e' qualcosa da trovare.
- **Due avvertenze sul numero**: (a) il fit e' su **due punti**, e il terzo (ub 128)
  ci cade male (37,4 previsti contro 33,5) perche' li' l'unione non e' satura — un
  fit a due punti resta un fit a due punti, e il cancello 5 lo falsifica in una
  corsa; (b) a contesto lungo C **non** e' 5,8 ms: cresce coi punteggi
  dell'indexer (~6,7 MiB × ub per strato CSA, audit 38 §6).

### Il backbone: perche' NON l'ho fatto

Non e' pigrizia ed e' d'accordo con la tua scala: aggiunge il 10% e vale 7 secondi
su 74. Ma c'e' anche una ragione strutturale che vale la pena mettere a verbale:
**i 7,4 GiB densi non sono in un buffer che questo meccanismo possa toccare.**
Stanno nei buffer del *modello*, allocati al caricamento, e i tensori del grafo ci
puntano dentro. `sched_reserve()` non li vede nemmeno: ricostruisce lo scheduler,
non il modello. Sfrattarne una parte a runtime vuol dire rifare l'allocazione dei
tensori del modello e rimappare i puntatori che ogni grafo si porta dietro — **un
cantiere in `llama-model`, non un parametro di questo**. Legittimo, ma e' un altro
progetto, e va deciso sapendolo.

---

## 8. La sequenza dei cancelli, in ordine

**1 — IDENTITA'.** Leva spenta, configurazione di riferimento.
Atteso: **SHA `CF2DEEA06E90`** e **12,83-12,92 t/s**, le sette riproduzioni. A
livello 0 il codice nuovo e' una `getenv` e un salto.
*Se lo SHA si muove qui, si ferma tutto.*

**2 — IL VALORE, contro un numero misurato.** `-ub 512`, `LLAMA_VRAM_A_FASI=1`.
Riferimento **R512 = 12,99 t/s** [MISURATO]. Atteso: **13,15-13,25**, cioe' il
recupero dei 2,2 ms/ciclo, con `VRAM libera ~1.121` nella riga di log. Lo SHA puo'
restare `CF2DEEA06E90`: le fasi non cambiano un'aritmetica.
*Sotto 13,05 il meccanismo non consegna il margine. Sopra 13,25, o e' rumore o R512
era sfortunata: si rifa'.*

**3 — CAPIENZA CONTRO MARGINE.** I quattro bracci del §5, n≥3 con
`LLAMA_SPEC_DRAFT_TOPK=1`. Soglia di lettura **±0,15 t/s** (rumore 0,8% ≈ 0,10).
I tre esiti sono in tabella li'. **B va girato a `_MARGINE=800`, non al pavimento**,
o confonde capienza e strozzamento.
Sanita' interna: i `colpi` di B devono essere ≥ quelli di C.

**4 — LA RICARICA CALDA.** Braccio 2 con `LLAMA_VRAM_A_FASI_CALDO=1`.
Atteso: `incoerenze dove/chi = 0` (**cancello duro**: qualunque altro valore
significa residenza non fidata, si spegne e si rimisura), `ricarica CALDA ~330 slot
[~124 ms]`, e i colpi dei primi 50 token della risposta **≥ 45%** invece del
~0-10% di una cache fredda. Sul t/s totale di 1.200 token l'effetto atteso e'
piccolo (**+0,1-0,2%**): il valore e' la latenza percepita, non il throughput, e va
letto sulla finestra iniziale.

**5 — IL PREFILL AL TETTO, livello 2.** Spazzata `-ub 1024 / 2048 / 2700`
(**fin dove il caricamento regge**, non fino a 512), `LLAMA_VRAM_A_FASI=2`, prompt
6.510. Attesi [DEDOTTO]: 7 passate → 66 s; 4 → 54 s; 3 → 50 s. Pavimento: se
ub 2048 sta sopra **70 s**, il modello a passate e' sbagliato e si scrive il numero.
Il braccio dice anche **fin dove si puo' salire** prima che il residuo di §5 chiuda
il margine.
Correttezza (mai esercitata a ub ≥ 256, audit 38 §6):
`LLAMA_DSV4_COMPRESS_DEBUG=1` → chiusure CSA `= n_tokens/4` e HCA `= n_tokens/128`
**esatte**, accettazione e p1 invariati, `divergenze replay = 0`. Lo SHA fra ub
diversi **non si applica**.

**6 — IL CARICO BREVE NON DEVE PAGARE NIENTE.** Sessione con turni da 30-60 token.
Atteso: **zero righe `vram_a_fasi` dopo la prima risposta** — stanno sotto la
soglia 64 e la fase non cambia. Se compaiono, ogni turno paga ~230 ms per niente.

**7 — NESSUNA CRESCITA NON VOLUTA.** `llama_context::vram_a_fasi` compare **al
massimo due volte per richiesta** e il buffer di decode resta stretto.

---

## 9. Cosa ho lasciato indietro, e perche'

- **`ggml-alloc.c` non toccato.** Il primo disegno aggiungeva
  `ggml_gallocr_libera_buffer` (~20 righe). Buttato: `sched_reserve()` fa gia' la
  stessa cosa con codice gia' esercitato, e quei file sono CRLF in albero (§3). Se
  servisse una transizione **piu' economica** di una ricostruzione completa, quella
  e' la strada e costa ~20 righe. Il cancello 2 dice se serve.
- **Il transito a gradini**: aggancio lasciato nella firma, manca il preavviso dal
  server (§6). E' un disegno, non un parametro.
- **Il backbone**: fuori portata strutturale, non solo di priorita' (§7).
- **La scomposizione di C**: e' dell'altro agente. Gli ho lasciato in §7 quello che
  il fit sa e quello che non sa.
- **`encode()` senza gancio**: DSV4 non usa il ramo encoder.
- **La bozza (DSpark) non toccata**: contesto, scheduler e cache suoi; il gancio la
  esclude su `ctx_other != nullptr`. Un secondo giro della stessa leva.
- **Nessuna sonda U** (audit 38 §8.2): il fit da' gia' 18,4 GiB/s, cioe' l'angolo
  "banda degradata" — quindi la leva **staged-copy** resta aperta e vale ancora
  ×1,3-1,5 sul termine K. Dopo la separazione, e' il candidato piu' serio rimasto.
- **Nessun cancello automatico sul contenuto**: i cancelli 1 e 2 chiedono uno SHA, e
  vale la regola di casa — **si contano i caratteri prima di leggere l'hash**.
  `E3B0C44298FC` e' lo SHA della stringa vuota e ha gia' fatto passare due cancelli
  su corse che non avevano prodotto niente.

## 10. In quattro righe

Il buffer di calcolo sa gia' crescere da solo e `llama_context` sa gia'
distruggerlo: la VRAM a fasi non era un cantiere in ggml, erano 183 righe in
`llama-context.cpp` piu' un ridimensionamento della cache che e' codice nostro.
Con la calibrazione il valore ha smesso di essere un'ipotesi: `-ub 512` costa
l'1,6% al decode perche' lascia 467 MiB liberi, e il meccanismo restituisce i
654 MiB che li causano — cancello 2, bersaglio 13,15-13,25 contro 12,99. Il
difetto non scommette: i megabyte restano liberi, e darli alla capienza e' una
domanda separata che ora si puo' finalmente porre da sola. Il resto e' C: 5,8-7,3
ms/token che nessun ubatch tocca, l'87% del prefill dopo questo lavoro, e il
fronte di qualcun altro.
