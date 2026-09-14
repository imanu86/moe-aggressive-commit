# P4, seconda cella — Impianto leggero, poi l'estensione a piu' strati

Versione 0.9 (in corso), 14 settembre 2026. Fase **P4** del [piano CPU/GPU](../PIANO_CPU_GPU_14_SETTEMBRE.md).
Parte da [P4, prima cella](../p4_costo/P4_COSTO_MECCANISMO_14_SETTEMBRE.md) — aperture B1, B2, B3 e
difetti 1, 2, 3 — e da [P3](../p3_uno_strato/P3_UNO_STRATO_14_SETTEMBRE.md) §9.
Misure e criteri: [protocollo](../PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md). Decisioni: [registro](../REGISTRO_CPU_GPU_14_SETTEMBRE.md).

Patch incrementale: [`p4_estensione.patch`](p4_estensione.patch), 6 file, diff rispetto
allo stato patchato di P4-costo. Log in [`log/`](log/), preset in
[`../banco_p0/preset_E*_p4.json`](../banco_p0/), generati da
[`genera_preset_p4e.py`](genera_preset_p4e.py).

---

**In una riga:** l'impianto per strato scende da **112,4 a 59,1 µs** (−47%), e quasi tutto
il taglio viene da **un solo intervento** — togliere il nodo host `submit`, che da solo
vale 42,3 µs per strato.

---

## 1. Che cosa e' stato toccato, e che cosa no

| | |
|---|---|
| Copia di lavoro | `D:\ds4_work\p3_work\source` (gia' patchata da P3 e da P4-costo), **6 file** modificati |
| Copia dello stato di partenza | `D:\ds4_work\p4_estensione_base` (i sei file allo stato P4-costo, per il diff incrementale) |
| Build | `D:\ds4_work\p3_work\build`, **una sola** compilazione per tutte le celle, codice 0 al primo tentativo |
| **Non** toccati | `qwen38_clean\bin_prod`, `qwen38_clean\source` e la sua build, il lanciatore quotidiano, il modello, lo snapshot `D:\ds4_work\p0_snapshot_20260914` |
| Commit | nessuno |
| Server | uno alla volta, guardia d'istanza unica superata prima di ogni avvio; nessun processo residuo al termine |

SHA256 dei binari usati da tutte le celle di questa fase:

| file | SHA256 |
|---|---|
| `ggml-cuda.dll` | `D214BE71D7A651FDC3C153289AE0C1E1AAF3413A0781F6700383647BA2C35905` |
| `llama.dll` | `B0BFFDE7C75AADA2E7BA2077FD37A4605C69862548EC1E75B7906CC1F06BCF04` |
| `llama-server.exe` | `837F500E86AEC6110CAB9ACFFD8064B0931F58938E4495FA09DB34C926CF36C2` |
| `llama-server-impl.dll` | `D1DEE985999BCBA0C1E5694BC7FE58F84E1ABF4CA3251146F0740464FA7012C3` |

Le opzioni nuove e il default cambiato:

| variabile | valori | default | che cosa fa |
|---|---|---|---|
| `LLAMA_MOE_CPU_FUSE` | 0/1 | **1** | **un** nodo host per strato invece di due |
| `LLAMA_MOE_CPU_GUARD_LIGHT` | 0/1 | **1** | la guardia del merge non legge piu' `y` sul PCIe |
| `LLAMA_MOE_CPU_AFFINITY` | `auto`/`first`/maschera/elenco | **auto** | dove si appoggiano i thread del pool |
| `LLAMA_MOE_CPU_FUSE_SPIN_US` | N | 0 | tetto del giro a vuoto del coordinatore nel modo fuso (0 = finche' la fase e' decode) |
| `LLAMA_MOE_CPU_THREADS` | N | **2** (era 4) | difetto 1 di P4-costo |

La funzione resta **spenta di default** (`LLAMA_MOE_CPU=0`): nessun preset di produzione
la accende. I default qui sopra valgono solo quando qualcuno l'accende.

## 2. Intervento 1 — un nodo host per strato

### 2.1 La fusione LETTERALE non esiste, e il motivo e' l'ordine di stream

L'incarico chiedeva che «il `wait` dello strato L e la `submit` dello strato L+1 diventino
un solo nodo». **Non e' realizzabile**, e vale la pena scriverlo per esteso perche' e' una
proprieta' della disposizione, non un limite dell'implementazione. Sullo stream un
strato e':

```
plan_L, export_L, HOST(submit_L), gather_L, lavoro GPU L, HOST(wait_L), guardia_L, add_L
```

- il `wait` dello strato L deve stare **prima** dell'`add` dello strato L, che e' il nodo
  che consuma `y`;
- la `submit` dello strato L+1 deve stare **dopo** l'`export` dello strato L+1, altrimenti
  pubblica un descrittore stantio (e' la regola gia' scritta in `moe_cpu_job.h`);
- ma `add_L` viene **prima** di `export_{L+1}`.

Quindi `wait_L < add_L < export_{L+1} < submit_{L+1}`: un solo nodo non puo' stare in due
punti separati da altri nodi. Metterli insieme al posto del `wait` (cioe' «pubblica e poi
attendi») sarebbe peggio: il calcolo CPU verrebbe fatto **dopo** il lavoro GPU dello
strato invece che accanto, e si butterebbe via tutta la concorrenza che il progetto P2
§9.2 ha disposto e che P4-costo §4.2 ha misurato funzionante.

### 2.2 Il risultato si ottiene togliendo l'altro nodo

Il nodo che **non si puo'** togliere e' il `wait`: e' l'unico modo che l'host ha di
ordinare l'`add` dopo la fine del calcolo, finche' non si accetta un'attesa sul
dispositivo (la cella C9, che P4-costo aveva rimandato per il rischio di annullamento).

Il nodo che **si puo'** togliere e' la `submit`, perche' la pubblicazione non ha bisogno
di un thread host: puo' farla il **kernel di export stesso**. La patch aggiunge una quinta
cella ai flag, `publish`, e il kernel di export vi scrive — come ultima cosa, dopo
`__syncthreads()` e `__threadfence_system()` — un numero strettamente crescente preso da
un contatore in VRAM. Il coordinatore del pool, invece di essere svegliato, **si arma da
solo** guardando quella cella.

Il nodo host che resta non attende piu' «il job in volo»: attende un **numero**.

```
   export_L  (scrive descrittore, attivazione, poi publish = n)
   gather_L, lavoro GPU L                    <- il pool calcola qui, in parallelo
   HOST(wait_seq)  : want = publish; attendi seq_done >= want
   guardia_L, add_L
```

### 2.3 Invariante 6 e stallo col replay del graph

**Invariante 6** (nessun mutex, nessuna API CUDA dentro la callback, ritorno in tempo
finito). Il nodo host del modo fuso legge due parole — `flags->publish` in memoria mappata
e `seq_done`, un atomico dell'esecutore — gira a vuoto per `spin_us`, poi blocca su
indirizzo con `WaitOnAddress`, con la stessa scadenza di P3. Non prende nessun lock e non
chiama nessuna API CUDA: e' esattamente il `wait_hook` di P3, scritto su un numero invece
che su `in_flight`.

**Stallo col replay del graph.** Il graph viene catturato una volta e rigiocato per ogni
token (11 catture su 2496 lanci, gli stessi numeri di P3 e P4): i nodi host sono nel graph
e vengono rieseguiti tali e quali. La condizione da evitare e' «il nodo fuso attende un
job che non e' stato sottomesso». E' chiusa da tre proprieta', tutte nel codice:

1. **Il nodo attende un numero, non un job.** `want` viene letto da `flags->publish`, che
   e' scritto dal kernel di export **dello stesso strato**, gia' eseguito per ordine di
   stream. Se questo strato non ha esportato niente — ripiego sul percorso GPU, `n_rows`
   fuori perimetro, bit `export` spento — `publish` porta ancora il numero dello strato
   precedente, che e' gia' concluso: `seq_done >= want` e il nodo **ritorna subito**.
2. **Ogni numero pubblicato viene sempre concluso.** Il kernel di export pubblica anche
   quando il piano e' fallito (scrive `magic = 0` e poi pubblica lo stesso): il pool prende
   il job, lo rifiuta per intestazione non valida e alza comunque `seq_done`. Un piano
   fallito diventa uno **stato** (invariante 7), non un blocco.
3. **Generazione e stato per job restano quelli di P2.** Il coordinatore assegna la
   generazione quando prende in carico la pubblicazione, registra `running`, e conclude
   con `record()` + `publish_flags()` + `seq_done`. Nel modo fuso il coordinatore e' il
   **proprietario unico** dell'esito (`job_claim` nasce gia' suo): la contesa fra
   coordinatore e host che la macchina a stati di P2 doveva arbitrare non esiste, perche'
   non c'e' piu' un secondo nodo host che possa strappare il job.
   Il prezzo dichiarato: **`cancel()` non e' esercitabile** nel modo fuso, e la scadenza
   del nodo host non strappa il job ma registra `timeout` (che contamina, quindi il decode
   fallisce sul controllo di `contaminated()`) e alza il veleno.

**Il costo del modo fuso**, ed e' onesto metterlo qui: nessuno puo' svegliare il
coordinatore, quindi in fase di **decode** gira a vuoto sulla cella `publish`. E' un core
occupato. Fuori dal decode dorme a grana di millisecondo (D09 rispettata). La misura dice
che il giro a vuoto costa meno dei 47 nodi host che toglie — ma e' una misura su questa
macchina e con questa fase, non una legge.

### 2.4 Un'ulteriore riduzione: descritta, non implementata

- **Un nodo ogni N strati.** Non funziona, e il motivo e' lo stesso del §2.1: l'`add` dello
  strato L consuma il contributo CPU **dello strato L**, quindi il `wait` deve stare prima
  di quell'`add`. Raggruppare significherebbe spostare gli `add` dopo la fine del gruppo,
  cioe' sommare il contributo dello strato L al residuo dello strato L+N: non e' la stessa
  aritmetica, e' un'approssimazione.
- **L'attesa sul DISPOSITIVO (la cella C9).** Ora e' il pezzo piu' grosso che resta: il
  nodo host che sopravvive costa 42,3 µs per strato, cioe' **2,0 ms per token** a 47
  strati. La forma piu' semplice non usa `cuStreamWaitValue64` e quindi non ha bisogno di
  nessuna API in callback: la **guardia stessa** gira a vuoto sulla cella `done` in memoria
  mappata (una lettura PCIe in giro, con `clock64()` come scadenza) prima di leggere il
  veleno. Rischi da misurare prima di adottarla: un kernel che gira a vuoto occupa SM e
  blocca lo stream — che e' l'effetto voluto — ma se il pool non pubblica mai, il kernel
  resta appeso e la scadenza deve essere dentro il kernel, non fuori. **Non implementata
  qui**: l'incarico chiede di descriverla, non di aggiungerla senza misura.

## 3. Intervento 2 — la guardia senza lettura PCIe

P4-costo §4.4 aveva attribuito i 15,0 µs per strato della guardia alla lettura del **flag
del veleno** in memoria host mappata, dichiarandolo «ipotesi con un fondamento, non una
misura». **L'ipotesi era sbagliata nell'oggetto**: il flag e' una parola sola, letta da 128
thread sullo stesso indirizzo, cioe' una transazione. Chi costava era il **conteggio dei
non finiti**, che scorre `y` per intero — `n_embd` = 2560 float, 10 KiB — e `y` vive anche
lui in memoria host mappata, quindi era una lettura di 10 KiB **attraverso il PCIe** fatta
da **un solo blocco** di 128 thread.

La correzione non toglie il controllo, gli **cambia lato**: lo fa il pool sul proprio
buffer, in memoria host, dove costa una passata locale, e il suo esito arriva alla guardia
gia' dentro il veleno. Un `y` non finito non diventa mai una somma. Resta sul dispositivo
la sola lettura del veleno.

Le due facce sono esclusive per costruzione (`caps.check_finite = guard_light`): il
controllo non sparisce mai e non viene mai fatto due volte.

## 4. Intervento 3 — thread e affinita'

**Il default passa da 4 a 2** (difetto 1 di P4-costo, +1,72 ms per token di sola contesa).

**Dove gira il thread che accoda alla GPU, misurato e non ipotizzato.** La patch stampa una
volta per corsa il processore logico su cui gira il thread che entra nel decode:

| corsa | processore logico |
|---|---|
| E1, E2, E3, E4 | **10** |
| EV8 | 7 |

La macchina ha 8 core fisici e 16 logici (Ryzen 7 5800X) con enumerazione a coppie, quindi
il logico 10 e' il **core fisico 5** e il logico 7 il core fisico 3. **Questo falsifica in
parte la spiegazione di P4-costo §4.1**, che diceva «fra cui quello su cui gira anche il
thread che accoda il lavoro alla GPU» riferendosi al core 0: il thread osservato non sta
sul core 0, e per giunta **non e' appuntato**, quindi si sposta (due valori diversi in
cinque corse). La contesa misurata da P4 resta vera come fatto; la sua spiegazione
per-core non e' confermata da questa misura e va riscritta come «il pool contende con un
threadpool che gira a `-t 16`, cioe' su tutti i core fisici».

`LLAMA_MOE_CPU_AFFINITY=auto` prende gli **ultimi** core fisici (logici 15 e 13 con due
thread, cioe' i core fisici 7 e 6): non e' una scelta contro il core 0, e' una scelta
contro il core 5 e contro i core bassi, dove finiscono per prime le code del sistema.
`first` riproduce la disposizione di P3 (logici 0,2,4,6).

## 5. Parte A — le misure dell'impianto

Scala **amplificata**: lo stesso impianto su **47 strati** con `cpu_max=0`. Nessuna route
viene deviata, `y` resta zero, **l'uscita del modello non cambia** — e infatti le impronte
restano identiche a E0 in tutte e quattro le celle, cioe' l'oracolo funziona anche qui.
Profilo `fumo`, 1396 token, `LLAMA_MOE_CPU_REPORT=0`.

| cella | configurazione | ms/token | Δ sul passo prima | **per strato** |
|---|---|---:|---:|---:|
| **E0** | ibrido spento — riferimento | **42,213** | — | — |
| **E1** | impianto di P3: due nodi host, guardia pesante, 4 thread sui primi core | **47,494** | +5,281 su E0 | **112,4 µs** |
| **E2** | **intervento 1**: un nodo host per strato | **45,506** | **−1,988** | **−42,3 µs** |
| **E3** | **intervento 2**: guardia senza lettura PCIe di `y` | **44,957** | **−0,549** | **−11,7 µs** |
| **E4** | **intervento 3**: 2 thread sugli ultimi core fisici | **44,993** | +0,036 | +0,8 µs |
| | **impianto leggero** | | **+2,780 su E0** | **59,1 µs** |

E1 riproduce la cella C15 di P4-costo (47,501 ms/token) a **0,007 ms** di distanza: la
scala amplificata e' ripetibile fra due build diverse, non solo fra due repliche.

Letture:

1. **Il nodo host `submit` valeva 42,3 µs per strato**, cioe' il 38% dell'intero impianto e
   il 71% del taglio ottenuto. Combacia con la misura indipendente di P4-costo, dove il
   **primo** nodo host (C14 − C13) valeva 41,9 µs.
2. **La guardia valeva 11,7 µs di lettura PCIe** sui 15,0 misurati da P4-costo. I 3,3 che
   restano sono il lancio del kernel e la lettura del veleno, che non si tolgono.
3. **Thread e affinita' non si vedono a `cpu_max=0`, ed e' cio' che devono fare**: con zero
   route CPU il pool non calcola, quindi non contende. +0,036 ms e' dentro il pavimento di
   rumore (±0,03) dichiarato da P4-costo. Il valore dell'intervento 3 si legge nella parte
   B, dove il pool calcola davvero. Va notato che in E2-E4 il coordinatore **gira a vuoto**
   per tutta la fase di decode (§2.3) e questo non costa nulla di misurabile: il modo fuso
   paga il proprio giro a vuoto e resta in guadagno di 1,988 ms.

<!-- SEGNAPOSTO: PARTE B -->

## Appendice — file toccati

| file | che cosa cambia |
|---|---|
| `ggml/include/moe_cpu_job.h` | quinta cella dei flag, `publish`, e la regola d'ordine del modo fuso |
| `ggml/src/ggml-cuda/moe-demand.cuh` | opzioni `FUSE`/`GUARD_LIGHT`, contatore di pubblicazione in VRAM, pubblicazione nel kernel di export, guardia leggera, **registro di piu' strati** (`cpu_groups`, `pending_cpu_group`), contatori aggregati con i byte risparmiati, avviso del prefill silenziato |
| `src/moe_cpu_executor.h` | `caps.fuse`, `caps.fuse_spin_us`, `caps.check_finite`, `caps.affinity_mode/mask`, `wait_seq_hook`, `nonfinite()`, `affinity_description()` |
| `src/moe_cpu_executor.cpp` | coordinatore del modo fuso, nodo host `wait_seq_hook`, controllo dei non finiti in memoria host, affinita' configurabile |
| `src/llama-moecpu.h` | documentazione delle opzioni nuove e del default a 2 thread |
| `src/llama-moecpu.cpp` | lettura delle opzioni, scelta del hook, riga di misura `[P4e]`, processore del thread che accoda alla GPU |

`src/llama-graph.cpp` **non** e' stato toccato: era gia' scritto per strato (`il`), quindi
l'estensione a piu' strati non ha richiesto nulla dal lato del grafo.
