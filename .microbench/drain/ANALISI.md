# MANDATO A — sovrapposizione del drain H2D al compute

## Perimetro e stato della consegna

- Sorgente ispezionato: `ds4-p4a/ds4_cuda.cu`.
- Blob del file corrente usato come base della diff:
  `e6b61ea0291ad914800640117d2489f637f6624c`.
- La patch è in `drain.patch` ed è stata verificata con
  `git apply --check --verbose .microbench/drain/drain.patch`.
- Il sorgente non è stato modificato. Come richiesto, non è stata eseguita
  alcuna compilazione e non è stato lanciato `ds4_server`.

Le righe sotto sono quelle del file corrente non patchato. Le zone indicate
nel mandato (~37300 e ~38500) si sono spostate: i siti equivalenti sono ora
nelle zone 38600, 39300, 40000 e 40600.

## Dove avviene il drain oggi

Il contatore del profiler interno è `WP_DRAIN_NS`, dichiarato a
`ds4-p4a/ds4_cuda.cu:4268`. Viene stampato come `drain_ms` a
`ds4-p4a/ds4_cuda.cu:4655` e alimentato nei seguenti siti:

1. **Drain finale del percorso tiering ENFORCE**

   - Chiamata misurata:
     `ds4-p4a/ds4_cuda.cu:39996-40007`.
   - La sync vera è dentro
     `cuda_moe_tiering_finish_vram_reservations`, a
     `ds4-p4a/ds4_cuda.cu:38674-38697`, in particolare
     `cuda_g73_finish_launched_copy(cache->route_upload_stream, ...)` a
     `38685-38689`.
   - Dopo la sync gli slot passano `LOADING -> VALID` e le promozioni sono
     committate a `38705-38709`.

   Questo è il sito principale corrispondente alla misura descritta nel
   mandato. Il worker ha già accodato H2D e kernel di pubblicazione sullo
   stream non bloccante, poi aspetta l’intero tail prima di scrivere
   `route_ready_host`.

2. **Drain anticipato ENFORCE prima del fallback SSD transiente**

   - `ds4-p4a/ds4_cuda.cu:39303-39340`, misura a `39322-39334`.
   - Usa la stessa
     `cuda_moe_tiering_finish_vram_reservations` del punto precedente.

   Questo drain non è un semplice rendezvous col compute: chiude o rimborsa
   promozioni già accodate prima di entrare in una lettura SSD potenzialmente
   lenta (`39303-39306`). La patch lo lascia intenzionalmente bloccante.

3. **Drain finale del percorso non-ENFORCE**

   - `cudaStreamSynchronize(cache->route_upload_stream)` a
     `ds4-p4a/ds4_cuda.cu:40683-40687`.
   - Contabilizzazione transport e gestione dell’errore a `40688-40719`.

La documentazione interna del timer conferma che `t_deliver_ms` misura solo
l’enqueue e che il tempo sul bus ricade nel drain
(`ds4-p4a/ds4_cuda.cu:32631-32646`). Il commento del worker descrive inoltre
`WP_DRAIN_NS` come parte del job prima della pubblicazione di
`route_ready_host` (`ds4-p4a/ds4_cuda.cu:4215-4229`).

## Eventi CUDA già esistenti e rilevanti

### Handshake delle route

`cuda_moe_expert_cache` ha già `route_consumer_done_event` a
`ds4-p4a/ds4_cuda.cu:28276-28291`.

- È creato con `cudaEventDisableTiming` a `37645-37651`.
- Il consumer lo registra sullo stream 0 in
  `ds4_gpu_moe_route_consumer_done`, `31007-31046`.
- Prima di prendere la generazione successiva, il worker verifica con
  `cudaEventQuery` che il consumer precedente abbia realmente terminato,
  `30762-30805`.

Questo evento protegge il **riuso dopo il compute**, non la disponibilità
dell’upload prima del compute. Non può quindi essere riutilizzato come evento
“H2D pronto”.

### Eventi di tracing dell’upload

Il decode trace possiede coppie `upload_start[layer]` /
`upload_end[layer]`, tipizzate tramite `cuda_trace_timing_event` a
`ds4-p4a/ds4_cuda.cu:28374-28418` e registrate sullo stream di upload a
`29463-29506`.

Non sono un primitive di sincronizzazione adatta:

- esistono per il tracing e sono usate solo quando il sample è attivo;
- `upload_end` viene registrato nel worker alla fine del job, non costituisce
  oggi il contratto permanente della mailbox;
- riusarli legherebbe la correttezza del serving a una funzione diagnostica
  opzionale.

### Precedenti dello stesso schema nel file

Il file usa già lo schema sicuro “record sullo stream di upload, wait sullo
stream 0”:

- staged KV: `cudaStreamWaitEvent(0, ring.slot_ready[slot], 0)` a
  `ds4-p4a/ds4_cuda.cu:21655-21658` e `21782-21785`;
- wave MoE: evento upload creato a `41455-41460`, registrato sullo stream di
  upload a `41684-41688`, atteso sullo stream 0 a `46564-46569` e
  `46846-46851`;
- Q1 resident upload: record + wait a `44921-44925`.

Gli altri eventi globali (`g_model_stage_event`, eventi KV, reuse event delle
cache, eventi della CPU lane) hanno ownership e buffer differenti e non sono
riutilizzabili per le route.

## Invariante protetto dalla sync bloccante

La sync protegge quattro aspetti distinti.

### 1. Visibilità dei dati e dei puntatori

Le copie H2D sono accodate su `route_upload_stream`, creato
`cudaStreamNonBlocking` a `ds4-p4a/ds4_cuda.cu:37645-37647`. Sullo stesso
stream vengono poi lanciati i kernel che pubblicano
`device_route_ptrs`/`device_slot_by_layer_expert`:

- publish singolo resident a `40616-40629`;
- publish batch a `38186-38220`;
- demand pipeline: copie a `38296-38308` e materialize/publish a
  `38320-38345`;
- publish transiente a `39921-39932`.

I kernel MoE consumer girano sullo stream 0. Poiché lo stream di upload è
non bloccante, non esiste ordine implicito fra i due stream. Oggi l’ordine è:

```
upload stream: H2D -> publish route_ptrs -> stream drain
host:                                      route_ready_host = sequence
stream 0:                                                     kernel consumer
```

Togliere soltanto la sync è scorretto: il consumer potrebbe leggere
`route_ptrs` non ancora pubblicati oppure dereferenziare uno slot mentre la
copia H2D è ancora in corso.

### 2. Stato host degli slot e transazione di promozione

Gli slot sono marcati `CUDA_MOE_CACHE_LOADING` prima della copia
(`ds4-p4a/ds4_cuda.cu:40425`) e diventano `VALID` soltanto dopo il drain
(`40705-40708` nel percorso non-ENFORCE e `38705-38709` in ENFORCE).
Nel tiering ENFORCE lo stesso confine committa o rimborsa budget, victim e
mappe host (`38583-38640`, `38643-38709`).

La variante event-based può pubblicare ottimisticamente il commit finale
perché il worker non può osservare un’altra richiesta finché il consumer
precedente non è terminato. Non può invece saltare il drain su rollback o
prima del drain anticipato: una invalidation con copie ancora in volo
permetterebbe di riusare o liberare memoria ancora posseduta dallo stream.

Per questo la patch arma l’evento soltanto se `ok/commit_on_success` è vero.
In caso di errore di enqueue, fallimento di `cudaEventRecord` o rollback,
ricade sulla sync bloccante corrente.

### 3. Lifetime dei buffer condivisi

`route_host_*`, `route_transient_*`, `device_route_ptrs` e alcuni slot
residenti sono condivisi fra richieste. Il commento zero-copy a
`ds4-p4a/ds4_cuda.cu:39529-39537` documenta il guardiano: il worker non può
servire N+1 finché `route_consumer_done_event` di N non è completo.

Con l’evento upload aggiunto, `route_consumer_done_event` viene registrato
dopo il wait e dopo i kernel consumer sullo stesso stream 0. Quindi prova
anche che:

- l’evento upload della generazione è stato consumato;
- le copie e il publish che lo precedono sono terminati;
- il compute che legge i buffer è terminato;
- lo slot evento può essere riusato.

### 4. Exactness del transport ledger

Il ledger dichiara che gli H2D sono committati solo dopo un drain riuscito
(`ds4-p4a/ds4_cuda.cu:27531-27544`). Una semplice registrazione evento non è
un drain host completato.

La variante minima non introduce una seconda macchina a stati per differire
il commit del ledger: quando l’overlap è armato chiama
`ds4_transport_h2d_batch_invalidate` prima del finish. Se il ledger è acceso,
il report espone quindi `complete=false` invece di contabilizzare falsamente
come completata una copia ancora in volo. Rendere anche il ledger asincrono
richiederebbe conservare il batch per generazione e chiuderlo dopo l’evento
consumer; è lavoro ulteriore, non necessario alla correttezza del serving.

## Forma sicura scelta

La patch aggiunge, solo con `DS4_CUDA_DRAIN_OVERLAP=1`:

1. due eventi `route_upload_ready_event[2]`, uno per parità della generazione
   della mailbox;
2. `route_upload_ready_generation`, che lega esplicitamente l’evento alla
   richiesta e impedisce di attendere un record vecchio;
3. un record sul `route_upload_stream` dopo tutte le H2D e dopo il publish
   finale;
4. un `cudaStreamWaitEvent(0, ready_event, 0)` in
   `cuda_moe_gpu_resident_routes_finish`, dopo che il worker ha pubblicato
   `route_ready_host` ma prima di restituire il controllo ai lanci consumer.

Il nuovo ordine è:

```
upload stream: H2D -> publish route_ptrs -> record ready_event
                                             |
stream 0: hot/hit compute già accodato -> wait event -> miss/dependent compute
host worker:                         publish route_ready senza stream drain
```

Il doppio evento è deliberato. Un solo evento sarebbe oggi probabilmente
protetto dall’handshake consumer, ma associare fisicamente l’evento allo
slot `generation & 1` rende verificabile la stessa regola della mailbox e
impedisce alias accidentali in evoluzioni future.

Con flag assente o diverso da `1`:

- gli eventi non vengono allocati;
- `cuda_moe_route_upload_overlap_arm` non viene chiamata;
- restano le sync correnti;
- il drain anticipato resta sempre sincrono.

## Perché non eventi per-route

Un evento per route non basta, con i kernel attuali, a far partire ciascun
expert separatamente:

- la demand pipeline consolida gate+up e down di tutti i miss in due H2D
  (`38296-38308`);
- `moe_publish_demand_batch_kernel` pubblica il batch come unità;
- i kernel split/miss successivi consumano l’array condiviso
  `device_route_ptrs` e processano il gruppo dei route.

Per ottenere progresso route-per-route servirebbero almeno upload separabili
(più stream o boundary evento fra route), pubblicazione parziale con
generation/valid bit per entry e kernel consumer spezzati per sottoinsieme.
È un rifacimento profondo del serving e della failure atomicity. La variante
per-generazione/per-layer è quindi il minimo sicuro applicabile al codice
corrente.

## Limiti e aspettative di misura

- Il vantaggio massimo è nel percorso split hit/miss: il compute hot/hit già
  accodato sullo stream 0 può avanzare mentre lo stream di upload completa i
  miss. Il compute dipendente non parte prima dei suoi dati: resta dietro
  l’evento del layer.
- Nel percorso non split non esiste compute indipendente sufficiente a
  nascondere tutto il trasferimento; la patch elimina l’attesa host e permette
  l’accodamento, ma il kernel dipendente attenderà comunque l’evento.
- Gli errori sincroni di enqueue/record mantengono il fallback bloccante. Un
  errore CUDA asincrono dopo un record riuscito emergerà sul grafo dipendente;
  l’evento impedisce l’esecuzione anticipata, ma il fallback host non può più
  essere deciso prima di rilasciare la mailbox. Per questo il flag resta
  sperimentale e default 0.
- `drain_ms` nel ramo overlap misurerà il costo di record/armamento, non la
  durata fisica H2D. La durata fisica resta visibile nella finestra GPU
  `upload_gpu_window_ms` del decode trace; il test va giudicato soprattutto su
  latenza token, `worker_wait_ms` e sovrapposizione GPU.
- Nessuna compilazione è stata eseguita per esplicita richiesta. Dopo
  l’applicazione è opportuno verificare prima il controllo con flag 0, poi
  `DS4_CUDA_DRAIN_OVERLAP=1` con e senza
  `DS4_CUDA_G73_ROUTE_IO_QD=4`, controllando errori mailbox/CUDA, latenza per
  token e correttezza numerica.
