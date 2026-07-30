# PINBUDGETFIX3 — neutralità stderr e lifetime del lock NextN

Data: 2026-07-30. La patch `pinbudgetfix3.patch` si applica direttamente al
tree corrente e sostituisce integralmente PINBUDGETFIX2. I soli target della
patch sono `ds4-p4a/ds4.c` e `ds4-p4a/ds4_cuda.cu` (14 hunk, +76/-1).
Non sono stati modificati i sorgenti, non è stato compilato nulla e non è
stato avviato alcun server.

## Gate diagnostico unico

Il gate scelto è:

```text
DS4_CUDA_HOST_PIN_DIAGNOSTICS=1
```

È coerente con il namespace delle variabili esistenti
`DS4_CUDA_HOST_PIN_*`; qualunque valore diverso dalla stringa esatta `1`,
compresa l'assenza della variabile, significa **spento**.

Lo stesso predicato `ds4_hostpin_diagnostics_enabled()` copre esattamente:

1. la riga `[host-pin-summary]` emessa a request-end;
2. le righe `[host-pin]` dei soli kind introdotti dalla patch,
   `dynamic_arena` e `mtp_window`.

Le righe dei kind preesistenti conservano il comportamento del tree corrente.
Il gate non copre e non disattiva mai la contabilità: i tag vengono applicati
sempre, gli alloc/free continuano ad aggiornare i bucket e
`g_hostpin_total_live`, e il tetto opt-in
`DS4_CUDA_HOST_PIN_TOTAL_BUDGET_GB` continua a vedere lo stesso totale.
Il predicato non introduce stato o inizializzazione concorrente: legge
l'ambiente soltanto nei percorsi freddi di allocazione e a request-end.

## Prova statica della neutralità a gate spento

Prima della v2 le allocazioni dell'arena dinamica/Q1 e la registrazione MTP
passavano già attraverso i wrapper del ledger: contribuivano al totale come
`other`, ma `ds4_hostpin_log_alloc()` sopprimeva `other`. La v3 cambia soltanto
il bucket in cui gli stessi byte vengono classificati; byte, chiamata CUDA,
ordine, fallback, esito e totale restano invariati.

Con il gate spento, il nuovo controllo ritorna prima di `fprintf` per entrambi
i nuovi kind e `ds4_hostpin_summary()` ritorna prima di leggere il ledger o
stampare. Pertanto non escono le sole famiglie di righe che la v2 aggiungeva:

```text
ds4: [host-pin] kind=dynamic_arena bytes=...
ds4: [host-pin] kind=mtp_window bytes=...
ds4: [host-pin-summary] phase=request-end ...
```

La prima famiglia comprende sia l'arena Q1 residente (tentativo mapped o
fallback unmapped) sia l'arena dinamica primaria (tentativo mapped o fallback
unmapped). Il reset/assegnamento del contatore NextN e il relativo getter non
contengono `fprintf`. Tutte le altre righe preesistenti ricevono gli stessi
argomenti: in particolare `total_live`, `total_peak`, ammissione al budget e
gli altri campi `hostpin_total` dipendono dal totale, che non cambia.
Ne segue, riga per riga, uno stderr identico al tree corrente quando
`DS4_CUDA_HOST_PIN_DIAGNOSTICS` è spento.

## Contatore NextN non stantio

Resta un solo stato:

```c
g_ds4_nextn_os_locked_bytes
```

Il suo lifetime ora coincide con quello delle mappe dell'engine:

- `ds4_engine_open()` lo azzera subito all'ingresso, prima di ogni ramo che
  possa decidere di non abilitare/eseguire il warmup NextN;
- il warmup pubblica con `= locked`, mai con `+=`, soltanto la somma dei
  payload i cui `VirtualLock`/`mlock` sono riusciti;
- `ds4_engine_close()` lo azzera dopo `model_close(&e->mtp_model)` e
  `model_close(&e->model)`, cioè dopo l'unmap che rimuove implicitamente gli
  OS lock.

Quindi un engine successivo senza warmup NextN osserva zero, non i circa
4,07 GiB dell'engine precedente. `DS4_NEXTN_PIN=0` resta correttamente a zero
grazie al reset di open anche se il warmup ritorna prima del calcolo `locked`.
Non sono stati aggiunti mutex, atomiche o campi di struct.

## Criterio di accettazione aggiornato

Con `DS4_CUDA_HOST_PIN_DIAGNOSTICS=1`, alla configurazione di campagna
`ctx=150000`, la riga request-end deve soddisfare:

```text
cuda_pinned_total_mib =
  other + window + range + indexer_zc + kv_arena + model_stage +
  route_stage + dynamic_arena + mtp_window

combined_mib = cuda_pinned_total_mib + os_locked_total_mib
os_locked_total_mib = nextn_os_lock_mib
```

Valori attesi:

| kind | atteso |
|---|---:|
| `window` | 2048 MiB senza arena dinamica; 0 con arena dinamica ON |
| `dynamic_arena` | 30719,25 MiB con arena dinamica ON |
| `kv_arena` | circa 1979–2162 MiB |
| `model_stage` | 256 MiB |
| `route_stage` | 40,5 MiB |
| `indexer_zc` | 0 oppure circa 346,5 MiB |
| `nextn_os_lock` | 4167,8 MiB = 4,0701 GiB con `DS4_NEXTN_PIN=2` |

La misura NextN corretta è la riga 4 di
`D:\ds4_work\lane_ab\runs\X_nextn_pin2\server.stderr.log`; non è il valore
approssimato di 4270 MiB riportato dalla v2. La conversione usata dal log è
quella del sorgente (`locked / 1048576.0`, `ds4.c:22602-22607` nel tree
corrente). Per i campi stampati a un decimale è ammessa una tolleranza di
pochi MiB; il ledger interno somma byte interi. `mtp_window` resta incluso
nell'identità e vale la dimensione della registrazione MTP effettivamente
viva.

## Perimetro e verifiche

La patch tocca soltanto contabilità e stampa. Non modifica allocatore range,
transiente/`os_file`, deadline, teardown/ledger retire, precheck route worker,
nextnfix, flag CUDA, fallback, ammissione, layout di struct o sincronizzazione
del percorso caldo.

`git apply --check --whitespace=error-all
.microbench/pinbudgetfix3/pinbudgetfix3.patch` è pulito sul tree corrente.
Il post-image è stato prodotto soltanto su copie temporanee interne alla
directory di consegna per calcolare gli hash; le copie sono poi state rimosse.

## SHA-256 prima e dopo

| file | tree corrente | post-image PINBUDGETFIX3 |
|---|---|---|
| `ds4-p4a/ds4.c` | `2d97991e6037c434e484ab6a8c8cc2a364e7cf69aa403ad5e6baa815d3dd6e5c` | `c06d2e136d3cd951a602ecccaedc0825665b4080e77fa8fc6f01bcf43e272fbe` |
| `ds4-p4a/ds4_cuda.cu` | `f96582e583ef531dd4102b38134223ff674e77c2b0a37bfd64f3509cbc4e8f37` | `545b4915613b7ef9a5a49ee789ab619cd38fa80ac38e08ac41725f6955d22f1d` |

SHA-256 di `pinbudgetfix3.patch`:
`f15db6570166917999f0bebe6826a69b4e08aef265d86f6e1516f58134a90e8d`.
