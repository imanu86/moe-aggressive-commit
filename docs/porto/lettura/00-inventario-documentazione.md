# Inventario della documentazione — cosa e' gia' scritto, e cosa mente

> Repo documentazione: `C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\`
> Repo codice: `D:\llama-overlap` (base upstream `5c3a58686`, HEAD `bd06d4ddf`)
> Compilato il 12 agosto 2026. **Ogni affermazione delle §2 e §3.1-§3.11 e' stata
> verificata da me aprendo il file di codice citato**, con `git log` e con
> confronto MD5 dove serviva. Le voci marcate «fonte: audit N» nelle §3.10-quater,
> §3.10-septies, §4.6 e §5.16 vengono dalla rilettura dei 73 audit e **non le ho
> riverificate una per una**: sono marcate come tali.
>
> Letti per intero: `docs/porto/mappa/` (README, DOVE_VA_IL_TEMPO,
> RAGIONAMENTO_MODELLO, `catena.py`, e i docstring di `estrai/condizioni/router/
> capienza/sharda/ricongiungi`), `mappa.json` + `guardie.json` (per programma),
> `ATLANTE_LEVE.md`, i 29 audit di `docs/porto/audit/`, `LEDGER_11_AGOSTO.md`,
> `RIPRESA_12_AGOSTO.md`, `12AGO_LA_REGRESSIONE_DEL_SYNC.md`, piu' l'inventario
> dei 76 `.md` di primo livello e delle 73 relazioni in `D:\llama-overlap\audit`.

---

## IL FATTO CHE CAMBIA COME SI LEGGE TUTTO IL RESTO

Nella cartella ci sono **due corpi di documentazione di due runtime diversi**, e
niente li separa a vista:

| | motore | dove sta il codice | finestra |
|---|---|---|---|
| **corpo A** | **DS4 / DwarfStark** (`ds4.c`, `ds4_cuda.cu`, `src/cuda/vram_expert_cache.cpp`) | `…\moe-aggressive-commit\ds4-port` | 1/8 → 2/8 |
| **corpo B** | **fork di llama.cpp** (`ggml/src/ggml-cuda/cache-esperti.cu`, `ggml-backend.cpp`) | `D:\llama-overlap` | 3/8 → oggi |

Il passaggio e' dichiarato una volta sola, in `RIPRESA_20260802_SERA.md`: «Il
motore di lavoro e' llama.cpp, non piu' il [fork]». Da li' in poi nessun
documento del corpo A e' stato ritirato, spostato o marcato.

**`docs/porto/mappa/` — l'unica mappa del codice che esiste — appartiene
interamente al corpo A.** Non descrive il codice che stiamo leggendo oggi.
Dimostrazione in §2.

---

## 1. INDICE

Ordinato per utilita' operativa oggi. `[A]` = runtime DS4, non piu' in uso.

### 1.0 La lettura del 12 agosto — `docs/porto/lettura/` (nuova, e' la piu' fresca)

Sei relazioni prodotte oggi. Cinque leggono il **codice**, questa (la 00) legge la
**documentazione**. Sono la fonte piu' aggiornata che esista sull'albero.

| file | blocco letto |
|---|---|
| `01-ingresso-e-decode.md` | `server-context.cpp`, `server.cpp`, `server-stream.cpp`: nascita del ciclo di decode speculativo, da dove vengono le metriche, KV ring e rollback, arresto pulito |
| `02-grafo-e-modello.md` | `llama-context`, `llama-graph`, `deepseek4`, `dflash` |
| `03-scheduler-e-join.md` | `ggml-backend.cpp`: split, ingressi, `us_sync`, `us_calc_altro`, il fallback «un esperto per volta», il join |
| `04-cache-esperti.md` | `cache-esperti.cu/.cuh`: `cache_vittima`, i contatori e la trappola del confronto, `FORK*`, `kern_copia`, **le leve una per una con la raggiungibilita' VERIFICATA** |
| `05-lane-cpu-e-mappato.md` | il worker CPU, `OVERLAP_K/SPIN/PIN`, `MAPPED_IBRIDO`, la finestra di sovrapposizione |
| `10-codex-sync.md` | indagine mirata sulla regressione di `sync` del 12/8 |

**Convergenza indipendente da segnalare**: la 04 e la 05 hanno trovato, leggendo
il codice senza sapere cosa cercavo, gli stessi due difetti di contatore della
§3.3 e §3.3-bis. Quando tre letture indipendenti arrivano allo stesso punto, non
e' un'opinione.

### 1.1 Da leggere per primi (stato corrente, corpo B)

| documento | cosa contiene | a quale domanda risponde |
|---|---|---|
| `RIPRESA_12_AGOSTO.md` | la configurazione da usare (512 slot, FORK=2, FORK_BLOCCHI=8, ASYNC=1 K=2, IBRIDO=1, FUSO=5, LRU=1, SFRATTO_PAR=1, W=0), i cinque fronti chiusi, il fronte che resta | «da dove riparto, e cosa non devo rimisurare» |
| `12AGO_LA_REGRESSIONE_DEL_SYNC.md` | il gradino del 13-14% al riavvio del 12/8, undici cause escluse con un numero ciascuna, la curva di capienza ribaltata | «perche' i numeri di oggi non si confrontano con quelli di ieri» |
| `LEDGER_11_AGOSTO.md` (74 KB) | il registro corsa-per-corsa dell'11/8 | «quel braccio e' gia' stato fatto? con che numero?» |
| `ATLANTE_LEVE.md` | le 77 leve del manifesto, la copertura degli script, le leve che promettevano molto e hanno dato zero, i vincoli fisici misurati | «cosa esiste, cosa e' stato provato, cosa non e' MAI stato provato» |
| `audit/` (29 file qui, **73 in `D:\llama-overlap\audit`**) | le relazioni primarie, con attesa dichiarata prima e cancello | «come funziona davvero questo sottosistema» |
| `LEDGER_10_AGOSTO.md`, `LEDGER_9_AGOSTO.md`, `LEDGER_6-8_AGOSTO.md` | i registri dei giorni precedenti | idem, per data |
| `CACCIA_ESTERNA_11AGO.md` (67 KB) | letteratura, repo, fork, HuggingFace sui quesiti aperti | «qualcuno fuori ha gia' risolto questo?» |
| `RECUPERO_SESSIONE.md` | rilettura del trascritto grezzo della sessione lunga del 10/8; ha **corretto due righe sbagliate dell'ATLANTE** | «cosa e' stato detto davvero, non cosa ricordo» |

### 1.2 Progetto e disegno (corpo B, ancora validi come intenzione)

| documento | cosa contiene | domanda |
|---|---|---|
| `DISEGNO_OVERLAP_FASE2.md` | il disegno della sovrapposizione CPU∥GPU, scritto prima del codice | «perche' l'overlap e' fatto cosi'» |
| `DISEGNO_SPLIT_FASE1.md` | lo split sequenziale dei due rami esperti | idem, fase 1 |
| `MANDATO_OVERLAP.md`, `MANDATO_FINESTRA.md` | i mandati del cantiere overlap | «cosa era stato chiesto» |
| `MANDATO_ANTICIPO.md` | ⛔ **si auto-marca FALSIFICATO** quattro ore dopo essere stato scritto | esempio di documento onesto |
| `PRICING_OVERLAP_CPU_GPU.md` | il pricing prima del codice: 55 ms su 108 sovrapponibili | «quanto valeva in teoria» |
| `PROTOCOLLO_MACCHINA.md` | due cantieri, una GPU, un arbitro | «come si condivide il banco» |
| `RICETTA_TRACCE.md` | come si fa (e come NON si fa) una traccia di stati e route | «come produco un tracciato utilizzabile» |

### 1.3 La testa speculativa / DSpark (corpo B)

`TESTA_METRICA.md` (p1 definito una volta per tutte) · `TESTA_ARITMETICA_RIFATTA.md`
· `TESTA_REVISIONE_CODEX.md` · `TESTA_PIANO_PICCOLO.md` · `MANDATO_TESTA.md` ·
`DSPARK_VERDETTO.md` · `MARKOV_IL_COLPEVOLE.md` → **ribaltato da**
`MARKOV_ASSOLTA.md` · `JACOBI_VERDETTO.md` + `MANDATO_JACOBI.md` (chiusa per
aritmetica) · `ISSUE_UPSTREAM_LOOKAHEAD_DSV4.md` (bozza mai aperta).

### 1.4 La campagna memoria/paging del 3-5 agosto — **numeri di un altro regime**

Tutti misurano 2,7-7 t/s. La SOTA di oggi e' **14,77**. Vanno letti per il
*meccanismo*, mai per il *numero*: `IL_TETTO_E_ORCHESTRAZIONE.md` (il tetto ~6,5
t/s) · `IBRIDO_PREFILL_GPU_DECODE_CPU.md` · `ZEROCOPY_SCALA.md` ·
`AMMISSIONE_ROUTING.md` · `GATE_IL_BLOCCO_FUNZIONA.md` · `GATE_TRE_DOMINI.md` ·
`MASSA_PER_RANGO.md` · `ABLAZIONE_LA_MASSA_SERVE.md` ·
`DECADIMENTO_FALSIFICATO.md` · `VRAM_PIENA_E_IL_GINOCCHIO.md` ·
`VRAM_TASSO_DI_CAMBIO.md` · `KV_MISURATA.md` · `CORSA_LUNGA_E_PAGING.md` ·
`AMMORTAMENTO.md` · `DRAFT_ORCHESTRATION_BOUND.md` · `IL_BANCO_NASCONDE_LA_CHAT.md`
· `REAP_FASE2_PREFETCH.md` · `CANCELLO_NEUTRALITA.md` (si auto-ribalta la stessa
sera) · `PIANO_GATE_MODELLO_CHE_NON_ENTRA.md`.

### 1.5 `[A]` Il corpo A — porto e runtime DS4. Storia, non riferimento

`mappa/` **per intero** (vedi §2) · `DIAGNOSI_VRAM.md` · `PIANO_RIMOZIONE.md` ·
`DSPARK_E_ATLANTE.md` · `NUCLEO_678_INVENTARIO.md` · `P1_inventario_trapianto.md`
· `P2_strato_windows.md` · `P3_layout_tensor.md` · `PIANO.md` · `PRIMO_RUN.md` ·
`PESI_0731.md` · `STATO_2AGO.md` · `RILETTURA_SERATA.md` · `DOVE_STA_LA_ROBA.md` ·
`HANDOFF_20260802.md` · `DA_RIPRENDERE.md` · `mandato_blk7_tiering.md` ·
`mandato_blk8_routeworker.md` · `mandato_blk9_guardiani.md` · `mandato_blk11_kv.md`
· `mandato_hotpath.md` · `mandato_free_at_size.md` · `mandato_una_residenza.md` ·
`mandato_wrap_sequential.md` · `FORK_NON_E_LENTO.md` · `IDEA_dspark_remoto.md`.

Il documento-cerniera e' `LLAMA_CI_BATTE.md` (2/8): «llama.cpp ci batte del 64%
in decode, e non ha nessuna cache esperti». E' quello che ha deciso il pivot.

---

## 2. COME SI USA LA MAPPA — e perche' oggi risponde alla domanda sbagliata

### 2.1 Cosa fa `catena.py`, letto dal sorgente

`mappa/catena.py` (295 righe). Legge `mappa.json` e, se c'e', `guardie.json`
(`catena.py:30-32`). Costruisce cinque indici: funzioni per nome, grafo delle
chiamate nei due versi, letture d'ambiente per variabile e per funzione, guardie
per `(file, riga)`, globali scritte per funzione.

**Dispatch, `catena.py:281-290` — questo e' il punto:**

```python
if   q == '--trappole':      m.trappole()
elif q == '--doppioni':      m.doppioni()
elif q == '--orfane':        m.orfane()
elif q.startswith('DS4_'):   m.variabile(q)      # <-- SOLO DS4_
else:                        m.funzione(q)
```

Una variabile che non comincia per `DS4_` **non viene mai trattata come
variabile**: finisce in `funzione()` e torna «non e' una funzione conosciuta».
Interrogarla su `LLAMA_CACHE_ESPERTI_FORK` o `LLAMA_OVERLAP_ASYNC` non da' un
errore: da' una risposta vuota che sembra «non c'e'».

**Quattro modi d'uso reali:**

| invocazione | restituisce |
|---|---|
| `python catena.py DS4_<VAR>` | i siti di lettura con funzione lettrice, semantica (`PRESENZA` marcata `[TRAPPOLA: presenza, non valore]`), la catena di guardie di ogni sito, chi deve chiamare risalendo a 3 livelli, quante funzioni accende a 4 livelli, **le altre variabili sui cammini accesi**, le globali scritte |
| `python catena.py <nome_funzione>` | definizioni con file:riga-riga_fine, chi la chiama (4 livelli), cosa chiama (3 livelli), le variabili del sottoalbero |
| `--trappole` | le variabili con almeno un sito a semantica di PRESENZA (`=0` le ACCENDE) |
| `--orfane` | variabili lette solo in funzioni che nessuno chiama |
| `--doppioni` | **non documentato nel README**: raggruppa per (categoria, frequenza, fase, vram) per trovare meccanismi che si contendono la stessa risorsa. Richiede `ricongiungi.py` eseguito prima (`catena.py:230-233`) |

`--doppioni` esiste nel codice e **non** nel README. **Funziona**: `mappa.json`
porta `schede_fuse: 4538` e tutte e 5.164 le funzioni hanno una `categoria`
(`altro` 1202, `controllo` 722, `parsing` 465, `trasporto` 410,
`quantizzazione` 396, `routing` 373, …), quindi la pipeline
`sharda.py → agenti → ricongiungi.py` e' stata completata. E' l'unica parte
dello strumentario che nessun documento menziona.

**Numeri di testa del README verificati contro i JSON**: 5.164 funzioni ✓,
12.883 archi ✓, 927 siti di lettura ✓, 661 variabili ✓, 453 a semantica di
PRESENZA ✓ (296 VALORE, 143 `ignoto`, 35 VALIDATE), 19.218 siti con catena di
guardie ✓ (18.291 di chiamata + 927 env). L'unico che non torna e' «10.059
condizioni distinte»: contando le stringhe di guardia distinte in
`guardie.json` ne vengono **6.638**. Puo' essere una definizione diversa, ma il
numero pubblicato non e' riproducibile dal file.

### 2.2 `mappa.json` e `guardie.json` sono di un ALTRO albero

```
mappa.json:  "radice": "ds4-port"
             78 file, 5.164 funzioni, 12.883 archi, 927 letture env
             661 variabili distinte:  DS4_* = 661   LLAMA_* = 0   GGML_* = 0
```

I file mappati sono `ds4.c`, `ds4_cuda.cu`, `ds4_server.c`, `rocm/*.cuh`,
`src/cuda/vram_expert_cache.cpp`, `src/platform/*`… **Nessuno di questi esiste in
`D:\llama-overlap`** (l'unica eccezione e' la copia di riferimento inerte in
`D:\llama-overlap\rif_dwarfstar\`, che non viene compilata).

Il README lo dice, ma di sfuggita, in mezzo alle istruzioni di rigenerazione
(`mappa/README.md:39`): `python estrai.py ../../../ds4-port mappa.json`.

**Conseguenza secca: la mappa non puo' rispondere a nessuna domanda sul codice
che stiamo leggendo.** Tutte le 77 leve in uso sono `LLAMA_*` o `GGML_*`; nella
mappa ce ne sono zero.

### 2.3 Campione di cinque simboli — richiesto dal mandato

Verifica contro **`ds4-port`** (l'albero da cui la mappa e' stata estratta) e
contro **`D:\llama-overlap`** (il codice di oggi).

| # | simbolo | mappa dice | `ds4-port` oggi | esito | `D:\llama-overlap` |
|---|---|---|---|---|---|
| 1 | `DS4_CUDA_Q8_F16_CACHE_MB` (esempio del README) | `ds4_cuda.cu:2882` | `:2887` — a 2882 c'e' `cuda_env_flag_enabled("DS4_CUDA_SPLITKV_DECODE", 0)` | **NO**, −5 | assente (solo `rif_dwarfstar/`) |
| 2 | `cuda_stream_selected_fill_spans_overlapped` | `ds4_cuda.cu:3865-4012` | definizione a `:3883` — a 3865 c'e' `&g_stream_selected_io_overlapped[i]);` | **NO**, −18 | **ASSENTE** |
| 3 | `DS4_CUDA_ROUTE_PREFETCH_HINT` | `ds4_cuda.cu:3736` | `:3752`, `:3825`, `:3834` — a 3736 c'e' `uint64_t offset;` | **NO**, −16 | **ASSENTE** |
| 4 | `DS4_EXPERT_TIERING_LOG_IDS` | `vram_expert_cache.cpp:176` | `:176` `config.log_ids = exact_one(std::getenv("DS4_EXPERT_TIERING_LOG_IDS"));` | **SI'** | **ASSENTE** |
| 5 | `DS4_CUDA_STREAMING_EXPERT_CACHE_N` (la «trappola :304») | `vram_expert_cache.cpp:304` `[PRESENZA]` | `:304` esatto; e `:300` per `DS4_CUDA_MOE_GPU_RESIDENT_ROUTES` | **SI'** | assente (solo `rif_dwarfstar/`) |

**Bilancio: 2 su 5 esatti, 3 su 5 sbagliati — e 5 su 5 inutilizzabili sul codice
di oggi.** Lo scarto non e' casuale: tutti e tre gli errori sono in
`ds4_cuda.cu`, che e' stato modificato **alle 10:18 del 2/8, trenta minuti dopo
la generazione di `mappa.json` (09:48)**. `vram_expert_cache.cpp`, gli altri due
campioni, e' rimasto fermo su quelle righe. Lo scarto cresce col numero di riga
(−5 a 2882, −16/−18 a 3736-3865, **−25 a 29443**), quindi e' un inserimento a
monte: il file e' cresciuto di ~25 righe dopo l'estrazione.

`guardie.json` e' **piu' vecchio ancora**: `08:26` contro `09:48` di `mappa.json`.
Le due meta' non sono nemmeno coerenti fra loro.

### 2.4 Verdetto operativo sulla mappa

- **Non interrogarla per il lavoro di oggi.** Non contiene il codice di oggi.
- Resta valida come **metodo**: `estrai.py` + `condizioni.py` girano su una radice
  qualunque (`README.md:39-40`), quindi rifarla su `D:\llama-overlap` costa «circa
  un minuto» — ma `catena.py:287` va corretto, perche' filtra su `DS4_`.
- I limiti dichiarati dal README restano veri e sono importanti: archi **per
  nome** (niente puntatori a funzione ne' overload), **macro non espanse**,
  semantica `ignoto` su 143 siti da guardare a mano, e vede il codice di **tutte**
  le piattaforme (un ramo `#if defined(__APPLE__)` risulta raggiungibile).
- `router.py` e' l'altra meta' e **non e' legata alla mappa statica**: mangia un
  log con `DS4_EXPERT_TIERING_LOG_IDS=1`. Anche quella variabile non esiste piu'.

---

## 3. LA LISTA DEGLI STANTII

Ordinata per costo se qualcuno ci si fida.

### 3.1 ⛔ 19 delle 77 leve del manifesto NON SONO LETTE DA NESSUNA PARTE

**La forma (a) del mandato, nella versione estrema: non e' un ramo
irraggiungibile, e' un ramo che non esiste.**

- **Documento**: `ATLANTE_LEVE.md` §1 — «Fonte: `tools/server/server.cpp`, la
  tabella che il server stampa all'avvio […] **E' la verita' del binario, non una
  lista scritta a mano**» e §2a «`reap` (17 leve, tutto il sottosistema)» elencate
  solo come «mai toccate da nessuno script».
- **Codice**: `tools/server/server.cpp:96-112` (17 righe `reap`) e `:83-85` (3
  righe `LLAMA_RING*`). Ricerca su tutto l'albero, escluse `build/` e `vendor/`:

```
  LLAMA_RING              -> 1 occorrenza:  server.cpp:83   (la riga del manifesto)
  LLAMA_RING_BATTITO      -> 1 occorrenza:  server.cpp:84
  LLAMA_RING_PROFONDITA   -> 1 occorrenza:  server.cpp:85
  LLAMA_REAP              -> 1 occorrenza:  server.cpp:96
  LLAMA_REAP_AMMISSIONE / _DECADIMENTO / _DECADIMENTO_BUSSATE / _DUMP /
  _ISTERESI / _LOCK / _MARGINE / _MAX_SCAMBI / _PERIODO / _PESO / _PREFETCH /
  _PROF / _SOGLIA / _THREADS / _TOPK   -> 1 occorrenza ciascuna: server.cpp:97-111
```

**L'unica leva `reap` viva e' `LLAMA_REAP_WS_MIN_GB`** (`common/working-set.cpp:19`).
Le altre 16 + le 3 `LLAMA_RING*` = **19 voci su 77** vengono stampate all'avvio
con il loro difetto e `(D)`, e non c'e' un solo `getenv` che le legga.

**E il motivo e' documentato: i due sottosistemi SONO STATI CANCELLATI.**
Commit `4b852d6b9`, 10/8 12:05, «via ring-esperti e reap: **2.121 righe in meno**»:

```
  common/reap.cpp                  1241 righe   CANCELLATO
  common/reap.h                      98         CANCELLATO
  ggml-cuda/ring-esperti.cu/.cuh                CANCELLATI
  ANELLO.md                          80         CANCELLATO
  -> salvato solo reap_fissa_working_set, estratto in common/working-set.cpp (39 righe)
```

Il messaggio del commit dice testualmente: «**Tolti anche i riferimenti orfani:
variabili d'ambiente**, righe di dump, voci di CMake, e le righe `LLAMA_REAP` da
venti script di misura. **Un mezzo taglio sarebbe stato peggio di nessun taglio.**»

**Le 19 righe del manifesto sono rimaste.** Sono l'unico posto in cui quei nomi
sopravvivono in un file compilato — e sono anche l'unico posto che finisce in
**ogni log di lancio**.

**Due documenti affermano il contrario, e il codice li smentisce a riga esatta:**

| documento | affermazione | smentita |
|---|---|---|
| `audit/50-tagliati.md:38-39` | «**La scansione dei sorgenti vivi non trova piu' simboli ring, observer reap, provider di ammissione o leve `LLAMA_REAP*` diverse dal minimo del working set.**» | `tools/server/server.cpp:83-85` (`LLAMA_RING`, `_BATTITO`, `_PROFONDITA`) e `:96-111` (16 `LLAMA_REAP*`). Sono stringhe in una tabella, non chiamate `getenv`: la scansione le ha mancate |
| `audit/46-dormienti.md` (tutto §2) | descrive `common/reap.cpp` come un modulo **vivo da 1.241 righe**, con ~15 riferimenti puntuali (`reap.cpp:44-53`, `:203,375`, `:288-301`, `:1022-1049`, `:1070-1076`, `:1203-1224`, `:848-889,917`) e «`reap_dump`, chiamato solo da `tools/server/server.cpp:397`» | **il file non esiste piu'**. Tutti i riferimenti puntano nel vuoto. `server.cpp` oggi ha **551 righe** e non chiama `reap_dump` |

L'audit 46 e' uno dei 29 presenti in `docs/porto/audit/`, ed e' proprio quello che
`ATLANTE_LEVE.md` §3 indica come «utile per la composizione» (`46-dormienti — …
reap … cosa dorme`). Chi lo apre oggi per capire il reap legge la descrizione
minuziosa di codice cancellato due giorni fa.

**Perche' costa**: `12AGO_LA_REGRESSIONE_DEL_SYNC.md:46` usa il manifesto come
prova che nulla e' cambiato al riavvio — «manifesto identico in **77 voci su
77**». Diciannove di quelle voci **non potevano cambiare**, perche' dietro non
c'e' niente. La prova e' vera al 75%.

Attenzione a non confondere: `LLAMA_KV_RING` **e' viva** ed e' un sottosistema
distinto, come `audit/50-tagliati.md:31` dice correttamente
(`ggml/src/ggml-cuda/kv-ring.cu:115`, `src/llama-context.cpp:551`,
`src/llama-kv-cache-dsv4.cpp:183`, `tools/server/server-context.cpp:2219`).

### 3.1-bis ⛔ Il DMA fra-strati e' «chiuso» con uno ZERO che misura il CANCELLO, non la leva

**La forma (a) del mandato nella sua versione piu' costosa: una leva dichiarata
falsificata con un numero, dove il numero e' quello del cancello che le ha
impedito di girare.** E il codice lo dice.

- **Documenti**: `RIPRESA_12_AGOSTO.md:31-32` — «il `DMA` fra-strati **non
  consegna un chunk su settemila**», elencato fra «Cosa e' stato chiuso, ognuno
  con un numero». `LEDGER_11_AGOSTO.md` §10.4, tre bracci: `d_w1` 11,13 t/s /
  colpi **46,7%** / chunk consegnati **0**, scartati 6.738; `d_w2` 11,04 /
  **46,4%** / **0** / 7.158; `d_w2c` (oracolo spento) 11,06 / **46,6%** / **0** /
  7.050. Conclusione tratta: «indistinguibile dal braccio esatto ⇒ la previsione
  non c'entra».

- **Codice**, `cache-esperti.cu:2438`:

```c
if (colpi_finestra * 1000 >= (uint64_t) c.dma_hit_pm * domande_finestra) {
    g[1] = CACHE_ESPERTI_DMA_GATE_PROVA;   // <-- SOLO da qui in poi il DMA puo' ammettere
```

  con `#define CACHE_ESPERTI_DMA_HIT_PM 534` (`cache-esperti.cu:81`), cioe' una
  **soglia del 53,4% di colpi** su una finestra di 32.768 domande dopo 4.096 di
  riscaldamento (`:79-83`, `:2417-2430`).

**I tre bracci girano a 46,4-46,7%: sette punti sotto la soglia.** Sotto quel
valore la macchina resta in `GATE_BASELINE` e **non entra mai in `PROVA`**, quindi
non ammette mai, quindi **consegna zero chunk per costruzione**. Lo zero misurato
non falsifica il DMA: misura `534`.

**Non e' una mia deduzione: e' scritto nel binario**, `cache-esperti.cu:1334-1342`,
e viene stampato all'avvio:

> «cancello DMA a hit_pm=%d per mille: **sotto quella percentuale di colpi non
> ammette MAI (resta in BASELINE)**. Abbassarlo con
> `LLAMA_CACHE_ESPERTI_DMA_HIT_PM` **per misurare la leva invece del cancello**.»

L'avviso e' del commit `684aa90ba`, «cancello del DMA: **giudicare il confronto
giusto**, e spegnersi davvero quando rifiuta» — **10/8 alle 22:51**, cioe' prima
dei bracci dell'11/8. Il meccanismo per accorgersene c'era, e i bracci sono stati
fatti lo stesso al difetto.

Aggravante: anche se il cancello passasse, `:2449-2452` **si auto-spegne** se
`chunk_prova == 0` o se i colpi scendono. E' una leva che si nega da sola in due
punti indipendenti.

**Il test che la chiude davvero** (una corsa, una variabile):
`LLAMA_CACHE_ESPERTI_DMA_HIT_PM=400` sui bracci `d_w2` / `d_w2c`. Se i chunk
restano 0, allora la leva e' falsificata. Finche' non e' fatto, **il DMA
fra-strati non e' chiuso**, ed e' elencato come chiuso in tre documenti.

E `LLAMA_CACHE_ESPERTI_DMA_HIT_PM` **non e' nel manifesto** (§3.2): non compare
nel record di lancio, quindi non c'e' traccia nei log di quale soglia abbia
girato.

### 3.2 ⛔ Il manifesto omette almeno 15 leve che il binario legge davvero

Stesso documento, stessa affermazione («la verita' del binario»). La tabella e'
compilata a mano — lo dice il commento sopra di essa, `server.cpp:36`: «Keep the
defaults aligned with their call sites» — e ne mancano:

| leva assente dal manifesto | letta a | nota |
|---|---|---|
| `LLAMA_CACHE_ESPERTI_SFRATTO_PAR` | `cache-esperti.cu:1255` | **e' nella configurazione SOTA** (`SFRATTO_PAR=1`) |
| `LLAMA_OVERLAP_JOIN_ASYNC` | `ggml-backend.cpp:1827` | citata da `RIPRESA_12_AGOSTO.md:38` con un numero |
| `LLAMA_OVERLAP_FINESTRA` | `ggml-backend.cpp:1860` | la leva del commit `d2387dd3a` (11/8 10:43), **+4% e satura a n=4** |
| `LLAMA_CACHE_ESPERTI_DMA` | `cache-esperti.cu:1275` (+ 3 siti) | il cammino DMA |
| `LLAMA_CACHE_ESPERTI_DOMANDA_DMA` | `cache-esperti.cu:1271` | |
| `LLAMA_CACHE_ESPERTI_DMA_HIT_PM` | `cache-esperti.cu:1293` | difetto **534 per mille** (`cache-esperti.cu:81`) |
| `LLAMA_CACHE_ESPERTI_FORK_ESATTO` | `cache-esperti.cu:1660`, `:1737` | commit `e468d1227` (11/8 17:43) |
| `LLAMA_CACHE_ESPERTI_FORK_PRIORITA` | `cache-esperti.cu:1686` | |
| `LLAMA_CACHE_ESPERTI_FORK_SERIALE` | `cache-esperti.cu:1632` | |
| `LLAMA_CACHE_ESPERTI_FATE` | `src/models/deepseek4.cpp:1406` | |
| `LLAMA_DSV4_INDEXER_FUSO` | `src/llama-context.cpp:329` | l'indexer fuso dell'audit 48 |
| `LLAMA_MMQ_X_IDS` | `ggml/src/ggml-cuda/mmq.cuh:4057` | il tile del cammino esperti (audit 56/57) |
| `LLAMA_GRAPH_REUSE_DISABLE` | `src/llama-context.cpp:349` | |
| `LLAMA_ATTN_ROT_DISABLE` | `src/llama-kv-cache.cpp:320` | |
| `LLAMA_DSV4_COMPRESS_DEBUG` | `src/llama-graph.cpp:756`, `src/llama-kv-cache-dsv4.cpp:779` | |

E il manifesto **non ha nessun gruppo `GGML_`**, quindi non stampa
`GGML_SCHED_PROFILO` (`ggml-backend.cpp:1806`) ne' `GGML_SCHED_DEBUG_INFO`
(`ggml-backend.cpp:1161`) — cioe' le due sonde con cui sono stati prodotti i
numeri centrali di `12AGO_LA_REGRESSIONE_DEL_SYNC.md`.

L'`ATLANTE_LEVE.md` porta la data **11/8 16:59**, cioe' e' stato scritto **dopo**
i commit che introducono `LLAMA_OVERLAP_FINESTRA` (10:43) e `LLAMA_MMQ_X_IDS`, e
prima di `FORK_ESATTO` (17:43). Non e' un documento vecchio: e' un documento che
descrive una tabella scritta a mano credendola generata.

### 3.3 ⛔ La sonda `GGML_SCHED_PROFILO` stampa MEDIE CUMULATIVE DALL'AVVIO, non finestre

**La forma (b) del mandato.** L'accumulatore e' una `static` di funzione, mai
azzerata (`ggml-backend.cpp:1905`: `static ggml_sched_profilo_acc prof;`), e la
stampa divide sempre per il totale dei grafi dall'inizio del processo
(`ggml-backend.cpp:2268-2292`):

```c
if (profilo && ++prof.n_graphs % 50 == 0) {
    fprintf(stderr, "sched-profilo: %lld grafi, ... ingressi %.3f ms (di cui sync %.3f), ...",
            prof.n_graphs,
            prof.us_ingressi/1000.0/prof.n_graphs,      // <-- media da SEMPRE
            prof.us_sync    /1000.0/prof.n_graphs, ...);
```

Non c'e' nessun reset in tutto il file. Ogni riga `sched-profilo:` e' quindi la
media su **tutti** i grafi macinati fino a quel punto, **prefill compreso**, e
scende lentamente man mano che la corsa procede — esattamente come il `[routeprof]`
di DS4.

**Chi ne dipende**: `12AGO_LA_REGRESSIONE_DEL_SYNC.md:26-34` confronta
`ingressi 2,839 → 7,202`, `sync 2,166 → 6,488`, `calc CPU 0,848 → 0,810`,
`join 24,698 → 25,601` fra due corse. Il confronto regge **solo se le due righe
sono state lette allo stesso valore di `n_graphs`** e le due corse hanno la stessa
composizione prefill/decode. Il documento non dice a quale delle stampe
periodiche si riferisce.

**E la trappola era gia' stata documentata, per l'altro runtime, e non e' stata
trasferita**: `mappa/DOVE_VA_IL_TEMPO.md:90-96` — «il numero stampato e' la media
di millisecondi per chiamata su tutte le chiamate fatte finora, non una finestra.
Per questo cala».

Corollario minore, stessa sonda: `prof.n_splits` viene incrementato **due volte
per ragioni diverse** — a `:1958` per lo split che sta calcolando il worker
(«contato, ma non lavorato qui») e a `:2145` per gli split effettivamente
lavorati. `split/grafo` non e' «split lavorati per grafo».

**Confermato indipendentemente, e con due aggravanti che io non avevo visto**, da
`lettura/05-lane-cpu-e-mappato.md` §A e §«cose che non tornano»:

1. **Il denominatore non e' il loro.** Le quattro voci del worker
   (`attesa-evento`, `calcolo`, `attesa-lavoro`, `join`) sono divise per
   `prof.n_graphs`, che conta i grafi del **bersaglio + quelli della bozza**,
   mentre il worker gira **solo sul bersaglio**. Sono quindi **diluite** di un
   fattore pari al rapporto fra i due. I **15,4 ms/grafo di calcolo CPU** che
   `RIPRESA_12_AGOSTO.md:50` indica come «il solo fronte che resta» passano da qui.
2. **I due contatori non partono insieme.** Il worker si crea **pigro, al primo
   dispatch**, mentre `prof.n_graphs` conta **da subito, prefill compreso**.

E `lettura/04-cache-esperti.md` aggiunge il caso peggiore, sulla stessa riga di
stampa: `vite-concluse` e' cumulativo mentre **`vive-censurate` e' un'istantanea**
calcolata sull'host (`popcount(installato[])`, `cache-esperti.cu:3802-3817`).
Due grandezze di natura diversa, sulla stessa riga, senza etichetta.

### 3.3-bis ⛔ Anche i COLPI sono un cumulativo dall'avvio, non il regime

Stessa forma (b), su un numero che compare in **ogni** verdetto dell'archivio.

Il dump dei contatori copia l'intero vettore dal device
(`cache-esperti.cu:3777`: `cudaMemcpy(v, runtime->cache.colpi, sizeof(v), …)`) e
calcola la percentuale su `dom = v[0] + v[1]` (`:3778`, `:3786`), cioe' sul
**totale di domande dall'inizio del processo**. Nessun azzeramento, nessuna
finestra. Il gate del DMA, per contrasto, usa esplicitamente
`colpi_finestra`/`domande_finestra` (`cache-esperti.cu:2438`): la macchina la
finestra ce l'ha, ma la **riga stampata no**.

La nota di memoria `cancello-sha-quando-vale` lo dice giusto («i contatori
`buchi`/`domande` sono **istantanee a battito**»), ma tutti i documenti che
confrontano i colpi lo trattano come una proprieta' del decode:
`ATLANTE_LEVE.md:98-99` (53,2% contro 56,1%), `ATLANTE_LEVE.md:191` (54,0 →
63,8%), `12AGO…:79-82` (60% / 55-60% / 55% / 11%), la memoria
`colpi-dal-trasporto-non-dalla-cpu` (87,3%). **Corse di lunghezza diversa (600
contro 1.200 token) hanno una frazione di prefill diversa nel denominatore.**

`ggml_cuda_cache_esperti_dump` viene chiamata da **tre** posti
(`cache-esperti.cu:1075`, `:1164` il battito, `:1837` la distruzione del
runtime): **anche il dump finale e' il cumulativo dell'intera corsa**, prefill
incluso. Non esiste da nessuna parte una lettura del solo decode.

E il campionamento e' governato da `LLAMA_CACHE_ESPERTI_BATTITO` /
`LLAMA_CACHE_BOZZA_BATTITO`, difetto 60 s (`cache-esperti.cu:356-358`). Il codice
avverte gia' a `:1153-1157` che «il battito fisso a 60 **ha mentito il 6/8**: una
richiesta da 41 s non stampava MAI, e un cancello automatico sul contatore ha
dichiarato "cache scavalcata" un braccio che funzionava». Gli script girano con
`BATTITO=200` (`ATLANTE_LEVE.md:145`), cioe' **piu' del triplo del difetto**.

### 3.4 ⚠ Tre riferimenti `file:riga` dentro i COMMENTI DEL CODICE sono gia' stantii — e uno e' stato copiato nella documentazione

**La forma (c) rovesciata: il commento e' giusto, il puntatore no.**

| dove | dice | cosa c'e' davvero a quella riga |
|---|---|---|
| `cache-esperti.cu:1325` | «kern_prenota **(:2534)** marca i gia' residenti e ritorna PRIMA di prenotare» | `:2534` e' `const int32_t k = chiave_di(strato, esperto);`, dentro un controllo di limiti. `kern_prenota` e' definita a **`:244`** e **`:2665`** |
| `cache-esperti.cu:1315` | «Nel ramo lru quella lettura la fa (scudo\|\|dma), a **:1806**» | `:1806` e' `cudaFree(runtime->cache.usato);`, cioe' la distruzione. La lettura vera e' a **`:1945`**: `if ((c.scudo \|\| c.dma) && c.predetto[slot])` |
| `RIPRESA_12_AGOSTO.md:31` | «`SCUDO` marca e non prenota (**`kern_prenota:2534`**)» | ha ereditato il riferimento sbagliato dal commento qui sopra |

Il *contenuto* delle tre affermazioni e' **corretto e verificato**; e' la
coordinata a essere marcia. Sono commenti scritti col commit `ad4cc2b2a` (11/8
15:33) e gia' spostati dal commit `e468d1227` (11/8 17:43), due ore dopo.

### 3.4-bis ⛔ REGOLA GENERALE: **ogni `file:riga` scritto l'11/8 e' oggi sbagliato**

Ho verificato **una per una** tutte le coordinate di codice che ho trovato nei
documenti e nei commenti. Il risultato non e' un elenco di sviste: e' un tasso.

| citato in | dice | e' davvero a | scarto |
|---|---|---|---|
| `RIPRESA_12_AGOSTO.md:31` / `cache-esperti.cu:1325` | `kern_prenota:2534` | `:244` e `:2665` | **−2290 / +131** |
| `cache-esperti.cu:1315` | «(scudo\|\|dma) a `:1806`» | `:1945` | **+139** |
| `LEDGER_11_AGOSTO.md` §10 | `cache_vittima` a `cache-esperti.cu:1786`/`:1831`/`:1834` | **`:1879`** (`:1786` e' `dma_leva = 0`, `:1831` e' `attiva = false`, `:1834` e' la `…_runtime_libera`) | **+93 / +48 / +45** |
| `LEDGER_11_AGOSTO.md` §8.3 | fallback per-esperto a `ggml-backend.cpp:1948` | **`:2044-2049`** | **+98** |
| memoria `277-copie-per-token…` | stesso fallback a `ggml-backend.cpp:1946` | idem | **+100** |
| memoria `join-73-percento…` | join a `ggml-backend.cpp:1881` | **`:1967-1993`**, e la logica **e' cambiata** | **+90 + semantica** |
| `LEDGER_11_AGOSTO.md` §8.3 | `LLAMA_MAPPED_IBRIDO` a `ggml-cuda.cu:1439` | `:1436` | −3 |
| `LEDGER_11_AGOSTO.md` | `LLAMA_DSV4_HC_FUSO` a `llama-context.cpp:307` | `:306` | −1 |
| `12AGO…:106` | `LLAMA_VRAM_ZAVORRA` a `cache-esperti.cuh:426` | esatto, ma e' il **commento**; il codice e' a `cache-esperti.cu:292` | ✓ / altro file |
| `DOVE_VA_IL_TEMPO.md:95` | `[routeprof] scale` a `ds4_cuda.cu:29443` | `:29468` | −25 |
| `DOVE_VA_IL_TEMPO.md:77` | `cache_invalidate` a `ds4_cuda.cu:1897` | `:1897` | ✓ |
| `DOVE_VA_IL_TEMPO.md:47` | `fill_spans_overlapped` a `ds4_cuda.cu:3865-4012` | `:3883` | −18 |
| `RAGIONAMENTO_MODELLO.md:122` | `publish_runtime_counters` a `vram_expert_cache.cpp:995` | (albero DS4, non verificato) | — |

**11 riferimenti su 13 sono sbagliati.** I due esatti sono in file che nessuno ha
piu' toccato. Lo scarto piu' grande e' di 2290 righe.

La causa e' banale e va detta: `cache-esperti.cu` e' passato per `ad4cc2b2a`
(11/8 15:33) e `e468d1227` (11/8 17:43, +515 righe dichiarate nel ledger stesso),
`ggml-backend.cpp` per `d2387dd3a` (11/8 10:43). **I riferimenti scritti la
mattina erano gia' marci la sera.**

**Regola operativa**: in questo archivio un `file:riga` vale come *indizio del
nome del file*, mai come coordinata. Cercare per **simbolo**, mai per numero. Chi
scrive dovrebbe citare `file:nome_funzione` o incollare la riga di codice.

### 3.5 ⚠ `ggml-backend.cpp:1946` e `:1881` (memoria + audit) puntano altrove

- **Affermazione** (nota di memoria `277-copie-per-token-fallback-scheduler`):
  «221.963 `cudaMemcpyAsync` le emette il fallback dello scheduler
  (**`ggml-backend.cpp:1946`**, un esperto per volta) […] La condizione e'
  `is_host`».
  **Codice oggi**: la condizione e' a **`ggml-backend.cpp:2044-2049`**
  (`ggml_backend_buffer_get_usage(input->buffer) == …USAGE_WEIGHTS &&
  ggml_backend_buffer_is_host(input->buffer) && node->op == GGML_OP_MUL_MAT_ID`).
  A `:1946` c'e' `return ec;` dentro la lambda `esci`. **Il meccanismo c'e'
  ancora; il numero di riga e' sbagliato di ~100.**
- **Affermazione** (nota `join-73-percento-finestra-uno-split`):
  «`ggml-backend.cpp:1881` fa il join al primo split successivo».
  **Codice oggi**: la condizione di join e' a **`ggml-backend.cpp:1967-1993`**, ed
  e' stata **cambiata**: con `LLAMA_OVERLAP_FINESTRA > 0` si unisce solo se lo
  split legge davvero un tensore del worker (`ggml_sched_split_dipende_dal_worker`,
  `:1883`). A `:1881` c'e' un commento sulle viste. **La descrizione e' superata
  dal commit `d2387dd3a`, non solo il numero di riga.**

### 3.6 ⚠ «Il tetto e' ~6,5 t/s» — superato di 2,3 volte, e il documento non ha perimetro

- **Documento**: `IL_TETTO_E_ORCHESTRAZIONE.md:79` — «**Il tetto e' ~6,4-6,5 t/s
  ed e' orchestrazione.** Due strade opposte ci arrivano e nessuna lo supera».
- **Oggi**: `RIPRESA_12_AGOSTO.md:23` → **14,77 t/s**.
- Il documento non dichiara ne' il motore ne' la configurazione nel titolo o nella
  conclusione: chi lo apre oggi legge un tetto assoluto. Il *ragionamento*
  (togliere tutto il paging non muove la velocita') resta valido e ha 6 conferme;
  **il numero e' di un altro banco**.

### 3.7 ⚠ `LLAMA_CACHE_ESPERTI_CURA` e' inerte per costruzione, e l'ATLANTE la descrive come una leva normale

- **Documento**: `ATLANTE_LEVE.md` §2b la elenca fra le «presenti negli script ma
  SEMPRE allo stesso valore letterale»: `LLAMA_CACHE_ESPERTI_CURA sempre 0
  (scadenza previsioni)`. Sembra una leva mai provata.
- **Codice**: `cache-esperti.cu:1309-1324` lo dice adesso a chiare lettere —
  `cache_vittima()` prova i rami nell'ordine `politica_massa -> lru ->
  (cura||scudo||dma) -> clock` e ognuno esce con `return`, quindi **con `lru=1`
  (che e' il difetto e la configurazione in uso) il blocco a 5 classi di CURA non
  e' MAI raggiunto**. Il binario stampa: `«CURA e' INERTE con lru=%d/massa=%d»`.
- Lo stesso vale per **`SFRATTO_PAR`**, che stampa «e' INERTE senza LRU pura»
  (`:1265`), e per **`SCUDO`** senza DMA (`:1329-1332`): «il prefetch muovera' 0
  byte».
- Il `RIPRESA_12_AGOSTO.md:29-32` **e' aggiornato** su questo. L'`ATLANTE` no.

### 3.8 ⚠ «68 audit» / «160 script»: i conti non tornano piu'

- `ATLANTE_LEVE.md:154` — «Le fonti primarie: **68 audit**». In
  `D:\llama-overlap\audit` ce ne sono **73**.
- `ATLANTE_LEVE.md:37` — «Estratto da **160 script** in `D:\ds4_work\llama_run\*.ps1`».
  Oggi ce ne sono **226**. Ogni riga «mai toccata da nessuno script» della §2a e'
  quindi da rifare su 66 script in piu'.
- **`docs/porto/audit/` e' un sottoinsieme parziale (29 su 73).** Gli audit citati
  dall'ATLANTE §3 `14-leve-overlap`, `19-reap`, `20-leve-trasversale` e `56-kernel`
  **non esistono qui**: stanno solo in `D:\llama-overlap\audit`. Mancano anche
  `53`, `54`, `55`, `57`-`61`, `64`, `01`-`20`, e tutti i nominali (`ACCEPTMOE`,
  `DMA`, `DWARFSTAR`, `FABLE_PREFETCH*`, `FORKJOIN`, `K_ADATTIVO`, `PAVIMENTO`,
  `RACCOLTA`, `SINKHORN`, `UPSTREAM_390`, `VERIFICA_CPU`, `CACCIA_ESTERNA`).
  **Chi legge solo `docs/porto/` vede meno di meta' delle fonti primarie.**

  Confronto MD5 fatto file per file: **i 29 non divergono**, sono copie esatte
  (l'unico che sta solo qui e' `70-riquantizzare-il-denso.md`; `71-…` e i quattro
  `7x-up_*` sono gli stessi byte di `PORTO_UPSTREAM_11AGO.md` e `UP_[A-D]_*.md`).
  **Il problema non e' la divergenza, e' l'assenza**: 44 relazioni su 73 non sono
  mai state copiate, e sono tutte quelle numerate `01`-`20` e `53`-`64` piu' i
  nominali. Non c'e' nessun indice che lo segnali.

### 3.9 ⚠ `12AGO…:106` cita `cache-esperti.cuh:426` per `LLAMA_VRAM_ZAVORRA`

Il riferimento **e' esatto**, ma punta al **commento** (`cache-esperti.cuh:426`:
«MiB allocati e mai usati: abbassa il margine a capienza ferma»), non
all'implementazione, che sta a **`cache-esperti.cu:287-315`** con il `getenv` a
`:292`. Da sapere se si va a leggere il comportamento invece della descrizione.

### 3.10 ⚠ `mappa/README.md` e `RAGIONAMENTO_MODELLO.md` presentano come attuale una politica che oggi e' ribaltata

`mappa/README.md:66-67` — «La seconda [meta'] ha **falsificato in un colpo tutta
la nostra politica di residenza**». Il documento a cui rimanda,
`RAGIONAMENTO_MODELLO.md:13-19`, conclude che **la LRU prende 0,0% di colpi** e
che l'insieme caldo statico (28,2%) la batte di 28 punti, raccomandandolo.
La configurazione di oggi usa `LRU=1` e misura **55-60% di colpi**
(`12AGO_LA_REGRESSIONE_DEL_SYNC.md:78-83`). Vedi §5.1: e' la contraddizione piu'
grossa dell'archivio.

### 3.10-bis ⛔ `FORK` si SPEGNE DA SOLO in tre casi, e nessun documento lo dice

Chiunque misuri `FORK=2` senza sapere questo misura il riferimento credendo di
misurare la leva. `cache-esperti.cu:1596-1642`:

```c
if (runtime->fj_leva > 0) {
    const char * w = getenv("LLAMA_CACHE_ESPERTI_W");
    if (!(w && *w && atoi(w) == 0)) {           // <-- W DEVE essere "0" ESPLICITO
        fprintf(stderr, "cache-esperti: FORK=%d richiede LLAMA_CACHE_ESPERTI_W=0 esplicito: fork SPENTO\n", …);
        runtime->fj_leva = 0;
    }
}
…
if (runtime->fj_leva > 0 && (runtime->dma_leva || runtime->domanda_dma)) {
    fprintf(stderr, "cache-esperti: FORK/JOIN e DMA non sono componibili: fork SPENTO\n");
    runtime->fj_leva = 0;
}
```

1. **`LLAMA_CACHE_ESPERTI_W` non impostata = fork SPENTO.** Non basta il difetto:
   serve la stringa `"0"` nell'ambiente. `RIPRESA_12_AGOSTO.md:20` elenca `W=0`
   nella configurazione, ma non dice che e' **obbligatorio**, e `ATLANTE_LEVE.md`
   non menziona l'accoppiamento.
2. **`DMA=1` o `DOMANDA_DMA=1` = fork SPENTO.** Non componibili.
3. **Solo sul bersaglio**: tutto il blocco e' dentro `if (!runtime->bozza)`
   (`:1596`). Sulla cache della bozza il fork non esiste.

E `LLAMA_CACHE_ESPERTI_FORK_SERIALE=1` **non e' una configurazione da misurare**:
il codice lo dice a `:1635-1636` — «la sovrapposizione e' SPENTA, e' una sonda di
diagnosi». Nessuna di queste tre leve e' nel manifesto (§3.2).

### 3.10-ter ⚠ `LLAMA_OVERLAP_VERIFICA` ha copertura ZERO a regime, e il codice lo sa

Il `getenv` sta a `ggml-cuda.cu:2636` e il commento che lo precede dice: «sotto
CUDA graph questo codice host gira **SOLO alla cattura** — ai replay non esiste.
**A regime la verifica non gira MAI** (costo zero, copertura zero) […] chi legge
non deve crederla tale». `ATLANTE_LEVE.md`
§2a la elenca fra le «mai toccate da nessuno script» come se fosse una leva da
provare: accenderla non verifica niente durante una corsa.

Stessa forma, altrove: `common/speculative.cpp:1331-1332` — «**INERTE DA NOI**:
giriamo con `--spec-type draft-dspark`, e questo costruttore e' di `draft-mtp`,
che non viene mai istanziato».

**Nota di metodo**: tutti i casi di forma (a) che ho trovato **io oggi nel codice
attuale** sono dichiarati a voce alta dal binario. Quelli che seguono, trovati
dagli audit, **non lo sono**.

### 3.10-quater ⛔ Il catalogo delle leve che non possono mordere — dagli audit

Ognuna e' una leva che qualcuno ha acceso, o potrebbe accendere, credendo di
misurare qualcosa. Ordinate per costo gia' pagato:

| leva / cammino | perche' non morde | fonte |
|---|---|---|
| **AcceptMoE** | era **ACCESA** in ogni braccio in cui la si credeva spenta: il cancello leggeva l'**ultima** riga `acceptmoe` del log, che e' il dump della cache **BOZZA**, zero per costruzione. Le op giravano e cambiavano lo SHA | audit 36 |
| **la lane CPU nei bracci a n-max 2** | `LLAMA_OVERLAP_BATCH_MAX=2` con batch di verifica da **3** token → `build_moe_ffn_overlap` ritorna `nullptr` e la lane **muore in silenzio**. Il `return nullptr` **non ha testimone** | audit 32, 35, 44 |
| **`LLAMA_RING=1`** | **spegne la cache esperti** in silenzio (l'init sta nel ramo `else`). «Chi prova ring + cache misura in realta' ring senza cache» | audit 46 |
| **`LLAMA_KV_RING=0`** | il test e' sulla **PRESENZA**, non sul valore: metterla a 0 **accende** il log SHA → il braccio di controllo differisce di **due** cose | audit 46 |
| **`LLAMA_CACHE_ORACOLO`** | stampa «oracolo: ACCESO», copia 1 KiB/token, e **non ha chiamanti**. Un braccio «oracolo» misura il predittore ordinario piu' il costo delle copie, con un log che giura il contrario | audit 42 |
| **`--spec-draft-p-min`** | il gate `p_min` esiste **solo** nel ramo DFlash; il ramo DSpark non lo consulta. **No-op totale**. E `p_split` non e' letto da nessuno in tutto l'albero | audit 43 |
| **i checkpoint della BOZZA** | **codice morto a runtime**: il probe fa cadere `ctx_dft_seq_rm_type` a PART, `use_ckpt_dft` resta falso, e le due `load_dft` girano su un checkpoint vuoto. Contatore di conferma: la riga `draft = X MiB` deve stampare **0.000** | audit 43, corregge audit 16 |
| **`LLAMA_SPEC_CONF_ESENTA_POS0`** | a n-max 1 e' un **no-op esatto**: esiste solo la posizione 0 | audit 34 |
| **`LLAMA_KV_POSMIN_VERO`** | **da sola** e' un no-op **dimostrabile per aritmetica** (a M=0 la formula riproduce `seq_pos_max`) | audit 39 |
| **`LLAMA_OVERLAP_VERIFICA`** | copertura **zero a regime per progetto**: sotto CUDA graph gira solo alla cattura | audit 44, e §3.10-ter |
| **`--poll`** | il threadpool con poll esiste solo `#ifndef GGML_USE_OPENMP`, e la build ha `GGML_OPENMP=ON`. **Inerte** | audit 47, corregge audit 31 |
| **`KMP_BLOCKTIME`** | ggml lo imposta, ma vcomp (MSVC) non legge le `KMP_*`. **Intento muto su Windows** | audit 47 |
| **`LLAMA_KV_RING_VRAM_TRACE`** | `LLAMA_KV_RING_VRAM_TRACE_BUILD=OFF`: la trace **non e' compilata**, la variabile e' morta. E' una delle 77 del manifesto | audit 47 |
| **`GGML_CUDA_NCCL=ON`** | in cache ma single-GPU. Inerte | audit 47 |
| **`--cache-reuse` / context-shift** | morti per costruzione su DEEPSEEK4; `--swa-full` e' **disabilitato con avviso** | audit 39, 47 |
| **la cache esperti nel prefill** | il cancello ammette `ne[0]*ne[1] ≤ 64` id, ma a ub 64 gli id sono **384**. I dump dentro il prompt restano **congelati al valore del warmup** — ed e' la prova | audit 38, 44 |
| **il ripiego «catastrofico»** di `ggml-cuda.cu` | **mai preso** per i nostri formati (IQ2_XXS e Q2_K passano da MMQ). Ma `GGML_CUDA_FORCE_CUBLAS` lo renderebbe raggiungibile | audit 38, 41 |
| **`dsv4_repeat_streams` e i bias `kq_b`** (porto #25370) | emettono **zero nodi** nella nostra configurazione → il verdetto «zavorra viva» del primo giro upstream era sbagliato **due volte su tre** | audit 45 |
| **`GRIGLIA_VARIABILE`** | non e' codice morto: e' **un braccio di falsificazione mai sparato**, l'unico modo di riprodurre il difetto che la griglia fissa cura | audit 44 |
| **`LLAMA_CACHE_ESPERTI_FORK` con `K=0,5`** | il lettore del pin usa `atoi`: il ramo CPU si costruisce ma il pin non lo vede → split GPU/GPU, ASYNC non spedisce. **E' il tappo dell'esperimento piu' importante** | audit 44 |
| **l'HEAD `babd15238`** | contiene due difetti corretti solo nel working tree (ubatch di decode a 8: avvelena ogni braccio dell'**1,8%**). «Si compila l'albero, non l'HEAD» | audit 40 |

### 3.10-quinquies ⛔ `audit/51-join-async.md` predisse **+26%**, la misura ha dato **+0,14%** — e il file non porta nessuna marca

Il caso piu' pulito di documento falsificato dai fatti e mai ritirato.

- **Previsione**, `audit/51-join-async.md`, scritta **prima** della patch: recupero
  di `45,0 × 0,65 = 29,25 ms/ciclo` → ciclo da 140,6 a **111,35 ms** →
  **16,65-16,74 t/s** da 13,19-13,26. Fascia di falsificazione dichiarata:
  «recupero sotto **10 ms** smentisce l'attribuzione ai drain».
- **Misura**, `LEDGER_11_AGOSTO.md` §16.3: `j_rif` **14,46** → `j_on` **14,48**.
  **+0,14%.** Il `sync` scende del 13% (2,166 → 1,884) e il ciclo non si muove
  (127,9 → 127,8).
- `RIPRESA_12_AGOSTO.md:38-39` lo archivia: «`LLAMA_OVERLAP_JOIN_ASYNC` acceso
  toglie il 13% del `sync` e **vale lo 0,5%**».

La previsione centrale era sbagliata di **26 punti percentuali**, la fascia di
falsificazione dichiarata dall'autore stesso e' stata **attraversata**, e
`audit/51-join-async.md` sta ancora nella cartella senza una riga in testa.
Peggio: l'audit 51 era gia' in tensione con tutto il resto del suo gruppo — il
suo 16,7 supera **ogni** tetto derivato per quella base (audit 33: **14,4**;
audit 33 riparato: 14,4-15,3; audit 37: **13,44**) — e il numero e' stato scelto
senza fare prima la corsa di profilo che `audit/44-overlap-macchina.md` metteva al
primo posto della sua tabella §9.

**Regola che ne esce**: una previsione con fascia di falsificazione dichiarata
vale il doppio — ma solo se qualcuno torna a scriverci sopra l'esito.

### 3.10-sexies ⛔ La BASE DI RIFERIMENTO e' cambiata a meta' campagna, e i cancelli vecchi sono stantii

Gli audit del 10/8 usano **due** riferimenti diversi come cancello d'identita', e
nessuno dei due file dichiara il cambio:

```
  audit 35, 36, 37, 40   ->  SHA CF2DEEA06E90   12,83-12,92 t/s
  audit 47, 48, 49, 51   ->  SHA 33D76723EB8D   13,19-13,26 t/s
```

E `audit/35-acceptmoe-rifusa.md` dichiara **morta** una base ancora precedente
(`B396AB2137B2080A` / 10,40-10,47). **Ogni cancello che riusa uno SHA di un'altra
fase e' stantio**, e i `t/s` attesi scritti dentro i cancelli non sono
confrontabili fra i due gruppi. Sommato al gradino del 12/8 (§4.2), oggi
esistono **quattro** basi di riferimento nell'archivio e nessun documento le
elenca.

**E c'e' una trappola gia' scattata due volte**: `audit/39-seqposmin-bugia.md`
avverte che **`E3B0C44298FC` e' lo SHA della stringa vuota**, e che ha «gia'
fatto passare due cancelli su corse che non avevano prodotto niente». Regola:
«contate i caratteri, non lo SHA».

### 3.10-septies ⛔ Altri contatori il cui nome non dice cosa misurano (forme b e c)

Raccolti dagli audit e da verificare prima di citarne i numeri. Tutti hanno un
`file:riga` nell'audit indicato — che pero' e' soggetto alla §3.4-bis.

| contatore / riga di log | cosa sembra | cosa e' | fonte |
|---|---|---|---|
| `guasti` | statistica di prefetch (e con `W=0` il lettore salta la riga) | **uscita numericamente sbagliata**: matmul con i pesi di un altro esperto, SHA rotto. Senza il marcatore «uscita NON valida» che invece il rilevatore replay usa | audit 42 §3.1 |
| `pubblicazioni` contro «lanci visti dal device» | due misure della stessa cosa | la VRAM a fasi **azzera `div[0..4]`** a ogni cambio fase mentre `pubblicazioni` (host) sopravvive → dopo un cambio fase si diagnosticano **replay saltati inesistenti**, o una divergenza contata sparisce | audit 42 §3.2 |
| `mean_len` | token per forward | statistica di **accettazione**, e **media condizionata** (solo i cicli con bozza). Quindi `ciclo = 1000·mean_len/t_s` **non e' un tempo di ciclo**: e' un ibrido — ed e' la grandezza su cui sono costruiti i «tetti» | audit 33, 34 |
| `acc per pos` | gradiente per posizione | curva di **sopravvivenza** `P(accettati ≥ i+1)`. Il gradiente e' il condizionale `v[i+1]/v[i]`. Letta come gradiente fa concludere che la coda e' marcia quando non lo e' | audit 43 |
| `draft acceptance` | p1 | token accettati/generati: **coincide con p1 solo a n-max 1**. Il ledger ha gia' rischiato di scambiarli due volte | audit 43 |
| blocco `statistics draft-dspark` | accettazione del proponente | **gonfiato ~+13%** dai replay. Leggere solo i contatori per-slot | audit 43 |
| `GiB residenti` (reap) | stato corrente | **cumulativo mai decrementato** (somma al lock, non sottrae allo sblocco) | audit 46 |
| `colpi %` con AcceptMoE accesa | tasso di colpi | le righe mascherate domandano **solo residenti**: sono colpi per costruzione. Il metro pulito sono i **buchi assoluti per token** | audit 35 §6, audit 36 |
| `LLAMA_CKPT_CRONO=0` | spegne i checkpoint | spegne il **CRONOMETRO**. I salvataggi girano comunque | audit 47 |
| `LLAMA_KV_ROLLBACK_PARZIALE=1` | evita il costo del rollback | evita restore+replay ma **NON il salvataggio**, che non ha leva | audit 47 |
| file `curve-ub{2,8,16,64}-*` | spazzata di `-ub` del bersaglio | il bersaglio e' **sempre a 64**: a variare e' l'ubatch della **bozza**. «Il nome inganna» | audit 38 |
| dump della cache «dopo il prompt» | prefill | warmup + i **primi ~72 token di decode**. «Ci sono cascato per un'ora scrivendo questo rapporto» | audit 38 |
| `buchi` fra bracci bit-identici | proprieta' della cache | **istantanee a battito**: +10,9% (175.861 contro 158.631) fra due bracci con la stessa identica computazione. Dispersione ±4% fra corse identiche | audit 36, 42, 44 |

**Nota di metodo che vale piu' della lista**: `audit/33-rollback-parziale.md` fa
la cosa giusta al contrario — verifica **esplicitamente** che `update_spec_stats`
non e' campionata, quindi il conteggio dei restore e' esatto **per costruzione**,
senza bisogno di eseguire. E' il modello: dichiarare la natura del contatore
prima di citarne il numero.

### 3.11 ℹ Cose che ho verificato e che invece TENGONO

Per non far perdere tempo a chi rifa' i controlli:

- **`ATLANTE_LEVE.md` §1, le sette categorie**: cache 17, spec 8, compute 10, kv
  10, vram 8, reap 17, diag 7 = **77**. Contate a mano su `server.cpp:38-120`:
  **tutte e sette esatte**.
- **Tutti i difetti citati dall'ATLANTE §2a/§2b coincidono col manifesto**:
  `SPIN=256`, `ACCEPTMOE_BATCH_MAX=8`, `KV_ROLLBACK_MARGINE=4`,
  `RING_PROFONDITA=380`, `VRAM_A_FASI_SLOT_MAX=1024`, `VRAM_A_FASI_UB=64`,
  `FORK_BLOCCHI=32`, `CACHE_BOZZA_BATTITO=60` (e il codice conferma: il difetto
  vero e' 60, `cache-esperti.cu:357`).
- **`ATLANTE_LEVE.md` §4, riga `K` frazionario**: «misurati PRIMA della correzione
  del parser `atoi`/`atof` (`979efd899`)». Verificato: oggi si legge con `atof` in
  **entrambi** i siti (`llama-context.cpp:1638`, `llama-graph.cpp:1825`). La
  correzione c'e'; i bracci restano da rifare.
- **`us_calc_altro` e' onestamente marcato**: `ggml-backend.cpp:1797` —
  `// graph_compute degli altri backend (lancio)`. La forma (c) del mandato qui
  **non** si applica: e' stata gia' corretta, e `12AGO_LA_REGRESSIONE_DEL_SYNC.md:32`
  riporta «calc altri (lancio)» con la nota.
- **`DOVE_VA_IL_TEMPO.md:77`** cita `ds4_cuda.cu:1897` per
  `cuda_stream_selected_cache_invalidate`: **esatto al netto della deriva** (la
  definizione e' proprio li').

---

## 4. LE DOMANDE GIA' CHIUSE CON UN NUMERO

Da non rimisurare. Fonte fra parentesi.

### 4.1 Configurazione e velocita' (corpo B, banco attuale)

| domanda | risposta | numero |
|---|---|---|
| Qual e' la SOTA? | 512 slot + `FORK=2` + `FORK_BLOCCHI=8` | **14,77 t/s**, ciclo 125,3 ms, contro 14,22 del riferimento appaiato, 2 ripetizioni allo 0,6% (`RIPRESA_12_AGOSTO.md:23`) |
| `FORK_BLOCCHI` conviene? | si', ed e' anti-correlato con la copertura | 8 → 12,38 t/s / ciclo 80,8 / copertura 5,1%; 32 (difetto) → 11,83 / 84,5 / 99,3%; 64 → 11,86; 112 → 11,91 (`ATLANTE_LEVE.md:47-53`) |
| Il fork vale, senza bozza? | si' | 11,28 → 11,90-11,92 t/s, **+5,5%**; sonda: 19.730 join visti, 19.613 gia' finiti = 99,4% (`ATLANTE_LEVE.md:82-87`) |
| Il fork vale, con la bozza? | **no**: −4,2% | `FORK=0` 14,17 / p1 0,86470 / 560,93 GiB; `FORK=2` 13,57 / p1 **0,75806** / 466,58 GiB. Ciclo −1,2%, byte −16,8%, ma p1 −12,3% (`ATLANTE_LEVE.md:97-100`) |
| A che batch il fork e' bit-esatto? | **≥ 2**; a 1 token no | causa: `mul_mat_vec_q<type,1>` contro il kernel MoE, albero di riduzione diverso (`ATLANTE_LEVE.md:108-115`) |
| Oltre 512 slot? | muro di VRAM, non politica | 512 → 12,01; **768 → 9,44**, matmul +78% (`RIPRESA_12_AGOSTO.md:34-36`) |
| Il join e' sync-bound? | **no**, per la terza volta | le barriere valgono **1/8**; il resto sono **15,4 ms per grafo** di calcolo CPU non coperto. `JOIN_ASYNC` toglie il 13% del sync e vale **0,5%** (`RIPRESA_12_AGOSTO.md:36-39`) |
| Serve un proxy sull'host? | no | giro di ritorno **11 µs**; `cudaMemcpyAsync` interferisce col calcolo **piu'** del nostro kernel a 8 blocchi: **+4,91 contro +2,91 ms** (`RIPRESA_12_AGOSTO.md:40-43`) |
| I pesi densi si possono liberare? | no, decima volta | **99,843%** dei 7383,67 MiB e' riletto a ogni token (`RIPRESA_12_AGOSTO.md:44-46`) |
| `LLAMA_OVERLAP_FINESTRA` quanto vale? | **+4%, satura a n=4** (attesa +50%, sbagliata) | commit `d2387dd3a` |
| Quanto e' avanti upstream? | base comune `5c3a58686` (9 luglio) | upstream **+436**, noi **+131**. I «108» e «153» erano artefatti del fetch shallow (`RIPRESA_12_AGOSTO.md:73-76`) |

### 4.2 Il gradino del 12/8 (obbligatorio prima di confrontare qualunque numero)

| domanda | numero |
|---|---|
| Quanto si e' perso al riavvio delle 06:07? | **−13/−14%**: 14,48/14,46 prima, 12,79-12,45 dopo. Due catene omogenee: −14,3% e −13,1% (`12AGO…:9-21`) |
| Dove sta? | **tutto nel sync**: ingressi 2,839 → 7,202 (+154%), di cui sync 2,166 → **6,488 (+200%)**. Calc CPU 0,848 → 0,810 (piu' basso), calc altri 3,015 → 2,933 (piu' basso) (`12AGO…:26-34`) |
| Costo per confine | ~76 confini/token × **+140 µs** = +10,7 ms/token contro +12,8 osservati (`12AGO…:36-38`) |
| Costo della sonda `GGML_SCHED_PROFILO` | era **0%** (14,78 contro 14,77), oggi **3,6%** (12,835 contro 12,375) (`12AGO…:40-42`) |
| Escluse con un numero | configurazione (77/77), binario (stesso .dll delle 02:35 aveva fatto 14,46), i tre KB (installati 03:28, due ore PRIMA delle corse buone), traiettoria (SHA `FE90AC77066D`, p1 0,85449, mean len 1,85, 627 grafi riusati), banda del letto mappato (**24,4 GiB/s** a 4 e a 64 GiB), GPU (SM 1950 MHz, PCIe gen4 x16, throttle 0x0, 94 W/170), CPU (boost 118-123%), driver (596.21 di aprile), **OneDrive (chiuso fa 12,21, cioe' PEGGIO)**, VRAM libera (**11255 MiB in tutte e sette**), contesa (server vivi max 1), secondo riavvio (12,30) (`12AGO…:44-68`) |
| Curva di capienza nel regime nuovo | 512 → 12,30/12,45 (ciclo 150,7/148,9); 448 → 12,91/12,99/12,78 (144,6/144,0/146,3); 339 → 12,63/12,82 (**139,2/137,3**); 256 → **10,44** (178,2). Sul **ciclo** vince 339, sul **t/s** vince 448 (`12AGO…:78-83`) |
| Precisione dello strumento | la ripetizione a 339 riproduce `sync` alla **terza cifra** (5,019 vs 5,017) (`12AGO…:89-91`) |
| Prefill del banco | **non e' una banda**: prompt di 68 token, `ub 512` → 21,9 e `ub 64` → ~22 (`12AGO…:125-128`) |

### 4.3 Le leve che promettevano molto e hanno dato zero (`ATLANTE_LEVE.md:187-199`)

| leva | verificato che fa | effetto sul ciclo |
|---|---|---|
| prefetch (`_W`, `_PREFETCH_FILTRO`) | colpi fino al **78%** | **da −15% a −44%** (non ~0) |
| `LLAMA_ACCEPTMOE` | **−349 GiB** di trasporto | ~0 |
| capienza `_SLOT` 339→480 | colpi 54,0 → **63,8%** | **−8,8%** |
| join asincrono | sync **−30%** | ~0 |
| `LLAMA_OVERLAP_SPIN` | da 2M a 0 | 0 |
| `LLAMA_VRAM_A_FASI` livello 1 | restituisce **506 MiB**, SHA identico | 0 |
| checkpoint | **2,36 ms/ciclo** | 1,6% |
| `ub` 64 → 1024 | prefill **×4,5** | **0 sul decode: e' gratis** |
| `ub` 1024 → 2048 | 4 passate invece di 7 | **−47% di prefill** |
| `K` frazionario | 6 bracci (1,5/2,0/2,33/2,5) | **contaminati dal parser `atoi`, mai rifatti** |
| D2R (fusione) | +25% dichiarato upstream | **mai misurato** |

### 4.4 Vincoli fisici misurati (`ATLANTE_LEVE.md:211-238`)

```
RAM bloccata        tetto ~78.300 MiB; esperti mappati 74.304; KV compresso
                    +6,6 MiB ogni mille token
VRAM condivisa      Windows la limita a ~76,7 GB; i mappati ne usano 74,3
VRAM dedicata       12.288 MiB; desktop 600-700; parte densa 7.384;
                    cache esperti 6,75 MiB per slot
PCIe gen4 x16       DUE NUMERI INCOMPATIBILI: 24,35-24,46 GiB/s (microbanco,
                    400 x 6,75 MiB in 108,28 ms) contro 18,4 GiB/s (audit).
                    Usare 18,4 come costante fisica unica E' SCORRETTO
deriva del banco    2,4% fra due corse identiche a SHA identico
ricattura grafo     ~50 ms a ogni cambio di taglia del batch
sfratto sequenziale ~0,07-0,08 ms per slot per ciclo (DEDOTTO da 3 punti)
contesto 104k       CARICA: ub 64 -> VRAM 419 MiB, prefill 22,61, decode 9,71;
                    ub 512 + indexer fuso -> VRAM 965, prefill 75,62, decode 9,81
ripristino slot     0,68-0,78 s, 23.693 token, 233,5 MiB -- ma la richiesta
                    successiva ri-prefilla lo stesso. Causa IGNOTA
```

### 4.5 Dal `LEDGER_11_AGOSTO.md` — i bracci che NON vanno rifatti

| braccio | configurazione | numero | verdetto |
|---|---|---|---|
| `g_dom` | `DOMANDA_DMA=1` | 14,25 contro 14,24 del riferimento, SHA identico | **leva = ZERO**; sposta il 2,0% dei byte |
| `w2` / `w4` | prefetch cieco W=2 / W=4 | 6,03 (ciclo 300,2) / **4,68** (393,2); 3.081 GiB in prefetch, 386.100 chunk scartati | il ciclo **raddoppia** |
| `o_ora` | prefetch con previsione **esatta** (oracolo) | 5,97 contro 5,89 del cieco e **11,89** senza | **sapere tutto vale +1,4%**: il prefetch e' falsificato dall'alto |
| `sc_w2s1` / `sc_w1s1` | SCUDO=1 | 10,99 / 11,05 contro 11,22, **0,00 GiB in prefetch** | proteggere i residenti e' **neutro-negativo (−1,5..−2,0%)** |
| `d_w1` / `d_w2` / `d_w2c` | DMA fra strati | 11,04-11,13 contro 11,22; **chunk consegnati 0**, scartati 6.738-7.158 | ⚠ **NON e' chiusa**: i tre bracci girano a 46,4-46,7% di colpi e il cancello ammette da **53,4%** — lo zero misura il cancello. Vedi §3.1-bis |
| overlap K | K=2 / K=1 / spento | 13,96 / 10,76 / 9,80; colpi **56,0% / 28,3% / 18,8%** sugli **stessi 339 slot** | i colpi misurano la frazione lasciata alla GPU, non la cache |
| capienza senza lane | 339 / 448 / 480 / 512 / 544 | 9,93 / 12,32 / 12,41 / **12,64** / **MORTO** | +24,1% da 339 a 448; 512 con **270 MiB liberi** |
| capienza con lane | 339 / 448 / 512 | 14,20 (ciclo 131,0) / 13,96 (129,7) / 14,06 (**132,3**) | +7,9 pt di colpi, −42,5 GiB, **e il ciclo peggiora**: sesta conferma orchestration-bound |
| `f0`/`f1`/`f2` | FORK 0/1/2, banco spoglio | 11,28 / **11,90** / 11,92 | attesa dichiarata prima: **11,90**. Il modello predice |
| blocchi | 8 / 32 / 64 / 112 | 12,38 / 11,83 / 11,86 / 11,91; copertura 5,1 / 99,3 / 99,5 / 91,4% | **32, il difetto, e' il punto peggiore della curva** |
| `x0`/`x1` | FORK=2 `ESATTO=1` contro FORK=0 | **identici cifra per cifra** (11,28 / 88,7 / SHA `5CD5806D6CA0`) | `ESATTO=1` fa cio' che dichiara; la seconda sorgente di divergenza vive a **batch ≥ 2** |
| `e_e1`/`e_e2` | `ESATTO=1` e `=2` con la lane | 13,88 / 13,91, p1 **0,74381 entrambi** | **cancello FALLITO**: la cura **cambia** la divergenza, non la toglie |
| `j_on` | `JOIN_ASYNC=1` | 14,48 contro 14,46; sync 2,166 → **1,884 (−13%)**, 10,7 copie/grafo | il ramo gira e morde sulla grandezza accusata, e vale **0,5%** |
| `j_f1`/`j_f4`/`j_f8` | `+FINESTRA` 1/4/8 | sync **1,911 / 1,941 / 1,878** = piatto | **falsificazione passata**: satura per **barriere**, non per ampiezza |
| microbench concorrenza | calcolo ∥ copia | calcolo 75,39 ms (318,3 GiB/s = 88% del picco), copia 28,17 (24,00 GiB/s), **insieme 78,01** | 28 ms di trasporto ne costano **2,62 (9%)** se girano accanto |
| traccia di uno strato | `kern_copia` | **810,7 µs** il gate, 1,1 e 1,1 gli altri due; gap 0,1 µs | **una copia su tre fa tutto**: la pipeline intra-strato vale +2% |
| `simula_sfratto.py` | 339 / 448 / 512 slot | LRU 40,3 / 47,5 / 50,8 · BELADY 63,4 / 68,3 / 70,5 · CONSUMATO 12,6 / 14,8 / 16,1 | i +23 punti di Belady sono un **TETTO**: raccoglibile **+4..7 pt ≈ +6%** |
| cinque euristiche | LFU · MASSA · SLRU · RIUSO · CONSUMATO | a 339: 37,7 · 10,7 · **6,8** · 7,8 · 12,6 contro LRU 40,3 | **nessuna batte la LRU** tranne SLRU da 448 in su (+2,9/+2,0), che a 339 crolla |
| finestre di predizione | W da 2 a 100, K=448 | predittivo **fra 44,5% e 47,1%**, piatto; oracolo 100% → 41,9% | **il predittivo non dipende dalla finestra**: solo il futuro sposta il numero |
| distinti in prefill | prosa / codice | 10.152 (92,2%) / 8.827 (80,2%); nessuno strato sotto 157/256 | **non esiste un sottoinsieme** |
| nsys `sc_rif` | 500 token, node trace | kernel 46.018,3 + copie 1.408,3 su 48.700 µs | **occupazione GPU 97,3%** |
| il conto dei 18 t/s | 84,0/11,90 → +motore di copia ~77/~13,0 → +finestra di strato ~57/~17,5 → tetto 54,2/18,5 | | **servono entrambi i pezzi**, nessuno da solo ci arriva |

### 4.6 Dagli audit — chiuse con un numero, e con la marcatura `[MISURATO]`

Solo quelle che non compaiono gia' sopra. Numeri presi dagli audit, **non
riverificati da me**: il perimetro e' quello della §3.10-sexies (quattro basi
diverse) e della §3.10-septies (contatori dal nome ambiguo).

| domanda | numero | fonte |
|---|---|---|
| Quanto costava il difetto `W=2`? | W=0 → **9,26 t/s** · W=1 → 7,90 · W=2 → **6,89**. Il difetto perdeva **37,2 ms/token, −25,6%** — e la misura era **gia' nel sorgente**, `cache-esperti.cuh:32-34` | audit 47 |
| LRU contro orologio, a 380 slot | colpi **45,2% contro 33,5%** — ma **un A/B in t/s non esiste**, quindi «LRU e' il difetto giusto» resta [IPOTESI] | audit 42 §1.1, 47 |
| Quanto costa la scansione LRU? | O(n_slot) per sfratto → ~**39.000 iterazioni/token** a 339 slot, stima **0,2-0,8 ms/token**, ×4 a 1.400 slot. Budget dichiarato dal contratto: 5 ms/token | audit 42 §1.2 |
| `-cms` sul re-prefill | 288 s → **2,7 s**, fattore **108**. Il numero da usare e' **32**, e la regola vera e' che i checkpoint **nascono ai punti di rottura**: `-cms` e' solo un **veto** | audit 39, 47 |
| `-ub` sul prefill | 22,6 → **72,9 t/s, ×3,2**. Modello a passate: `K = 4.045 ms/passata`, autoconvalida `74.304 MiB / K = 18,4 GiB/s`; predizione fuori campione 90,4 s previsti contro **89,3 misurati (1,2%)** | audit 40, 47 |
| Il termine fisso del prefill | **non e' costante**: `C(L) = C₀ + s·L`, C₀ **5,0-5,2 ms**, s **0,10-0,15 ms per 1.000 token**. Le due pendenze misurate a ub 512 coincidono (0,146 e 0,147) e la controprova aritmetica da' 774 kFLOP/token/token-di-contesto | audit 41 |
| Quanto del prefill e' spiegato? | libro mastro 2,5-4,2 contro **5,5±0,3**: **30-50% non spiegato**. Due indiziati con discriminatore nsys gia' scritto | audit 41 |
| L'op indexer fusa | **11 nodi → 1**, −210 nodi. Ma il metro **non e' il t/s** (+0,14%, dentro un rumore di ±1,6%): e' il **buffer di calcolo**, da 6.960,93 a **~430 MiB, ~16×**, a ctx 104k | audit 48 |
| La fusione HC | **+16,5%**, grafo 34.329 → **10.507 nodi** | audit 45 |
| AcceptMoE, coppia a conf 0,8 | buchi **−38,5%** (137.458 → 84.499), byte a domanda **−349,3 GiB** — e t/s **10,43 → 10,37**. La resa cala: mean_len −8,3%, cicli **+29%**, rifiuti della bozza 32% → **55%** | audit 36 |
| AcceptMoE, costo del macchinario a leva spenta | eval 127.393 contro 127.309 ms = **+0,07%**, uscita bit-esatta, con 80 lanci kernel per forward | audit 36 |
| Il tetto della base attuale | **14,4 t/s** (non 13,79): siamo all'**89%**. Riparando il rollback: 14,4 / 14,8 / 15,3 per C_save 0/4/8 ms | audit 33 |
| Il rollback parziale | costa **+1,16 MiB di VRAM** (non una fotografia): basta allargare l'anello di M righe. Premio atteso **13,44**, banda 13,2-13,7, **insensibile a C_save** | audit 37 |
| Il checkpoint speculativo | **11,7 MiB** in ~124 `tensor_get`, **~599 volte** per 1.200 token. Scatta a **ogni** episodio perche' DEEPSEEK4 non e' in `llm_arch_supports_rs_rollback` | audit 43, 47 |
| Il tetto della RAM bloccata | fra **74,7 GiB (passa) e 76,9 (no)**. A 104k il bilancio arriva a **78.231 MiB = 76,4 GiB**, cioe' dentro la banda in cui il carico muore. Correzione di unita': 74.304 MiB sono **72,6 GiB**, non «74,3» | audit 42, 46 |
| p1 e' deterministico? | **si', alla quinta cifra**: due corse identiche danno `0,86470` e `0,86470`. Ma lo spread fra bracci della stessa famiglia e' **±0,05**, piu' grande dell'effetto di quasi ogni leva | audit 43 |
| p1 dipende dal contenuto | **0,865 su HTML contro 0,667-0,676 su prosa** | audit 43 |
| Il gradino condizionale della bozza | e' **uno solo**: 0,86 → 0,78 fra la posizione 1 e la 2. Dalla 2 alla 5 la banda e' **0,75-0,85 senza pendenza** — la sopravvivenza crolla perche' e' un **prodotto**, non perche' la coda peggiori | audit 43 |
| Il confronto con DwarfStar | noi **13,23** contro DGX Spark **18,05** (**73-96%, quasi parita'**), M5 Max 39,35 (34-48% con **1/40** della banda), e **battiamo** il loro streaming (12,16). €/(t/s): **~83 contro 150-300** = miglior rapporto di **2-3,5×**. Ma **tutti i loro numeri sono senza speculazione, il nostro no** | audit 52 |
| Nessuno satura la banda | ~5-5,7 GB/token: M3 Ultra usa il **20%** del suo tetto, Spark il **25-30%** | audit 52 |

### 4.7 `[A]` Chiuse sul runtime DS4 — il meccanismo vale, il numero no

| domanda | numero | fonte |
|---|---|---|
| Dove andavano i 288 ms/token | `read_gate` **167,3 ms = 70,5%**; drain 20,3; deliver 5,8; `wait_ms` e `pickup_lag_ms` **entrambi 0** | `mappa/DOVE_VA_IL_TEMPO.md:19-33` |
| Il muro delle letture | **3,25 GB/s** dalla standby list, 1,578 GiB/token, 718 letture/token, `inflight_avg` 2,32 su 4 | idem |
| Perche' 3 letture per esperto | gate/up/down letti **separatamente**: 718 invece di 258 chiamate | `DOVE_VA_IL_TEMPO.md:58-66` |
| Il modello quanti esperti tocca | **258 distinti per token, mediana = min = max** (costante); Jaccard fra token consecutivi **0,232**; **161 nuovi su 258** | `mappa/RAGIONAMENTO_MODELLO.md:54-57` |
| Insieme di lavoro | 1 token → 258; 4 → 687; 16 → 1.773; 64 → 3.980; 256 → **6.803** | `RAGIONAMENTO_MODELLO.md:65-69` |
| Copertura dei piu' caldi | 181 → 27,2%; 320 → 37,4%; 512 → 46,8%; 1024 → **62,3%** | `RAGIONAMENTO_MODELLO.md:60-63` |
| Belady per capienza | 181 → 47,8%; 274 → 56,1%; 320 → 59,0%; 512 → 67,3%; 1024 → **77,8%** | `RAGIONAMENTO_MODELLO.md:75-79` |
| Il tetto della gerarchia di memoria | **~6,4-6,5 t/s**: Q2+gate 6,55 (togliendo i crolli), Q1 residente 6,36 (senza niente da paginare). Prefill 7,11 contro 2,3-2,5 | `IL_TETTO_E_ORCHESTRAZIONE.md:32-35, 79-85` |
| Il paging sparisce davvero? | si': fault duri/s mediana **0** (Q1) contro 795-1.124 (Q2) | `IL_TETTO_E_ORCHESTRAZIONE.md:20-27` |

---

## 5. LE CONTRADDIZIONI INTERNE

### 5.1 🔴 LRU: «prende ZERO colpi, e' la peggiore politica costruibile» ↔ «nessuna euristica implementabile la batte»

| | dice | fonte |
|---|---|---|
| 2/8 | **LRU 0,0%** · FIFO 0,0% · casuale 11,1% · **insieme caldo statico 28,2%** · Belady 47,8% · cache infinita 90,3%. «Su questo schema la LRU non e' una politica mediocre: **e' la peggiore costruibile**». Raccomanda l'insieme caldo statico, «anche piu' semplice» | `mappa/RAGIONAMENTO_MODELLO.md:13-19, 29-30, 88-92` |
| 11/8 | **Belady 63,4% contro LRU 40,3%**, e «**nessuna euristica implementabile batte la LRU**» (LFU, massa, SLRU, riuso, consumato: tutte sotto) | memoria `prefetch-falsificato-sfratto-vale-23-punti` |
| 11/8 | «Il **miglior set STATICO** fa **37,5%** contro il **59,4%** della LRU» | memoria `rotazione-64-percento-serve-il-futuro` |
| 12/8 | in produzione `LRU=1`, colpi misurati **55-60%** | `RIPRESA_12_AGOSTO.md:20`, `12AGO…:78-83` |

**I due verdetti sono opposti in segno**: al 2/8 lo statico batte la LRU di +28
punti, all'11/8 la LRU batte lo statico di +22. E `mappa/README.md:66-67` continua
a presentare il verdetto del 2/8 come il risultato che «ha falsificato in un colpo
tutta la nostra politica di residenza». Chi apre la mappa oggi ne ricava di
spegnere la LRU.

**La riconciliazione esiste gia' — ed e' sepolta nel docstring di un file
python.** `mappa/capienza.py` (righe 3-22) dice esattamente questo:

> «I numeri che giustificano il reap-loop vengono TUTTI da una simulazione a
> **181 slot su 4551, cioe' il 4% di capienza** […] Ma il reap-loop lavora sul
> gradino RAM↔SSD, e li' la capienza non e' il 4%: la RAM tiene circa il 58%
> degli esperti. **A quella capienza la curva e' tutta un'altra cosa — la LRU va
> a zero solo quando la cache e' molto piu' piccola del ciclo di riuso, e a meta'
> capienza non lo e' piu'.**»

Cioe': la LRU va a zero **solo** sotto il ~4% di capienza; a 339-512 slot siamo
in un altro punto della curva e la LRU vince. **Nessun documento `.md` rimanda a
`capienza.py`.** La spiegazione c'e' ed e' invisibile — e nel frattempo il
verdetto sbagliato viene rilanciato dal README della mappa.

### 5.2 🔴 Il manifesto e' «la verita' del binario» ↔ 19 voci morte e 15 leve non elencate

`ATLANTE_LEVE.md` §1 contro `tools/server/server.cpp:36` («Keep the defaults
aligned with their call sites» = manutenzione manuale) e contro la §3.1/§3.2 qui
sopra. Un documento che si dichiara «costruito dal CODICE, non dalla memoria»
riporta come inventario del binario una tabella scritta a mano.

### 5.3 🟠 `LLAMA_CACHE_ESPERTI_FORK`: «sempre 0, mai provata» ↔ «+5,5%» ↔ «−4,2%» ↔ «+3,9%»

Quattro verdetti nello stesso archivio, tutti veri **in regimi diversi** e non
sempre etichettati:

- `ATLANTE_LEVE.md` §2a (versione originale) — «sempre 0», da lista delle mai toccate.
- `ATLANTE_LEVE.md` §2a-bis — **+5,5%** sul banco senza lane CPU (11,28 → 11,90).
- `ATLANTE_LEVE.md:94` — «**MA SOLO SENZA BOZZA.** Con la speculazione accesa
  perde il **4,2%**» (14,17 → 13,57).
- `RIPRESA_12_AGOSTO.md:91-93` — «la leva sembrava perdere il 4,2% e **vale +3,9%**»,
  una volta riportato `FORK_BLOCCHI=8` dall'altro banco.

E l'unica misura precedente (`audit/32-seconda-posizione.md`, 9/8: +0,9%) era
presa **con la lane accesa a K=2, dove `kern_copia` muove 0,08 GiB e non c'e'
niente da coprire**. La §2a-bis dell'ATLANTE lo spiega; la §2a **non e' stata
cancellata** e continua a elencare la leva fra le mai toccate.

### 5.4 🟠 La capienza: «339→480 vale −8,8%» ↔ «339→512 vale +3,9%» ↔ «512 perde contro 448 e 339»

- `ATLANTE_LEVE.md:191` (tabella §4) — capienza 339→480: colpi 54,0 → 63,8%,
  **ciclo −8,8%**.
- memoria `277-copie-per-token-fallback-scheduler` — «sul banco senza lane la
  **capienza paga**: 339→512 fa **9,93 → 12,64 t/s**».
- `RIPRESA_12_AGOSTO.md:16` — 512 e' la configurazione da usare, **+3,9%** su 339.
- `12AGO…:78-83` — **dopo il riavvio la curva si ribalta**: sul ciclo vince 339
  (137-139 contro 149-151), sul t/s vince 448.

Quattro verdetti che dipendono da (lane accesa/spenta) × (prima/dopo il gradino
del 12/8). Solo l'ultimo lo dichiara.

### 5.5 🟠 Il prefill: `ub` «vale ×4,5 ed e' gratis» ↔ «a 68 token non cambia niente»

- `ATLANTE_LEVE.md:198` — `ub` 64 → 1024: **prefill ×4,5**, «0 sul decode: e'
  gratis». Memoria `prefill-due-manopole`: «`ub 512` vale **3,2×**».
- `12AGO…:125-128` — «Il prefill del nostro banco **NON e' una banda**. Il prompt
  e' di 68 token […] `ub 512` da' 21,9 e `ub 64` da' ~22, **identici**. I 100+ t/s
  di prefill sono di corse con prompt da 6000 token».

Non e' un errore: e' la stessa leva su due carichi. Ma l'ATLANTE riporta ×4,5
senza dire su quale lunghezza di prompt, e chi lo legge ci costruisce sopra.

### 5.6 🟠 PCIe: 24,4 GiB/s ↔ 18,4 GiB/s — **contraddizione gia' dichiarata, mai risolta**

`ATLANTE_LEVE.md:217-223` la dichiara esplicitamente: «DUE NUMERI INCOMPATIBILI,
non uno […] Finche' non sono etichettati, usare 18,4 come costante fisica unica
**E' SCORRETTO**». `12AGO…:56` rimisura **24,4 GiB/s** con `blocco.exe`; la
memoria `gpu-satura-41-percento-kern-copia` usa **18,2 GiB/s misurati contro 18,4
del microbench» per concludere che siamo gia' al tetto. L'ipotesi (24,4 = copia
sintetica da RAM pinnata, 18,4 = lettura a domanda da memoria mappata) **non e'
mai stata verificata**.

### 5.7 🔴 La SOTA e' 14,77 **o** 14,46, e la differenza e' il doppio della ripetibilita' dichiarata

Dentro **lo stesso file**, `LEDGER_11_AGOSTO.md`:

- §15.2 `qs512b`, 512 slot + FORK=2 + blocchi 8: **14,77 t/s, ciclo 125,3**, con
  due ripetizioni che concordano allo **0,6%**.
- §16.3 `j_rif`, **stessa configurazione dichiarata** (512 slot, FORK=2, blocchi
  8, lane K=2, bozza, 1.200 token): **14,46, ciclo 127,9**.

**2,1% di distanza fra due corse dichiarate identiche**, cioe' **tre volte e mezzo**
la ripetibilita' annunciata. `RIPRESA_12_AGOSTO.md:23` riporta solo 14,77, e su
quel numero e' costruito il confronto col riferimento appaiato (+3,9%).

### 5.8 🔴 Conclusioni ritirate PIU' AVANTI NELLO STESSO FILE, senza toccare la prima

`LEDGER_11_AGOSTO.md` e' un registro cronologico, quindi contiene i suoi stessi
errori in ordine. Chi lo apre e cerca una risposta trova la prima, non l'ultima:

| §  | dice | § | ritira |
|---|---|---|---|
| 12.5 | «`FORK=2` perde il 4,2%, e **la colpa e' del p1 che crolla del 12,3%**» — apre un cantiere sulla bit-esattezza | 15.3 | il crollo esiste **solo a 339 slot**: a 448 il p1 e' **0,86604**, cioe' **piu' alto** del riferimento 0,86470; a 512 e' 0,85449. **E' una lotteria di traiettoria, non un danno** |
| 7 | la finestra dell'overlap vale «fino a **+50%**» | 16.4 | **il join non e' sync-bound**: le barriere sono **un ottavo**; la leva vale **0,5%** |
| 6 | i **+23,1 punti** di Belady sono «sul tavolo» | 6 (correzione in coda) | erano un **TETTO**, non raccoglibili: raccoglibile **+4..7 pt ≈ +6%** |

### 5.9 🟠 `FORK_BLOCCHI=8`: tre cifre e due percentuali per la stessa corsa

- `LEDGER_11_AGOSTO.md` §13 → **12,38 t/s**, «+10,3% su 11,22»
- §14.1 riepilogo → «**12,43**, +10,8%»
- §14.1 braccio `x2` (`FORK=2 ESATTO=0`, stesso banco) → **12,39 t/s / 80,7 ms**
- `ATLANTE_LEVE.md:49` → **12,38 / 80,8**

Quattro numeri per lo stesso punto del banco spoglio.

### 5.10 🟠 La deriva del banco: 2,4% ↔ 2,2% ↔ «niente sotto il 4% era decidibile»

`ATLANTE_LEVE.md:224` la fissa a **2,4%** e su quella soglia diversi audit
dismettono leve («qualunque verdetto sotto il 3% va rifatto»).
`RIPRESA_12_AGOSTO.md:66-68` dice: «alle 05:00 la deriva era del **2,2%**» —
`f5` e `f5b`, stessa configurazione e stesso SHA, **14,17 e 14,48** — e conclude
«**niente sotto il 4% era decidibile in coda alla sessione**».
Ma altri bracci riproducono a **0,14%** (`g_rif`/`g_rifb`), **0,25%**
(`o_w0`/`o_w0b`) e **cifra per cifra** (`b_rif`/`b_rifb`, `x0`/`x1`).
**La deriva non e' una costante del banco: e' una proprieta' del braccio**, e
usarla come ghigliottina fissa ha gia' fatto dismettere leve.

### 5.11 🟠 Il cancello d'identita' SHA e' un protocollo che la configurazione adottata ha gia' sciolto

`audit/70-riquantizzare-il-denso.md` §5.2 pretende come protocollo di promozione
che «i due SHA candidati devono coincidere fra loro», usando la bit-identita'
come rete di sicurezza. Ma la configurazione di `RIPRESA_12_AGOSTO.md` **cambia
lo SHA per costruzione** (`5CD5806D6CA0` → `0EFF1EBB450C`; `33D76723EB8D` →
`FE90AC77066D`) e rende **i colpi non confrontabili** con `FORK=0`. Il protocollo
presuppone una rete che in produzione non c'e' piu'. La `RIPRESA` lo dice («**lo
SHA cambia**»), l'audit 70 no.

### 5.12 🟠 «La capienza non paga» ↔ «512 e' la SOTA»: e' la stessa domanda su due banchi

`audit/70` §6.2 usa la curva `ASYNC=0` GPU-only per concludere che gli slot sopra
512 non valgono; `LEDGER_11_AGOSTO.md` §9 mostra che con la lane 339→512
**peggiora il ciclo** (131,0 → 132,3) nonostante +7,9 punti di colpi. Ma §15.2
mostra che **512 + FORK=2 + BLOCCHI=8 e' la SOTA** (125,3 ms). **La capienza paga
solo in composizione col fork**: l'audit 70 e' stato scritto sul banco pre-fork.

### 5.12-bis 🔴 `audit/46-dormienti.md` e' stato superato da `audit/50-tagliati.md` **tre ore dopo**, e non lo dice

- `46-dormienti.md` (10/8 **09:20**) descrive `ring-esperti` e `reap` come
  sottosistemi **vivi ma dormienti**, con l'analisi riga per riga di
  `common/reap.cpp` (1.241 righe) e la raccomandazione «`reap` va cancellato
  quasi tutto».
- `50-tagliati.md` (10/8 **12:05**) esegue: i due sottosistemi **sono cancellati**.

Il 46 non porta nessuna marca. Non e' un dettaglio: e' l'audit che
`ATLANTE_LEVE.md` §3 indica come **la** fonte sul reap («46-dormienti —
ring-esperti, reap, kv-ring: cosa dorme»), ed e' uno dei 29 copiati in
`docs/porto/audit/`. Chi lo apre per capire il reap studia codice inesistente.

E il 50 a sua volta contiene l'affermazione falsa della §3.1 («la scansione non
trova piu' leve `LLAMA_REAP*`»). **La catena di verifica si e' chiusa su se
stessa senza toccare l'unico file che conta.**

Stessa forma della §5.8: la correzione esiste, e' arrivata presto, e non e' stata
propagata all'indietro. **Questo archivio non ha un meccanismo di ritiro.**

### 5.13 🟡 Un porto upstream che spegnerebbe una nostra leva

`audit/7x-up_c_model.md` §2.6: il nostro `llama-graph.cpp:864-868` fa
`lid_f16 = (name == "lid") && cparams.fused_lid`; upstream (`#25370`,
`2ed3c1abb`) fa `cparams.flash_attn && name != "lid"`. **Sono complementari**:
portarlo alla lettera **spegne l'op indexer fusa**. `audit/71-porto-upstream-11ago.md`
non lo elenca affatto (era fuori dal range dei 153 commit poi rivelatosi
artefatto del fetch shallow).

### 5.14 🟡 `MARKOV_IL_COLPEVOLE.md` ↔ `MARKOV_ASSOLTA.md`, `CANCELLO_NEUTRALITA.md` ↔ se stesso, `MANDATO_ANTICIPO.md` ↔ se stesso

Queste **non sono un problema**: tutte e tre portano il ribaltamento in testa al
file, con il link. Sono il modello da imitare. Le cito perche' chi cerca
contraddizioni le trovera' e non deve perderci tempo.

### 5.15 🟡 «68 audit» ↔ 73 file ↔ 29 copiati qui; «160 script» ↔ 226

Vedi §3.8. Tutti i conteggi dell'ATLANTE §2 («54 leve su 77 compaiono in almeno
uno script, 33 in nessuno») sono calcolati su 160 script su 226.

### 5.16 🔴 LE CONTRADDIZIONI FRA AUDIT — diciotto, e nessuna marcata

Gli audit si correggono a vicenda **in avanti**: il piu' recente vince, ma il
piu' vecchio resta identico sullo scaffale. Chi cerca una risposta e apre il file
col numero piu' basso (o col nome piu' pertinente) porta via il verdetto
sbagliato. Elenco completo, dal piu' costoso:

| # | contraddizione | chi corregge chi |
|---|---|---|
| 1 | AcceptMoE dichiarata «l'unica via sopra il muro», break-even p2' ≥ 0,45-0,60. Misurata: p2' **0,793/0,832 — sopra il break-even** — e t/s **8,96-10,37, sotto il muro** 12,83-12,95. Il modello di break-even e' falsificato: il collo non e' la qualita', e' la **resa del ciclo** | **36 → 32** |
| 2 | «Contare i ripristini richiede di eseguire» → e' derivabile dai contatori. E i numeri di 32 vengono da bracci sbagliati: 13,7% e' `fu0_k2b` (FUSO=0) e 30,9% non corrisponde a nessun braccio della base. Veri: **13,2%** e **24,5-29,4%**. Il «tetto 13,79» e' mal posto: vero **~14,4**, siamo all'**89%** non al 93,3% | **33 → 32** |
| 3 | conf-min data come leva che «morde» (8,69→9,99) → dimostrata **strettamente non-positiva a n-max 1** anche a sovrapprezzo zero. «Depennare il +3,8% dal registro» | **34 → 31, 32** |
| 4 | Il rimedio del rollback (fotografare l'anello) e' piu' caro del necessario: basta **allargarlo di M righe (+1,16 MiB)**. E il premio scende da 13,2-14,3 a **13,2-13,7, centro 13,44**, perche' `C_save` **resta pagato da entrambi i lati** | **37 → 33** |
| 5 | Il rollback misurato da' **12,94 t/s** e la SOTA post-rollback **13,21-13,23**, contro il **13,44** atteso da 37 (banda 13,2-13,7): sotto la banda | **43, 45 → 37** |
| 6 | Il margine SWA dichiarato «chiuso e va bene» → per code profonde la SWA grezza e' il **primo** muro (**128 posizioni**), e alzare `LLAMA_KV_ROLLBACK_MARGINE` **da solo non fa niente** | **39 → 37** |
| 7 | «LRU e' il default giusto» → **l'A/B in t/s non esiste** (solo colpi), e 42 §1.2 da' il meccanismo per cui potrebbe perdere: scansione **O(n_slot) per sfratto**, ~39.000 iterazioni/token, **0,2-0,8 ms/token**, che cresce con la capienza. 47 e 49 lo promuovono comunque a difetto | **42 → 47, 49** |
| 8 | L'ottimo `K=2` potrebbe essere gia' stato misurato **con AcceptMoE accesa** (36 ha scoperto che lo era quando la si credeva spenta), e nessun braccio ha mai misurato K × AM: **le due leve comprano la stessa merce** (i non-residenti). Inoltre l'ottimo di K non e' una proprieta' della macchina ma del **tasso di colpi**: ogni leva che muove i colpi invalida la spazzata K | **44 → 32, 35, 36 e la propria §2** |
| 9 | «Piatta sul progresso» era vera **solo a ub 64**, dove 39 ms di trasporto seppellivano una rampa da 0,3-0,8. E il termine C **non e' costante**: `C(L) = C₀ + s·L` con C₀ 5,0-5,2 e s **0,10-0,15 ms per 1.000 token** — non 5,8-7,3 fissi | **41 → 38, 40** |
| 10 | Previsione **16,65-16,74 t/s** che supera **ogni** tetto derivato per la base (14,4 / 14,4-15,3 / 13,44), scelta senza fare prima la corsa di profilo che 44 metteva al primo posto. Misurata: **+0,14%** (vedi §3.10-quinquies) | **misura → 51** |
| 11 | «Nessuna riga nuova nel log» come cancello C0 di AcceptMoE: **sbagliato**, la riga esce anche a leva spenta (`am_cont` allocato incondizionatamente). E 36 aggiunge il secondo strato: esce anche per l'**altra** cache | **35, 36 → `ACCEPTMOE.md`** |
| 12 | I checkpoint della **bozza** non sono «esclusi dal cronometro»: **non esistono a runtime** (il probe fa cadere `ctx_dft_seq_rm_type` a PART, `use_ckpt_dft` resta falso) | **43 → 16** |
| 13 | L'op indexer «identica riga per riga a upstream» → vero **con una eccezione**, il ramo `materialize` del kv-ring, verificata con diff testuale | **48 → 45** |
| 14 | Quattro verdetti del primo giro upstream corretti: #25370 inerte per 2/3 (`dsv4_repeat_streams` emette **zero nodi**, i bias `kq_b` non nascono mai da noi), #25784 liquidata in blocco mentre dentro c'e' il rollback dello stato compresso, #25832 schedata male | **45 → `UPSTREAM_390.md`** |
| 15 | Conteggio dei tagli: **~1.650 righe** stimate contro **2.072 nette** dichiarate, senza scomposizione della differenza | **50 ↔ 46** |
| 16 | `seq_rm` citato a `llama-kv-cache-dsv4.cpp:1307-1321` e a `:1646-1671`: **stesso codice, file cresciuto**. E' la §3.4-bis vista da dentro l'archivio | **47 ↔ 33** |
| 17 | La base di riferimento cambia a meta' gruppo: `CF2DEEA06E90`/12,83-12,92 (35,36,37,40) → `33D76723EB8D`/13,19-13,26 (47,48,49,51). Nessuno dei due gruppi lo dichiara | trasversale, vedi §3.10-sexies |
| 18 | Il nostro **13,23 include la speculazione**; **tutti** i numeri DwarfStar sono **senza**. Se non lo si dichiara accanto al numero, il confronto e' viziato | **52**, su se stesso |

**Cosa ne segue, ed e' la conclusione piu' importante di questa sezione**: gli
audit **funzionano** — quasi ogni errore e' stato trovato, e trovato in fretta,
da un altro audit. Quello che manca non e' la verifica: e' la **propagazione
all'indietro**. Nessun file corretto porta una riga in testa. Il costo si paga
tutto al momento della lettura, e lo paga chi non sa quale sia l'ultimo numero.

---

## RIASSUNTO — venti righe, priorita' alla §3

1. **La mappa del codice non e' del nostro codice.** `docs/porto/mappa/` e'
   estratta da `ds4-port` (runtime DS4/dwarfstark): 661 variabili `DS4_*`, **zero
   `LLAMA_*`, zero `GGML_*`**. Nessuno dei 78 file mappati esiste in
   `D:\llama-overlap`. E `catena.py:287` tratta come variabile **solo** cio' che
   comincia per `DS4_`: chiedere una leva `LLAMA_*` non da' errore, da' vuoto.
2. Campione richiesto: **2 su 5 esatti** — i due in `vram_expert_cache.cpp`. I tre
   in `ds4_cuda.cu` sono sfasati di 5-25 righe, perche' il file e' stato toccato
   **30 minuti dopo** la generazione di `mappa.json`. E `guardie.json` e' piu'
   vecchio di `mappa.json` (08:26 contro 09:48): le due meta' non sono coerenti
   nemmeno fra loro.
3. **Ma la regola vera e' peggiore, e vale per tutto l'archivio: 11 riferimenti
   `file:riga` su 13 che ho verificato sono sbagliati** (§3.4-bis), con scarti da
   1 a 2.290 righe. I due esatti sono in file che nessuno ha piu' toccato. In
   questo archivio un `file:riga` ha una vita di **ore**: cercare per simbolo.
4. **Il DMA fra-strati e' elencato fra le cose «chiuse con un numero», e il numero
   e' quello del suo cancello.** I tre bracci girano a **46,4-46,7% di colpi**; il
   cancello ammette da **53,4%** (`CACHE_ESPERTI_DMA_HIT_PM 534`,
   `cache-esperti.cu:81`, confronto a `:2438`). Sotto la soglia non ammette **mai**:
   i «zero chunk su settemila» misurano `534`. Il binario lo **stampa** all'avvio
   (`:1334-1342`, commit del 10/8 **prima** dei bracci). Un test lo chiude:
   `LLAMA_CACHE_ESPERTI_DMA_HIT_PM=400`.
5. **Il manifesto mente in due versi.** **19 delle 77 leve non sono lette da
   nessuna parte**: sono le 16 `reap` + 3 `LLAMA_RING*` dei due sottosistemi
   **cancellati** dal commit `4b852d6b9` (10/8, −2.121 righe), che dichiara di
   aver «tolto anche i riferimenti orfani: variabili d'ambiente» e ha lasciato
   in piedi proprio la tabella che finisce in **ogni log**. E il manifesto
   **omette almeno 15 leve vive**, fra cui `SFRATTO_PAR` — che sta nella
   configurazione SOTA — `OVERLAP_JOIN_ASYNC`, `OVERLAP_FINESTRA`, la famiglia
   `DMA` e `FORK_ESATTO/PRIORITA/SERIALE`. Nessun gruppo `GGML_`: non stampa le
   due sonde con cui misuriamo.
5-bis. **Due audit descrivono codice che non esiste piu'.**
   `audit/50-tagliati.md:38` afferma «la scansione dei sorgenti vivi non trova
   piu' […] leve `LLAMA_REAP*`» — le trova, a `server.cpp:96-111`. E
   `audit/46-dormienti.md` descrive `common/reap.cpp` come un modulo vivo da
   **1.241 righe** con quindici riferimenti puntuali: **il file e' stato
   cancellato**. E' uno dei 29 audit copiati qui, ed e' quello che l'ATLANTE
   indica come la fonte da leggere sul reap.
6. Quindi `ATLANTE_LEVE.md` §1 — «e' la verita' del binario, **non una lista
   scritta a mano**» — e' falso: `server.cpp:36` dice esplicitamente che i difetti
   si allineano a mano. E `12AGO…:46` usa «manifesto identico in 77 voci su 77»
   come prova che nulla e' cambiato: 19 di quelle voci non potevano cambiare.
7. **`GGML_SCHED_PROFILO` stampa medie cumulative dall'avvio, non finestre.**
   L'accumulatore e' una `static` mai azzerata (`ggml-backend.cpp:1905`) e la
   stampa divide per `prof.n_graphs` totale (`:2268-2292`), prefill compreso.
8. Il che tocca il documento piu' recente: `12AGO_LA_REGRESSIONE_DEL_SYNC.md`
   confronta `ingressi`/`sync`/`join` fra due corse senza dire a quale delle
   stampe periodiche si riferisce ne' con che composizione prefill/decode.
9. **Stessa forma sui COLPI**, il numero piu' citato dell'archivio: sono un
   `cudaMemcpy` del contatore device, cumulativo dall'avvio
   (`cache-esperti.cu:3777-3786`). La macchina una finestra ce l'ha
   (`colpi_finestra`, `:2438`); **la riga stampata no**. Corse da 600 e da 1.200
   token non hanno lo stesso denominatore.
10. E c'e' un'aggravante trovata dalla `lettura/05`: le quattro voci del worker
    sono divise per un `n_graphs` che conta **bersaglio + bozza** mentre il worker
    gira **solo sul bersaglio**, quindi sono **diluite**. Passa da li' anche il
    numero su cui poggia tutto il fronte aperto — i **15,4 ms/grafo** di calcolo
    CPU non coperto. La trappola era **gia' documentata** per l'altro runtime
    (`mappa/DOVE_VA_IL_TEMPO.md:90-96`) e non e' mai stata trasferita.
11. **`CURA`, `SCUDO` e `FORK_PRIORITA` sono inerti nella configurazione in uso**,
    e ora il binario lo **stampa** (`cache-esperti.cu:1309-1342`, `:1703`).
    `ATLANTE_LEVE.md` §2b le elenca ancora come normali leve «sempre 0», cioe'
    «da provare». Il codice e' piu' aggiornato della documentazione.
12. **Contraddizione peggiore: la LRU.** Il 2/8 «prende ZERO colpi, e' la peggiore
    politica costruibile, usate l'insieme caldo statico (28,2%)»; l'11/8 «nessuna
    euristica implementabile la batte» e «il miglior set statico fa 37,5% contro
    59,4%». **Segno opposto.** Oggi giriamo con `LRU=1` e 55-60% di colpi, e
    `mappa/README.md:66` continua a rimandare al verdetto del 2/8.
13. **La riconciliazione esiste ed e' invisibile**: sta nel docstring di
    `mappa/capienza.py` (righe 3-22) — la LRU va a zero **solo sotto il ~4% di
    capienza**, e a 339-512 slot non ci siamo. Nessun `.md` rimanda a quel file.
14. **La SOTA e' 14,77 o 14,46**: `LEDGER_11_AGOSTO.md` §15.2 e §16.3 danno due
    numeri a **2,1% di distanza** per la stessa configurazione dichiarata, cioe'
    tre volte e mezzo la ripetibilita' annunciata (0,6%). La `RIPRESA` riporta 14,77.
15. **`audit/51-join-async.md` predisse `16,65-16,74 t/s`; la misura ha dato
    `14,46 → 14,48`, cioe' `+0,14%`.** La fascia di falsificazione dichiarata
    dall'autore stesso e' stata attraversata, il numero superava **ogni** tetto
    derivato per quella base (14,4 / 13,44), e **il file non porta nessuna marca**.
16. **Diciotto contraddizioni fra audit, nessuna marcata** (§5.16). Gli audit si
    correggono a vicenda in avanti e in fretta — 36 falsifica 32, 33 corregge 32,
    37 corregge 33, 41 corregge 38 e 40, 42 contraddice 47 e 49, 43 corregge 16 —
    ma **il file corretto resta identico sullo scaffale**. Quello che manca a
    questo archivio non e' la verifica: e' la **propagazione all'indietro**.
17. Stessa forma dentro un file solo: il `LEDGER_11_AGOSTO.md` ritira le proprie
    conclusioni piu' avanti senza toccare la prima («il fork rompe il p1 del
    12,3%» §12.5 → ritirato §15.3; «la finestra vale +50%» §7 → §16.4 vale 0,5%;
    «+23 punti di Belady» → «era un TETTO, raccoglibile +6%»).
18. **Oggi esistono QUATTRO basi di riferimento e nessun documento le elenca**:
    `B396AB2137B2080A`/10,4 (morta), `CF2DEEA06E90`/12,83-12,92 (audit 35-40),
    `33D76723EB8D`/13,19-13,26 (audit 47-51), e il post-riavvio del 12/8. Ogni
    cancello che riusa lo SHA di un'altra fase e' stantio — e attenzione:
    **`E3B0C44298FC` e' lo SHA della stringa vuota**, ha gia' fatto passare due
    cancelli su corse che non avevano prodotto niente.
19. **`docs/porto/audit/` e' meno di meta' delle fonti primarie**: 29 file qui
    contro **73** in `D:\llama-overlap\audit` — e i 29 sono copie esatte, quindi
    il problema e' l'**assenza**, non la divergenza. Quattro audit che l'ATLANTE
    indica come «utili per la composizione» (`14`, `19`, `20`, `56`) non stanno
    qui. Conteggi da rifare: «68 audit» → 73; «160 script» → **226**. E la deriva
    del banco non e' una costante (2,4% / 2,2% / «niente sotto il 4%» contro
    bracci che riproducono a **0,14%** e cifra per cifra), ne' lo e' il PCIe
    (**24,4 contro 18,4 GiB/s**, dichiarato irrisolto e usato comunque).
20. **Cosa invece tiene, verificato**: le sette categorie del manifesto
    (17/8/10/10/8/17/7 = 77) sono esatte; tutti i difetti citati dall'ATLANTE
    coincidono col codice; i numeri di testa del `mappa/README.md` sono esatti
    (5.164 funzioni, 12.883 archi, 927 letture, 453 PRESENZA, 19.218 siti) tranne
    «10.059 condizioni distinte», che dal file ne da' **6.638**;
    `LLAMA_OVERLAP_K` oggi si legge con `atof` in entrambi i siti; e
    `us_calc_altro` e' onestamente marcato «(lancio)» a `ggml-backend.cpp:1797` —
    **la forma (c) del mandato e' gia' stata corretta, e non ne ho trovate altre.**
