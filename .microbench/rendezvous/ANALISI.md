# Analisi del rendez-vous decode / route worker

## Esito

Snapshot analizzato: `ds4-p4a/ds4_cuda.cu`, SHA-256
`044696c0674c11034bc318fcc8a2b0e1ab5f4d1dcfd51667a2a1bc0747b0c797`
(2026-07-28). I riferimenti di riga sotto appartengono a questo snapshot.

**Tetto teorico del batching esatto: 1 richiesta totale, cioè la richiesta del
layer corrente; 0 layer futuri accodabili in anticipo.**

La route esatta del layer `N+1` dipende dall'attivazione prodotta dal layer
`N`. Un ring o una coda possono sostituire il mailbox singolo, ma al momento in
cui il worker termina `N` non esiste ancora una seconda richiesta esatta da
svuotare. Il batching multi-layer non può quindi ridurre i circa 43 passaggi per
token senza cambiare l'algoritmo (predizione/speculazione delle route) o senza
eliminare il confine fra thread.

Non è stata prodotta `rendezvous.patch`: una patch limitata alla coda o al
"drain prima di dormire" non ridurrebbe il numero di passaggi e il drain
immediato è già il comportamento corrente. Le alternative che riducono davvero
il conteggio richiedono un refactoring dei contratti G73, del mailbox e della
proprietà CUDA; presentare un piccolo diff OFF-default come soluzione sarebbe
fuorviante.

## Struttura attuale della pubblicazione

### 1. Un solo snapshot host-visible

`cuda_moe_route_request` contiene una sola parola di pubblicazione,
`sequence`, seguita dal payload: generazione, layer, conteggi hit/miss, offset,
route selezionate, pesi e slot (`ds4-p4a/ds4_cuda.cu:873-893`).

La cache contiene:

- un solo `route_request_host` e il suo alias device
  `route_request_device` (`ds4-p4a/ds4_cuda.cu:28262-28268`);
- una coppia `route_submitted_sequence` / `route_consumed_sequence` /
  `route_completed_sequence`, con le corrispondenti generazioni
  (`ds4-p4a/ds4_cuda.cu:28282-28290`);
- due soli `route_mailbox[2]` (`ds4-p4a/ds4_cuda.cu:28291`).

I due mailbox non contengono richieste. Ogni slot contiene soltanto
`generation` e `state` (`ds4-p4a/ds4_cuda.cu:929-932`) e protegge la durata
dello staging e dei consumer per due generazioni alternate. Il buffer della
richiesta resta singolo.

Il buffer request viene allocato una sola volta con `cudaHostAllocMapped` e
mappato nel device address space con `cudaHostGetDevicePointer`
(`ds4-p4a/ds4_cuda.cu:37569-37575`). Lo stesso schema è usato per le parole
`ready` e `failed` (`ds4-p4a/ds4_cuda.cu:37555-37568`).

### 2. Il decode impedisce l'overwrite prima del claim

Prima di riusare lo snapshot, `cuda_moe_gpu_resident_routes_begin` legge
sequence e generation precedenti e aspetta che il worker abbia pubblicato la
coppia `route_consumed_*` (`ds4-p4a/ds4_cuda.cu:45172-45201`). Questo rende
esplicita la capacità uno del canale request: il producer può sovrascrivere
soltanto dopo che il consumer ha copiato e reclamato la richiesta precedente.

Il decode genera quindi una nuova `sequence` e una nuova `generation`, sceglie
`route_mailbox[generation & 1]`, verifica che sia riusabile e lo porta in
`GPU_WRITING` (`ds4-p4a/ds4_cuda.cu:45208-45229`).

### 3. La GPU costruisce e pubblica la richiesta

Il decode lancia `moe_resolve_resident_routes_kernel`, passandogli direttamente
`selected`, `weights`, layer, sequence e generation
(`ds4-p4a/ds4_cuda.cu:45237-45269`). Gli atomici
`route_submitted_sequence/generation` vengono aggiornati dopo il lancio
(`ds4-p4a/ds4_cuda.cu:45294-45299`), ma non sono la parola che sveglia il
worker.

Il kernel:

1. legge le route selezionate e consulta la mappa
   `(layer, expert) -> slot` (`ds4-p4a/ds4_cuda.cu:25569-25598`);
2. scrive tutto il payload della request (`ds4-p4a/ds4_cuda.cu:25599-25619`);
3. esegue `__threadfence_system()` e scrive per ultima
   `request->sequence` (`ds4-p4a/ds4_cuda.cu:25620-25634`).

Quindi `route_request_host->sequence`, non l'atomico
`route_submitted_sequence`, è la publication word GPU -> worker. Nel caso
all-hit non-G73 il kernel può anche pubblicare direttamente `ready_sequence`;
con G73 `defer_all_hit_ready` vale 1
(`ds4-p4a/ds4_cuda.cu:45264-45269`), perciò anche l'all-hit deve attraversare
il worker.

### 4. Osservazione, barriera, copia e claim del worker

Il worker legge `route_request_host->sequence` in testa al loop. Chiama
`SwitchToThread()` soltanto se la sequence è zero o coincide con quella già
consumata (`ds4-p4a/ds4_cuda.cu:40079-40107`). Quando vede una nuova sequence:

1. data il pickup (`ds4-p4a/ds4_cuda.cu:40110-40118`);
2. esegue `MemoryBarrier()` su Windows;
3. copia l'intera request in uno snapshot locale;
4. ricontrolla sequence e generation;
5. chiama `cuda_moe_route_mailbox_worker_claim`
   (`ds4-p4a/ds4_cuda.cu:40119-40142`).

Il claim non è un semplice indice di coda. Per generation maggiori di uno
richiede che l'evento CUDA del consumer precedente sia già completo, porta il
mailbox precedente da `UPLOAD_ENQUEUED` a `CONSUMER_DONE`, poi porta quello
corrente da `GPU_WRITING` a `WORKER_OWNS` e solo allora pubblica
`route_consumed_sequence/generation`
(`ds4-p4a/ds4_cuda.cu:30762-30824`). Se il consumer precedente non è completo,
il protocollo fallisce chiuso: non c'è una fase "queued, non ancora
claimable".

Questa barriera di lifetime sarebbe un secondo ostacolo a un producer
multi-layer anche se le route future esistessero: il worker non può iniziare
`N+1` finché i kernel consumer di `N` possono ancora usare gli slot condivisi e
lo staging.

### 5. Pubblicazione della completion

Nel ramo all-hit G73 il worker classifica gli outcome, porta il mailbox in
`UPLOAD_ENQUEUED`, pubblica `route_ready_host` fra barriere e infine aggiorna
`route_completed_*` (`ds4-p4a/ds4_cuda.cu:40289-40333`).

Nel ramo miss, dopo I/O/staging/upload, il worker pubblica prima l'eventuale
failure, esegue la barriera host, porta il mailbox in `UPLOAD_ENQUEUED`, scrive
`route_ready_host`, esegue la barriera successiva e pubblica
`route_completed_*` (`ds4-p4a/ds4_cuda.cu:40732-40785`).

Il decode sincronizza/polla il resolver, poi aspetta che
`route_ready_host == sequence` (`ds4-p4a/ds4_cuda.cu:45324-45383`) ed esegue
una barriera dopo l'osservazione (`ds4-p4a/ds4_cuda.cu:45503-45509`).

La vita della generazione non termina al `ready`. Dopo che tutti i consumer
routed/shared FFN del layer sono stati accodati, `ds4.c` chiama
`ds4_gpu_moe_route_consumer_done` (`ds4-p4a/ds4.c:12088-12093`); la funzione
registra un evento sul default stream e ne pubblica la generation
(`ds4-p4a/ds4_cuda.cu:31007-31045`). Il claim della generazione successiva
controlla proprio quell'evento.

## Dipendenza che impedisce il batch multi-layer

Le route non sono metadati noti dal modello o dal solo indice di layer. Per
ogni layer, `router_selected` e `router_weights` sono il risultato del router
applicato all'attivazione corrente:

- l'input FFN viene costruito da `after_attn_hc`, che a sua volta usa
  `g->cur_hc` (`ds4-p4a/ds4.c:11724-11773`);
- il matmul del router produce i logits da `g->ffn_norm`, poi
  `ds4_gpu_router_select_tensor` produce top-k e pesi
  (`ds4-p4a/ds4.c:11784-11797`);
- quegli stessi tensori sono passati al MoE
  (`ds4-p4a/ds4.c:11955-11978`) e infine al resolver CUDA
  (`ds4-p4a/ds4_cuda.cu:45244-45269`).

Nel loop dei layer, la chiamata del layer `N` deve terminare prima che
`g->cur_hc` venga sostituito con `g->after_ffn_hc`; soltanto allora comincia
`N+1` (`ds4-p4a/ds4.c:13074-13090`). Quindi:

```text
route[N]
  -> pesi/compute MoE[N]
  -> after_ffn_hc[N]
  -> attenzione + norm[N+1]
  -> logits router[N+1]
  -> route[N+1]
```

Con lo split path, `begin()` anticipa il servizio miss rispetto ad alcuni
kernel hit dello stesso layer (`ds4-p4a/ds4_cuda.cu:45900-45910`), ma
`finish()` resta nello stesso `routed_moe_launch_impl` prima della chiusura del
layer (`ds4-p4a/ds4_cuda.cu:47073-47096`). È overlap intra-layer, non
look-ahead inter-layer.

Conoscere in anticipo gli indirizzi dei tensori di `N+1` non basta: i loro
valori non esistono ancora. Accodare un kernel GPU dipendente è possibile
perché lo stream ordina dati che resteranno sul device; accodare il lavoro del
route worker richiede invece che la GPU abbia già materializzato e pubblicato
gli ID esatti che determinano hit, miss e I/O host.

Per questo il confronto con le circa 104 dispatch Metal in un command buffer
non si trasferisce direttamente: Metal ammortizza l'encoding/submit di comandi
GPU con dipendenze device-side; qui il confine critico è un risultato
device-side che decide lavoro host-side data-dependent.

## Tetto teorico dichiarato

Per route esatte e per un singolo token decode:

| Grandezza | Tetto |
|---|---:|
| Richieste esatte materializzate simultaneamente dal grafo attuale | 1 |
| Layer futuri accodabili mentre si serve il corrente | 0 |
| Riduzione ottenibile con il solo passaggio mailbox singolo -> ring | 0 rendez-vous/token |
| Rendez-vous minimi con l'attuale separazione decode/worker | uno per layer che richiede servizio host |

Il ring migliorerebbe la capacità soltanto in un workload che produce più
request indipendenti (per esempio token/layer realmente paralleli). Questo
percorso rifiuta `n_tokens != 1` in
`cuda_moe_gpu_resident_routes_begin` (`ds4-p4a/ds4_cuda.cu:45068-45074`), per
cui quel caso non è il decode misurato.

## Perché il "drain prima di tornare in attesa" non è una patch

Il worker già non esegue uno yield incondizionato dopo un job. Sia il ramo
all-hit sia il ramo miss fanno `continue`; la testa del loop rilegge subito la
publication word (`ds4-p4a/ds4_cuda.cu:40326-40333`,
`ds4-p4a/ds4_cuda.cu:40784-40791`, poi `:40079-40107`). Se una nuova sequence
fosse già pubblicata, verrebbe trattata senza `SwitchToThread()`.

Nella sequenza reale, però, il decode deve ancora eseguire il resto di `N`,
produrre l'attivazione di `N+1`, eseguire il router di `N+1` e far pubblicare la
nuova request dal kernel. Al primo giro dopo il job il worker vede quindi la
vecchia sequence e torna correttamente nel ramo idle. Una coda vuota e un
mailbox vuoto hanno qui lo stesso comportamento.

Questo spiega anche perché una finestra di spin limitata non cambia il numero
di rendez-vous: non crea route future e non rimuove nessun confine
data-dependent.

## Alternative che riducono davvero il numero di passaggi

### A. Servizio inline sul thread di decode

Estrarre il corpo per-request del worker in una funzione condivisa e, dietro
un flag come `DS4_CUDA_ROUTE_INLINE_SERVICE=0` di default, invocarla dal decode
dopo che il resolver ha reso visibile la request. Il route thread non
riceverebbe più request in questa modalità.

Tetto: **43 -> 0 passaggi decode/route-worker per token**. Resterebbe una
pubblicazione GPU -> host per layer, perché la dipendenza algoritmica non
scompare.

È l'alternativa più diretta rispetto alla metrica richiesta, ma non è un diff
locale: bisogna preservare context/device CUDA del thread, cancellazione I/O,
deadline, quarantena fail-closed, transizioni mailbox, outcome G73, telemetry,
upload stream e consumer event. Inoltre si perde l'overlap fra decode e I/O.
Va trattata come modifica architetturale e misurata separatamente.

### B. Worker soltanto sui miss; all-hit autorevole sulla GPU

Il kernel possiede già il fast path che pubblica `ready_sequence` sugli
all-hit (`ds4-p4a/ds4_cuda.cu:25620-25627`), ma G73 lo disabilita passando
`defer_all_hit_ready=1` e usa il worker per classificazione/outcome, tiering e
chiusura mailbox (`ds4-p4a/ds4_cuda.cu:40246-40327`).

Una variante OFF-default valida dovrebbe:

1. rendere autorevole il completion GPU per gli all-hit;
2. evitare del tutto la pubblicazione di quella request al route worker, non
   soltanto smettere di aspettarne il `ready`;
3. trasferire o rendere differibili classificazione G73, osservazioni tiering,
   `route_g73_outcomes` e transizioni `consumed/completed`;
4. mantenere l'evento consumer che protegge route pointers e slot.

Tetto: da `L` rendez-vous a `L_miss`; best case 0, worst case invariato se ogni
layer ha almeno un miss. Un semplice flip di `defer_all_hit_ready` non è
corretto: il chiamante G73 controlla la pubblicazione degli outcome del worker
(`ds4-p4a/ds4_cuda.cu:45942-45960`) e il producer successivo aspetta ancora
`route_consumed_*`.

### C. Speculazione delle route

Predire per tutti i layer le route del token corrente usando il token
precedente permetterebbe un batch host, ma non sarebbe la stessa richiesta
esatta. Servirebbe comunque una validazione per layer e un fallback sui
mismatch. Senza un contratto esplicito di predizione, accuratezza e replay non
è una soluzione semanticamente equivalente.

## Raccomandazione

Non implementare un ring multi-layer nel protocollo corrente: aggiunge stati e
superficie di failure senza avere mai più di un elemento producibile.

Se l'obiettivo primario è il numero di handoff, valutare prima l'alternativa A
con un refactoring esplicito e OFF-default. Se l'obiettivo è il critical path e
la telemetria mostra molti all-hit, l'alternativa B può dare un rapporto
rischio/beneficio migliore, ma deve spostare l'intero contratto all-hit G73 e
non soltanto la parola `ready`.
