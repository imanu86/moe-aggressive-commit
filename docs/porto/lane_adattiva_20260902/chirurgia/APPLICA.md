# LANE ADATTIVA — due patch, ordine di applicazione e verifiche (2/9/2026)

Chirurgo in sola scrittura sullo scratchpad. **Nessun file di `D:\llama-subtract` e'
stato toccato**: gli originali sono stati copiati in `orig\` in sola lettura, le
modifiche vivono in `mod1\` (stadio 1) e `mod\` (stadio 1+2). Mai `git` in
`D:\llama-*`.

Marcatore di ogni riga nuova: `// lane-adattiva (2/9)` — distinguibile da
`// chirurgo19 (1/9)` della «terza mano».

---

## 0. Base

`BASE.txt` porta mtime, dimensione e SHA256 dei sette originali. I tre file CUDA
sono quelli delle **19:24 del 1/9**, cioe' il sorgente del binario `18444E20`:

| file | mtime | SHA256 (primi 16) |
|---|---|---|
| `ggml/src/ggml-cuda/cache-esperti.cu` | 2026-09-01 19:24:37 | `5274EF2DF689FB20` |
| `ggml/src/ggml-cuda/cache-esperti.cuh` | 2026-09-01 19:24:41 | `F34A31FC6BC70F2B` |
| `ggml/src/ggml-cuda/ggml-cuda.cu` | 2026-09-01 19:24:13 | `C10ADFBDCF87674E` |
| `src/llama-graph.cpp` | 2026-08-15 17:51:29 | `2355850B13F71451` |
| `ggml/src/ggml-cpu/ggml-cpu.c` | 2026-08-15 11:57:27 | `2A23DCF218F7E941` |
| `ggml/src/ggml-backend.cpp` | 2026-08-25 01:50:48 | `CE552E4D08D4E101` |
| `ggml/include/ggml.h`, `ggml/src/ggml.c`, `ggml/src/ggml-impl.h` | (invariati da settimane) | vedi BASE.txt |

**Tutti i file dell'albero sono CRLF.** I patch sono stati generati con GNU
`diff -u` (byte-fedele, i CR sono dentro il patch), non con `git diff`, che sotto
`core.autocrlf=true` produce un patch LF che poi **non applica**. Applicare cosi':

```
cd D:\llama-subtract
patch -p1 --binary < ...\lane_adattiva_1_contatori_guardia.patch
patch -p1 --binary < ...\lane_adattiva_2_leva.patch
```

(`git apply` funziona solo con `core.autocrlf=false`; e comunque **mai git in
`D:\llama-*`**.) Provato: i due patch in sequenza su una copia pulita di `orig\`
danno file **byte-identici** a `mod\` su tutti e nove i file.

---

## 1. Ordine

1. **`lane_adattiva_1_contatori_guardia.patch`** (267 righe, **4 file**) — PRIMO BRACCIO.
   Uscita **bit-identica per costruzione**: nessuna forma cambia, nessuna env
   nuova, nessun valore calcolato cambia. Cancello: G1 `AD3D3770…FE11` 3/3 e
   `voci fuori tabella == 0`.
2. **`lane_adattiva_2_leva.patch`** (716 righe, 6 file) — si applica **SOPRA** il primo.
   **Rigenerato il 2/9 contro l'albero di OGGI**, cioe' con lo stadio 1 gia'
   dentro (verificato: i nove file dell'albero vivo sono byte-identici a
   `mod1\`). Dry-run stretto sull'albero vivo: `patch -p1 --binary --fuzz=0
   --dry-run` **esce 0 su tutti e sei i file**, e l'albero resta intatto.
   A `LLAMA_OVERLAP_K_MIN_NONRES` assente o 0 resta anch'esso bit-identico
   (vedi §4e); a 1 = sonda; a 2 = decide.

---

## 2. File e righe toccate

### Stadio 1 — contatori + guardia

**QUATTRO file. `ggml/src/ggml-impl.h` NON viene toccato** (decisione di regia:
quell'header e' incluso da tutto l'albero e una riga li' ricompilerebbe l'intero
backend CUDA per un contatore — vedi D1).

| file | riga (orig) | intervento |
|---|---|---|
| `ggml/src/ggml-backend.cpp` | 33 | blocco `extern "C"` con le due dichiarazioni `GGML_API` + contatore atomico + due definizioni (+35) |
| `ggml/src/ggml-backend.cpp` | 2789 | stampa `sched-worker-lane: voci fuori tabella=` (+14) |
| `ggml/src/ggml-cpu/ggml-cpu.c` | dopo 16 | dichiarazione `extern` **locale** `GGML_API void ggml_mmid_fuori_tabella_inc(void);` (+9) |
| `ggml/src/ggml-cpu/ggml-cpu.c` | 1631 | **la guardia**: salta + azzera + conta (+34, di cui 28 di commento) |
| `ggml/src/ggml-cuda/cache-esperti.cuh` | dopo 419 | quattro campi contatore (+25) |
| `ggml/src/ggml-cuda/cache-esperti.cu` | 83 | `CACHE_ESPERTI_CONTATORI` **62 → 65** (+4 di commento) |
| `ggml/src/ggml-cuda/cache-esperti.cu` | dopo 3031 | assegnazione slot 55, 62, 63, 64 (+5) |
| `ggml/src/ggml-cuda/cache-esperti.cu` | dopo 7312 | **conteggio `lane_cpu_residenti`** + **bilancio delle destinazioni** (62/63), blocco separato in coda (+42) |
| `ggml/src/ggml-cuda/cache-esperti.cu` | 8413-8419 | stampa dei quattro sulla riga `tre vie router/massa` (+21 / −4) |

### Stadio 2 — la leva

| file | riga (dopo stadio 1) | intervento |
|---|---|---|
| `ggml/include/ggml.h` | 2425-2429 | quinto parametro `lane_adattiva` + contratto (+15 / −1) |
| `ggml/src/ggml.c` | 5380-5393 | quinto parametro, `n_righe`, `params[3]` (+16 / −3) |
| `ggml/src/ggml-cuda/cache-esperti.cuh` | 605-610 | firma del lanciatore: `int lane_adattiva` (+6 / −1) |
| `ggml/src/ggml-cuda/cache-esperti.cu` | 6919-6926 | **firma** del kernel: `template <bool planner_trace, bool adattiva = false>` + argomento `int lane_ad` (+12 / −2) |
| `ggml/src/ggml-cuda/cache-esperti.cu` | dopo il blocco dello stadio 1 | **`if constexpr (adattiva) { … }`**: blocco C, −1 sulle cedute, `perm_inv`, tre contatori, bigezione (+96) |
| `ggml/src/ggml-cuda/cache-esperti.cu` | 7755, 7798-7814 | parametro del lanciatore + **quattro istanziazioni** (+50 / −16) |
| `ggml/src/ggml-cuda/ggml-cuda.cu` | 3305-3315 | legge `op_params[2]` e lo passa (+8 / −1) |
| `src/llama-graph.cpp` | 18 | `#include <cstdio>` (+1) |
| `src/llama-graph.cpp` | dopo 1868 | **la leva**: env a valore, **rifiuto sul contesto BOZZA**, rifiuto con `K < 1`, testimone stderr (+55) |
| `ggml/src/ggml-cuda/cache-esperti.cuh` | dopo `k_adattivo` | **`int lane_conta`** (+16) |
| `ggml/src/ggml-cuda/cache-esperti.cu` | dopo il blocco SCUDO_TRANSITO | lettore `LLAMA_CACHE_ESPERTI_LANE_CONTA` a valore + testimone `lane_conta=1` (+17) |
| `ggml/src/ggml-cuda/cache-esperti.cu` | testa del kernel | `__shared__ unsigned int lane_acc[4]` + azzeramento con `__syncthreads()` **prima di ogni uscita divergente** (+14) |
| `ggml/src/ggml-cuda/cache-esperti.cu` | coda del kernel | i **tre livelli**: GUARDIA per riga con RIPIEGO, AUDIT in shared con una atomica per lancio, statistica dietro `c.lane_conta` |
| `ggml/src/ggml-cuda/cache-esperti.cu` | riga `tre vie` | **due formati**: esteso a `lane_conta=1`, altrimenti **il formato storico verbatim** |
| `src/llama-graph.cpp` | 1886, 1910 | i due `ggml_cache_esperti_partiziona` col quinto argomento (+3 / −2) |
| `src/llama-graph.cpp` | 1918-1923 | `ids_gpu` a sei colonne **solo a livello 2** (+13 / −2) |

---

## 3. Verifiche statiche (4a-4e del mandato)

### 4a — righe ESISTENTI di `kern_partiziona` modificate: **0 nel corpo**

- **Stadio 1: 0 rimozioni in tutto il kernel — ne' nel corpo ne' nella firma.**
  Le 4 rimozioni del patch stanno a riga 83 (la `#define`) e 8414-8419 (la
  `fprintf` del dump), **fuori** dal kernel (che va da 6910 a 7313).
- **Stadio 2: 2 rimozioni dentro l'intervallo del kernel, ed entrambe sono la
  FIRMA** — `template <bool planner_trace>` e la riga di chiusura degli argomenti
  `… unsigned long long * div) {`. **Zero righe del CORPO.** Le altre 25 rimozioni
  sono la firma del lanciatore e le due istanziazioni (esplicitamente ammesse dal
  mandato), piu' `ggml.h`, `ggml.c`, `ggml-cuda.cu`, `llama-graph.cpp`.
- Quindi: la scrittura dei −1 a `:7307`, `perm_inv` a `:7311`, il bilancio
  `:7289-7302`, il ramo `k_cpu == 0` e ogni altra istruzione restano **invariati**,
  e nell'istanziazione `<planner_trace, false>` il blocco della leva **non si
  compila**. La piattaforma di riproduzione bit-esatta del difetto n.1 non si
  sposta.

### 4b — siti che leggono `CACHE_ESPERTI_CONTATORI` o dimensionano `colpi[]`

Grep su tutto l'albero vivo (`ggml/`, `src/`, `common/`, `tools/`): **quattro
soli siti, tutti in `cache-esperti.cu`, tutti espressi con la macro**, quindi si
adeguano da soli al 65:

| riga | sito | esito |
|---|---|---|
| 83 | `#define CACHE_ESPERTI_CONTATORI` | portato a 65 |
| 2979 | `cudaMalloc(&cache.colpi, CONTATORI * sizeof(uint64_t))` | 496 → 520 byte, automatico |
| 3216 | `cudaMemset(cache.colpi, 0, CONTATORI * …)` | automatico |
| 8206-8207 | `uint64_t v[CONTATORI]` + `cudaMemcpy(v, …, sizeof(v))` | automatico |

Altri lettori di `colpi` che **non** dipendono dalla taglia: `:3737` `cudaFree`;
`:8186` `cudaMemcpy(out, colpi, 2*sizeof(uint64_t))` (legge i primi due).
Offset massimo gia' in uso: **61**. Gli offset relativi (`c.lane_cpu + N`) arrivano
al massimo a `+16` = `colpi + 48`. Slot **55 confermato libero**.

> **Nota (non un difetto, ma va saputo):** `:8474-8476` fa
> `cudaMemcpy(r, cache.lane_cpu, 24 * sizeof(unsigned long long))`, cioe' legge
> `colpi + 32 .. colpi + 55`. **`r[23]` e' esattamente il nostro slot 55**: da ora
> conterra' `lane_cpu_residenti` invece di zero. **`r[23]` non viene stampato da
> nessuna parte** (si stampano solo r[3], r[5..16]), quindi nessuna riga di log
> cambia — ma chi in futuro leggesse `r[23]` come «indice libero» sbaglierebbe.

### 4c — memset: stride e tipo

`GGML_TENSOR_BINARY_OP_LOCALS` (ggml.h:320-326) espande, per il **dst**,
`GGML_TENSOR_LOCALS(int64_t, ne, dst, ne)` e `GGML_TENSOR_LOCALS(size_t, nb, dst, nb)`:
quindi in `ggml_compute_forward_mul_mat_id` **`ne0 == dst->ne[0]`,
`nb1 == dst->nb[1]`, `nb2 == dst->nb[2]`** (i nomi `nb10..nb13` sono quelli di src1,
non collidono).

L'indirizzo scelto e' **lo stesso identico** che usa `ggml_compute_forward_mul_mat_id_one_chunk`
a `:1514`: `dst->data + (i1*nb1 + i2*nb2)` con `i1 = id` (`:1502`) e
`i2 = i12 = row_mapping.i2 = iid1` (`:1500`, `:1503`). Nel loop di raggruppamento
quei due sono proprio `id` e `iid1`. ⇒ `memset((char*)dst->data + id*nb1 + iid1*nb2, …)`
colpisce **esattamente la riga che `one_chunk` non scrivera' piu'**.

Tipo: `GGML_ASSERT(nb0 == sizeof(float))` a `:1560` (prima del sito), `float * dst_col`
a `:1514`, `memcpy(&dst_col[…], tmp, …*sizeof(float))` a `:1520` ⇒ **dst e' F32 e
contiguo in dim 0**, quindi `ne0*sizeof(float)` e' la lunghezza giusta della riga.
Promozioni: `id` (int) e `iid1` (int64_t) per `size_t` ⇒ `size_t`; `ne0` (int64_t)
per `sizeof(float)` ⇒ `size_t`. Nessun overflow, nessun segno.

### 4d — la stampa del worker non dipende dalla leva

La riga `sched-worker-lane: voci fuori tabella=%llu` sta **fuori** da
`if (ggml_sched_profilo_attivo())` e **fuori** da `if (n > 0)`, e non guarda
nessuna variabile della lane adattiva. Il contatore stesso vive in ggml-base e
viene incrementato da `ggml-cpu.c` sempre, a leva accesa o spenta.
L'unica condizione residua e' `sched->worker != NULL`, che e' **la stessa
condizione sotto cui esiste la lane CPU**: senza worker non esiste `ids_cpu`,
quindi non esiste un −1 su questo cammino.

### 4e — con `LLAMA_OVERLAP_K_MIN_NONRES` assente o 0: nessun cammino nuovo

Un solo lettore in tutto l'albero: `src/llama-graph.cpp:1882`. La catena e':

```
getenv -> lane_adattiva (0/1/2)  ->  ggml_cache_esperti_partiziona(..., lane_adattiva)
                                      -> op_params[2]
                                         -> ggml-cuda.cu:3312  lane_ad
                                            -> cache-esperti.cu:7908  lane_ad
                                               -> scelta del template + guardie a runtime
   lane_adattiva ==2 ?  -> larghezza di `part` (ggml.c:5396) e vista ids_gpu (llama-graph:1975)
```

A **0** (assente, o qualunque valore diverso da 1 e 2 — il lettore e' **a valore**,
`(liv == 1 || liv == 2) ? liv : 0`):

- `ggml.c:5396` `n_righe = selected->ne[1]` ⇒ **stesso tensore di prima**;
- `params[3] = {strato, k_cpu, 0}`: i primi 8 byte identici e il terzo int a 0,
  che e' gia' il contenuto di `op_params` (azzerato alla creazione del tensore)
  ⇒ **`op_params` byte-identico**, quindi anche il riuso/confronto dei grafi;
- `llama-graph:1975` prende il ramo `else` ⇒ **`ids_gpu` identica**;
- `cache-esperti.cu:7908` `lane_ad = 0` ⇒ istanziazione `<planner_trace, false>`
  ⇒ **`if constexpr (adattiva)` non esiste nel binario**;
- nessun `fprintf` di testimone (la lambda esce a `return 0` prima).

⇒ **nessun cammino nuovo raggiungibile.**

A **1** (sonda): forme invariate (`n_righe` non raddoppia, `ids_gpu` invariata);
si compila `<_, true>` e girano solo i contatori `lane_ad_cpu_vive` /
`lane_ad_gpu_colonne` con `vive = k_cpu`. Lo SHA resta identico.

---

## 4. Dove il disegno NON era applicabile, e cosa ho fatto

### D1 — `ggml-backend.cpp` **non puo'** chiamare `ggml-cpu` (BLOCCANTE)

Il disegno §B.6 mette l'esposizione in `ggml/include/ggml-cpu.h`
(`ggml_cpu_mmid_fuori_tabella()`) e la lettura in `ggml-backend.cpp`.
**Non linka**: `ggml/src/CMakeLists.txt:283` fa
`target_link_libraries(${backend} PRIVATE ggml-base)` — la dipendenza e' a senso
unico, `ggml-cpu.dll` → `ggml-base.dll`. Un simbolo di ggml-cpu chiamato da
ggml-base e' irrisolto al link.

**Fatto:** il contatore vive **in ggml-base** (`ggml-backend.cpp`). `ggml-cpu.c`
**incrementa** (verso permesso), `ggml-backend.cpp` **definisce, legge e stampa**.

**Le dichiarazioni NON stanno in `ggml/src/ggml-impl.h`** (seconda decisione di
regia, adottata): quell'header e' incluso da tutto l'albero e una riga li'
ricompilerebbe l'intero backend CUDA — decine di minuti — per un contatore.
Invece:

- `ggml-backend.cpp` porta un blocco `extern "C" { GGML_API void
  ggml_mmid_fuori_tabella_inc(void); GGML_API uint64_t
  ggml_mmid_fuori_tabella_get(void); }` seguito dalle definizioni senza
  decorazione, che ereditano linkage C e `dllexport` dalla dichiarazione — lo
  stesso idioma con cui `ggml_aligned_malloc` e' dichiarato una volta e definito
  in `ggml.c`;
- `ggml-cpu.c` porta **una riga** `GGML_API void
  ggml_mmid_fuori_tabella_inc(void);` accanto agli include.

Verificato: `GGML_API` **e' gia' visibile in `ggml-cpu.c` senza ggml-impl.h**,
via `#include "ggml.h"` (riga 15); il file e' C, quindi la dichiarazione basta,
senza `extern "C"`. In ggml-cpu (che non definisce `GGML_BUILD`) `GGML_API` vale
`__declspec(dllimport) extern`, in ggml-base `__declspec(dllexport) extern`.
**Provato a banco**: `ggml-cpu.s1.obj` contiene il thunk
`__imp_ggml_mmid_fuori_tabella_inc`, `ggml-backend.cpp.s1.obj` contiene le due
definizioni — l'import/export attraverso le DLL e' esattamente quello previsto.
**Cambiano tre sole TU: nessun altro file dell'albero cambia intestazione.**

### D2 — su MSVC non esiste un'atomica a 64 bit in `ggml-cpu.c`

Il disegno usa `atomic_fetch_add_explicit(&ggml_mmid_fuori_tabella, 1, …)` su un
`uint64_t`. In `ggml-cpu.c` sotto MSVC, `atomic_int` e' **`volatile LONG`** (32
bit) e `atomic_fetch_add_explicit` prende `(atomic_int*, LONG, memory_order)`
(`ggml-cpu.c:111-146`): un `uint64_t` non compila.
**Fatto:** conseguenza di D1 — l'atomica sta in `ggml-backend.cpp`, che e' C++ e
ha gia' `<atomic>`: `std::atomic<uint64_t>`. `ggml-cpu.c` chiama una funzione,
non tocca l'atomica. E l'atomica **serve davvero**: la mul_mat_id CPU e'
raggiunta sia dal threadpool principale sia dal thread del worker overlap.

### D3 — `k_vivo = min(k_cpu, n_miss)` e' **sbagliato in produzione**

Il pseudo-diff §B.6 conta `n_miss` e assume che «le prime `k_vivo` colonne della
permutazione siano i non-residenti». Vero **solo se `perm` e' ordinata per
classe**. Ma a `:7265-7275`, quando `compatta && pesi_validi`, `perm` viene
**riordinata per peso zero** — e `LLAMA_ACCEPTMOE_COMPATTA` e' acceso nel
lanciatore di produzione (`p1b_conf.ps1:106`). Dopo quel riordino una colonna di
classe 0 puo' stare dopo una residente, e `min(k_cpu, n_miss)` cederebbe la
colonna sbagliata: la CPU terrebbe un residente e la GPU riceverebbe un miss ⇒
**una copia PCIe nuova**, cioe' esattamente il canale che ha ucciso `r54_k1`, e
il cancello «`di cui RESIDENTI = 0` esatto» **non passerebbe**.
**Fatto:** decisione **colonna per colonna**: si cede `j < k_cpu` **sse
`chiave[perm[j]] != 0`**. Cosi' «ceduta ⟺ residente ⟺ contata in
`lane_cpu_residenti`» e il cancello e' vero per costruzione. `k_vivo` resta
definito come `k_cpu − cedute` (per i contatori), non come una soglia.

### D4 — il blocco C perdeva la compattazione a peso zero di AcceptMoE

Il pseudo-diff scrive `g[j] = … : riga[perm[j]]` senza riprodurre la regola di
`:7307` (`-1` quando `compatta && peso == 0`). Sarebbe il rischio 3 del §B.7,
lasciato aperto: la GPU ricaricherebbe colonne **matematicamente nulle**.
**Fatto:** il blocco C applica la **stessa identica regola** di `:7307` a tutte
le colonne che la GPU calcola davvero (le cedute e le sue). La compattazione
continua a valere.

### D5 — il duplicato per le colonne che la CPU tiene

Il disegno scrive `riga[perm[k_cpu]]`. E' un id valido, ma `perm[k_cpu]` puo'
essere proprio una colonna che la compattazione ha portato a `-1`: duplicarla
**rimetterebbe in domanda** un esperto che AcceptMoE aveva tolto, cioe' una
possibile copia nuova.
**Fatto:** si usa **il primo id non negativo gia' scritto nel blocco C**, cioe'
un esperto che la GPU sta calcolando comunque in quella riga ⇒ zero domanda
nuova, per costruzione. Ripiego a `riga[perm[k_cpu]]` solo nel caso degenere in
cui l'intera riga sia compattata a `-1`.

### D6 — la larghezza di `part`: **righe, non colonne**

Il disegno porta `part` da `[2·ne0, n_tok]` a `[3·ne0, n_tok]`. **Non si puo'**
senza toccare il corpo del kernel: `:7305` fa
`int32_t * o = out + (size_t) t * 2 * ne0;`, e con la riga larga 3·ne0 quell'indirizzo
sarebbe sbagliato per ogni `t > 0`. Cambiarlo violerebbe «0 righe del corpo
modificate»; lasciarlo com'e' e riscrivere dopo sarebbe una **corsa fra thread**
(i thread scriverebbero l'uno sopra l'altro, e non c'e' `__syncthreads()` legale
li' — si e' gia' oltre due uscite divergenti).
**Fatto:** `part` diventa **`[2·ne0, 2·n_tok]`**. Le prime `n_tok` righe restano
A|B **con il passo di riga invariato** (quindi `o = out + t*2*ne0` resta corretto,
riga non toccata); il blocco C sta nelle righe `[n_tok, 2·n_tok)`, indirizzo
`out + (n_tok + t)*2*ne0`. La vista GPU diventa
`ggml_view_2d(part, ne0, n_tokens, part->nb[1], n_tokens*part->nb[1])`: stesso
passo di riga, offset di `n_tokens` righe. Costo: `part` raddoppia — 288 byte
invece di 144 a `n_tokens = 3`.

### D7 — il rifiuto con `LLAMA_OVERLAP_K < 1` e il testimone stanno nell'host

`cache_leva_rifiutata` e' `static` in `cache-esperti.cu` e non e' visibile da
`llama-graph.cpp`, dove la leva viene letta (sorgente unica della verita').
**Fatto:** `fprintf(stderr, "cache-esperti: LEVA RIFIUTATA LANE_ADATTIVA -- …")`
con la stessa formulazione, piu' `#include <cstdio>` (non c'era; `LLAMA_LOG_*`
sarebbe filtrabile dal callback del server — la lezione del chirurgo 16).

### D12 — TRE LIVELLI: la guardia si lega al MECCANISMO, non allo strumento

**Correzione di disegno (zen-morse, accolta).** La D11 legava *tutto* a
`LANE_CONTA`, e sbagliava: a `LANE_CONTA=0` la leva sarebbe girata in produzione
con bilancio e biiezione muti, cioe' **senza il rilevatore del guasto §44 che la
leva stessa puo' introdurre**. Una guardia si lega al meccanismo che protegge,
mai allo strumento che misura.

**Tre livelli, e due nomi distinti per le due cose che prima erano una sola.**

| livello | che cos'e' | quando gira | costo |
|---|---|---|---|
| **1** | la guardia di `ggml-cpu.c` (salta, azzera, conta) | **SEMPRE** | un confronto per id |
| **2a — GUARDIA** | biiezione di `perm_inv` **per riga**, + **RIPIEGO** | **con la leva ≥ 2, sempre**, indipendente da `LANE_CONTA` | ≤ 36 confronti in registri, **zero atomiche** |
| **2b — AUDIT** | bilancio `cpu_vive + gpu_colonne == ne0 × partizioni` | **con la leva ≥ 1, sempre** | shared + **una atomica globale per lancio** |
| **3** | statistica (`lane_cpu_residenti`, bilancio a leva spenta) | dietro `LANE_CONTA=1` | ciclo + atomica **per riga** |

#### GUARDIA — dove sta, e perche' li'

**Per riga, dentro `kern_partiziona`, sul risultato appena calcolato e PRIMA che
gli id e `perm_inv` diventino visibili a un qualunque consumatore.** Righe di
`mod/ggml/src/ggml-cuda/cache-esperti.cu`:

| riga | che cosa |
|---|---|
| **7445-7477** | **LA GUARDIA**: costruisce i sei valori che `perm_inv` *sta per* prendere e ne verifica la biiezione con una maschera a 6 bit in registri. Legge solo `perm[]` e `chiave[]` — array locali, nessuna memoria globale, nessuna atomica |
| **7478** | `const bool cede = !rotta;` — la decisione |
| 7482 | `int32_t * g = out + …` (puntatore, nessuna scrittura) |
| **7489** | **prima scrittura** di `g[]` (blocco C) |
| 7505 | `g[j] = dup` (colonne che la CPU tiene) |
| **7514** | `o[j] = -1` (colonne cedute) — solo `if (cede)` |
| **7520** | `o[ne0 + perm[j]] = …` (riscrittura di `perm_inv`) |

La guardia è **33 righe sopra la prima scrittura**. I lettori di questi id sono
kernel successivi sullo stesso stream: nessuno può aver letto. Un controllo a
valle — nel dump, o in un aggregato di fine lancio — arriverebbe dopo la
pubblicazione e **non potrebbe più correggere niente**: sarebbe un referto, non
una guardia.

**Il RIPIEGO.** Con `cede == false` il predicato di cessione degenera in
`tiene(j) = (j < k_cpu)`, cioè il cammino **senza cessione** sulle forme larghe:
nessun `-1` nelle colonne CPU (il blocco `if (cede)` non gira), blocco C con le
colonne CPU duplicate, `perm_inv` quella della leva spenta. **L'uscita resta
corretta**: è il §44 evitato, non solo contato. Contare e basta lascerebbe uno
strato con meno di sei esperti e un'uscita sbagliata ma plausibile.

#### AUDIT — aggregato, e non può innescare ripieghi

`cpu_vive + gpu_colonne` accumulati **in shared** (`lane_acc[0..1]`) e riversati
**una volta sola per lancio** col pattern «ultimo thread arrivato»
(`mod:7533-7534`, flush a `mod:7547`). Non è una difesa per riga: quando lo si
potrebbe leggere, la riga è già pubblicata. È il cancello di **fine corsa**
«CEDERE ≠ ELIMINARE», con fail-loud se la somma non è un multiplo esatto delle
partizioni.

#### Perche' NIENTE atomiche per riga nel livello 2

Il ~1,5% dello stadio 1 veniva **proprio** dal ciclo e dall'atomica per riga sul
cammino piu' caldo. Il livello 2 quindi: la GUARDIA sta tutta in registri (zero
memoria), e l'AUDIT accumula in shared e fa **una** `atomicAdd` globale per
contatore per lancio.

**La riduzione senza barriere.** Gli accumulatori si azzerano **in testa al
kernel** (`mod:7434-7437`), l'unico punto in cui tutti i thread del blocco sono
ancora vivi — sotto ci sono due uscite divergenti (`t >= n_lav` e il ramo
`k_cpu == 0`) e dopo una di quelle una `__syncthreads()` si impicca (regola di
casa sulle barriere «sullo stesso sito»). Il riversamento in fondo **non usa
barriere**: `__threadfence_block()` ordina i contributi, poi l'ultimo thread ad
arrivare (`atomicAdd(&lane_acc[3],1)+1 == n_lav`) fa le atomiche globali.

#### La riga finale, a leva accesa (sempre, anche con `LANE_CONTA=0`)

```
cache-esperti: lane adattiva: guardia: ripieghi=N | audit: somma=S (X.XX per partizione)
cache-esperti: ATTENZIONE lane adattiva: N righe ripiegate            [se N > 0]
cache-esperti: ATTENZIONE lane adattiva: audit NON torna -- ...       [se S % partizioni != 0]
```

Il testimone è il bilancio stesso: se `somma > 0` la riduzione del livello 2 ha
girato, cioè la leva era armata. Non serve propagare il livello fin qui.

#### Le tre verifiche

- **(i) leva 0 + `LANE_CONTA=0`**: `<_, false>` ⇒ ogni `if constexpr (adattiva)`
  sparisce (accumulatori, barriera, meccanismo, guardia, audit);
  `lane_ad_armata` è una costante di compilazione `false`; i due blocchi di
  statistica sono `if (c.lane_conta && …)` ⇒ non eseguono. **Il cammino è quello
  del binario attuale meno il ciclo e le atomiche dello stadio 1.**
- **(ii) leva 2 + `LANE_CONTA=0`**: guardia e audit girano (`mod:7445`, `:7533`),
  il riversamento pure (`:7547`), e la riga finale esce col testimone.
- **(iii) nessuna decisione del meccanismo legge un contatore di misura**:
  verificato sul sorgente generato — nel blocco `mod:7440-7524` non compare un
  solo `c.lane_cpu_residenti`, `c.lane_ad_cpu_vive`, `c.lane_ad_gpu_colonne` né
  `c.lane_conta`.

**Doppio conteggio evitato**: a leva armata il bilancio lo scrive la riduzione
del livello 2; il blocco di statistica a leva spenta è guardato da
`!lane_ad_armata` (`mod:7569`), che a leva spenta è costante e fa collassare la
condizione sul cammino di oggi.

### D11 — i CONTATORI dietro env, la GUARDIA sempre (decisione di regia 2/9)

**Dato nuovo**: la strumentazione dello stadio 1 **costa tempo** — decode
**−1,48%** contro prefill **−0,16%** rispetto a S0 §56, **a lavoro identico**.
Il ciclo su `k_cpu` e le tre atomiche per riga stanno sul cammino piu' caldo che
abbiamo, e una MISURA non deve pesare sul servizio.

**Decisione, recepita nella patch 2**: il blocco di conteggio in coda a
`kern_partiziona` va dietro `c.lane_conta`, letto a init da
`LLAMA_CACHE_ESPERTI_LANE_CONTA` (a VALORE, difetto 0, solo `=1` accende),
con testimone `cache-esperti: lane_conta=1` quando acceso. Restano **sempre
attive** la guardia di `ggml-cpu.c` (un confronto per id) e la riga
`sched-worker-lane: voci fuori tabella=`.

I tre vincoli, verificati sul codice generato:

1. **A `LANE_CONTA=0` + leva 0**: i tre punti di conteggio sono
   `if (c.lane_conta && …)`; nessun ciclo, nessuna atomica. Il cammino e' quello
   del binario ratificato **piu' la sola guardia CPU**. Nota: `lane_adattiva_1`
   e' gia' nel binario, quindi **la patch 2 modifica righe che la patch 1 aveva
   aggiunto** — e' voluto e visibile nel diff.
2. **La cessione NON dipende da `lane_conta`.** Verificato sul sorgente generato:
   nel blocco del MECCANISMO (`mod:7392-7451`) **non compare un solo
   `c.lane_*`, `atomicAdd` o `ceduti`** — ogni scrittura (blocco C, `-1` sulle
   colonne cedute, `perm_inv`) testa `chiave[perm[j]]` direttamente. I contatori
   sono misura, non meccanismo.
3. **La riga `tre vie` ha due formati**: a `lane_conta=1` quello esteso coi
   quattro campi; altrimenti **il formato storico**, verificato testualmente
   identico a quello pre-stadio-1 (a meno del rientro). I log del servizio non
   cambiano e nessun parser a valle va toccato.

**⚠ Conseguenza dichiarata**: a `LANE_CONTA=0` tace anche la **biiezione di
`perm_inv`** (`lane_ad_perm_rotta`), cioe' il rilevatore del «guasto muto» e'
spento in produzione. E' un cancello di **COLLAUDO**: il braccio della leva va
corso con `LANE_CONTA=1` e `perm_rotta == 0` va verificato li'. La correttezza
della cessione non dipende da lui — e' un testimone, non una difesa.

### D9 — la leva NON deve poter armarsi sul contesto BOZZA (§E.1, ACCOLTA)

Il censimento (E) ha stabilito che il drafter **non riceve le colonne CPU**, e non
per fortuna: il cancello di `llama-graph.cpp:2346` vuole `LLM_ARCH_DEEPSEEK4`, e
l'header GGUF della bozza (`DSpark-draft-Q2K.gguf`) dice
`general.architecture = dflash` (il bersaglio dice `deepseek4`). Quindi
`build_moe_ffn_overlap` non e' mai chiamata per la bozza e `kern_partiziona` non
gira mai sul runtime `bozza`.

**Ma quello e' un fatto del MODELLO, non del codice**: se un domani la bozza
fosse un `deepseek4` distillato, il confinamento cadrebbe in silenzio. Su
decisione di regia la riga entra nella patch 2, dentro la lambda della leva,
subito dopo `if (lv == 0) { return 0; }`:

```cpp
        if (cparams.ctx_other != nullptr) {
            return 0;
        }
```

`cparams` e' gia' in scope (usato a `:1936` per `cparams.warmup`), ed e' **lo
stesso predicato** con cui `llama-context.cpp:1904` sceglie il runtime `bozza`
della cache esperti.

### D10 — `LLAMA_OVERLAP_VERIFICA` NON e' valida a livello 2 (a REGISTRO, non in patch)

La sonda di `ggml-cuda.cu:3316-3374` verifica l'invariante **vecchia**
`o[o[ne0+i]] == s[i]`, che la leva cambia: `perm_inv` indicizza il concat largo
`k_cpu+ne0`, quindi ogni colonna GPU da' `pos >= ne0`, e una colonna ceduta da'
`o[pos] == -1`. La sonda conterebbe disallineamenti su ogni riga. Non c'e'
overflow (`parte` e' dimensionata a meta' e legge solo A|B), ma il blocco C non
viene mai letto.

**Decisione di regia: nessuna modifica nella patch 2.** La sonda resta spenta ed
e' dichiarata **non valida a livello 2**. La riscrittura corretta — che conta e
non corregge, e collassa sul codice di oggi a livello 0 — resta documentata in
**§E.5 di `SEZIONE_E_censimento.md`** per chi volesse accenderla.

### D8 — il bilancio delle destinazioni entra GIA' nello stadio 1 (ACCOLTA)

Il mandato iniziale diceva «62-64 possono essere dichiarati ma restano 0»; il
disegno §C.5 li vuole invece **nel primo braccio**, perche' il bilancio delle
destinazioni e' il cancello «CEDERE ≠ ELIMINARE» **e** l'unico denominatore che
non dipende dal cancello `router_*`. **La regia ha accolto: il blocco e' nello
stadio 1.** Uscita ancora bit-identica (due sole atomiche in piu').

Forma effettiva nel patch — in coda a `kern_partiziona`, dopo il conteggio di
`lane_cpu_residenti`:

```c
    int lane_ad_vive = k_cpu < ne0 ? k_cpu : ne0;

    if (c.lane_ad_cpu_vive && c.lane_ad_gpu_colonne) {
        atomicAdd((unsigned long long *) c.lane_ad_cpu_vive,    (unsigned long long) lane_ad_vive);
        atomicAdd((unsigned long long *) c.lane_ad_gpu_colonne, (unsigned long long) (ne0 - lane_ad_vive));
    }
```

`lane_ad_vive` e' **non-const di proposito**: lo stadio 2 inserisce il suo
`if constexpr (adattiva) { … }` **fra la dichiarazione e il bilancio** e la
abbassa di `ceduti`. Cosi' lo stadio 2 resta una pura INSERZIONE anche qui, la
somma fa `ne0` per riga in ogni configurazione, e il cancello
«`cpu_vive + gpu_colonne` = 6,00 per partizione» ha il suo **riferimento
misurato a leva spenta**, come chiedeva §C.5.
`lane_ad_perm_rotta` (64) resta invece a zero fino allo stadio 2: la bigezione di
`perm_inv` ha senso solo dove la leva la riscrive.

---

## 5. Rischi residui, dichiarati

1. ~~`ggml_dsv4_moe_decode` potrebbe assumere `ne0-k_cpu`~~ — **CHIUSO dal
   censimento (E)**: `ggml_cuda_dsv4_moe_decode_supported` (`ggml-cuda.cu:3153`)
   ammette **esplicitamente `ids->ne[0] >= 1 && <= 6`**, e l'op usa
   `n_routes = ids->ne[0]` e `ids->nb[1]/sizeof(int32_t)` in modo generico. Il
   costo a sei colonne e' `mid` da 96 a 144 KiB per strato a `n_tok=3`, dal pool.
   Resta solo: **non fondere tile e lane adattiva nella stessa misura**, perche'
   il tile cambia il kernel che consuma `ids_gpu` e i due effetti non sarebbero
   separabili. La leva `LLAMA_DSV4_DECODE_TILE_VRES` e' comunque spenta.
2. **`n_lav < n_tok`** (replay stantio): le righe `t >= n_lav` del blocco C
   restano non inizializzate, come gia' oggi succede al blocco A. Nessuna
   esposizione nuova, ma nemmeno risolta.
3. **`lavori`** (§A.7 del disegno): il cambio di numerici puo' spostare la
   traiettoria del testo. Resta un cancello (±3%), non una nota.
4. **La riga di stderr in piu'** dello stadio 1 (`sched-worker-lane: …`) non tocca
   lo SHA del testo generato, ma **cambia lo stderr**: se un harness confronta
   l'intero stderr, va aggiornato.
5. **Il costo dello stadio 1 non e' zero in TEMPO** (e' zero in USCITA): il
   conteggio aggiunge un ciclo di ≤ `k_cpu` iterazioni e un'atomica condizionale
   per riga in `kern_partiziona`. Bit-identico, non gratis.

---

## 6. Cancelli, invariati rispetto al disegno §B.5

| cancello | stadio 1 | stadio 2 leva 0 | leva 1 | leva 2 |
|---|---|---|---|---|
| G1 corto 0731 | `AD3D3770…FE11` | idem | idem | diverge, legittimo |
| ri-baseline S1 | `97DF3AB0…5EC0` | idem | idem | idem |
| `voci fuori tabella` (sempre attivo) | **0** | 0 | 0 | > 0, ≈ colonne cedute |
| `lane_cpu_residenti` (statistica) | — | **richiede `LANE_CONTA=1`** | idem | idem |
| GUARDIA `ripieghi` + AUDIT `somma` | — | — | attivi | **attivi anche con `LANE_CONTA=0`** |
| `di cui RESIDENTI=` | ~30% atteso | ~30% | ~30% | **0 esatto** |
| `cpu_vive + gpu_colonne` | **`6,00`/partizione** ← il riferimento | `6,00` | `6,00` | `6,00` |
| `perm_rotta` | 0 (non ancora scritto) | 0 | 0 | **0** |
| copie / `kern_fj_copia` | — | — | — | **±1%** |
| `lavori` | — | — | — | **±3%** |


---

## 7. Sezione (E) — censimento dei consumatori delle colonne CPU

Consegnata a parte in **`SEZIONE_E_censimento.md`** (da appendere al documento
del disegno dopo la sezione D). Ventitre siti censiti con verdetto
«tollera / NON tollera / non raggiunto / non riceve le colonne CPU».

Esiti che ricadono su questa patch:

- **Il drafter non riceve le colonne CPU** (arch `dflash`, non `deepseek4`) ⇒
  la riga difensiva di **D9** entra comunque nella patch 2.
- **I due `-1` non si intersecano mai**: AcceptMoE solo in `j >= k_cpu`
  (`:7316`), la cessione solo in `j < k_cpu`; consumatori fisicamente diversi.
- **La GPU non vede mai la parte CPU**: `assicura` riceve `ids->data` del nodo
  MUL_MAT_ID **CUDA**, cioe' `ids_gpu`; con lo stadio 2 e' il blocco C a sei
  colonne con id validi. Piu' otto guardie `esperto < 0` gia' presenti.
- **La chiave di riuso dei grafi non cambia**: la forma di `part` e' funzione di
  (livello statico, `n_tokens`), deterministica per taglia.
- **Il rischio tile e' chiuso** (vedi §5.1).
- **`LLAMA_OVERLAP_VERIFICA` non e' valida a livello 2** ⇒ **D10**, a registro,
  fuori dalla patch.
