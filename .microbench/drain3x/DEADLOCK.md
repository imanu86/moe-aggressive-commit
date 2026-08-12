# Fase 1 — autopsia dei due tentativi di drain

## Esito

La causa completa del blocco **non è determinabile con certezza dai due diff e
dal sorgente corrente**. È possibile:

1. provare che entrambi i patch modificavano il binario e il percorso del
   worker anche con `DS4_CUDA_DRAIN_OVERLAP` spento;
2. ricostruire la catena d'attesa visibile;
3. provare che nel sorgente corrente manca un arco necessario per chiamare
   quella catena un deadlock: nessuna operazione accodata su
   `route_upload_stream` attende stream 0, `route_ready_host` o
   `route_consumer_done_event`.

Attribuire i 13,6 s/token a layout, acquire atomici, code placement o a una
specifica lock CUDA sarebbe quindi un'ipotesi, non una diagnosi. In accordo con
il mandato, la consegna si ferma a una patch di sola strumentazione e non
contiene un terzo tentativo di overlap.

Base ispezionata:

```
ds4-p4a/ds4_cuda.cu
SHA-256 5688dcd362deb80fb25a95715a9ef350cbb87c5f9515b56e1d31d041ffa51b4
```

Non sono stati compilati binari e non è stato avviato `ds4_server`.

## Riproduzione statica della non-neutralità

### Tentativo 1

`drain.patch` non aveva un percorso OFF identico:

- inseriva due `cudaEvent_t` e un atomic dentro
  `cuda_moe_expert_cache`, prima degli atomic della mailbox
  (`.microbench/drain/drain.patch:17-40`); il layout condiviso fra decode e
  worker cambiava sempre;
- trasformava il finish ENFORCE bloccante in un helper comune con
  `allow_overlap`; il call site finale passava `allow_overlap=1` anche con il
  flag spento e il test del flag avveniva soltanto dentro
  `cuda_moe_route_upload_overlap_arm`
  (`.microbench/drain/drain.patch:192-254,276-286`);
- il percorso non-ENFORCE chiamava lo stesso helper nuovo prima di ricadere
  sulla `cudaStreamSynchronize`
  (`.microbench/drain/drain.patch:301-313`);
- dopo il drain ENFORCE eseguiva sempre un nuovo load acquire di
  `route_upload_ready_generation`
  (`.microbench/drain/drain.patch:278-289`);
- nel consumer caricava sempre `route_submitted_generation` prima del test del
  flag (`.microbench/drain/drain.patch:329-337`).

Queste modifiche smentiscono la neutralità dichiarata dal primo documento. Non
identificano però, da sole, un ciclo d'attesa.

### Tentativo 2

`drain2.patch` eliminava il cambiamento di layout della cache e non chiamava
l'helper overlap dal ramo OFF, ma non rendeva il binario OFF strutturalmente
identico:

- aggiungeva comunque il sidecar globale
  `g_moe_drain_overlap`, spostando i globali successivi nella BSS
  (`.microbench/drain2/drain2.patch:17-30`);
- aggiungeva un `getenv`, un confronto al fast path di
  `cuda_moe_expert_cache_prepare`, due handle locali e nuovi rami di
  init/release anche con richiesta falsa
  (`.microbench/drain2/drain2.patch:34-158`);
- soprattutto sostituiva entrambi i blocchi di drain con grandi
  `if (!g_moe_drain_overlap.requested) { blocco legacy } else { ... }`.
  Il ramo preso eseguiva le primitive legacy, ma CFG, dimensione e placement di
  `cuda_moe_tiering_enforce_request` e `cuda_moe_route_worker` cambiavano
  comunque (`.microbench/drain2/drain2.patch:238-316,317-481`);
- aggiungeva un ramo runtime al consumer
  (`.microbench/drain2/drain2.patch:482-511`).

Con flag realmente falso, il secondo diff **non** crea eventi upload, non
esegue `cudaEventRecord`, non esegue `cudaStreamWaitEvent` e continua a
chiamare le stesse sync legacy nello stesso ordine sorgente. Restano code
layout, CFG, BSS, lettura dell'ambiente e init/fast-path diversi. Questi fatti
sono sufficienti per dire “non neutro”, ma non per dire quale di essi causi
13,6 secondi né per inventare una lock che il diff non acquisisce.

## Contratto corrente protetto dalla sync

Le righe seguenti sono del file corrente, non patchato.

1. Il resolver GPU pubblica richiesta, sequence e generation da stream 0; il
   decode pubblica poi gli atomic submitted
   (`ds4-p4a/ds4_cuda.cu:46102-46128,46153-46157`).
2. Il worker copia la richiesta mappata e acquisisce lo slot mailbox con CAS
   `GPU_WRITING -> WORKER_OWNS`
   (`ds4-p4a/ds4_cuda.cu:40982-41000` e `31003-31020`).
3. H2D e kernel di publish vengono accodati sullo stream non bloccante
   `route_upload_stream`; nel demand pipeline i due H2D sono a
   `38814-38924` e il publish a `38937-38950`. Il percorso legacy ha H2D a
   `41409-41436` e publish a `41467-41497`.
4. Il finish ENFORCE drena con
   `cuda_g73_finish_launched_copy(route_upload_stream, ...)`
   (`39319-39340`, call site finale `40848-40865`). Il non-ENFORCE usa
   `cudaStreamSynchronize(route_upload_stream)` (`41527-41561`).
5. Solo dopo il drain il worker porta lo slot a
   `UPLOAD_ENQUEUED` (`31023-31041`) e scrive `route_ready_host`
   (`41613-41627`).
6. Il decode, dopo l'eventuale sync dello stream 0
   (`46183-46216`), gira su `route_ready_host`
   (`46221-46362`) e soltanto allora può accodare il compute dipendente.
7. A fine consumo `ds4_gpu_moe_route_consumer_done` registra
   `route_consumer_done_event` su stream 0
   (`31203-31242`). Alla generazione seguente il worker lo controlla con
   `cudaEventQuery` (`30959-31001`) prima di riusare mailbox e buffer.

I quattro aspetti protetti dal confine sono quindi confermati:

- visibilità di H2D e `device_route_ptrs` fra stream non bloccanti;
- commit/rollback dello stato host `LOADING -> VALID` e delle promozioni;
- lifetime di staging, transient buffer, route pointer e slot residenti;
- exactness del transport ledger, chiuso soltanto dopo un drain riuscito.

## Catena d'attesa provata e arco mancante

La catena osservabile è:

```
decode host
  aspetta route_ready_host == sequence             :46242
    ↓
route worker
  può scriverlo soltanto dopo publish_upload       :41616-41625
    ↓
route worker
  aspetta il completamento di route_upload_stream  :39331 oppure :41544
    ↓
GPU upload stream
  H2D -> materialize/publish
```

Questa è una staffetta bloccante, non ancora un ciclo. Per un deadlock serve
anche:

```
GPU upload stream -> qualcosa posseduto/atteso dal decode o da stream 0
```

Nel file corrente quell'arco esplicito non esiste:

- `route_upload_stream` è creato `cudaStreamNonBlocking`
  (`38257-38263`);
- le operazioni route accodate su di esso sono memcpy, kernel di publish e
  record di eventi; non c'è alcun `cudaStreamWaitEvent` su questo stream;
- `route_consumer_done_event` non viene sincronizzato dal worker:
  `cudaEventQuery` a `30973-30990` è non bloccante e, se NotReady, il codice
  fail-closes invece di attendere;
- la CAS della mailbox non gira in attesa: un fallimento porta direttamente a
  `cuda_moe_route_mailbox_fail_closed`;
- il decode non trattiene un mutex della route mentre gira su
  `route_ready_host`.

Esistono attese ulteriori in sottopercorsi (evento del bounce WRAP,
`gpu_join_mutex`, I/O cancellabile, mutex della CPU lane), ma i dati forniti
non mostrano che i 13,6 s siano in uno di quei siti. Assegnare loro la causa
sarebbe arbitrario.

## Cosa manca per inchiodare la causa

Servono dati di una riproduzione del braccio che si blocca, raccolti prima
dell'abort:

1. valore testuale e valore parsato di `DS4_CUDA_DRAIN_OVERLAP` una sola volta
   all'init, insieme all'indirizzo della specializzazione worker selezionata;
2. sito esatto del drain (`tiering-reservation` o
   `route-worker-non-enforce`), sequence, generation e layer;
3. durante il blocco, ogni 250 ms:
   `cudaStreamQuery(route_upload_stream)`, `cudaStreamQuery(0)`,
   `cudaEventQuery(route_consumer_done_event)`, generation associata
   all'evento, stato/generation dello slot mailbox, submitted/consumed/
   completed e i due word host ready/failed;
4. una riga terminale quando il drain completa o raggiunge la deadline.

Interpretazione:

- upload NotReady + stream 0 Success + consumer event Success isola il blocco
  nel tail H2D/publish, senza ciclo host/mailbox;
- upload NotReady + stream 0 NotReady mostra una contesa/scheduling GPU ma non
  ancora una dipendenza: a quel punto serve una timeline Nsight Systems con le
  operazioni dei due stream;
- consumer event NotReady con generation precedente identifica mancato
  rilascio del consumer, ma non spiega da solo il drain corrente perché
  l'upload stream non attende quell'evento;
- flag parsato ON nel presunto controllo OFF o dispatch inatteso chiude invece
  immediatamente l'autopsia come errore di configurazione/selezione binario.

`drain3x.patch` aggiunge soltanto questa diagnostica, selezionata con
`DS4_CUDA_DRAIN_DEADLOCK_DIAG=1` tramite una specializzazione template del
route worker. La specializzazione normale non esegue query o logging nuovi.

