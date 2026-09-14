# P2 — Esito della compilazione e della verifica dell'esecutore host CPU

**14 settembre 2026.** Fase di compilazione concordata: macchina libera, nessuna
misura di baseline in corso, nessun `llama-server` avviato, nessuna GPU usata.

Questo documento riporta l'esito della fase che il progetto
([`PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md`](PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md)
§16, «Prossima azione») aveva lasciato aperta con la frase più importante di
tutto il documento: *«nulla di tutto questo è stato compilato»*. Adesso lo è.

**Il risultato in una riga: il progetto compila al primo tentativo, e la batteria
passa senza un solo controllo fallito in 250 esecuzioni complete del binario.**
Nessun difetto di correttezza è emerso nel codice dell'esecutore; l'unico difetto
vero stava nel lanciatore `.ps1` (§6.5). Le modifiche ai sorgenti sono tutte
diagnostiche e sono elencate in §6, dove si dice anche perché nessuna di esse
tocca la semantica della macchina a stati.

---

## 1. Che cosa è stato toccato, e che cosa no

| | |
|---|---|
| Toccato | solo file sotto `docs/porto/p2_esecutore/`: tre sorgenti (aggiunte diagnostiche), un nuovo script di ciclo, i log, questo documento |
| **Non** toccato | `qwen38_clean\source` (nessuna lettura in scrittura, nessuna ricompilazione del motore), `bin_prod`, qualunque file sotto `Documents\Codex` |
| Avviato | solo `test_esecutore.exe`, host-only. **Nessun `llama-server`**, nessuna GPU |
| Commit | nessuno |

La build privata del motore è stata usata in **sola lettura**, per le tre `.lib`
e le tre `.dll` corrispondenti, esattamente come fa
`freetoken_hybrid\build.cmd`.

---

## 2. Comandi riproducibili

Dalla cartella `docs/porto/p2_esecutore/`:

```
:: compilazione (il .ps1 compila e poi esegue; il .cmd compila soltanto)
build_test.cmd

:: batteria T1-T17, i quattro modi
test_esecutore.exe --threads 4
test_esecutore.exe --threads 6
test_esecutore.exe --full --threads 4
test_esecutore.exe --full --threads 6
test_esecutore.exe --weights C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\cpu_quant_audit --threads 4
test_esecutore.exe --weights C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\cpu_quant_audit --threads 6
```

```powershell
# cicli delle prove di corsa (nuovo, §6.4)
.\cicla_corse.ps1 -Giri 50 -Thread 4,6
.\cicla_corse.ps1 -Giri 20 -Thread 4,6 -Weights C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\cpu_quant_audit
```

Equivalente con il lanciatore `.ps1` (compila **e** esegue, come da progetto —
il `.cmd` non va toccato a caldo):

```powershell
.\build_test.ps1 -Threads 4
.\build_test.ps1 -Threads 6 -Full
.\build_test.ps1 -Threads 4 -Weights C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\cpu_quant_audit
```

**Compilatore e ambiente**

| | |
|---|---|
| Compilatore | MSVC `cl.exe` **19.44.35227** per x64 (toolset `14.44.35207`) |
| Ambiente | `vcvars64.bat` di Visual Studio 2022 Community |
| Flag | `/nologo /std:c++17 /utf-8 /O2 /EHsc /MD /W4` |
| Include | `%QROOT%\source\ggml\include` e `src` |
| Librerie | `ggml-cpu.lib`, `ggml-base.lib`, `ggml.lib` della build privata. **Nessun'altra**: in particolare nessuna `Synchronization.lib`, nessuna libreria CUDA |
| `QROOT` | `C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean` |
| Sorgenti compilati | `test_esecutore.cpp`, `moe_cpu_executor.cpp`, `moe_cpu_host_memory_plain.cpp` (il fornitore CUDA resta escluso, come previsto: è lavoro di P3) |
| Macchina | AMD Ryzen 7 5800X, 8 core fisici / 16 logici, Windows 11 Pro 10.0.26200 |

Log: [`log/build.log`](log/build.log), [`log/test_*.log`](log/),
[`log/cicli_*.log`](log/), [`log/dipendenze.log`](log/dipendenze.log).

---

## 3. Esito della compilazione

**Compila al primo tentativo, con zero errori.** Non è stata necessaria nessuna
correzione per compilare: le due correzioni di compilazione previste dalla
revisione (E1, nome e firma del proc-address; E2, `<malloc.h>`) erano già
applicate nei sorgenti ed erano giuste.

| | |
|---|---|
| Errori | **0** |
| Avvisi a `/W4` | **15**, tutti `C4324` sulla stessa struttura |
| Avvisi di codepage (`C4819`) | **0** |

`C4324` è *«la struttura è stata compilata in base all'identificatore di
allineamento»*: MSVC segnala che ha inserito padding per rispettare un
`alignas`. Le quindici occorrenze sono le celle di `moe_cpu_executor::impl`
allineate alla linea di cache (`moe_cpu_executor.cpp`, righe 276-293 nella
versione finale). **È il comportamento voluto** — l'allineamento serve a evitare il false
sharing fra coordinatore e worker — e l'avviso non indica nessun problema.
Non è stato silenziato: un `#pragma warning(disable: 4324)` nasconderebbe anche
i casi in cui il padding *non* fosse voluto.

---

## 4. Esiti dei test, per configurazione e per numero di thread

La batteria esegue **74 controlli** distribuiti sui diciassette test. Tutte e sei
le configurazioni li passano tutti.

| Configurazione | Forme | Thread | Controlli | Falliti | Durata |
|---|---|---|---|---|---|
| rapida | K=512 H=128 E=4, pesi sintetici | 4 | 74 | **0** | 1,3 s |
| rapida | K=512 H=128 E=4, pesi sintetici | 6 | 74 | **0** | 1,3 s |
| `--full` | K=2560 H=640 E=4, pesi sintetici | 4 | 74 | **0** | 5,1 s |
| `--full` | K=2560 H=640 E=4, pesi sintetici | 6 | 74 | **0** | 5,0 s |
| `--weights` | K=2560 H=640 E=128, **pesi veri del prototipo** | 4 | 74 | **0** | 1,2 s |
| `--weights` | K=2560 H=640 E=128, **pesi veri del prototipo** | 6 | 74 | **0** | 0,8 s |

I `--weights` sono i `.bin` del prototipo del 13 settembre
(`...\rip\work\cpu_quant_audit\{gate_22,up_22,down_20}.bin`, IQ2_S/IQ2_S/IQ4_NL,
128 esperti): **pesi quantizzati veri, non sintetici**.

Copertura per test in una singola corsa (numero di controlli):

| Test | Controlli | Che cosa prova | Esito |
|---|---|---|---|
| T1 | 2 | parità col riferimento GGML, una route | ok |
| T2 | 2 | somma pesata di due route | ok |
| T3 | 2 | la piastrellatura parallela non cambia il risultato | ok |
| T4 | 3 | zero route è un esito valido, senza veleno né contaminazione | ok |
| T5 | 4 | generazione e stato per job | ok |
| T6 | 4 | dieci header non validi: rifiutati, avvelenati, `y` intatto, contamina | ok |
| T7 | 3 | annullamento senza stallo e riarmo | ok |
| T8 | 5 | submit rientrante rifiutato senza toccare il job in volo | ok |
| T9 | 2 | cambio di fase, `quiesce`, distruzione cronometrata | ok |
| T10 | 1 | nessun riuso anticipato del buffer su otto job | ok |
| T11 | 1 | nessuna allocazione nuova a regime | ok |
| T12 | 12 | **annullamento durante un `compute()` genuinamente in corso** | ok |
| T13 | 13 | **scadenza del `wait` con completamento tardivo, e recupero** | ok |
| T14 | 12 | routine contro errore, e riconoscimento della contaminazione | ok |
| T15 | 1 | **teardown con un job in volo** | ok |
| T16 | 3 | sette configurazioni non valide più il fornitore assente | ok |
| T17 | 4 | idempotenza ed errore di `register_layer` | ok |
| **totale** | **74** | | **0 falliti** |

---

## 5. Verifiche esplicite chieste dal progetto (§16, «Cosa resta da verificare in compilazione»)

### 5.1 Le tre `.lib` bastano, e non serve `Synchronization.lib` — **confermato**

Il binario si collega con le sole `ggml-cpu.lib`, `ggml-base.lib`, `ggml.lib`.
`dumpbin /dependents test_esecutore.exe` ([`log/dipendenze.log`](log/dipendenze.log)):

```
ggml-cpu.dll, ggml-base.dll, MSVCP140.dll, KERNEL32.dll,
VCRUNTIME140.dll, VCRUNTIME140_1.dll, api-ms-win-crt-*.dll
```

Tre conclusioni si leggono da questa lista:

1. **nessuna dipendenza da `Synchronization.dll` né da
   `api-ms-win-core-synch-l1-2-0.dll`.** La scelta di risolvere
   `WaitOnAddress`/`WakeByAddressAll` a caldo con `GetProcAddress` è verificata
   dal linker, non solo dichiarata nei commenti;
2. **nessuna dipendenza CUDA** (né `ggml-cuda.dll`, né `cudart`, né `nvcuda`): il
   test è davvero host-only, come il progetto prometteva;
3. `ggml.dll` **non compare fra le dipendenze**, pur essendo `ggml.lib` fra le
   librerie collegate: il binario non importa nessun simbolo da quella DLL.
   Non è un difetto — la riga è la stessa di `freetoken_hybrid\build.cmd` e
   copiare la DLL costa nulla — ma è un'informazione che vale la pena avere
   scritta prima di P3, dove l'elenco delle librerie va rifatto per il motore.

### 5.2 `ggml_quantize_chunk` con IQ2_S e imatrix di soli uno — **accettato, nessun ripiego necessario**

Verificato in due modi indipendenti, perché sull'esito di questo punto poggiava
la possibilità stessa di girare senza i `.bin` del prototipo.

**Per esecuzione.** `test_esecutore.cpp:83-85` costruisce
`std::vector<float> imatrix(n_per_row, 1.0f)` e chiama
`ggml_quantize_chunk(GGML_TYPE_IQ2_S, ..., imatrix.data())`. La chiamata ritorna,
non asserisce, e i byte prodotti danno **parità bit a bit** col riferimento GGML
(§5.4) sia a K=512 sia a K=2560.

**Per lettura dei sorgenti della build privata** (in sola lettura):

- `ggml.c:7984-7990` — `ggml_quantize_requires_imatrix()` elenca `IQ2_XXS`,
  `IQ2_XS` e `IQ1_S`. **`IQ2_S` non è nell'elenco**: per lui la matrice di
  importanza è facoltativa, quindi passargliene una non può far scattare
  l'`GGML_ASSERT(imatrix != NULL)` di `ggml.c:8002-8004`, e non passargliela
  nemmeno;
- `ggml-quants.c:5142` — `quantize_row_iq2_s_impl` usa `quant_weights` sotto un
  `if (quant_weights)`: il puntatore è opzionale per costruzione. Una matrice di
  soli uno entra nel ramo pesato con peso unitario, non in un ramo di errore;
- `ggml.c:8010` — `ggml_quantize_chunk` chiama da sé `ggml_quantize_init(type)`,
  che per `IQ2_S` esegue `iq2xs_init_impl` (`ggml.c:7952-7958`). L'assert
  *«forgot to call ggml_quantize_init()?»* di `ggml-quants.c:5150` non può
  quindi scattare passando dalla via che il test usa.

**Conseguenza operativa: il ripiego previsto dal progetto non serve.** La
batteria gira con pesi sintetici quantizzati sul momento. Il percorso
`--weights` con i `.bin` del prototipo è stato comunque eseguito (§4) e passa:
resta come secondo riferimento, non come necessità.

### 5.3 `WaitOnAddress` si risolve — **sì, percorso nativo**

Il progetto chiedeva di sapere **con quale percorso**. Il codice non lo rendeva
osservabile dall'esterno del binario, quindi è stata aggiunta la diagnostica
`moe_cpu_wait_backend()` (§6.1). Su questa macchina la batteria stampa:

```
attesa inattiva: WaitOnAddress/WakeByAddressAll
```

Cioè `LoadLibraryA("api-ms-win-core-synch-l1-2-0.dll")` seguito dai due
`GetProcAddress` riesce: **il ripiego `Sleep(1)` non è attivo**. Questo chiude
il rischio R6 per quanto riguarda *questa* macchina: la latenza di risveglio
misurata in P4 sarà quella del percorso nativo, e non c'è il millisecondo di
`Sleep(1)` nascosto dentro i numeri.

### 5.4 Parità bit a bit, non solo ≤ 1e-6 — **confermata, zero elementi diversi**

Questo è il punto su cui il progetto era esplicitamente in dubbio («che la parità
col riferimento GGML sia davvero bit a bit e non solo entro 1e-6, come lo era nel
prototipo»). **Lo è.**

La misura non è una soglia: è il **conteggio degli elementi float diversi**,
con il confronto `a[i] != b[i]` fatto elemento per elemento (`unequal()`,
`test_esecutore.cpp:200-204`), su sedici casi di attivazione a tre scale
diverse (×0,25, ×1, ×4).

| Confronto | Configurazione | Confronti eseguiti | **Elementi diversi** | NRMSE peggiore |
|---|---|---|---|---|
| esecutore contro riferimento GGML `mul_mat_id`, una route | K=512 | 8 192 | **0** | 0 |
| esecutore contro riferimento sommato, due route pesate | K=512 | 8 192 | **0** | 0 |
| esecutore parallelo contro `reference_expert()` seriale | K=512 | 8 192 | **0** | 0 |
| le stesse tre, `--full` | K=2560 | 40 960 ciascuna | **0** | 0 |
| le stesse tre, `--weights` (pesi veri) | K=2560, 128 esperti | 40 960 ciascuna | **0** | 0 |

In totale **540 672 confronti di float, zero diversi**, su sei configurazioni
(2 × 3 × 16 × 512 per le rapide, più 4 × 3 × 16 × 2560 per le altre quattro).
La parità vale anche fra il percorso a 4 thread e quello a
6: la piastrellatura non cambia il risultato (T3, NRMSE esattamente 0 e zero
elementi diversi), che è la proprietà che serve per poter cambiare
`n_threads` in P4 senza rimettere in discussione la numerica.

Il controllo sul conteggio è ora **vincolante**, non solo stampato: erano già
presenti i controlli sulla soglia 1e-6, sono stati affiancati da tre controlli
`== 0` sugli elementi diversi (§6.2). Se un domani la parità si degradasse a
«entro 1e-6», la batteria fallirebbe invece di passare in silenzio.

### 5.5 `/utf-8` compatibile con gli header GGML — **sì, e non è load-bearing su questa macchina**

Due fatti distinti, e vanno tenuti distinti.

**Compatibile: sì, senza riserve.** La compilazione con `/utf-8` produce **zero
avvisi `C4819`** (il codice che MSVC emette quando un file non è rappresentabile
nella codepage attiva). Il motivo si legge nei file: gli header GGML inclusi —
`ggml.h`, `ggml-cpu.h`, `ggml-backend.h` — **non contengono un solo byte non
ASCII**, quindi non c'è niente che `/utf-8` possa reinterpretare male. I sorgenti
di P2, al contrario, contengono da 1 a 21 righe non ASCII ciascuno (em-dash,
virgolette basse, i caratteri di riquadro della macchina a stati in
`moe_cpu_executor.h`) e sono tutti **UTF-8 valido**.

**Load-bearing su questa macchina: no.** Va detto perché il progetto lo
presentava come una difesa contro un difetto silenzioso, ed è onesto riportare
che il difetto, qui, non si manifesta. Compilando la *stessa* riga **senza**
`/utf-8` (prova di controllo eseguita fuori dall'albero, in cartella
temporanea) si ottiene comunque codice di uscita 0, gli stessi 15 `C4324` e
nessun altro avviso. La codepage ANSI di sistema è 1252, che mappa ogni byte a
un carattere: nessuna delle sequenze UTF-8 presenti nei sorgenti termina con il
byte `0x5C`, quindi la continuazione di riga temuta dal progetto non si verifica.

**Conclusione: `/utf-8` resta, e la motivazione nel progetto va corretta da
«chiude un difetto» a «chiude un difetto possibile su un'altra macchina».**
È assicurazione contro una codepage diversa o contro un carattere aggiunto
domani, non la riparazione di un guasto presente. Il flag non costa nulla e non
ha effetti collaterali misurabili; toglierlo per il motivo sbagliato — «tanto
compila lo stesso» — sarebbe la mossa che riapre il caso fra sei mesi su una
macchina diversa.

### 5.6 I ritardi iniettati non fanno scattare le scadenze — **confermato, con margini misurati**

Il progetto chiedeva di verificare che i 120-300 ms iniettati non facessero
scattare «per sbaglio» le scadenze, e aggiungeva la regola giusta: *«se succede,
è il banco a essere sbagliato, non il codice»*. Il modo di saperlo non è l'esito
binario del giro ma il **margine**, quindi i tre tempi vengono ora stampati dalla
batteria (§6.3) e raccolti a ogni giro dal ciclo (§6.4). Numeri su 240 giri:

| Prova | Ritardo iniettato | Tempo misurato (min / max su 240 giri) | Scadenza | Margine peggiore |
|---|---|---|---|---|
| T12 — `cancel()` a 30 ms su un calcolo da 120 ms | 120 ms | 30,2 / **45,7 ms** | `wait_timeout` 5 000 ms, `ack_timeout` 2 000 ms | **44×** sulla più stretta delle due |
| T13 — scadenza del `wait` a 3 ms su un calcolo da 300 ms | 300 ms | 3,2 / **19,1 ms** | limite del banco 200 ms | **10×** |
| T15 — teardown con job in volo, distruzione a 20 ms di 150 | 150 ms | 114,1 / **130,1 ms** | 2 000 ms | **15×** |

Tre osservazioni che i numeri permettono e che le sole spunte verdi non
permetterebbero:

1. **nessuna scadenza è scattata per sbaglio, nemmeno una volta su 240 giri.**
   Il rischio R15 («`ack_timeout_us` troppo corto produce falsi
   irrecuperabili») non si è manifestato: `unrecoverable()` è sempre risultato
   falso in T12, cioè il coordinatore ha sempre riconosciuto entro il limite;
2. **T13 è la prova con il margine più stretto**, ed è per costruzione: 200 ms di
   limite su un calcolo da 300 ms. Il margine misurato resta comunque ampio (19,1
   ms nel caso peggiore, il 90% sotto il limite) perché ciò che si misura è la
   scadenza del `wait` a 3 ms più il costo di ritorno, non il calcolo. Se un
   giorno questo numero si avvicinasse ai 200 ms sotto carico, **la correzione è
   allargare il limite del banco**, non il codice: la proprietà provata è «la
   scadenza scatta a calcolo in corso», non «scatta entro 200 ms». La nota è ora
   scritta accanto al controllo, dove la si cercherebbe;
3. **il teardown di T15 costa esattamente i ~130 ms che restano del calcolo**
   (150 iniettati meno i 20 di attesa prima di distruggere), non i 2 s del
   limite. È la conferma per misura di ciò che §11.2 argomenta per costruzione:
   la distruzione attende il coordinatore e nient'altro. Se attendesse una
   barriera spaiata o una scadenza, il numero sarebbe diverso, non solo più
   grande.

### 5.7 Controllo statico dell'invariante 6 (punto 18 di §13) — fatto, esito positivo

Non era nell'elenco delle verifiche di compilazione ma costa un `grep` e il
progetto lo prevede. In `moe_cpu_executor.cpp` non compare **nessuna** chiamata
`cuda*`/`cu*`, **nessun** `std::mutex`, `lock_guard`, `unique_lock` o
`condition_variable`, e `<mutex>` **non è nemmeno incluso**. L'invariante 6 —
nessun callback attende un mutex che il thread in attesa del graph possa
trattenere — è vero per costruzione, non per ispezione caso per caso.

---

## 6. Correzioni fatte

**Nessuna correzione di correttezza è stata necessaria nel codice
dell'esecutore.** Le quattro modifiche di §6.1-§6.4 sono **diagnostiche** —
rendono osservabile ciò che il progetto chiedeva di verificare — e nessuna tocca
la macchina a stati, gli atomici, l'ordine delle operazioni o l'aritmetica.
Un difetto vero c'era, ma **negli script**, non nei sorgenti: §6.5 e §6.6.
Tutte sono elencate qui perché il progetto chiede che ogni correzione sia
annotata, anche quando è piccola.

### 6.1 `moe_cpu_wait_backend()` — nuova funzione diagnostica

*File: `src/moe_cpu_executor.h` (dichiarazione), `src/moe_cpu_executor.cpp`
(definizione, accanto a `moe_cpu_state_name`), `src/test_esecutore.cpp`
(stampa).*

Restituisce `"WaitOnAddress/WakeByAddressAll"`, `"Sleep(1) (ripiego)"` oppure
`"sleep_for (non Windows)"` a seconda del percorso effettivamente risolto.

**Perché.** La verifica n. 3 del progetto («che `WaitOnAddress`/
`WakeByAddressAll` si risolvano su questa macchina, **e con quale percorso**»)
non era osservabile: `sync_api` è in un namespace di dettaglio dentro il `.cpp` e
il ripiego è silenzioso per disegno. Senza questa riga, un binario caduto sul
ripiego `Sleep(1)` passerebbe la batteria identicamente e in P4 si
misurerebbe una latenza di risveglio con dentro un millisecondo di cui nessuno
saprebbe l'origine. Chiude anche la parte diagnostica del rischio R6
(«l'esecutore dovrebbe registrare quale percorso ha scelto»).

**Perché non cambia la semantica.** Legge lo stesso `static` locale che il
percorso di attesa già usa (`sync()`), non ne crea un secondo, non modifica
niente, ed è chiamata solo dal test prima di costruire l'esecutore.

### 6.2 Parità bit a bit resa vincolante

*File: `src/test_esecutore.cpp`, T1/T2/T3.*

Aggiunti il conteggio `unequal_internal` per T3 (T1 e T2 già lo avevano), i
totali dei confronti nella riga di stampa, e **tre controlli `== 0`** sugli
elementi diversi accanto ai tre controlli di soglia esistenti.

**Perché.** Il progetto dichiara la parità bit a bit come l'obiettivo (§13 punto
1: «NRMSE ≤ 1e-6, atteso **zero diversi**») ma la batteria controllava solo la
soglia. Il conteggio era stampato e non verificato: una regressione da «bit a
bit» a «entro 1e-6» — cioè esattamente la differenza fra il prototipo e ciò che
P2 vuole garantire — sarebbe passata senza che nessun controllo fallisse.
Adesso il criterio dichiarato e il criterio verificato coincidono.

### 6.3 Stampa dei margini delle scadenze in T12, T13, T15

*File: `src/test_esecutore.cpp`.*

Le tre prove stampano ora il tempo misurato accanto alla scadenza e al valore
atteso, con la nota su quale sia la correzione giusta se il margine si
restringesse.

**Perché.** È la verifica n. 7, e non è verificabile con un esito binario: un
controllo che passa dice solo che la scadenza non è scattata *questa volta*.
Il margine dice **quanto** manca, che è l'informazione che serve per decidere,
su una macchina carica, se il difetto è nel banco o nel codice. In T15 il valore
atteso (~130 ms) è scritto accanto al numero perché un teardown che costasse
molto di più o molto di meno significherebbe che sta attendendo qualcosa di
diverso dal coordinatore — cosa che il limite dei 2 s non rivelerebbe mai.

### 6.4 `cicla_corse.ps1` — nuovo script

*File nuovo: `cicla_corse.ps1`.*

Ripete la batteria N volte per ciascun numero di thread, conta passati e
falliti, conserva l'output completo di ogni giro fallito in un file separato, e
riporta durata (min / mediana / max) e i margini di T12/T13/T15 sull'intero
ciclo.

**Perché ricicla la batteria intera e non i soli T12-T15.** Due ragioni, e la
prima è dirimente: **T15 prova la distruzione con un job in volo, e la
distruzione è osservabile solo se il processo termina davvero.** Un ciclo interno
al processo proverebbe una cosa diversa da quella che il test dichiara di
provare. La seconda è che la batteria intera costa poco più dei soli T12-T15 —
il grosso del tempo è la quantizzazione iniziale dei banchi — quindi il ciclo
risulta più severo, non meno: ogni giro riesegue anche i cinquanta controlli
non di corsa.

**Nota di metodo dentro lo script.** La mediana è calcolata ordinando e prendendo
l'elemento centrale. È scritto nel commento perché è un errore già pagato in
questo progetto («la *mediana* era il MASSIMO»).

### 6.5 `build_test.ps1` moriva su stderr innocuo — **difetto vero, corretto**

*File: `build_test.ps1`.*

Questo è l'unico difetto di sostanza emerso in tutta la fase, ed è istruttivo
perché **non stava nel codice ma nel lanciatore**, cioè esattamente dove nessuno
lo cercava.

**Il sintomo.** `build_test.cmd` lanciato a mano compilava ed eseguiva; lo stesso
lavoro fatto da `build_test.ps1` — che il progetto indica come **il** lanciatore,
per la regola «un `.bat` modificato a caldo risuscita il server» — falliva con un
errore che non c'entrava niente con la compilazione. I due script, che §17.2 del
progetto vuole **equivalenti**, non lo erano.

**La causa.** Windows PowerShell 5.1 avvolge ogni riga di stderr di un eseguibile
nativo in un `ErrorRecord` (`NativeCommandError`). Con `$ErrorActionPreference =
'Stop'` — che `build_test.ps1` imposta, correttamente, in cima — **una sola riga
di stderr termina lo script, anche se il comando è riuscito e ha restituito 0**.
Su questa macchina `vcvarsall.bat` stampa su stderr
`"vswhere.exe" non è riconosciuto...` (la cartella dell'Installer non è nel
PATH: avviso innocuo, l'ambiente viene impostato lo stesso) e poi ritorna 0.
Il `.ps1` moriva prima ancora di arrivare al controllo di `$LASTEXITCODE`, che
era la riga giusta e non veniva mai eseguita.

**La correzione.** La chiamata al `.cmd` è ora racchiusa fra un
`$ErrorActionPreference = 'Continue'` e il ripristino del valore precedente in un
`finally`. **L'autorità sull'esito resta il codice di uscita**, controllato
subito dopo, che è l'unico segnale che distingue davvero una compilazione
riuscita da una fallita: lo stderr, su un compilatore, non lo è. Verificato dopo
la correzione con tutte e quattro le combinazioni del lanciatore: `-Threads`,
`-Full`, `-Weights`, `-Experts`, tutte con `ESITO POSITIVO` e codice 0.

**Perché conta oltre a P2.** È la stessa classe di difetto della memoria di
progetto «strumenti che mentono in silenzio», con il segno rovesciato: qui lo
strumento non mentiva dicendo che andava bene, falliva dicendo che andava male.
Il costo è simmetrico — si smette di fidarsi del lanciatore giusto e si torna a
lanciare il `.cmd` a mano, che è precisamente la pratica che il progetto voleva
evitare.

### 6.6 Un `.cmd` deve restare in puro ASCII — **difetto introdotto e corretto nella stessa fase**

*File: `build_test.cmd`.*

Annotato perché è stato introdotto **da questo lavoro** e vale più della sua
dimensione. Aggiornando la nota in testa al `.cmd` vi sono state scritte due
virgolette basse (`«»`). Il file è UTF-8; `cmd.exe` lo legge nella codepage
attiva, non in UTF-8; la sequenza multibyte ha rotto il parsing della riga e la
build è fallita con `"m" non è riconosciuto come comando`.

È **la stessa classe di difetto** che `/utf-8` chiude per i sorgenti C++ (§5.5),
manifestata dall'altro lato del confine: nel `.cmd` non esiste nessun `/utf-8`
da attivare, e l'unica difesa è non metterci caratteri non ASCII. Il file
originale infatti scriveva ovunque `e'` e mai `è` — la disciplina c'era già, ma
non era scritta. Ora lo è, in una nota dentro il file stesso, dove la si
cercherebbe. Il `.cmd` è di nuovo puro ASCII, verificato per byte.

---

## 7. Cicli delle prove di corsa

Il progetto è netto su questo punto: *«una prova di corsa che passa una volta non
ha detto niente»*. Numeri:

| Tornata | Configurazione | Thread | Giri | Passati | Falliti | Durata per giro (min / mediana / max) |
|---|---|---|---|---|---|---|
| prima | rapida | 4 | 50 | **50** | **0** | 1,297 / 1,305 / 1,421 s |
| prima | rapida | 6 | 50 | **50** | **0** | 1,302 / 1,308 / 1,423 s |
| pesi veri | `--weights` | 4 | 20 | **20** | **0** | 0,808 / 0,816 / 0,931 s |
| pesi veri | `--weights` | 6 | 20 | **20** | **0** | 0,809 / 0,821 / 0,929 s |
| certificazione finale | rapida | 4 | 50 | **50** | **0** | 1,288 / 1,298 / 1,431 s |
| certificazione finale | rapida | 6 | 50 | **50** | **0** | 1,295 / 1,300 / 1,410 s |
| **totale cicli** | | | **240** | **240** | **0** | ~296 s |

La tornata di certificazione finale è stata rieseguita dopo la correzione del
lanciatore (§6.5) per avere log generati dal binario definitivo; i sorgenti C++
sono identici fra le tre tornate, e i numeri infatti coincidono entro la
dispersione della macchina.

Contando anche le dieci corse singole (le sei di §4 più le quattro di verifica
del lanciatore: `-Threads`, `-Full`, `-Weights`, `-Experts`), il binario è stato
eseguito **250 volte**: 250 su 250 con `ESITO POSITIVO`, cioè **18 500 controlli
superati e nessuno fallito**. Nessun giro ha prodotto una sola riga `[ko]`, e i
file `log/cicli_*_guasti.log` non esistono perché non c'è stato niente da
scriverci.

La dispersione delle durate è del 9-10% fra minimo e massimo, coerente con la
regola di metodo del progetto sulla macchina non quieta. Nessun giro si è
avvicinato a una scadenza (§5.6).

**Che cosa questo autorizza a dire, e che cosa no.** Autorizza a dire che la
macchina a stati di §11.1 — rivendicazione unica per CAS, riconoscimento a
generazione, uscita dei worker su `pool_retire` — regge le tre corse che il
progetto sapeva di dover provare: annullamento durante un `compute()` in corso
(T12), scadenza del `wait` con completamento tardivo (T13), teardown con job in
volo (T15). **Non** autorizza a dire che sia priva di corse: 240 giri su una
macchina scarica esercitano una distribuzione di intrecci, non tutte. Le corse
che dipendono dal thread di callback del driver CUDA — cioè il contesto vero in
cui `submit_hook` e `wait_hook` gireranno — non sono esercitate qui **per
costruzione**, perché qui non c'è nessun driver: le chiama il thread del test.
Questa è la differenza fra P2 e P3, ed è la ragione per cui R14 resta aperto.

---

## 8. Che cosa resta aperto per P3

Nell'ordine in cui conviene affrontarlo.

1. **R2 — la concorrenza reale fra `submit` e `wait` (prima misura di P3, non
   l'ultima).** È la condizione di esistenza dell'intero guadagno, e nel
   prototipo era già andata storta una volta: 339,5 µs contro 253,5 quando il
   `wait` finiva accodato troppo presto. Nulla di ciò che è stato verificato qui
   la tocca: il test host-only chiama i due hook di seguito dallo stesso thread,
   che è il caso in cui la concorrenza **non c'è per definizione**.
2. **`ggml_cuda_mapped_tensor_host_ptr` non è esportata** (verifica n. 6 del
   progetto). Non verificabile in P2 — il fornitore CUDA
   (`moe_cpu_host_memory_cuda.cpp`) non viene compilato qui, per disegno. Resta
   il lavoro di P3 già elencato in §14: aggiungerla alla tabella `strcmp` di
   `ggml-cuda.cu` (~6000-6035). Il proc-address del buffer type,
   `ggml_backend_cuda_mapped_buffer_type_for_device`, c'è già.
3. **R14 — un nodo `wait` già accodato sopravvive al `cancel()` del suo job.**
   Resta aperto e **non è mitigabile dentro l'esecutore**: i nodi host non hanno
   parametri (§12, obbligo 3), quindi l'esecutore non può distinguere il `wait`
   del job vecchio da quello del nuovo. La precondizione dichiarata in §11.1
   (`set_phase` → `quiesce` → `cudaDeviceSynchronize` prima di `rearm()`) va
   **verificata nel chiamante** in P3, non assunta. In P2 è stata esercitata solo
   la parte che l'esecutore controlla: fino a `rearm()` nessun job esce `ok`
   (T7, T12).
4. **R15 — taratura di `ack_timeout_us`.** I 200 ms del progetto restano una
   proposta. Qui il riconoscimento è sempre arrivato con 44× di margine, ma su un
   pool che condivide i core col threadpool del server (R7) il margine sarà
   diverso. Da registrare a ogni scadenza, come dice il progetto: una sola in una
   corsa è un difetto da investigare, non da tollerare.
5. **`max_rows = 3` non è provato**, e resta dichiarato tale (riga 23 di §13,
   lavoro di P5). In P2 è verificato solo che `n_rows` fuori dai limiti sia
   rifiutato (T6).
6. **`ggml.lib` è collegata ma non contribuisce nessun import** (§5.1). Da tenere
   presente quando in P3 si rifà l'elenco delle librerie per il motore, dove la
   situazione sarà diversa.
7. **La motivazione di `/utf-8` nel progetto va corretta** da «chiude un difetto»
   a «chiude un difetto possibile su un'altra macchina» (§5.5). Il flag resta.
8. **`C4324` × 15 resta come avviso**, deliberatamente non silenziato (§3).
9. **Le tre DLL copiate accanto all'eseguibile non sono ignorate da git.**
   `.gitignore` copre `*.exe` (riga 26) e `*.obj` (riga 25), quindi
   `test_esecutore.exe` e i tre `.obj` non compaiono; `ggml.dll`,
   `ggml-base.dll` e `ggml-cpu.dll`, copiate da `build_test.cmd`, sì. Sono
   **artefatti di build della build privata**, non sorgenti, e non vanno
   committate: 1,7 MB che nel repo non servono a nessuno e che invecchiano
   rispetto alla build da cui provengono. Prima del commit di P2: aggiungere
   `*.dll` (o le tre righe specifiche) al `.gitignore`, oppure cancellarle.
   Segnalato qui perché è il genere di cosa che si scopre dopo, quando è già
   nella storia.

---

## 9. Stato finale dei processi

Verificato a fine lavoro:

```
tasklist | findstr test_esecutore   ->  nessun processo
tasklist | findstr llama-server     ->  nessun processo
```

Nessun `llama-server` è mai stato avviato in questa fase. `bin_prod` non è stato
toccato. Il motore non è stato ricompilato.

---

## 10. Voce di registro (bozza)

**Data e fase.** 14 settembre 2026, **P2 — Esecutore CPU, fase di compilazione e
verifica**. Macchina libera, nessuna misura di baseline in corso. Nessun server,
nessuna GPU, nessun commit.

**Ipotesi.** I sorgenti di P2, scritti il 14 settembre senza mai essere
compilati, si compilano con le sole librerie della build privata GGML, e la
macchina a stati di §11.1 — verificata fin qui **per sola lettura** — regge alle
tre prove di corsa che il progetto sapeva di dover fare, ripetutamente e non una
volta sola.

**File toccati** (tutti sotto `docs/porto/p2_esecutore/`, nessun file del motore,
nessun file sotto `Documents\Codex`):

| File | Modifica |
|---|---|
| `src/moe_cpu_executor.h` | dichiarazione di `moe_cpu_wait_backend()` (diagnostica) |
| `src/moe_cpu_executor.cpp` | definizione di `moe_cpu_wait_backend()` (diagnostica) |
| `src/test_esecutore.cpp` | stampa del percorso d'attesa; conteggio degli elementi diversi per T3 e tre controlli `== 0` per T1/T2/T3; stampa dei margini di T12/T13/T15 |
| `cicla_corse.ps1` | **nuovo**: ciclo delle prove di corsa con conteggio, margini e mediana vera |
| `build_test.ps1` | **difetto corretto**: lo stderr innocuo di `vcvarsall` terminava il lanciatore a compilazione riuscita; l'esito e' ora il codice di uscita. Aggiunta la nota che la fase e' stata eseguita |
| `build_test.cmd` | nota aggiornata (fase eseguita) e regola scritta: il file deve restare in **puro ASCII**, perche' `cmd.exe` non lo legge in UTF-8 |
| `PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md` | rimando all'esito in testa; §17.2 corretto: `/utf-8` e' assicurazione, non riparazione |
| `ESITO_COMPILAZIONE_P2_14_SETTEMBRE.md` | **nuovo**: questo documento |
| `log/` | **nuova**: log di build, di test e dei cicli |

**Risultato e limite.** Compila al primo tentativo: zero errori, quindici avvisi
`C4324` voluti (padding da `alignas`), zero `C4819`. La batteria da 74 controlli
passa in tutte e sei le configurazioni (rapida, `--full`, `--weights` con i pesi
veri del prototipo; 4 e 6 thread). I cicli delle prove di corsa danno **240 giri
su 240 passati, zero falliti**; contando le corse singole, 250 esecuzioni e
18 500 controlli senza un fallimento. Le cinque verifiche aperte del progetto
sono chiuse: le tre `.lib` bastano e non serve `Synchronization.lib`
(confermato dal linker, non solo dai commenti); `ggml_quantize_chunk` accetta
IQ2_S con imatrix di soli uno, quindi **il ripiego sui `.bin` non serve**;
`WaitOnAddress` si risolve nativamente, il `Sleep(1)` non è attivo; la parità col
riferimento GGML è **bit a bit**, 540 672 confronti di float con **zero elementi
diversi**; i ritardi iniettati non hanno mai avvicinato una scadenza (margine
peggiore 10× su T13). **Limite.** Tutto questo è host-only: i due hook li chiama
il thread del test, non il thread di callback del driver, quindi la corsa che
conta davvero — `submit` e `wait` accodati sullo stream, R2 — **non è stata
toccata**. 240 giri su una macchina scarica esercitano una distribuzione di
intrecci, non tutte. E `/utf-8`, verificato compatibile, si è rivelato **non
necessario su questa macchina**: resta come assicurazione, non come riparazione.

**Decisione.** Proseguire su P3. Nel codice dell'esecutore nessuna correzione di
correttezza è stata necessaria; l'unico difetto vero stava nel **lanciatore**
`build_test.ps1`, che su PowerShell 5.1 moriva sullo stderr innocuo di
`vcvarsall` a compilazione riuscita, rendendo i due script non equivalenti
(corretto: l'autorità sull'esito è il codice di uscita). Le altre quattro
modifiche sono diagnostiche e servono a rendere
osservabile ciò che il progetto chiedeva di verificare — in tre casi su quattro
il difetto non era nel codice ma nel fatto che il codice non permetteva di
sapere se stesse funzionando per la ragione giusta (percorso d'attesa silenzioso,
parità stampata ma non verificata, scadenze provate col binario invece che col
margine).

**Regressioni aperte.** Nessuna. Restano aperti dal progetto R2 (da misurare per
primo in P3), R14 (da verificare nel chiamante, non mitigabile nell'esecutore),
R15 (taratura), e il punto 6 di §16: `ggml_cuda_mapped_tensor_host_ptr` non è
ancora in tabella, va aggiunta in P3.

**Stato dei processi avviati.** Nessuno. `tasklist` non mostra né
`test_esecutore` né `llama-server`. `bin_prod` non toccato, motore non
ricompilato, nessun commit.

**Prossima azione.** Aprire P3 dalla misura del rischio **R2** — confronto del
tempo di blocco fra `wait` accodato dopo il lavoro GPU e `wait` accodato subito
dopo `submit`, che deve riprodurre il divario 253,5 / 339,5 µs del prototipo.
È la condizione di esistenza dell'intero guadagno e va fatta **prima**
dell'integrazione, non dopo: se la concorrenza non c'è, tutto il resto di P3 è
lavoro speso su una premessa falsa.
