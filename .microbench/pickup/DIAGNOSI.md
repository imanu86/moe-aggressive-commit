# Diagnosi della latenza di pickup del route worker

Snapshot diagnosticato: `ds4-p4a/ds4_cuda.cu`, SHA-256
`b7b2ca4d52cfa8440db147438568c9b1a414cfe7430c60b8ef21cb5e2b510630`
(2026-07-28). Il file era in modifica concorrente; i numeri di riga sotto sono
quelli di questo snapshot e la patch viene mantenuta separata fino a
`GO_APPLY`.

## Meccanismo esatto di attesa

Il route worker è `cuda_moe_route_worker` a
`ds4-p4a/ds4_cuda.cu:39480`. Il suo loop principale legge direttamente la
parola di pubblicazione host-visibile:

- `ds4-p4a/ds4_cuda.cu:39511-39513`: carica
  `cache->route_request_host->sequence` e considera il worker senza lavoro
  quando la sequence è zero oppure è già stata consumata;
- `ds4-p4a/ds4_cuda.cu:39514-39518`: sul ramo Windows chiama
  `SwitchToThread()` **a ogni iterazione**; sugli altri sistemi chiama
  `usleep(0)`;
- `ds4-p4a/ds4_cuda.cu:39521-39528`: quando vede una nuova sequence prende il
  timestamp `wprof_pickup_ns` prima della barrier, della copia della request e
  del claim, quindi il profiler misura davvero il ritardo di osservazione e non
  il lavoro successivo.

Non c'è `Sleep(1)`, condition variable, evento, wait con timeout o `_mm_pause`
in questo loop. Non c'è neppure un passo temporale esplicito di 1 ms:
`SwitchToThread()` cede il resto della time slice a un altro thread pronto sul
processore e poi il worker dipende dalla rischedulazione di Windows. Se non c'è
un thread eleggibile può tornare subito; sotto contesa può invece tenere il
worker fuori CPU fino a una successiva decisione dello scheduler.

## Compatibilità con la misura

La misura implica circa 43 job per token:

`34914 ms / 800 token / 43 job per token = 1,015 ms/job`.

Questo è compatibile con un yield dello scheduler a ogni poll: nei momenti
caldi una pubblicazione avvenuta subito dopo `SwitchToThread()` non viene vista
finché Windows non rischedula il route worker, e una cadenza osservata vicina a
1 ms può quindi emergere dalla contesa/timer resolution/scheduling della
macchina. Non è però un `Sleep(1)` codificato né una garanzia contrattuale di
`SwitchToThread`; il codice spiega la firma e offre il punto corretto da
ottimizzare, ma il valore preciso di 1 ms è una proprietà osservata dello
scheduler sul sistema profilato.

`queue_ms` non isola questo solo fenomeno: come documentato a
`ds4-p4a/ds4_cuda.cu:4236-4238`, comprende anche la latenza dal submit del
resolver GPU al pickup. `pickup_lag_ms`, invece, usa il pickup preso nel punto
sopra e il wait-start del decode.

## Segnale economico per limitare lo spin

Il profiler possiede già `g_workerprof_token_active`:

- `ds4-p4a/ds4_cuda.cu:4678-4685`: i marker begin/end lo impostano con store
  release;
- `ds4-p4a/ds4_cuda.cu:32533-32538` e `:32555-32558`: i marker sono chiamati
  prima degli early return degli altri osservatori;
- `ds4-p4a/ds4_cuda.cu:4481-4488`: il worker lo usa per separare
  `idle_token_ms` da `idle_free_ms`.

Oggi il marker viene aggiornato solo con `DS4_CUDA_WORKER_PROFILE` attivo. La
patch può riusare lo stesso atomico senza armare gli altri osservatori,
aggiornandolo quando è attivo il profiler **oppure**
`DS4_CUDA_WORKER_PICKUP_SPIN_US > 0`. Con flag nuovo a zero resta il gating
attuale e quindi il comportamento di default resta invariato.

## Patch prevista e rischi

Con `DS4_CUDA_WORKER_PICKUP_SPIN_US=N`, nel solo ramo senza nuova sequence e
nel solo intervallo in cui `token_active` è vero, il worker farà polling con
`YieldProcessor()` su Windows (`_mm_pause` su x86) fino a un budget massimo di
N microsecondi per episodio caldo; esaurito il budget tornerà allo stesso
`SwitchToThread()` attuale. Se il token termina, lo spin viene interrotto e il
worker torna subito al yield. Se un token inizia mentre il worker era in idle
libero, l'edge 0->1 arma un nuovo budget.

Rischi:

- durante ciascuna finestra calda il route worker occupa attivamente un
  logical processor; `YieldProcessor/_mm_pause` riduce pressione e consumo
  rispetto a un tight loop puro, ma non rende lo spin gratuito;
- valori troppo alti possono sottrarre CPU al thread di decode o ad altri
  worker, specialmente con oversubscription/SMT, e peggiorare latenza o
  consumo;
- dopo N microsecondi resta il comportamento scheduler-driven corrente, quindi
  il beneficio riguarda le pubblicazioni che arrivano nella finestra calda;
- il default `0` non esegue timer, pause o nuovi load nel loop di attesa e non
  aggiorna `token_active` fuori dal gating già esistente del profiler: è quindi
  il percorso sicuro e identico a oggi.
