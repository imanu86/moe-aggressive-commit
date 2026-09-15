# P7 · cella 5 — l'apertura A7 chiusa, e la corsia CPU rimisurata — 15 settembre 2026

Cella in **ripresa** dopo l'interruzione dell'agente della sera del 14/9. Chiude l'apertura A7 della
[cella 4](P7_CELLA4_POLLING_E_CORSIA_BOZZA_14_SETTEMBRE.md) («il contributo CPU arriva davvero a
`moe_out` sulle righe di bozza?») e rimisura la corsia CPU sul binario corretto.

---

## 0. Verdetto in otto righe

1. **La risposta ad A7 è: NO, non arrivava** — ed era la lettura (1) di cella 4 §5.5, quella che
   quel documento definiva «un difetto di correttezza vero». Il contributo CPU usciva dal pool
   **esattamente zero**, e il 47,8% di byte risparmiati della cella 4 era comprato con una perdita
   numerica silenziosa.
2. **La causa è un disaccordo di indirizzamento fra chi scrive il descrittore del job e chi lo
   legge**: il kernel di export scrive con passo di riga (`row * MOE_CPU_MAX_PER_ROW + e`), il pool
   leggeva con un cursore compattato. I due coincidono **solo finché tutte le route stanno sulla
   riga 0** — cioè in tutto P3, tutto P4 e nel banco host di P2. La corsia di bozza è la prima
   configurazione in cui la riga 0 non ha route e la riga 1 le ha tutte.
3. Corretta quella, la NRMSE sulla riga di bozza passa da **1,000000 a 0,012958** e l'accettazione da
   0,69652 a **0,79298** — cioè **sopra** lo 0,76990 del riferimento a corsia spenta.
4. Sulla strada ci sono stati altri **due difetti**, entrambi fatali: la modalità diagnostica a due
   righe faceva **morire il server** (`__trap()` nel pianificatore) e il flag di sola bozza
   inquinava la politica della cache anche in diagnostica. Entrambi corretti.
5. **Il cancello `R < 13 ms` NON passa: `R ≈ 22,2 ms`**, peggio dei 19,7 della cella 4 — perché
   adesso il pool fa aritmetica **vera** su esperti **diversi**, mentre prima moltiplicava 155 volte
   l'esperto 0 per zero.
6. **Ma la scomposizione ribalta la lettura del perché.** La sola *consegna* (impianto + attesa
   esposta − risparmio di trasporto) vale **−4,29 ms per ciclo**, cioè `R = 11,5 ms`: **passerebbe il
   cancello da sola**. Tutto il fallimento è nell'**aritmetica CPU: +11,17 ms per ciclo**.
7. Costo per esperto CPU **72 µs** (155 esperti per ciclo): terza conferma indipendente del numero
   della memoria del 10/9 (0,074-0,08 ms) e dei 76 µs dedotti dalla cella 4.
8. **t/s: 28,086 contro 30,827** sullo stesso caso e sullo stesso binario (**−8,9%**), contro il +5%
   che sarebbe servito. **La corsia si chiude — negativa, non più inconclusiva** — ma con
   un'apertura quantificata che prima non c'era (§8, A3).

---

## 1. Lo stato ereditato, e la decisione su di esso

### 1.1 Che cosa c'era

L'agente precedente si era fermato al messaggio «Ora applico la patch». Sul disco:

| artefatto | data | stato |
|---|---|---|
| `src/llama-graph.cpp`, `src/llama-moecpu.{h,cpp}`, `ggml/src/ggml-cuda/moe-demand.cuh` | 14/9 20:21 | modificati nella copia di lavoro |
| `llama.dll`, `ggml-cuda.dll` | 14/9 20:21 | compilati (`build_20260914_202124.log`, codice 0) |
| `preset_T1_p7.json` … `preset_T7_p7.json`, `genera_preset_p7c5.py` | 14/9 20:22 | scritti |
| documento della cella, patch, corse | — | **inesistenti** |

La ricostruzione chiesta dal dispaccio è stata fatta: `D:\ds4_work\p3_work\tmp\ref_c4\source` è lo
snapshot immutabile `D:\ds4_work\p0_snapshot_20260914\source` con le quattro patch applicate in
ordine (`p3_uno_strato` → `p4_costo` → `p4_estensione` → `p7_cella4`, tutte con
`patch -p1 --binary`, tutti gli hunk puliti). Il `diff -ru` fra quel riferimento e l'albero di
lavoro ha dato **esattamente i quattro file** sopra.

### 1.2 Che cosa faceva

Il lavoro parziale era **tutto strumentazione**, coerente e ben commentata, e realizzava quattro cose:

- **NRMSE e route CPU RIGA PER RIGA** (`diag_acc` esteso a `4 + 3·MOE_CPU_MAX_ROWS`, `diag_u` a
  `4 + MOE_CPU_MAX_ROWS`, nuovo array `rowc` scritto dal kernel di export): la cella 4 sapeva
  *quante* route CPU c'erano, non *su quale riga*, ed è esattamente la domanda di A7;
- **la sonda del contributo** `LLAMA_MOE_CPU_PROBE` (0 spenta, 1 `y := 0` ovunque, 2 solo riga 0,
  3 solo righe di bozza, 4 marcatore costante), applicata **dentro la guardia del merge**, dopo
  l'attesa e prima dell'`add`;
- **i contatori del nodo `add`** (`merge_calls`, `merge_senza_piano`), per riconoscere un `add` che
  arriva senza che `remap` abbia appena pianificato lo stesso strato;
- **la guardia del contesto di bozza** `LLAMA_MOE_CPU_MTP_GUARD` (difetto 6 di cella 4), con
  `cparams.ctx_type == LLAMA_CONTEXT_TYPE_MTP` come discriminante e un contatore che conta **sempre**,
  anche a guardia accesa.

E sette preset T1-T7 che mettevano insieme diagnostica, sonde, riferimento e candidato.

### 1.3 La decisione: **si tiene e si completa**

Il progetto era giusto — è la strumentazione che serviva, ed è stata la strumentazione a trovare la
causa. **Nessuna riga è stata rifatta.** Quello che mancava era tutto il resto: la patch non era
salvata, nessuna corsa era stata eseguita, e **il binario del 14/9 20:21 non era mai stato lanciato
nemmeno una volta**. Alla prima esecuzione è morto (§3.1).

Al lavoro ereditato questa cella ha aggiunto: le **tre correzioni** (§4), il **testimone del pool**
(§3.3), due celle nuove (**T1B** e **T8**) e una terza per la scomposizione (**T9**), più la cella di
servizio **T1C**.

---

## 2. Le corse

Tutte sul profilo `fumo`, budget screening, binari `D:\ds4_work\p3_work\build\bin`.
Guardia d'istanza unica verificata prima di ogni avvio; nessun processo residuo alla fine.

| corsa | cella | che cos'è | esito | RAM min |
|---|---|---|---|---:|
| `20260915_073257` (solo log) | T1 | diagnostica per riga, guardia MTP **spenta** | **FALLITA all'avvio**: `CUDA error: unspecified launch failure` | — |
| `20260915_074330` (solo log) | T1B | come T1 ma guardia MTP accesa | **FALLITA allo stesso punto** — la guardia non c'entrava | — |
| `20260915_075156` (solo log) | T1C | T1B con `CUDA_LAUNCH_BLOCKING=1` | **FALLITA di proposito**: nomina il kernel (`remap`, moe-demand.cuh:1088) | — |
| `20260915_080137` | T1B r1 | diagnostica per riga, dopo la correzione del pianificatore | valida | 7,15 GB |
| `20260915_081044` | T1B r2 | come sopra, con il **testimone del pool** | valida | 7,17 GB |
| `20260915_081723` | T1B r3 | come sopra, con i testimoni degli **ingressi** | valida | 7,10 GB |
| `20260915_082427` | T1B r4 | come sopra, **dopo la correzione di A7** | valida | 7,08 GB |
| `20260915_082942` | **T6** | corsia accesa **corretta** — il candidato | valida | 7,25 GB |
| `20260915_083437` | **T5** | corsia spenta, stesso binario — il riferimento | valida | 7,15 GB |
| `20260915_084036` | **T8** | corsia accesa, sonda 1 (`y := 0`) — la prova | valida | 7,16 GB |
| `20260915_084538` | **T9** | corsia accesa, `NOCOMPUTE=1` — la scomposizione | valida | 7,13 GB |
| `20260915_085102` | **T7** | corsia accesa corretta, **contatori** | valida come lettura dei contatori | 7,11 GB |

Nove corse valide, tre avvii falliti (due per un difetto, uno di proposito).
**La RAM libera minima non è mai scesa sotto 7,08 GB** — tre gigabyte di margine sulla soglia R-RAM,
più dei 5,1 GB della cella 4 (che aveva due modelli caricati in una fase diversa della giornata).

Binari usati dalle corse valide: `llama.dll` **02352c5fe0e42399** (15/9 08:21),
`ggml-cuda.dll` **7e2241aaa3969d43** (15/9 07:58).

---

## 3. La diagnosi di A7 — quattro passi, ciascuno con una prova

### 3.1 Passo 0 (non previsto): la diagnostica a due righe faceva morire il server

La prima corsa di T1 non è mai arrivata a servire una richiesta: il server muore durante il
caricamento, subito dopo `srv load_model: loaded multimodal model`, con
`CUDA error: unspecified launch failure`. Riprodotto due volte (14/9 20:23, 15/9 07:32), e una terza
con la guardia MTP accesa — quindi **non era il nodo `add` ereditato dal contesto di bozza**.

`preset_T1C_p7.json` (`CUDA_LAUNCH_BLOCKING=1`) ha nominato il colpevole in una corsa:

```
CUDA error: unspecified launch failure
  current device: 0, in function remap at D:\ds4_work\p3_work\source\ggml\src\ggml-cuda\moe-demand.cuh:1088
```

La riga 1088 è il `CUDA_CHECK(cudaGetLastError())` **subito dopo il lancio di
`moe_grouped_plan_decode`**: il pianificatore. E in quel kernel «unspecified launch failure» ha un
solo significato possibile — `moe_grouped_plan_fail()` chiama `__trap()`.

Quale invariante scattava, e perché solo in diagnostica: **difetto 1**, §4.1.

*Regola di metodo, la stessa che la cella 4 ha imparato al contrario: un errore CUDA asincrono nomina
il primo lancio DOPO il guasto, non il guasto. `CUDA_LAUNCH_BLOCKING=1` costa una corsa e toglie
l'ambiguità; tre ore di lettura del codice non ci erano riuscite.*

### 3.2 Passo 1 — dove sono le route CPU, e con quale errore

`preset_T1B_p7.json`, modalità diagnostica (il piano resta identico a `cpu_max = 0`, la guardia
confronta il contributo CPU con quello che la GPU calcola per le **stesse** route, poi azzera `y`).
Riga di log nuova di questa cella:

```
moe cpu [P7c5] per RIGA: riga 0: routeCPU 0, job 0, confronti 7043, NRMSE -1.000000, max 0
                       | riga 1: routeCPU 24802, job 7043, confronti 7043, NRMSE 1.000000, max 1.05492
                       | riga 2: routeCPU 0, job 0, confronti 0, NRMSE -1.000000, max 0
                       | nodi add 1316 (senza piano dello strato 0) | sonda 0
```

Quattro letture, tutte e quattro utili:

1. **La corsia fa quello che deve**: 24.802 route CPU, **tutte sulla riga 1**, zero sulla riga 0.
   La riga di ammissione conserva la politica attuale parola per parola.
2. **NRMSE sulla riga di bozza = 1,000000 esatto, `max |errore|` = 1,05492** = la grandezza del
   riferimento. `NRMSE = √(Σd²/Σr²) = 1` con `r ≠ 0` significa una cosa sola: **`y` è zero**.
   Non «impreciso»: zero.
3. **Riga 0: `max = 0`.** Anche lì `y` è zero — quindi non è un contributo finito sulla riga
   sbagliata, è un contributo che non c'è.
4. **`nodi add ... senza piano dello strato 0` e `nodo add nel contesto di BOZZA 0`**: il
   **difetto 6 della cella 4 non si riproduce**. Il contesto della bozza non soddisfa mai le
   condizioni del nodo `add` (i suoi esperti non sono legati alla cache a domanda, quindi
   `demand_gpu` è falso), e ogni `add` incontrato dal backend aveva un piano appena costruito per lo
   stesso strato. Il contatore a zero è una prova; la guardia resta, accesa di default, perché
   costa nulla e l'invariante va controllato (§4.3).

Le impronte di T1B sono `c35b20a2290b9c1b` / `f9382a098058a1f2`, **identiche a M1/S6/S12**: la
diagnostica non commette, come deve.

### 3.3 Passo 2 — il testimone del pool: «non calcolato» o «non visto»?

Una NRMSE di 1 non distingue due cause molto diverse: il pool non calcola, oppure calcola e la GPU
non lo vede. Serviva un testimone **dal lato host**, e non c'era. Aggiunto (`misura_y`, una passata
su `y` in memoria locale subito dopo il calcolo, stampata ogni `LLAMA_MOE_CPU_REPORT` decode):

```
moe cpu [periodico]: POOL route calcolate 88303, job con y non nullo 0, max |y| 0
moe cpu [periodico]: pubblicati 33887, conclusi 33887, falliti 0, non finiti 0, ... contaminato no
```

**Il pool prende 88.303 route, conclude 33.887 job senza un fallimento — e scrive zero.**
Non è un problema di visibilità: è il pool stesso, che rilegge il proprio buffer in memoria locale,
a dire che non ha prodotto niente. La causa è a monte dell'aritmetica.

### 3.4 Passo 3 — i tre ingressi, e il colpevole

Stesso testimone, esteso ai tre ingressi dell'aritmetica:

```
POOL route calcolate 88303, job con y non nullo 0, max |y| 0,
     max |peso| 0, max |x| 13.7851, byte non nulli del banco 7119613
```

- attivazione: **arriva** (`max |x| = 13,79`);
- banchi degli esperti: **popolati** (7,1 milioni di byte non nulli);
- **peso di routing: ZERO. Sempre. Su 88.303 route.**

`y = Σ peso · down(SiLU(gate·x)·(up·x))` con tutti i pesi a zero fa zero, qualunque cosa faccia il
resto. Il pool eseguiva l'intera aritmetica — e la moltiplicava per zero.

Da lì al difetto il passo è breve, ed è **difetto 2**, §4.2.

### 3.5 Passo 4 — la prova che non può mentire

Con la correzione applicata, `preset_T8_p7.json` è T6 con la **sonda 1**: la guardia del merge azzera
`y` su tutte le righe dopo l'attesa e prima dell'`add`. Piano, maschera dei pesi, byte non trasferiti
e aritmetica CPU restano **quelli della corsia vera**: cambia solo il contributo che l'`add` somma.

| | T6 (contributo vero) | T8 (contributo azzerato) | *S7/S9/S10/S11, cella 4* |
|---|---|---|---|
| impronta `L01@corto` | `e31f4ae102ecfa17` | **`aacc1d0c9b2a614f`** | ***`aacc1d0c9b2a614f`*** |
| impronta `S01@corto` | `8335d70ed4061bf3` | **`0c30b61c05fb2468`** | ***`0c30b61c05fb2468`*** |
| accettazione su `L01` | **0,79298** (452/570) | **0,69652** (420/603) | ***0,69652 (420/603)*** |
| token accettati, due casi | 1.341 | **1.397** | ***1.397*** |

Due conclusioni, e nessuna delle due era disponibile alla cella 4:

1. **L'`add` arriva eccome a `moe_out`**: azzerare `y` cambia il testo in modo grossolano. La
   lettura (2) di §5.5 («il testo cambia per la sola mascheratura») **cade**.
2. **Tutte le corse «corsia accesa» della cella 4 erano, numericamente, esattamente T8.** Le
   impronte coincidono, l'accettazione coincide alla quinta cifra, il numero di token coincide.
   S7 e S10 davano lo stesso testo perché **nessuno dei due sommava niente**: non era una
   coincidenza generosa su 1.397 token, era la stessa identica corsa.

---

## 4. Le correzioni

Tre difetti, tre correzioni, in `p7_cella5.patch` (671 righe, 7 file, verificata riapplicandola a una
copia pulita di `tmp\ref_c4`: i file risultanti coincidono **byte per byte** con l'albero di lavoro).

### 4.1 Difetto 1 — uno slot ammesso per la bozza restava senza recenza, e il piano dopo trappava

`ggml/src/ggml-cuda/fork-moe-kernels.cuh`, commit differito del pianificatore (righe 296-312).

L'invariante 5 della cella 4 («frequenza e LRU non contano le righe di bozza») era realizzato così:

```c
const bool unique_solo_bozza = unique_draft[unique] != 0;
if (!unique_cpu && !unique_solo_bozza) { last_used[slot] = ...; }
if (unique_solo_bozza) { continue; }
```

In modalità **attiva** i miss di sola bozza vengono tolti dagli array di trasferimento, quindi non
ricevono mai uno slot e il ramo non si presenta. In modalità **diagnostica** la compattazione non
avviene per costruzione (`if (n_cpu > 0 && !cpu_diag)`): quei miss restano miss GPU, **vengono
ammessi in uno slot** — e poi non ricevono nessuna recenza. Uno slot appena allocato ha
`last_used = 0`, e in cima alla chiamata **successiva** c'è:

```c
if (... || (resident >= 0 && last_used[slot] == 0)) { moe_grouped_plan_fail(...); }  // -> __trap()
```

Da cui «unspecified launch failure» al primo decode a due righe. Lo stesso buco è latente anche in
modalità attiva, ogni volta che un miss di sola bozza **non** viene scelto per la CPU (tetto
`MOE_CPU_MAX_PER_ROW` raggiunto): la simulazione della cella 3 conta fino a 10 esperti di sola bozza
per strato, cioè esattamente al tetto.

**Correzione**: un residente non può restare senza età. L'invariante 5 dice che la bozza non deve
*spostare la politica a proprio favore*, non che un residente possa avere recenza nulla — quindi allo
slot appena ammesso per una richiesta di sola bozza si dà la **recenza più vecchia rappresentabile**
(`last_used[slot] = 1`), che lo lascia primo candidato allo sfratto.

### 4.2 Difetto 2 — **LA CAUSA DI A7**: due indirizzamenti diversi per lo stesso descrittore

`src/moe_cpu_executor.cpp`, `validate_and_prepare()`.

Il kernel di export (`moe-demand.cuh`, `moe_cpu_export_kernel`) scrive la route `e` della riga `row`
all'indice

```c
const uint32_t idx = row * MOE_CPU_MAX_PER_ROW + (uint32_t) j;
job->expert[idx] = cpu_experts[i];
job->weight[idx] = router_weights[route];
```

— un **passo di riga fisso**, che è anche la ragione per cui l'array è lungo
`MOE_CPU_MAX_ROWS × MOE_CPU_MAX_PER_ROW` invece del numero di route compattate. Il pool leggeva:

```c
int32_t cursor = 0;
for (row = 0; row < j.n_rows; ++row)
    for (e = 0; e < j.n_routes[row]; ++e, ++cursor) {
        const int32_t expert = j.expert[cursor];      // <-- CURSORE COMPATTATO
        const float   weight = j.weight[cursor];
```

**I due indirizzamenti coincidono solo finché tutte le route stanno sulla riga 0.** È il caso di
tutto P3, di tutto P4 e del banco host di P2 — che ha confrontato 540.672 float con zero differenze
senza poter vedere il difetto, perché girava a una riga sola.

Con la corsia di bozza la riga 0 ha **zero** route e la riga 1 le ha tutte: il pool leggeva le celle
`0 … m-1`, che il kernel di export azzera all'inizio di ogni job
(`for (i < MOE_CPU_MAX_ROUTES) { job->expert[i] = 0; job->weight[i] = 0.0f; }`).
Esperto **0** — un indice valido, che supera il controllo di dominio. Peso **0,0** — un valore
finito, che supera il controllo di finitezza. **Il job passava ogni verifica**, il pool eseguiva
l'intera aritmetica sull'esperto 0 moltiplicandola per zero, la guardia non trovava niente di non
finito, e il contributo usciva esattamente nullo.

**Correzione**: il lettore usa lo stesso passo dello scrittore, e il passo è la **costante di
compilazione** `MOE_CPU_MAX_PER_ROW`, non `caps.max_per_row` — chi scrive usa quella, e un lettore
che usasse il tetto configurato ricadrebbe nello stesso difetto ogni volta che i due non coincidono
(e non coincidono: `caps.max_per_row` vale `MOE_CPU_MAX_PER_ROW` solo con la corsia accesa).

### 4.3 Difetto 3 (era il 7 della cella 4) — in diagnostica il flag di sola bozza inquinava la politica

`fork-moe-kernels.cuh`, dopo la partizione CPU/GPU. La cella 4 lo aveva dichiarato «piccolo,
dichiarato, non corretto». Non era piccolo: è il difetto 1 che lo rendeva letale, e comunque rompeva
la promessa scritta nel commento del pianificatore — «*in diagnostica il piano, il gather, il commit
e i pesi sono identici a `cpu_max = 0`*». Il flag serve a **scegliere** gli esperti CPU (che in
diagnostica servono solo a produrre il job da confrontare): fatto quello, in diagnostica si azzera,
così il commit differito della chiamata successiva non lo vede.

### 4.4 Quello che si è aggiunto senza correggere niente

- **Guardia del contesto di bozza** (`LLAMA_MOE_CPU_MTP_GUARD`, default 1) e il suo contatore. Il
  difetto 6 della cella 4 **non si riproduce** (contatore a zero in tutte le corse): la guardia resta
  come rete, non come correzione, e ha costo nullo.
- **Testimone del pool** (`misura_y`): route calcolate, job con `y` non nullo, `max |y|`,
  `max |peso|`, `max |x|`, byte non nulli del banco. Una passata su memoria locale che il controllo
  dei non finiti faceva già. **Da tenere**: è ciò che ha trovato la causa in due corse.
- **Stampa periodica dei contatori dell'esecutore** (una volta ogni `LLAMA_MOE_CPU_REPORT` decode).
  Prima si stampavano solo alla chiusura del contesto — e il banco chiude il server **a forza**,
  quindi quella riga non è mai arrivata in un log in tutta la giornata del 14/9.

---

## 5. La verifica della correzione

`preset_T1B_p7.json` r4, stesse condizioni di r1-r3, dopo la correzione di §4.2:

| grandezza | prima (r3) | dopo (r4) |
|---|---:|---:|
| **NRMSE riga 1** | **1,000000** | **0,012958** |
| `max \|errore\|` riga 1 | 1,05492 | **0,00862229** |
| `max \|peso\|` visto dal pool | **0** | **0,860275** |
| job con `y` non nullo | **0** | **28.224** |
| `max \|y\|` | 0 | 1,30853 |
| route CPU riga 0 / riga 1 | 0 / 24.802 | 0 / 24.802 |
| valori non finiti | 0 | 0 |
| impronte `L01` / `S01` | `c35b20a2` / `f9382a09` | `c35b20a2` / `f9382a09` |

NRMSE **0,0130** contro lo 0,0084 del progetto P2 §8: stesso ordine, e la differenza è attesa —
P2 misurava un esperto per riga, qui sono 3,3 esperti per riga sommati fra loro, ciascuno con il
proprio errore di quantizzazione.

**Neutralità del binario**: `preset_T5_p7.json` (corsia spenta, stesso binario, tutte e tre le
correzioni presenti) dà impronte `c35b20a2290b9c1b` / `f9382a098058a1f2`, **identiche a M1**
(`20260914_143936_P7_p7_mtp_bozza1_r1`), a S6 e a S12. Le correzioni non toccano il lato spento.

**Invarianti della cella 3 §5.1**, letti da T7 (modalità attiva, contatori):

```
uniche 139040 = colpi 81064 + missGPU 30952 + missCPU 27024 (invariante1 OK)
coppie 163850, routeCPU 27024, uniciCPU 27024
byte trasferiti 61012582400, byte risparmiati 53269708800 (46.61%)
non finiti 0 | graph: lanci 3392, catture 10
pubblicati 34921, conclusi 34921, falliti 0, contaminato no, irrecuperabile no
```

Invariante 1 verificato a ogni stampa, zero non finiti, zero job falliti, nessuna contaminazione,
nessuna ricattura di graph in più, `n_routes ≤ n_slots` (20 contro 64) invariato, route CPU tutte
sulla riga 1 (invariante 6), frequenza e recenza non aggiornate sulle righe di sola bozza
(invariante 5, ora anche senza rompere l'invariante di stato dello slot).

---

## 6. La rimisura — la tabella delle prove

Tutte le colonne dal `print_timing` del server sul caso lungo `L01@corto` (1.024 token generati), che
è la lettura che non mescola casi. `ciclo = ms/token × lunghezza media di accettazione`;
`R = 15,77 + Δciclo` (anatomia della riga di verifica, cella 3, riusata tale quale).

| | **T5** corsia spenta | **T9** consegna senza aritmetica | **T8** corsia + sonda `y:=0` | **T6** corsia **corretta** | **T7** corretta + contatori |
|---|---:|---:|---:|---:|---:|
| t/s su `L01` | **30,827** | 31,933 | 26,387 | **28,086** | 28,063 |
| ms per token | 32,44 | 31,32 | 37,90 | **35,61** | 35,63 |
| accettazione | **0,76990** | 0,69652 | 0,69652 | **0,79298** | 0,79298 |
| lunghezza media | 1,770 | 1,697 | 1,697 | **1,793** | 1,793 |
| **ciclo** (ms) | **57,41** | 53,13 | 64,29 | **63,84** | 63,89 |
| **Δciclo** | — | **−4,29** | +6,88 | **+6,43** | +6,48 |
| **R** (ms) | 15,77 | **11,48** | 22,65 | **22,20** | 22,25 |
| NRMSE riga 1 | — | — | — | **0,012958** *(da T1B r4)* | — |
| byte risparmiati | — | — | — | — | **46,61%** |
| esperti CPU per ciclo | — | — | — | — | **155,0** |
| impronta `L01` | `c35b20a2290b9c1b` | `aacc1d0c9b2a614f` | `aacc1d0c9b2a614f` | `e31f4ae102ecfa17` | `e31f4ae102ecfa17` |
| impronta `S01` | `f9382a098058a1f2` | `0c30b61c05fb2468` | `0c30b61c05fb2468` | `8335d70ed4061bf3` | `8335d70ed4061bf3` |
| RAM libera min | 7,15 GB | 7,13 GB | 7,16 GB | 7,25 GB | 7,11 GB |

*T9 e T8 hanno `y` nullo per costruzione: le loro impronte e la loro accettazione non sono
candidature, sono strumenti di scomposizione. T7 è una verifica dei contatori, non una misura di
tempo (i contatori forzano una sincronizzazione del dispositivo) — che dia 28,063 contro i 28,086 di
T6 dice solo che in questa configurazione il costo della sincronizzazione è sotto il rumore.*

### 6.1 Il cancello

> **Cancello dello stadio 2: `R < 13 ms`. Misura: `R = 22,20 ms`. NON PASSA.**

E non passa **peggio** dei 19,7 ms della cella 4 — il che, letto da solo, sembra un passo indietro.
Non lo è: i 19,7 della cella 4 erano il costo di un pool che moltiplicava 155 volte **l'esperto 0**
per **zero**, cioè con località di cache perfetta e nessun peso da leggere. I 22,2 sono il costo
dell'aritmetica **vera**, su 155 esperti **diversi**. È il primo numero onesto che questa leva abbia
mai prodotto.

### 6.2 Il t/s

Confronto diretto, stesso caso, stesso binario, corse consecutive:
**28,086 contro 30,827 = −8,9%** (−8,7% sull'aggregato dei due casi: 27,834 contro 30,463).

Contro il **28,66 t/s** del giorno il confronto **non si fa**: quello è su `solo_libero` (16 casi),
questo su `fumo` (2 casi). Il criterio del piano era comunque **+5% su 28,66**, e il candidato perde
il 9% dal proprio riferimento omogeneo: il blocco `solo_libero` non è stato eseguito perché il
dispaccio lo subordina esplicitamente al superamento del cancello su `R`, e il cancello non passa.

---

## 7. La scomposizione di R — dove sono i 22,2 ms

È la parte nuova, e ribalta la lettura del §6.7 della cella 4.

| voce | ms per ciclo | da dove |
|---|---:|---|
| **consegna netta** (impianto + attesa esposta − risparmio di trasporto) | **−4,29** | `ciclo(T9) − ciclo(T5)` = 53,13 − 57,41 |
| **aritmetica CPU** | **+11,17** | `ciclo(T8) − ciclo(T9)` = 64,29 − 53,13 |
| costo della sonda (T8 soltanto) | +0,45 | `ciclo(T8) − ciclo(T6)`, a parità di lunghezza non confrontabile — residuo |
| **saldo misurato** | **+6,43** | `ciclo(T6) − ciclo(T5)` |

Tre conseguenze, tutte con un numero.

1. **La consegna non è il problema: è un guadagno.** Con la corsia accesa e il pool che non esegue
   una sola moltiplicazione, il ciclo **si accorcia di 4,29 ms** — cioè `R = 11,5 ms`, che
   **passerebbe il cancello da solo**. L'impianto a polling (0,65 ms per ciclo su 47 strati),
   l'attesa esposta e i nodi del grafo costano meno di quanto il 46,61% di byte non trasferiti
   restituisce. Il risparmio di trasporto stimato dalla cella 3 (−5,5 ms) è confermato: al netto
   dell'impianto resta −4,3.
2. **Tutto il fallimento è l'aritmetica CPU**, e vale **11,17 ms per ciclo**. La disuguaglianza della
   cella 4, riscritta con numeri tutti misurati e nessuno dedotto:

   > la corsia paga quando `n_cpu × costo_per_esperto < risparmio_di_consegna`.
   > Qui: **`155 × 72 µs = 11,17 ms` contro `4,29 ms`**. Manca un fattore **2,6**.

   (Il fattore della cella 4 era 1,7, ma calcolato su un'aritmetica finta. 2,6 è il numero vero.)
3. **Il costo per esperto CPU è 72 µs.** Terza misura indipendente, e la prima in un regime sano e
   con aritmetica reale: la memoria del 10/9 dice 0,074-0,08 ms, la cella 4 deduceva 76 µs. Lo
   scarto fra le tre è del 5%. **Il parametro si può considerare stabilito** (l'apertura A4 della
   cella 4 si chiude come misura, resta solo la scomposizione fra aritmetica e serializzazione).

---

## 8. Difetti trovati

1. **Il descrittore del job aveva due indirizzamenti diversi, e il difetto era invisibile a una
   riga.** §4.2. È la causa di A7 e vale l'intera cella 4 stadio 2. La firma è la peggiore possibile:
   il job passa **ogni** controllo, perché lo zero è un esperto valido e un peso finito.
   *La lezione generale: un contratto fra due lati va provato nella configurazione che li
   DISTINGUE. Il banco host di P2, 540.672 confronti a zero differenze, non poteva trovarlo, perché
   con tutte le route sulla riga 0 i due indirizzamenti danno lo stesso indirizzo. Un test a una
   riga non prova un formato a più righe: prova il caso in cui il formato non conta.*
2. **Un residente senza recenza faceva trappare il piano successivo.** §4.1. Latente anche in
   modalità attiva, al tetto delle route per riga. *La lezione: quando si aggiunge un `continue` a un
   ciclo di commit, la domanda non è «che cosa salto» ma «quale invariante scriveva la riga che sto
   saltando».*
3. **La diagnostica non era neutra sulla politica** (difetto 7 della cella 4, che lo dichiarava e non
   lo correggeva). §4.3. Da solo era piccolo; insieme al difetto 2 rendeva impossibile la corsa che
   avrebbe trovato il difetto 1.
4. **Il difetto 6 della cella 4 non esiste.** Il contesto della bozza **non** costruisce il nodo
   `add`: `demand_gpu` è falso per i suoi esperti, e il contatore lo dice (`nodo add nel contesto di
   BOZZA 0` in tutte le corse, `merge senza piano dello strato 0`). Era un'ipotesi ragionevole letta
   sul codice e mai controllata con un contatore. *La lezione è quella della cella 4 §6.1, applicata
   a sé stessa: un difetto ipotizzato leggendo il codice resta un'ipotesi finché un contatore non lo
   conta.*
5. **I contatori dell'esecutore non arrivavano mai in un log.** Si stampavano alla chiusura del
   contesto; il banco chiude il server a forza. Per tutta la giornata del 14/9 nessuna corsa ha
   avuto la riga «pubblicati / conclusi / falliti». Corretto con la stampa periodica (§4.4).
   *La lezione: un contatore che si stampa solo all'uscita pulita non esiste, se il protocollo non
   esce mai pulito.*
6. **Il preset T1 dell'agente precedente non era eseguibile** (guardia MTP spenta **e** diagnostica:
   la combinazione che fa trappare il pianificatore). Non è un difetto del suo progetto — nessuno
   poteva saperlo prima di lanciarlo — ma vale la nota di metodo: **un binario compilato e mai
   lanciato non è un binario funzionante**. Quello del 14/9 20:21 non ha mai servito una richiesta.

---

## 9. Aperture

| # | apertura | perché adesso | prima misura |
|---|---|---|---|
| **A3′** | **Più thread nel pool** — l'unica leva che può ribaltare il segno, e adesso è **quantificata**. L'aritmetica CPU è 11,17 ms per ciclo contro 4,29 di consegna guadagnata: serve un fattore 2,6. La curva dei thread di P4 (ottimo a 2) fu presa dove il pool calcolava per **uno** strato, cioè dove dominava la contesa, non l'aritmetica. Se l'aritmetica scalasse linearmente, **6 thread** porterebbero il saldo a circa −0,6 ms, cioè **sotto zero**; 4 thread a +1,3, ancora in perdita | `preset_T6_p7.json` con `LLAMA_MOE_CPU_THREADS` 4 e 6, profilo `fumo`, contro T5. Due corse |
| **A5′** | **La corsia su pochi strati.** Costo e risparmio scalano con gli strati ma non con la stessa pendenza. Con un fattore 2,6 da recuperare, un sottoinsieme deve essere molto migliore della media: la prima cosa da fare è **leggere la frazione di miss di sola bozza per strato** dai contatori di T7, non lanciare corse | contatori per strato di `c5_..._t7_..._moecpu.txt`, poi `LLAMA_MOE_CPU_LAYERS` sui primi dieci |
| **A10** | **Il risparmio di consegna esiste ed è gratis: si può prendere senza la CPU?** T9 dice che togliere dal PCIe gli esperti di sola bozza vale **−4,29 ms per ciclo**. Se quegli esperti, invece di andare alla CPU, venissero semplicemente **non serviti** (route mascherata, contributo nullo), il testo cambierebbe — ed è esattamente T8, che perde. Ma se venissero serviti da una **sorgente più economica sulla GPU** (quantizzazione più bassa solo per le righe di bozza), il costo sarebbe di trasporto, non di aritmetica CPU. Non misurato, non progettato | nessuna: è un'idea, va prima portata a progetto |
| **A1** | **La politica della cache senza la corsia CPU** (invariante 5 da solo). Invariata rispetto alla cella 4, e adesso più sicura: il difetto 1 mostra che accendere `draft_from_row` senza la selezione CPU **espone** il buco della recenza — che questa cella ha già chiuso | invariata: una manopola che accenda `draft_from_row` senza la selezione CPU, poi `preset_M1` contro sé stesso sui colpi reali |
| **A2** | **L'impianto a polling applicato a P4-estensione.** Invariata. Rafforzata da T9: l'impianto, misurato dentro una corsa vera, è dentro il rumore | invariata |
| **A6a/A6b** | Bias QSA per riga, dedup del gather QSA. Invariate | invariate |
| **A4** | **Si chiude come misura**: 72 µs, terza conferma indipendente. Resta solo la domanda «quanto di quei 72 µs è aritmetica e quanto serializzazione», che serve solo se A3′ dà un risultato ambiguo | il banco host-only di P2 con un cronometro attorno a `reference_expert` |

### 9.1 Che cosa NON riaprire

- **A7 è chiusa.** Il contributo CPU non arrivava, la causa è nota, corretta e verificata con una
  NRMSE. Non si riapre.
- **Il difetto 6 della cella 4** non esiste: il contatore lo dice, e la guardia che lo preveniva
  resta accesa a costo zero. Non si riapre.
- **Il prefetch della riga di verifica** resta chiuso dalla cella 3 (D24).
- **Il divario dei colpi di cache** resta chiuso (D19).

---

## 10. Bozza di voce di registro

**Data e fase.** 15 settembre 2026, mattina (07:29-08:55). P7 cella 5 — chiusura dell'apertura A7 e
rimisura della corsia CPU sulle righe di bozza dell'MTP. Cella in ripresa dopo l'interruzione
dell'agente della sera del 14/9.

**Ipotesi.** A7 di cella 4: su S7 (pool che calcola) e S10 (`NOCOMPUTE=1`) il testo è identico, e le
tre letture possibili sono «il contributo non arriva a `moe_out`», «il testo cambia per la sola
mascheratura», «il testo cambia per il difetto 6». Una corsa diagnostica con NRMSE per riga e una
sonda che azzera il contributo devono scegliere fra le tre.

**File toccati.** Copia di lavoro `D:\ds4_work\p3_work\source`, nessun commit del motore.
Riferimento `D:\ds4_work\p3_work\tmp\ref_c4\source` (snapshot P0 + le quattro patch in ordine).
Sette file: `ggml/src/ggml-cuda/fork-moe-kernels.cuh` (difetti 1 e 3),
`ggml/src/ggml-cuda/moe-demand.cuh` (sonda, per-riga, contatori dell'`add` — ereditati),
`src/llama-graph.cpp` + `src/llama-moecpu.{h,cpp}` (guardia del contesto di bozza — ereditata;
testimone del pool e stampa periodica — nuovi), `src/moe_cpu_executor.{h,cpp}` (**difetto 2**, la
causa di A7, e il testimone). Patch: `docs/porto/p7_speculazione/p7_cella5.patch`, 671 righe,
verificata riapplicandola a una copia pulita — file identici byte per byte.
Documento: `docs/porto/p7_speculazione/P7_CELLA5_A7_15_SETTEMBRE.md`.
Log puliti: `docs/porto/p7_speculazione/log/c5_*`.
Preset nuovi: `preset_T1B/T1C/T8/T9_p7.json` (più T1-T7 ereditati), generatori
`genera_preset_p7c5.py` e `genera_preset_p7c5_sonda_bloccante.py`.

**Configurazioni.** Profilo `fumo`, budget screening, MTP bozza 1 (testa condivisa), contesto 262144,
64 slot esperti, 47 strati nell'ibrido, `cpu_max = 0`, 2 thread, impianto a polling con scadenza
300 ms. Binari `D:\ds4_work\p3_work\build\bin` (`llama.dll` 02352c5fe0e42399,
`ggml-cuda.dll` 7e2241aaa3969d43).

**Run validi.** Nove: T1B r1-r4 (diagnostica, le ultime tre con strumentazione crescente), T6, T5,
T8, T9, T7. **Non validi**: tre avvii di T1/T1B/T1C morti in caricamento — due per il difetto 1, uno
(T1C) provocato di proposito con `CUDA_LAUNCH_BLOCKING=1` per nominare il kernel. **RAM libera minima
7,08 GB** in tutte le corse, mai vicina alla soglia R-RAM di 4 GB.

**Risultato e limite.** **A7 è chiusa con la lettura (1): il contributo CPU non arrivava, perché era
esattamente zero.** Causa: il kernel di export scrive il descrittore del job con passo di riga
(`row × MOE_CPU_MAX_PER_ROW + e`), il pool lo leggeva con un cursore compattato; i due coincidono
solo con tutte le route sulla riga 0, che è il caso di P3, P4 e del banco host di P2. Il pool leggeva
celle azzerate — esperto 0, peso 0,0 — che superano ogni controllo. Corretto, più altri due difetti
(recenza mancante su uno slot ammesso per la bozza → `__trap()` nel pianificatore; flag di sola bozza
non neutro in diagnostica). Verifica: NRMSE sulla riga di bozza **1,000000 → 0,012958**,
accettazione **0,69652 → 0,79298** (sopra lo 0,76990 del riferimento), impronte a corsia spenta
identiche a M1. **Cancello `R < 13`: `R = 22,20 ms`, NON PASSA.**
t/s **28,086 contro 30,827** sullo stesso caso e binario, **−8,9%**. Scomposizione: la sola consegna
vale **−4,29 ms per ciclo** (`R = 11,5`, passerebbe), l'aritmetica CPU **+11,17 ms**; costo per
esperto **72 µs** su 155 esperti per ciclo; byte risparmiati 46,61%. Limite: profilo `fumo`, due
casi; nessuna valutazione di qualità (D15); il blocco `solo_libero` non è stato eseguito perché
subordinato al cancello.

**Decisione.** **La corsia CPU sulle righe di bozza si CHIUDE — negativa, non più inconclusiva.**
Il meccanismo è corretto (invarianti tutti verificati, zero non finiti, zero job falliti) e la sua
*consegna* è in guadagno; è l'aritmetica CPU a non stare nel bilancio, per un fattore 2,6.
Le tre correzioni si **adottano** comunque, perché due sono difetti di correttezza veri (uno letale)
e la terza è una rete a costo zero. Tutte le manopole restano spente di default. Resta aperta, e
adesso quantificata, la sola leva che può ribaltare il segno: **più thread nel pool (A3′)**.

**Regressioni.** Nessuna. Corsia spenta: impronte `c35b20a2290b9c1b` / `f9382a098058a1f2`, identiche
a M1, S6 e S12; `qwen38_clean\bin_prod`, `qwen38_clean\source`, il lanciatore quotidiano, i modelli e
lo snapshot `p0_snapshot_20260914` non sono stati toccati.

**Stato processi.** Nessun `llama-server` attivo, porta 8100 libera, nessun processo residuo.

**Prossima azione.** **A3′**: `preset_T6_p7.json` con `LLAMA_MOE_CPU_THREADS` 4 e 6 contro T5, due
corse sul profilo `fumo`. Se il saldo non scende sotto zero a 6 thread, la corsia è chiusa per
sempre e la cella 6 passa ad A1 (la politica della cache senza la corsia CPU, costo zero) e alle leve
lossless della riga di verifica (A6a/A6b).

---

## 11. Artefatti

- Patch incrementale: [`p7_cella5.patch`](p7_cella5.patch) (671 righe, 7 file), contro
  `D:\ds4_work\p3_work\tmp\ref_c4\source`. Generatore: [`genera_patch_c5.sh`](genera_patch_c5.sh).
- Preset: [`../banco_p0/preset_T1_p7.json`](../banco_p0/preset_T1_p7.json) … `preset_T9_p7.json`
  (T1B, T1C, T8, T9 nuovi di questa cella). Generatori:
  [`genera_preset_p7c5.py`](genera_preset_p7c5.py),
  [`genera_preset_p7c5_sonda_bloccante.py`](genera_preset_p7c5_sonda_bloccante.py).
  **T2, T3, T4 non sono stati eseguiti**: nascevano per interrogare la vecchia configurazione
  (guardia MTP spenta), e T8 sul binario corretto risponde meglio alla stessa domanda riproducendo
  esattamente le impronte della cella 4.
- Log puliti: [`log/`](log/), prefisso `c5_` — riepiloghi e righe dell'ibrido per ogni corsa, più
  `c5_t1_avvio_fallito_trap.txt` e `c5_t1c_lancio_bloccante_trap.txt` (gli avvii falliti, che non
  producono una cartella di corsa). Copiatore: [`copia_log_c5.py`](copia_log_c5.py).
- Corse complete: `D:\ds4_work\banco_p0_run\20260915_08*_P7-cella5_*` (nove cartelle).
- Riferimento del diff: `D:\ds4_work\p3_work\tmp\ref_c4\source` — **si conserva**, è la base del
  `diff` della cella 6. La copia usata per verificare la patch
  (`D:\ds4_work\p3_work\tmp\verifica_c5`) è stata cancellata dopo il confronto: si rifà in un minuto
  con lo script, e tenere due alberi identici invita a patchare quello sbagliato.
