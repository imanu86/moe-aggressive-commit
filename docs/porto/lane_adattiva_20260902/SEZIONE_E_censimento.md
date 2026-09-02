# (E) INVARIANTE INVERTITA — censimento dei consumatori delle colonne CPU

Da appendere a `docs/porto/lane_adattiva_20260902/LANE_ADATTIVA_tetto_e_patch_20260902.md`
dopo la sezione (D). Chirurgo, **sola lettura, nessuna corsa, nessun file di
`D:\llama-subtract` toccato, mai git.**

> **Numerazione.** Tutte le righe di `cache-esperti.cu` citate qui sono
> **misurate sull'albero DI OGGI, cioe' DOPO lo stadio 1** (verificato: i quattro
> file dello stadio 1 nell'albero vivo sono byte-identici a `mod1\`, gli altri
> tre sono agli SHA di `BASE.txt`). Sono quindi le righe su cui si applichera' lo
> stadio 2. Rispetto al disegno (che numera il sorgente pre-patch) lo scarto e'
> di **+9 righe** da `:87` in poi: p.es. il `-1` di AcceptMoE, `:7307` nel
> disegno, oggi e' **`:7316`**.

La domanda della sezione: **con la leva accesa, chi legge una colonna che porta
`-1`, o la permutazione che la nomina, e che cosa ne fa?** Per ogni sito:
`tollera −1` / `NON tollera` / `non raggiunto` / `non riceve le colonne CPU`.

---

## E.0 Il risultato in una riga

**Su ventitre siti censiti, uno solo non tollera la leva**: la sonda
`LLAMA_OVERLAP_VERIFICA` (`ggml-cuda.cu:3316-3374`), che verifica l'invariante
*vecchia* `out[out[ne0+i]] == selected[i]`. È una diagnostica, spenta in
produzione e viva solo prima della cattura — ma è **proprio la sonda che si
accenderebbe durante il collaudo della leva**, e senza la correzione griderebbe
falsi disallineamenti su ogni riga con una colonna ceduta. Proposta in §E.5.

Tutto il resto tollera, o non è raggiunto, o non riceve mai le colonne CPU.

---

## E.1 (a) IL DRAFTER — non riceve le colonne CPU, per ARCHITETTURA

| # | sito | file:riga | verdetto |
|---|---|---|---|
| a1 | cancello d'ingresso dell'overlap | `src/llama-graph.cpp:2346` | **non riceve le colonne CPU** |
| a2 | modello bozza in produzione | `D:\ds4-models\DSpark-draft-Q2K.gguf` | **non riceve le colonne CPU** |
| a3 | creazione del nodo partizione | `src/llama-graph.cpp:1886`, `:1910` | unici due siti, entrambi dentro `build_moe_ffn_overlap` |
| a4 | cache bozza (runtime separato) | `cache-esperti.cu:982`, `:1021-1023`, `:2828` | **non raggiunto** |

**La prova, non l'argomento.** Il ramo overlap si apre solo dentro

```
llama-graph.cpp:2346:  if (arch == LLM_ARCH_DEEPSEEK4 && gate_up_exps == nullptr && ...)
```

e l'architettura dei due modelli, letta dall'header GGUF:

| file | `general.architecture` | `general.name` | esperti |
|---|---|---|---|
| `C:\ds4-models\DS4-0731-IQ2XXS.gguf` (bersaglio) | **`deepseek4`** | DeepSeek V4 Flash | 256, 6 usati |
| `D:\ds4-models\DSpark-draft-Q2K.gguf` (bozza) | **`dflash`** | Dspark Flash Drafter | 256, 6 usati |

Il drafter **è** un MoE a 256 esperti e **usa** la cache (`LLAMA_CACHE_BOZZA_SLOT=12`,
runtime con `bozza=1` scelto da `cparams.ctx_other != nullptr`,
`llama-context.cpp:1904`) — ma la sua architettura non è `deepseek4`, quindi
`build_moe_ffn_overlap` non viene mai chiamata per lui, quindi
`ggml_cache_esperti_partiziona` non viene mai creata, quindi **`kern_partiziona`
non viene mai lanciato sul runtime bozza** e nessuna vista `ids_cpu` esiste in
quel grafo. La cache bozza vede solo domanda, mai partizione.

⇒ **La leva è GIÀ confinata al bersaglio. Nessuna riga è necessaria.**

**Ma la difesa costa una riga, e il confinamento oggi poggia su un fatto del
modello (l'arch della bozza), non su un'invariante del codice.** Se un domani la
bozza fosse un `deepseek4` distillato, il confinamento cadrebbe in silenzio. Riga
da aggiungere, dentro la lambda della leva in `llama-graph.cpp`, subito dopo
`if (lv == 0) { return 0; }`:

```cpp
        // lane-adattiva (2/9): la leva vive SOLO sul bersaglio. Oggi la bozza
        // non arriva nemmeno qui (arch `dflash`, non `deepseek4`, cancello di
        // :2346), ma quello e' un fatto del MODELLO, non del codice: se la
        // bozza diventasse deepseek4 il confinamento cadrebbe in silenzio.
        // `cparams.ctx_other != nullptr` e' lo STESSO predicato con cui
        // llama-context.cpp:1904 sceglie il runtime `bozza` della cache.
        if (cparams.ctx_other != nullptr) {
            return 0;
        }
```

`cparams` è già in scope in `build_moe_ffn_overlap` (usato a `:1936` per
`cparams.warmup`). **Raccomandata**: costa una riga e chiude un'invariante
non dichiarata.

---

## E.2 (b) `cache-esperti.cu` — ogni lettore dopo la partizione

| # | sito | file:riga | verdetto | perché |
|---|---|---|---|---|
| b1 | bilancio `lane_cpu`/`lane_gpu`/`lane_scudati` | `:7298-7311` | **tollera** | legge `chiave[]` e `perm[]`, locali del kernel; non tocca le colonne d'uscita |
| b2 | il nostro blocco (misura + destinazioni) | coda del kernel, stadio 1 | **tollera** | idem; `lane_ad_vive` è l'unica variabile che la leva aggiorna |
| b3 | rilevatore di replay stantio | `:6943-6966` | **tollera** | confronta `n_tok` pubblicato/catturato e i puntatori `ids`/`out`; non legge mai una colonna. `n_tok` **non cambia** con la leva (il tensore raddoppia in righe, non `s0->ne[1]`) |
| b4 | traccia CESTRC — `ids[6]`, `stati[6]` | `:7102-7104` | **tollera** | scrive `riga[i]` (ordine **ROUTER**, mai `-1`) e `stato[i]`, **prima** di ogni permutazione: il `-1` della leva vive solo in `o[]`, che la traccia non legge |
| b5 | traccia CESTRC — `fork[6]` | `:6251` | **tollera, e migliora** | vedi sotto |
| b6 | lettori python della traccia | `leggi_cestrc.py`, `analyze_route_trace.py` | **tollera** | leggono `ids` come `int16` dal record, che non contiene mai il `-1` della leva |
| b7 | `kern_decidi` | `:5025` `if (e < 0 \|\| e >= c.n_esperti) continue;` | **tollera** | guardia esplicita, già presente |
| b8 | `kern_fj_maschera` / `kern_fj_copia` / DMA | `:4866`, `:5109`, `:5387`, `:5506`, `:5561`, `:5877`, `:6394`, `:6473` (invariate) | **tollera** | otto guardie `esperto < 0 \|\| >= n_esperti`, due delle quali col commento «audit 42 §4.1: mai» |
| b9 | quale `ids` arriva alla domanda GPU | `ggml-cuda.cu:2799-2802` | **non riceve le colonne CPU** | vedi sotto |
| b10 | AcceptMoE: i due significati di `-1` | `:7316` (peso zero) contro la leva (cessione) | **tollera — separati per costruzione** | vedi §E.3 |
| b11 | ramo `k_cpu == 0` e sanificazione | `:7117-7152`, `:7135` | **non raggiunto** | la leva **rifiuta di armarsi** con `LLAMA_OVERLAP_K < 1`; a K≥1 la Bresenham non produce mai `k_cpu == 0` |
| b12 | `kern_tile_sanifica_slot` | `:6260-6263` | **non raggiunto** | solo sul cammino tile, spento di difetto (§E.4) |

### b9 — la GPU non vede MAI la parte CPU, e con lo stadio 2 vede solo il blocco C

`ggml_cuda_cache_esperti_assicura` (che lancia `kern_decidi` e la famiglia
`kern_fj_*`) riceve `ids->data` **del nodo `MUL_MAT_ID` che sta girando su
CUDA** (`ggml-cuda.cu:2800-2802`). Nel ramo overlap quel nodo è costruito con
`ids_gpu` (`llama-graph.cpp:1944`, `:1946`, `:1956`). I tre nodi costruiti con
`ids_cpu` (`:1963`, `:1965`, `:1978`) girano sul **backend CPU**: la loro
`mul_mat_id` è `ggml_compute_forward_mul_mat_id`, mai il cammino CUDA.

⇒ **Con lo stadio 2 la GPU riceve esclusivamente la vista a sei colonne del
blocco C**, che per costruzione (§B del patch) contiene: gli id veri delle
colonne cedute e delle colonne GPU, e un **id valido duplicato** — preso fra
quelli già presenti nel blocco C — nelle colonne che la CPU si tiene. **Mai il
`-1` della cessione.** La lettura fuori slab di `mmvq.cu:1408`
(`ids[...]` letto come `uint32_t`) e l'abort del cammino generico
(`ggml-cuda.cu:2924`) restano irraggiungibili.

### b5 — la maschera `fork` cambia significato, e nel verso giusto

`:6251` accende `tr.fork[j] = m` cercando **per valore d'id**
(`tr.ids[j] == esperto`) fra gli id che la GPU sta servendo. Oggi le colonne date
alla CPU non compaiono mai in `ids_gpu`, quindi restano a `255` — ed è così che
§A.4 ha potuto fare la controprova. **Con la leva le colonne cedute compaiono in
ids_gpu, quindi passano da 255 a 0/1.** Non è una perdita: `255` continua a
significare esattamente *«non vista dalla GPU» = «calcolata dalla lane CPU»*, e
diventa così il **testimone lato GPU della cessione**, indipendente dai contatori.
Il duplicato non confonde il conteggio: il router non ripete un esperto dentro la
stessa riga, quindi `dup` corrisponde sempre a una colonna che la GPU calcola
davvero.

---

## E.3 I due `-1` nello stesso tensore: come li distingue ogni consumatore

È la domanda più pericolosa del censimento, e la risposta è **disgiunzione per
colonna**, non un tag:

| `-1` | dove viene scritto | quale colonna | chi lo legge |
|---|---|---|---|
| **AcceptMoE, peso zero** | `:7316`, guardato da `compatta && j >= k_cpu && peso == 0` | **solo `j >= k_cpu`** | oggi `ids_gpu`; con la leva il **blocco C**, che riproduce la stessa regola |
| **cessione, lane adattiva** | blocco della leva | **solo `j < k_cpu`** | **solo `ids_cpu`** — la guardia CPU dello stadio 1 |

Le due popolazioni **non si intersecano mai**, e i due consumatori sono
fisicamente diversi: le colonne `[0, k_cpu)` le legge soltanto `ids_cpu`
(backend CPU), le colonne `[k_cpu, ne0)` di `o[]` con la leva accesa **non le
legge più nessuno** (la GPU passa al blocco C). Nessun consumatore deve
distinguere due significati: ognuno ne vede uno solo.

Il blocco C, che è l'unica finestra della GPU, **riproduce la regola di `:7316`
verbatim** per le colonne che la GPU calcola davvero — quindi la compattazione a
peso zero continua a valere e la leva non ricarica colonne matematicamente nulle
(era il rischio 3 di §B.7, qui chiuso).

Il terzo `-1` del file — `:7135`, ramo `k_cpu == 0`, `o[j] = c.calendario_slot_diretti ? 0 : -1`
— è **irraggiungibile** con la leva armata, perché la leva rifiuta di armarsi con
`LLAMA_OVERLAP_K < 1` (§C.2 del disegno). È esattamente il motivo di quel rifiuto:
lì il `-1` cadrebbe in colonne `j < k_cpu` con significato «compattazione», cioè
lo stesso posto con l'altro significato.

---

## E.4 (c) `ggml-backend.cpp`, worker e CUDA graph — e (d) il tile

| # | sito | file:riga | verdetto | perché |
|---|---|---|---|---|
| c1 | worker: `n_lavori`, split, join | `ggml-backend.cpp:892`, `:953`, `:1927`, `:2808` | **non ispeziona gli id** | il worker conta lavori e tempi; non legge un solo valore di `ids` |
| c2 | copia di confine della vista CPU | `llama-graph.cpp:1997` (concat) | **tollera** | nessun controllo d'intervallo sui valori; `part` cresce di **144 byte** a `n_tokens=3` (da 144 a 288) |
| c3 | riuso del grafo **per taglia** | `llama-context.cpp:1767-1814` | **tollera — la chiave non cambia** | vedi sotto |
| c4 | cattura/replay CUDA graph, `div[4]` | `cache-esperti.cu:6943-6966`, `:6965` | **tollera** | la griglia resta **fissa** a `GGML_CACHE_ESPERTI_TOK_MAX`; `n_tok` (`= s0->ne[1]`) non cambia |
| d1 | `ggml_cuda_dsv4_moe_decode_supported` | `ggml-cuda.cu:3153` | **tollera** | **ammette esplicitamente `ids->ne[0] >= 1 && ids->ne[0] <= 6`** |
| d2 | `ggml_cuda_op_dsv4_moe_decode` | `ggml-cuda.cu:3174-3180` | **tollera** | usa `n_routes = ids->ne[0]` e `ids->nb[1]/sizeof(int32_t)` come passo: **generico, non assume `ne0 − k_cpu`** |
| d3 | forma dell'uscita del tile | `ggml-cuda.cu:3157` `op->ne[1] == ids->ne[0]` | **tollera** | il nodo nasce da `ids_gpu`, quindi coerente per costruzione |
| d4 | la leva del tile | `LLAMA_DSV4_DECODE_TILE_VRES` | **non raggiunto in produzione** | assente nel lanciatore ⇒ `dsv4_decode_tile_for_layer()` falso |

### c3 — perché la chiave di riuso non cambia

Il riuso è **per taglia**: `graph_reuse_per_taglia` confronta `ubatch.n_tokens`
con `gf_res_prev_n_tokens` e, al cambio, **ricostruisce** la topologia
(`llama-context.cpp:1767-1772`, `:1814`). La forma di `part` è una funzione di
**(livello della leva, `n_tokens`)**, e il livello è letto **una volta per
processo** (`static const int lane_adattiva`): per una data taglia la forma è
deterministica e costante per tutta la corsa. ⇒ **nessuna forma nuova per token,
nessuna forma variabile a runtime, nessuna ricattura in più.** È lo stesso
vincolo per cui l'opzione (ii) «K per strato» era stata scartata: qui è
rispettato.

### d — quanto costa davvero il tile a sei colonne

Il cancello di ammissione **già oggi accetta fino a sei colonne**
(`ids->ne[0] <= 6`): la vista a 4 colonne di oggi e quella a 6 della leva
ricadono nello stesso ramo. Il costo è aritmetico e lineare in `n_routes`:
`mid` passa da `2048 × 4 × n_tok` a `2048 × 6 × n_tok` float, cioè da 96 KiB a
144 KiB per strato a `n_tok = 3` — allocati dal pool, non nuovi byte PCIe.
**Il rischio segnalato in consegna si ridimensiona a zero dimensionale**: resta
solo la raccomandazione di **non fondere i due bracci** (tile + lane adattiva)
nella stessa misura, perché il tile cambia il kernel che consuma `ids_gpu` e i
due effetti non sarebbero separabili.

---

## E.5 L'UNICO sito che NON tollera, e la proposta minima

### `LLAMA_OVERLAP_VERIFICA` — `ggml-cuda.cu:3316-3374` — **NON tollera**

La sonda verifica l'invariante **vecchia**:

```c
const int32_t pos = o[ne0 + i];
if (pos < 0 || pos >= ne0 || o[pos] != s[i]) {
    disallineati++;
}
```

Con la leva a livello 2 **entrambe le condizioni diventano false-positive**:

1. `perm_inv[i]` vale `k_cpu + j` per ogni colonna servita dalla GPU, cioè
   **`>= ne0`** in tutte le righe: la sonda le conta tutte come disallineate;
2. per una colonna ceduta `o[pos]` vale `-1`, non `s[i]`.

Inoltre `parte` è dimensionata `2*ne0*n_tok` mentre il tensore ne ha il doppio:
**non c'è overflow** (la sonda legge in difetto, solo la metà A|B), ma il blocco C
— dove ora vivono gli id che la GPU consuma davvero — **non viene mai letto**.

È una diagnostica, spenta in produzione, e gira **solo prima della cattura**. Ma è
letteralmente la sonda che si accende per collaudare questa leva: lasciarla così
significa consegnare un cancello che grida sempre, cioè un cancello morto.

### Proposta minima — insegnarle l'invariante nuova, **senza clamp**

`k_cpu` e `strato` sono già in scope (`ggml-cuda.cu:3305-3306`); basta leggere il
terzo parametro dell'op, che lo stadio 2 già scrive.

```c
                    // lane-adattiva (2/9): l'invariante cambia con la leva.
                    // A livello 2 perm_inv indicizza il concat largo k_cpu+ne0
                    // e le colonne CPU cedute portano -1: la vecchia formula
                    // `o[o[ne0+i]] == s[i]` grida su ogni riga. Qui si verifica
                    // la stessa cosa nella forma nuova -- e si CONTA, non si
                    // corregge: un disallineamento vero deve restare visibile.
                    const int lane_ad = ((const int32_t *) dst->op_params)[2];
                    const int larghezza = lane_ad == 2 ? k_cpu + ne0 : ne0;
                    const int n_righe_t = lane_ad == 2 ? 2*n_tok : n_tok;
                    std::vector<int32_t> parte((size_t) 2*ne0*n_righe_t);
                    ...
                    for (int t = 0; t < n_tok; ++t) {
                        const int32_t * o = parte.data() + (size_t) t*2*ne0;
                        const int32_t * g = lane_ad == 2
                                ? parte.data() + (size_t) (n_tok + t)*2*ne0 : nullptr;
                        const int32_t * s = sel.data() + (size_t) t*ne0;
                        for (int i = 0; i < ne0; ++i) {
                            const int32_t pos = o[ne0 + i];
                            if (pos < 0 || pos >= larghezza) { disallineati++; continue; }
                            // la copia buona sta nella colonna CPU `pos` se
                            // pos < k_cpu, altrimenti nel blocco C a pos-k_cpu
                            const int32_t calcolato = (lane_ad == 2 && pos >= k_cpu)
                                    ? g[pos - k_cpu] : o[pos];
                            if (calcolato != s[i]) disallineati++;
                        }
                    }
```

Due sole modifiche di sostanza: la dimensione di `parte` e la scelta della
finestra da cui leggere l'id calcolato. A `lane_ad == 0` **ogni espressione
collassa su quella di oggi** (`larghezza = ne0`, `n_righe_t = n_tok`,
`calcolato = o[pos]`): la sonda resta identica a leva spenta.

**Non è nella patch dello stadio 2 consegnata** — è una modifica alla
diagnostica, non alla leva, e va decisa dalla regia. Se la leva si collauda con
`LLAMA_OVERLAP_VERIFICA=1`, va fatta **prima**; se il collaudo usa solo i
contatori (`di cui RESIDENTI=0`, `cpu_vive+gpu_colonne`, `perm_rotta`,
`voci fuori tabella`), la sonda va semplicemente **lasciata spenta e dichiarata
non valida a livello 2** — che è comunque un fatto da mettere a registro, perché
oggi nessuno lo saprebbe.

---

## E.6 Riepilogo dei verdetti

| verdetto | siti |
|---|---|
| **tollera** | b1, b2, b3, b4, b5, b6, b7, b8, b10, c1, c2, c3, c4, d1, d2, d3 |
| **non riceve le colonne CPU** | a1, a2, b9 |
| **non raggiunto** | a4, b11, b12, d4 |
| **NON tollera** | **b-verifica (`ggml-cuda.cu:3316-3374`)** — proposta in §E.5 |

Nessun sito richiede un clamp. Le due sole aggiunte proposte sono **una riga di
confinamento difensivo** (§E.1, raccomandata ma non necessaria) e **la sonda
riallineata** (§E.5, necessaria solo se la si accende).
