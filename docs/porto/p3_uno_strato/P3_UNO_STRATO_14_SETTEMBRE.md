# P3 — Un solo strato nel server, MTP spento

Versione 1.0, 14 settembre 2026. Fase **P3** del [piano CPU/GPU](../PIANO_CPU_GPU_14_SETTEMBRE.md).
Contratto del planner: [P1](../P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md).
Esecutore: [progetto P2](../p2_esecutore/PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md) e
[esito della sua compilazione](../p2_esecutore/ESITO_COMPILAZIONE_P2_14_SETTEMBRE.md).
Misure e criteri: [protocollo](../PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md). Decisioni: [registro](../REGISTRO_CPU_GPU_14_SETTEMBRE.md).

Questa fase **integra nel server** l'esecutore di P2 e il planner di P1, su **un solo
strato**, con MTP spento. La patch e' unica: [`p3_uno_strato.patch`](p3_uno_strato.patch),
diff unificato rispetto allo snapshot immutabile di P0
(`D:\ds4_work\p0_snapshot_20260914\source`), che **non viene modificato**. Si applica con
`patch -p1 --binary`: il flag e' necessario perche' i sorgenti hanno terminatori CRLF, e
senza di esso `patch` rifiuta tutti gli hunk con «different line endings». Verificata con
`--dry-run` contro lo snapshot: 17 file, zero rifiuti.

**In una riga:** la patch funziona e a funzione spenta e' indistinguibile dal binario
precedente (18 impronte su 18 identiche, 24,4275 contro 24,4344 t/s); la modalita' attiva
taglia il 38,7% dei trasferimenti dello strato, ma **non** batte il riferimento — 23,51
contro 24,44 — perche' il meccanismo costa 1,80 ms per token e il risparmio di banda ne
restituisce 0,21.

---

## 1. Che cosa e' stato toccato, e che cosa no

| | |
|---|---|
| Copia di lavoro | `D:\ds4_work\p3_work\source`, copiata da `D:\ds4_work\p0_snapshot_20260914\source` (2999 file). Gli SHA256 dei sedici file toccati sono stati verificati contro `source_hashes.json` **prima** di modificarli: tutti coerenti |
| Build di lavoro | `D:\ds4_work\p3_work\build`, binari in `D:\ds4_work\p3_work\build\bin` |
| **Non** toccati | `qwen38_clean\bin_prod`, il lanciatore quotidiano, il modello, l'albero `qwen38_clean\source` e la sua `build`, lo snapshot di P0 |
| Commit | nessuno |

## 2. Lo strato scelto: **strato 1**

Il perimetro di P3 e' **un solo strato**. Va scelto fra i 47 supportati (gate/up IQ2_S
codice 22, down IQ4_NL codice 20); lo **strato 2** e' escluso perche' ha gate/up IQ3_S
(codice 21) — e' l'unico dei 48, come conferma `expert_layer_types.json` del prototipo:

| combinazione (gate, up, down) | strati |
|---|---|
| (22, 22, 20) — IQ2_S / IQ2_S / IQ4_NL | **47** |
| (21, 21, 20) — IQ3_S / IQ3_S / IQ4_NL | 1, ed e' lo strato 2 |

Fra i 47, la scelta e' guidata dalla distribuzione dei miss: uno strato che sbaglia di
rado la cache non esercita quasi mai il ramo CPU, e P3 non misurerebbe niente. Ricavato
da `trace64.jsonl` (36.913 piani, tratto caldo `step > 64`, 703 piani per strato):

| strato | miss medi per piano | frazione di piani con almeno un miss |
|---:|---:|---:|
| 0 | 5,420 | 0,960 |
| 1 | **4,535** | **0,976** |
| *2* | *4,494* | *0,983* (escluso: IQ3_S) |
| 12 | 3,807 | 0,947 |
| … | … | … |
| 31 | 0,596 | 0,403 |

**Si sceglie lo strato 1**: fra i 47 supportati e' quello con la **frazione piu' alta di
piani con almeno un miss** (97,6%), cioe' quello in cui il ramo CPU si accende quasi a
ogni token — che e' esattamente cio' che serve a una prova di integrazione — ed e' il
secondo per miss medi (4,535). Lo strato 0 ha piu' miss medi (5,420) ma si accende meno
spesso (96,0%). Lo strato 1 ha in piu' una proprieta' utile: e' **adiacente** allo strato
2 escluso, quindi la stessa corsa esercita il confine del ripiego.

Questo non e' un criterio di prestazione: e' un criterio di **copertura**. La scelta
dell'insieme di strati per il guadagno e' lavoro di P4.

## 3. Le opzioni di controllo

Tutte da **ambiente**, tutte lette **una volta sola** (static locale): cambiarle richiede
il **riavvio del processo**, come stabilito dal piano. Default: **spento**. Il preset del
banco le imposta nel suo blocco `env`.

| variabile | valori | default | chi la legge |
|---|---|---|---|
| `LLAMA_MOE_CPU` | 0 / 1 | **0** | libllama e backend CUDA |
| `LLAMA_MOE_CPU_LAYERS` | elenco separato da virgole, es. `1` | vuoto | libllama e backend CUDA |
| `LLAMA_MOE_CPU_MAX` | 0 / 1 / 2 (tetto strutturale 4) | 2 | libllama e backend CUDA |
| `LLAMA_MOE_CPU_DIAG` | 0 / 1 | 0 | libllama e backend CUDA |
| `LLAMA_MOE_CPU_REPORT` | N: stampa i contatori ogni N lanci di graph | 0 (mai) | backend CUDA |
| `LLAMA_MOE_CPU_THREADS` | core del pool | 4 | libllama |
| `LLAMA_MOE_CPU_WAIT_US` | scadenza del nodo host `wait` | 2000000 | libllama |
| `LLAMA_MOE_CPU_ACK_US` | scadenza del riconoscimento | 200000 | libllama |

Perche' le prime cinque sono lette da **due** lati: il planner decide sul dispositivo
(contratto P1 §4.2 passo 5) e il confine di P2 — una tabella C con due callback e quattro
puntatori — non porta configurazione, di proposito. Le due letture usano le stesse
variabili e la stessa semantica; una divergenza si vedrebbe subito perche' il ramo CPU
richiede che **entrambi** i lati siano d'accordo (senza hook installati il planner riceve
`cpu_max = 0`).

Con `LLAMA_MOE_CPU=1` ma nessuno strato ammesso, o con `LLAMA_MOE_CPU_MAX=0`, la funzione
si spegne con un avviso: non esiste una configurazione che accende meta' del percorso.

## 4. Come funziona, in ordine di esecuzione

```
   moe_grouped_plan_decode      commit differito, deduplica, classificazione,
                                PARTIZIONE CPU/GPU, slot ai soli miss GPU,
                                ALIAS per le route CPU
   moe_cpu_export_kernel        scrive job (token, esperto logico, peso originale)
                                e attivazione in memoria mappata; azzera IN LOCO
                                il peso GPU delle route CPU; __threadfence_system()
   cudaLaunchHostFunc(submit)   nodo host: pubblica e sveglia il pool
   moe_grouped_gather_decode    i SOLI miss GPU
   mul_mat_id gate/up, SiLU,    lavoro GPU, CONCORRENTE al calcolo CPU
   mul_mat_id down
   pesatura e riduzione         -> moe_out   (legge i pesi MASCHERATI)
   cudaLaunchHostFunc(wait)     nodo host: attende l'esito, con scadenza
   moe_cpu_merge_guard_kernel   veleno -> NaN; diagnostica -> confronto e azzeramento
   add: moe_out += y            legge `y` in ZERO-COPY dalla memoria mappata
   ... shared expert
```

### 4.1 Il planner (`fork-moe-kernels.cuh`)

- `plan->n_misses` significa ora **esclusivamente miss GPU da trasferire**. I quattro
  lettori storici — commit differito, contatori diagnostici, gather, traccia — sono stati
  cambiati **nello stesso intervento**, come prescrive il contratto P1 §6.
- Tre array nuovi nel piano: `UNIQUE_IS_CPU`, `CPU_UNIQUE`, `CPU_EXPERTS`
  (`moe_grouped_plan_size` si adegua da sola perche' usa `ROUTE_ARRAY_COUNT`), piu' i
  campi `n_cpu` e `cpu_active`.
- Partizione: `n_cpu = max(0, min(cpu_max, n_misses, n_unique - 1))`, **prima**
  dell'assegnazione degli slot e del gather. Quali miss: i **primi nell'ordine degli
  indici unici** (D13), che e' l'ordine di prima comparsa fra le route gia' materializzato
  da entrambi i cammini di deduplica. Non legge nulla dello stato della cache.
- Il termine `n_unique - 1` garantisce che resti almeno un unico GPU da cui prendere lo
  **slot alias**; l'alias e' il minimo indice unico non CPU, ed e' protetto dalla bitmap
  del piano (il kernel lo verifica: `route_storage[alias] == 1`).
- Commit differito con tre insiemi distinti: **mappatura** solo miss GPU, **recenza** solo
  unici non CPU, **frequenza e decadimento** tutti gli unici. Il tick di orologio di un
  unico CPU viene consumato ma non scritto, cosi' l'aritmetica dell'indice non cambia.
- Contatori: sette invece di due —
  `[0]` uniche, `[1]` miss GPU, `[2]` miss CPU, `[3]` coppie token/esperto,
  `[4]` route servite dalla CPU, `[5]` colpi GPU, `[6]` unici CPU (diagnostica inclusa).
  `report_hits` stampa ora **due percentuali distinte**, colpi GPU e quota CPU: con i miss
  CPU la vecchia formula `1 - mancanti/richiesti` li conterebbe come colpi.
- Traccia: lo schema porta ora `misses_cpu`.

### 4.2 La maschera a peso GPU zero — una deviazione dal progetto, argomentata

Il piano prevedeva «un tensore dei pesi mascherati per il calcolo GPU», con l'obbligo
(rischio R3 di P2) di **verificare che le fusioni CUDA della riduzione consumino il
tensore mascherato**.

Qui la maschera si applica **in loco**: il kernel di export legge il peso originale della
route CPU (lo mette nel job) e poi scrive `0.0f` nella stessa cella del tensore dei pesi.
Tre conseguenze, tutte a favore:

1. **non esiste** un secondo tensore che una fusione possa leggere al posto di quello
   mascherato. `ggml_cuda_match_moe_weighted_reduction` prende `match.weights` da `src[1]`
   del `MUL`, che e' esattamente la cella azzerata. Il rischio R3, per il lato dei pesi,
   e' chiuso **per costruzione** invece che per verifica;
2. nessun nodo nuovo nel graph per la maschera, quindi nessuna occasione in piu' di
   rompere una fusione esistente;
3. l'ordine e' garantito dallo stream: il tensore dei pesi e' gia' calcolato quando il
   kernel del planner parte (e' un ingresso del `mul_mat_id` del gate), e viene consumato
   dopo. A ogni token il grafo lo ricalcola da capo, quindi l'azzeramento del token
   precedente non sopravvive.

La maschera si applica **dopo** la normalizzazione e la scala originali del routing, e
**non si rinormalizza**: i pesi delle altre route restano identici bit per bit. La somma
dei pesi effettivamente applicati resta quella del router perche' il contributo mancante
viene aggiunto dalla CPU con lo **stesso** peso originale.

I pesi di routing raggiungono il backend agganciati al nodo del `mul_mat_id`
(`up->src[4]` e `cur->src[4]` in `llama-graph.cpp`), come gia' fa la cache legacy con
`src[3]`. `ggml_cuda_mul_mat_vec_q` li passa a `remap` insieme all'attivazione `src1`.

### 4.3 Il punto di somma e il marcatore

`moe_out = ggml_add(ctx0, moe_out, y)`, **dopo** la pesatura delle righe e la loro
riduzione e **prima** del ritorno di `build_moe_ffn`, quindi prima dello shared expert
(contratto P1 §3.10 e §4.6). Il contributo CPU non passa una seconda volta per la
moltiplicazione dei pesi.

`y` non e' una copia: e' una **vista ggml stabile** costruita sopra il buffer mappato
dell'esecutore. Il blocco dell'esecutore e' allocato sul buffer type `CUDA0_Mapped`, che
`ggml_backend_buft_is_cuda()` riconosce come CUDA: il kernel `add` della GPU legge `y`
in **zero-copy** (10 KiB per strato sul PCIe, contro gli ~1,9 MiB per esperto che il
gather non fa piu'). La vista e' creata **una volta per contesto** e riusata da tutti i
graph: se fosse creata per strato o per replay i puntatori dei nodi cambierebbero e il
graph verrebbe ricatturato a ogni token.

Lo stesso nodo fa da **marcatore**: quando il backend lo incontra (riconoscimento per
puntatore, `src[1]->data == hooks->y_dev`) accoda prima `cudaLaunchHostFunc(wait)` e poi
la guardia del merge. Nessun operatore ggml nuovo; un solo `add` in piu' per strato.

### 4.4 Veleno e modalita' diagnostica

`moe_cpu_merge_guard_kernel` gira fra il `wait` e l'`add`:

- **veleno**: se `flags->poison` vale 1, `y` viene riempito di **NaN**, non di zeri. Un
  errore non puo' diventare uno zero silenzioso e plausibile (invariante 7). La prima
  cintura resta il controllo di `contaminated()` alla fine di `decode()`, che **fa fallire
  il passo**;
- **diagnostica**: si confronta il contributo CPU con il contributo che la GPU calcola per
  le **stesse route** — somma di `peso[route] * riga di ffn_moe_down` — si accumulano
  NRMSE, massimo assoluto e un anello degli ultimi 256 token, e poi `y` viene **azzerato**,
  cosi' l'uscita del modello resta esattamente quella del percorso GPU;
- in entrambe le modalita' si contano i valori **non finiti** in `y`.

In modalita' diagnostica il planner riempie soltanto gli elenchi `CPU_UNIQUE` /
`CPU_EXPERTS` (servono al kernel di export): i miss restano tutti miss GPU,
`UNIQUE_IS_CPU` resta a zero, non c'e' alias e non c'e' maschera. Piano, gather, commit e
pesi sono quindi **identici a `cpu_max = 0`** — ed e' per questo che la diagnostica non
puo' cambiare l'uscita del modello. Il solo residuo e' il nodo `add` in piu', che somma
zero.

### 4.5 Guardie e ripiego

Il ripiego sul percorso precedente si decide **prima dell'invio** (invariante 7), mai in
volo. Tre livelli:

| dove | che cosa controlla |
|---|---|
| `llama-moecpu.cpp` (creazione) | tipi con tratti CPU, forme divisibili per i blocchi, puntatori host mappati per i tre banchi, nessun bias degli esperti, `n_seq_max == 1` |
| `llama-graph.cpp` (costruzione del graph) | percorso a domanda attivo, strato ammesso, `n_tokens` dentro `max_rows`, gate e up **separati**, SiLU **senza clamp**, nessun bias/scala degli esperti, nessuna pesatura prima dell'FFN, nessuna LoRA |
| `moe-demand.cuh` (bind e remap) | gate/up IQ2_S e down IQ4_NL, forme coerenti, strato nell'elenco, hook installati con ABI e forme combacianti, attivazione e pesi contigui e F32 |

Se una qualunque manca, il planner riceve `cpu_max = 0` e non viene costruito nessun nodo
`add`: il graph e' identico a quello di prima.

### 4.6 Durata degli oggetti

- `llama_context::reserve()`: `set_phase(idle)` e `quiesce()` **prima** di
  `reset_transient_memory` (che e' il punto in cui i graph muoiono). La chiamata sta nel
  chiamante invece che dentro `ggml_backend_cuda_reset_transient_memory`, come proponeva
  il progetto P2 §5: l'ordine ottenuto e' lo stesso e il backend CUDA non deve conoscere
  l'esecutore. **Deviazione dichiarata.**
- `~llama_context()`: dopo `synchronize()`, `set_phase(idle)` e `quiesce()`, piu' il
  riepilogo dei contatori.
- `llama_free()`: la distruzione vera dei buffer avviene **dopo** `delete ctx`, quando lo
  scheduler e i backend — e con loro i `cudaGraphExec` che referenziano `y` — non esistono
  piu'. Il progetto P2 §5 otteneva lo stesso risultato dichiarando l'esecutore come membro
  **prima** di `sched`; qui l'esecutore non e' un membro (e' di `llama-moecpu.cpp`, come
  `llama-moecache.cpp` per la cache), quindi l'ordine si ottiene rimandando la distruzione
  a `llama_free`. **Deviazione dichiarata, stesso ordine.**
- `graph_compute()`: `set_phase(prefill)` per i batch, `set_phase(decode)` per il decode:
  fuori dal decode e durante il prefill il pool dorme e non ruba core (D09).
- fine di `decode()`: se `contaminated()`, il passo **fallisce** con `-1`.

---

## 5. Come si costruisce

Nessun `.bat` modificato a caldo; lanciatore in `.ps1`.

```powershell
# configurazione (una volta): Ninja, Release, CUDA arch 86, DLL condivise,
# stessi interruttori del fork della build privata
D:\ds4_work\p3_work\compila.ps1 -SoloConfigura

# compilazione
D:\ds4_work\p3_work\compila.ps1 -Target llama-server -Parallel 4
```

`compila.ps1` rifiuta di partire se qualcuno e' in ascolto sulla porta 8100. I log
finiscono in `D:\ds4_work\p3_work\prove\build_<data>.log`.

## 6. Come si prova

```powershell
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_p0

# 2 - la funzione spenta e' neutra
.\avvia_blocco.ps1 -Preset preset_A_p3.json -Profilo fumo

# 3 - diagnostica sullo strato 1, cpu_max = 2
.\avvia_blocco.ps1 -Preset preset_D_p3.json -Profilo fumo

# 4 - attiva, prima il fumo poi l'insieme libero (regola D14: prima il B)
.\avvia_blocco.ps1 -Preset preset_B_p3.json -Profilo fumo
.\avvia_blocco.ps1 -Preset preset_B_p3.json -Profilo solo_libero -Budget screening
```

Nessun comando contiene credenziali: `avvia_blocco.ps1` legge la API key dal lanciatore
di produzione e non la stampa mai.

I tre preset sono in `docs/porto/banco_p0/`: `preset_A_p3.json` (ibrido spento),
`preset_B_p3.json` (attivo, strato 1, `cpu_max=2`), `preset_D_p3.json` (diagnostica).
Puntano tutti a `D:\ds4_work\p3_work\build\bin` e differiscono **solo** per
`LLAMA_MOE_CPU` e `LLAMA_MOE_CPU_DIAG`; ogni preset dichiara **esplicitamente** tutte le
opzioni dell'ibrido, cosi' un valore ereditato dalla sessione PowerShell precedente non
puo' falsare un lato.

---

## 7. Risultati

Sette blocchi del banco, tutti con lo stesso modello, le stesse fixture congelate e lo
stesso preset a meno delle opzioni dell'ibrido. Un solo `llama-server` alla volta, guardia
d'istanza unica superata prima di ogni avvio, nessun processo lasciato attivo. Copie dei
riepiloghi in `D:\ds4_work\p3_work\prove\`, righe del ramo CPU in [`log/`](log/).

### 7.1 Prova 1 — build

Tre passate, tutte con `compila.ps1` e nessun `.bat` modificato a caldo:

| passata | che cosa | esito |
|---|---|---|
| 1 | configurazione + build completa (478 obiettivi) | codice 0 |
| 2 | aggiunta dei contatori di cattura del graph | **errore di link**: gli `extern` erano finiti dentro `namespace qwen_moe_demand` mentre le definizioni stanno a scope globale. Corretto, codice 0 |
| 3 | correzione dei pesi di routing nel percorso fuso (§8, difetto 2) | codice 0 |

Nessun avviso nuovo attribuibile alla patch. Hash SHA256 dei binari finali in
[`log/hash_binari.txt`](log/hash_binari.txt); i quattro che contano:

| file | byte | SHA256 (primi 32) |
|---|---:|---|
| `ggml-cuda.dll` | 192.372.224 | `98FDE11464167542ECA187F46AA60449` |
| `llama.dll` | 2.673.664 | `87218E4FE01ED0E00149A03383690538` |
| `llama-server-impl.dll` | 3.179.008 | `D1DEE985999BCBA0C1E5694BC7FE58F8` |
| `llama-server.exe` | 10.752 | `837F500E86AEC6110CAB9ACFFD8064B0` |

Le stringhe nuove sono verificabili nei binari (`moe cpu: ATTIVO` e `LLAMA_MOE_CPU_LAYERS`
in `llama.dll`; `moe cpu: strato`, `quota CPU` e `ggml_cuda_mapped_tensor_host_ptr` in
`ggml-cuda.dll`).

*Nota di riproducibilita'.* **Dopo** le corse i sorgenti sono stati toccati una volta
ancora per riportare i **terminatori di riga** delle righe non modificate a quelli dello
snapshot, cosi' che la patch sia leggibile (senza, il diff di `llama-context.cpp` era
l'intero file). Il contenuto e' identico byte per byte a meno dei `\r`: una ricompilazione
produrrebbe binari funzionalmente identici ma con hash diversi, perche' il PE porta un
timestamp.

### 7.2 Prova 2 — la funzione spenta e' neutra

Due misure, la seconda molto piu' forte della prima.

| corsa | profilo | impronte confrontate col riferimento `20260914_072049` | diverse |
|---|---|---:|---:|
| `20260914_085927_P3_p3_ibrido_spento_r1` | fumo | 3 | **0** |
| `20260914_094556_P3_p3_ibrido_spento_r1` | solo_libero | **18** (16 liberi + 2 riscaldamenti) | **0** |

La seconda e' il controllo A dell'insieme libero, eseguito con i binari **finali**: le
diciotto impronte SHA256 del testo coincidono una per una con quelle del blocco di
riferimento, prodotto da binari diversi (`qwen38_clean\build\bin`). E la neutralita' non
e' solo del testo:

| | t/s sull'insieme libero (somma/somma) | rapporto |
|---|---:|---:|
| riferimento `20260914_072049` | 24,4344 | — |
| **A — patch con l'ibrido spento** | **24,4275** | **0,9997 (−0,03%)** |

Meno di un terzo del rumore fra blocchi misurato in P0 (0,06%). **La patch, a funzione
spenta, non e' distinguibile dal binario precedente ne' nel testo ne' nella velocita'.**

### 7.3 Prova 3 — diagnostica sullo strato 1, `cpu_max = 2`

Corse `20260914_091222` (fumo, contatori accesi) e `20260914_101459` (insieme libero,
contatori spenti).

| controllo | esito |
|---|---|
| impronte identiche al riferimento | **18 su 18** sull'insieme libero, 3 su 3 sul fumo. La diagnostica **non** altera l'uscita |
| valori non finiti in `y` | **0** |
| contaminazione | mai; nessun decode fallito |
| invariante 1 (`uniche = colpi + missGPU + missCPU`) | **OK** a ogni stampa |
| ricatture del graph | 11 catture e 4 riavvii di riscaldamento su 2496 lanci — **gli stessi numeri del lato spento**: i puntatori introdotti dalla patch sono stabili |
| contatori (fine della corsa di fumo) | uniche 3170 = colpi 1721 + missGPU 1449 + missCPU 0; coppie 3170; route CPU 584; unici CPU 584; byte 2.856.268.800 |

**Errore fra contributo CPU e contributo GPU per le stesse route**, accumulato su 305
token dello strato 1:

| | valore |
|---|---:|
| NRMSE aggregata | **0,0109** |
| NRMSE per token (min–max nell'anello degli ultimi 256) | 0,0060 – 0,0168 |
| massimo assoluto | **6,6 · 10⁻⁴** |
| valori non finiti | 0 |

E' lo stesso ordine di grandezza del prototipo del 13 settembre (NRMSE peggiore ~0,0084,
candidato tre miss/due CPU ~0,0063) e resta un ordine di grandezza sotto la soglia 0,05
del banco. **Non e' un criterio di qualita' del modello**: dice solo che l'aritmetica CPU
riproduce quella GPU entro la differenza attesa fra le due quantizzazioni
dell'attivazione, e che non c'e' un errore grossolano.

### 7.4 Prova 4 — modalita' attiva

**Profilo fumo**, contatori accesi (`20260914_091801` con `cpu_max = 2`,
`20260914_092328` con `cpu_max = 1`). Nessun NaN, nessuna contaminazione, invariante 1
sempre soddisfatto, 11 catture del graph su 2496 lanci in entrambi i casi:

| | uniche | colpi GPU | miss GPU | miss CPU | route CPU | byte sullo strato 1 | rispetto alla diagnostica |
|---|---:|---:|---:|---:|---:|---:|---:|
| diagnostica | 3170 | 1721 | 1449 | 0 | 584 | 2.856.268.800 | 1,000 |
| **attiva `cpu_max = 2`** | 3170 | 1686 | **888** | 596 | 596 | **1.750.425.600** | **0,613** |
| attiva `cpu_max = 1` | 3170 | 1679 | 1181 | 310 | 310 | 2.327.987.200 | 0,815 |

Con due esperti CPU i trasferimenti dello strato scendono del **38,7%**, e il tasso di
colpi GPU tiene meglio di quanto il simulatore di P1 avesse previsto sulla traccia
storica: 1686 colpi contro 1721 della diagnostica, cioe' **−2,0%**, non i −6,6 punti
percentuali della curva `route` a `cpu_max = 2`. Il carico e' diverso (banco congelato di
P0 contro la traccia del 13/9), quindi la curva di P1 va rifatta su questa traccia prima
di sceglierne l'ordine in P4 — era gia' il limite n. 3 dichiarato dal rapporto P1.

**Insieme libero**, regola D14 — prima il candidato B, il controllo A solo perche' B non
ha mostrato vantaggio:

| corsa | preset | t/s (somma/somma) | rapporto su A | rapporto su 24,44 |
|---|---|---:|---:|---:|
| `20260914_094556` | A — ibrido spento | 24,4275 | 1,0000 | 0,9997 |
| `20260914_101459` | D — diagnostica | 23,3983 | 0,9579 | 0,9576 |
| `20260914_092846` | **B — attivo, strato 1, `cpu_max = 2`** | **23,5135** | **0,9626** | **0,9623** |

**Il candidato NON batte il riferimento: 23,51 contro 24,44, cioe' −3,8%.** Il controllo A
dice che la regressione e' **specifica del candidato, non generale**: la stessa build con
l'ibrido spento fa 24,4275, indistinguibile dal riferimento. Il divario e' uniforme sui
sedici casi (B/A fra 0,945 e 0,981), non prodotto da un caso anomalo.

**Impronte cambiate con la CPU attiva** — non e' un difetto di per se' (l'aritmetica CPU e
quella CUDA quantizzano diversamente l'attivazione, rischio R10 del progetto P2), ma va
elencato: **15 su 18**.

| cambiate (15) | invariate (3) |
|---|---|
| L01@corto, L01@ctx32k, L02@corto, L02@ctx32k, L03@corto, L03@ctx32k, L04@ctx32k, L05@corto, L05@ctx32k, L06@corto, L06@ctx32k, L07@corto, L07@ctx32k, L08@corto, L08@ctx32k | L04@corto, riscaldamento_1, riscaldamento_2 |

Un solo caso libero su sedici produce lo stesso testo; i due riscaldamenti (otto token
ciascuno) non cambiano. La qualita' dei liberi non e' valutabile in screening (D15): il
confronto di qualita' appartiene a P6.

### 7.5 Prova 5 — dove va il costo

La differenza fra «attiva» e «diagnostica» era indicata come primo indizio del costo delle
righe fittizie. **La misura esiste, ma non isola quel costo, e conviene dirlo invece di
attribuirle un significato che non ha**: in entrambe le modalita' la GPU calcola le
**stesse dieci righe**. In modalita' attiva due di quelle righe sono fittizie (slot alias,
peso zero) e costano esattamente quanto le righe vere che sostituiscono. Il costo delle
righe fittizie non e' quindi una spesa in piu': e' un **risparmio mancato**, e diventa
misurabile solo con una maschera che salti il calcolo prima di leggere i pesi — cioe' dopo
P4, come dice il piano.

Quello che la terna A/D/B misura davvero e' piu' utile:

| confronto | ms per token | lettura |
|---|---:|---|
| A — ibrido spento | 40,937 | riferimento della stessa build |
| D − A | **+1,801** | costo del solo **MECCANISMO**: kernel di export, nodo host `submit`, nodo host `wait`, guardia del merge, nodo `add`, calcolo CPU. Nessun risparmio di byte, nessun cambio di traiettoria della cache |
| B − D | **−0,209** | quello che il **risparmio del 38,7% dei trasferimenti** piu' il cambio di traiettoria della cache restituiscono |
| B − A | **+1,591** | candidato completo, su **un solo strato** |

Questi numeri **non vanno moltiplicati per 47 strati**: il piano lo vieta, e ci sono due
ragioni tecniche perche' sarebbe sbagliato in entrambe le direzioni — parte del costo e'
per-token e non per-strato, e parte del risparmio cresce con il numero di strati serviti.

Il rapporto fra le due colonne e' pero' netto e non dipende dalla scala: **il meccanismo
costa oggi circa nove volte quello che il risparmio di banda gli restituisce su questo
strato**. Finche' resta tale, estendere agli altri 46 strati non puo' produrre un guadagno,
e P4 deve partire dal costo del meccanismo, non dall'estensione.

### 7.6 Stato dei processi e della macchina

Sette accensioni del server, tutte chiuse (`stop_process_forzato`, come previsto per un
processo senza finestra); al termine nessun `llama-server` attivo e nessun LISTENING sulla
8100. Caricamenti del modello fra 190,9 e 226 s. `bin_prod`, il lanciatore quotidiano, il
modello e l'albero `qwen38_clean` non sono stati toccati.

---

## 8. Difetti trovati e corretti

1. **`extern` dentro il namespace sbagliato.** I contatori di cattura del graph sono
   definiti a scope globale in `ggml-cuda.cu`; le dichiarazioni `extern` erano finite
   dentro `namespace qwen_moe_demand`. Tre simboli non risolti in fase di link. Corretto
   spostandole prima dell'apertura del namespace.

2. **I pesi di routing non arrivavano al planner nel percorso FUSO — il difetto che
   spegneva silenziosamente tutto il ramo CPU.** La prima stesura prendeva i pesi da
   `dst->src[4]`, dove `dst` e' l'argomento che il backend passa a
   `ggml_cuda_mul_mat_vec_q`. Nel percorso non fuso `dst` **e'** il nodo `mul_mat_id` e
   funziona; nel percorso **fuso** il backend passa come `dst` il nodo **GLU**
   (`ggml-cuda.cu:4209`, `4248`, `4336`, `4401`), che non ha nessun `src[4]`. Risultato:
   `router_weights == nullptr`, il ramo CPU non partiva mai, e la prima corsa diagnostica
   ha stampato `routeCPU 0, uniciCPU 0, diag confronti 0` con impronte identiche — cioe'
   **un successo apparente**. Era la classe di difetto piu' cara: una funzione spenta che
   sembra accesa. Corretto prendendo il tensore dal nodo vero nel ciclo dei nodi
   (`pending_router_weights`, scritto da `cgraph->nodes[i]` subito prima di tentare la
   fusione) e usandolo come ripiego quando `dst->src[4]` e' nullo.

   Corretto anche il **modo in cui il difetto si sarebbe scoperto**: `remap` stampa ora una
   volta sola, con i valori veri, il motivo per cui il ramo CPU non e' partito. Un ripiego
   silenzioso costa piu' a diagnosticarlo che a scriverlo.

3. **`\n` diventato un a capo vero dentro una stringa C.** Una riscrittura scriptata di
   `llama-context.cpp` ha trasformato `\n` in un ritorno a capo dentro un
   `LLAMA_LOG_ERROR`. Trovato da un controllo di sola sintassi (`cl /Zs`) eseguito **prima**
   che la compilazione arrivasse a quel file. E' la stessa famiglia della regola di metodo
   del 6-7/9 sugli heredoc e su `sed -i`: le riscritture scriptate su un albero Windows
   vanno verificate, non date per riuscite.

4. **BOM in un preset scritto da PowerShell.** `ConvertTo-Json | Set-Content -Encoding utf8`
   produce un BOM che `json.load` di Python rifiuta: un blocco intero e' partito, ha
   caricato il modello per 211 s e non ha misurato niente. I preset si scrivono in Python
   con `encoding="utf-8"` e senza BOM. Il blocco e' stato rifatto; nessun dato invalidato,
   solo tempo macchina perso.

**Difetti NON trovati**, e vale la pena elencarli perche' erano i rischi attesi: nessun
NaN, nessuna corruzione della cache, nessuno stallo, nessun errore di memoria, nessuna
contaminazione, nessuna ricattura del graph in piu' rispetto al lato spento, e le fusioni
CUDA della riduzione non hanno scavalcato ne' assorbito l'`add` del contributo CPU
(rischio R3 del progetto P2, chiuso: la maschera in loco lo rende impossibile per i pesi,
e le impronte identiche in diagnostica lo provano per l'`add`).

---

## 9. Aperture per P4

**La domanda che P4 deve aggredire per prima non e' «quali strati», ma «perche' il
meccanismo costa 1,8 ms per token su un solo strato».** L'estensione ai 47 strati, con
questo rapporto costo/risparmio, non puo' produrre un guadagno.

| # | apertura | perche' e' credibile | prima misura da fare |
|---|---|---|---|
| A1 | **Costo a CPU spenta, con i nodi host presenti** (punto 22 di P2 §13) | separa il costo dell'IMPIANTO — due nodi host, kernel di export, guardia, nodo `add` — da quello del CALCOLO CPU. Oggi non e' misurabile perche' `llama-moecpu.cpp` rifiuta di accendersi con `LLAMA_MOE_CPU_MAX=0`: e' **una riga di guardia** da allentare | `LLAMA_MOE_CPU=1 LLAMA_MOE_CPU_MAX=0` sull'insieme libero, contro il lato A |
| A2 | **I due nodi host costano piu' del calcolo** | un `cudaLaunchHostFunc` dentro un graph richiede al driver di svegliare un thread di callback e blocca il graph finche' la callback non ritorna: due volte per token. 1,8 ms e' compatibile con due risvegli lenti, non con i ~250 microsecondi di aritmetica misurati dal prototipo | A1 lo decide; se e' l'impianto, la leva e' ridurre il numero di nodi host (uno solo, oppure uno ogni N strati) |
| A3 | **La concorrenza fra `submit` e `wait` non c'e'** (rischio R2 di P2, «la prima misura di P3, non l'ultima» — qui e' rimasta ultima) | il prototipo misurava 253,5 microsecondi con lavoro concorrente e 339,5 senza. Se il `wait` viene servito prima che il lavoro GPU dello strato sia accodato, il guadagno sparisce senza che nulla sbagli | confronto del tempo di blocco fra `wait` accodato dopo il lavoro GPU e `wait` accodato subito dopo `submit` |
| A4 | **Il nodo `add` in piu' rompe una fusione** | `ggml_cuda_match_moe_weighted_reduction` fonde `MUL` piu' la catena di `ADD`; un consumatore in piu' di `moe_out` puo' cambiare la decisione. In diagnostica le impronte non cambiano, quindi la **numerica** e' la stessa, ma il **costo** puo' non esserlo | contare le fusioni della riduzione pesata con e senza il nodo `add` |
| A5 | **L'ordine dei miss CPU** | sulla traccia storica `freq` domina `route` (piu' colpi, meno byte). Qui i colpi tengono molto meglio del previsto (−2,0% invece di −6,6 punti), quindi il margine di `freq` potrebbe essere diverso | rifare le curve di P1 su una traccia del banco congelato, come chiedeva il limite n. 3 del rapporto P1 |
| A6 | **Quattro contro sei core, e la contesa col threadpool del server** (D03, rischio R7) | non toccata in P3: tutte le corse sono a quattro core | dopo A1, perche' prima va saputo se il calcolo CPU pesa nel bilancio |
| A7 | **Lo schema della traccia** | `misses_cpu` c'e', ma nessun replay e' stato fatto con la CPU attiva | prima di riusare `LLAMA_MOE_ROUTE_TRACE` per un confronto |
| A8 | **La strada della maschera vera** | oggi le righe fittizie non costano piu' delle righe vere, ma non fanno risparmiare niente: il prototipo riduceva davvero il numero di righe GPU | solo dopo P4, come dice il piano, e solo se A1-A3 non spiegano il costo |

Restano aperti, non toccati da P3: **R14** del progetto P2 (un nodo `wait` gia' accodato
sopravvive al `cancel()` del suo job — il chiamante di P3 non ha mai chiamato `cancel()`,
quindi la precondizione dichiarata non e' stata ne' verificata ne' violata) e **R15**
(taratura di `ack_timeout_us`: nessun riconoscimento e' mai scaduto, ma non e' stato
sollecitato).

---

## 10. Bozza di voce per il registro

**Data e fase.** 14 settembre 2026. **P3 — Un solo strato nel server, MTP spento.**
Integrazione nel server dell'esecutore di P2 e del planner di P1 su un solo strato, con
build separata, sette blocchi del banco e nessun commit.

**Ipotesi.** Il contratto di P1 e l'esecutore di P2 possono essere integrati nel server su
un solo strato senza rompere la matematica, la cache o la cattura del graph; la funzione
spenta resta neutra; la modalita' attiva riduce i trasferimenti dello strato. Tutte e tre
verificate. **Non** verificata, e non ipotizzata come acquisita, la quarta: che la
riduzione dei trasferimenti si traduca in velocita'.

**ID della modifica/revisione.** P3-v1.0, patch unica
`docs/porto/p3_uno_strato/p3_uno_strato.patch` (2.928 righe aggiunte, 17 tolte, 17 file),
diff rispetto a `D:\ds4_work\p0_snapshot_20260914\source`, che non e' stato modificato.
Gli SHA256 dei sedici file preesistenti toccati sono stati verificati contro
`source_hashes.json` prima della modifica.

**File toccati.** ggml-base: `ggml/include/ggml-moe-cpu.h` (nuovo),
`ggml/include/moe_cpu_job.h` (nuovo), `ggml/src/ggml.c` (tabella dei hook). Backend CUDA:
`fork-moe-kernels.cuh` (partizione CPU/GPU, alias, sette contatori), `moe-demand.cuh`
(opzioni, kernel di export, guardia del merge, riconoscimento del nodo di merge, report),
`moe-demand-api.cuh`, `mmvq.cu`, `ggml-cuda.cu` (nodo host `wait`, proc-address di
`ggml_cuda_mapped_tensor_host_ptr`, contatori di cattura). libllama: `llama-moecpu.h/.cpp`
(nuovi, possiedono l'esecutore), `moe_cpu_executor.h/.cpp`, `moe_cpu_host_memory.h`,
`moe_cpu_host_memory_cuda.cpp` (copiati da P2, con l'aggiunta di `base_tensor()`),
`llama-graph.cpp` (pesi di routing sul nodo, `add` del contributo CPU),
`llama-context.cpp` (creazione, fasi, `quiesce`, controllo della contaminazione),
`src/CMakeLists.txt`.

**Configurazioni confrontate.** Preset in `docs/porto/banco_p0/`: `preset_A_p3.json`
(ibrido spento), `preset_B_p3.json` (attivo, strato 1, `cpu_max=2`),
`preset_B_p3_contatori.json`, `preset_B_p3_max1_contatori.json`, `preset_D_p3.json` e
`preset_D_p3_senza_contatori.json` (diagnostica). Differiscono solo per le opzioni
dell'ibrido; ciascuno le dichiara tutte esplicitamente.

**Run validi.**

| corsa | profilo | ruolo | risultato |
|---|---|---|---|
| `20260914_085927_P3_p3_ibrido_spento_r1` | fumo | neutralita' | 3/3 impronte uguali |
| `20260914_091222_P3_p3_ibrido_diagnostica_strato1_r1` | fumo | diagnostica | NRMSE 0,0109, max 6,6e-4, 0 NaN |
| `20260914_091801_..._attivo_strato1_contatori_r1` | fumo | attiva `cpu_max=2` | byte −38,7%, invariante 1 OK |
| `20260914_092328_..._attivo_strato1_max1_contatori_r1` | fumo | attiva `cpu_max=1` | byte −18,5% |
| `20260914_092846_P3_p3_ibrido_attivo_strato1_r1` | solo_libero | **candidato B** | **23,5135 t/s** |
| `20260914_094556_P3_p3_ibrido_spento_r1` | solo_libero | **controllo A** | **24,4275 t/s**, 18/18 impronte uguali |
| `20260914_101459_..._diagnostica_strato1_senza_contatori_r1` | solo_libero | scomposizione | 23,3983 t/s, 18/18 impronte uguali |

**Run invalidi.** Uno: il primo tentativo del blocco di scomposizione (server acceso,
modello caricato in 211 s, nessuna misura prodotta) per un BOM nel preset scritto da
PowerShell. Rifatto. La corsa `20260914_090430` e' superata dalla `20260914_091222`: fatta
con i binari precedenti alla correzione dei pesi di routing, quindi il suo ramo CPU non era
mai partito — resta agli atti come la corsa che ha rivelato il difetto.

**Risultato e limite.** La funzione spenta e' **neutra** (24,4275 contro 24,4344, e 18
impronte su 18 identiche). La diagnostica **non altera l'uscita** (18 su 18) e dice che
l'aritmetica CPU riproduce quella GPU con NRMSE 0,0109 e massimo 6,6e-4. La modalita'
attiva **funziona**: invariante 1 sempre soddisfatto, zero NaN, zero contaminazioni,
nessuna ricattura del graph in piu', trasferimenti dello strato 1 ridotti del **38,7%** con
`cpu_max=2`. **Il candidato non batte pero' il riferimento: 23,5135 contro 24,44, cioe'
−3,8%, e il controllo A dice che la regressione e' specifica del candidato.** La
scomposizione: il meccanismo costa **+1,801 ms per token** su un solo strato, il risparmio
di banda ne restituisce **0,209**. Limiti: un solo strato, un solo token per passo, un solo
carico (l'insieme libero del banco congelato), una sola replica per lato, nessuna verifica
di qualita' (non applicabile in screening per D15), nessuna misura di prefill.

**Decisione.** **Correggere, non estendere.** Non si passa ai 47 strati: con il rapporto
costo/risparmio misurato, l'estensione non puo' produrre un guadagno. P4 comincia dal costo
del meccanismo, nell'ordine A1 poi A2/A3 poi A4 (§9); la scelta dell'insieme di strati e
l'ordine dei miss CPU vengono dopo. La funzione resta **spenta di default**: nessun preset
di produzione la accende, e la neutralita' del percorso spento e' provata sia nel testo sia
nella velocita'.

**Regressioni aperte.** Nessuna introdotta a funzione spenta. A funzione attiva il testo
cambia in 15 casi su 18 — previsto (rischio R10 di P2), non valutato in qualita' perche' lo
screening non lo consente (D15). Restano R14 e R15 del progetto P2, non sollecitati.

**Stato dei processi avviati.** Nessun `llama-server` attivo, nessun LISTENING sulla 8100,
nessuna compilazione in corso al termine.

**Prossima azione.** P4, misura A1: allentare la guardia di `llama-moecpu.cpp` che rifiuta
`LLAMA_MOE_CPU_MAX=0`, e misurare sull'insieme libero il costo dell'impianto con i nodi
host presenti e zero route CPU. E' il numero che decide se la leva successiva e' il numero
di nodi host (A2/A3) o l'aritmetica CPU (A6).
