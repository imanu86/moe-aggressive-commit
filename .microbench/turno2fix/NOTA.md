# C1 — preservazione fra richieste consecutive

## Esito

`turno2fix.patch` è una patch opt-in per il guasto «ogni richiesta dopo la
prima fallisce». Non modifica i sorgenti presenti nel working tree: sposta
effettivamente la preservazione davanti a qualunque lavoro della richiesta
quando `DS4_CUDA_PRESERVE_ACROSS_REQUESTS=1`, quindi non dipende dal fatto che
la richiesta sia il secondo turno della stessa conversazione. Il valore
assente, vuoto, `0` o diverso esattamente da `1` lascia la cura disattivata.

La patch tocca soltanto `ds4-p4a/ds4.c` e `ds4-p4a/ds4_cuda.cu`; non tocca
allocatore di range, transiente/deadline, host-pin, nextnfix, indexerzc o
ADMIT/hot-reserve.

## Meccanica della cura

1. Subito dopo `ds4_gpu_dynamic_arena_request_begin()` (`ds4.c:23800`) e
   prima sia del loop token-per-token (`:23845`) sia del prefill freddo
   (`:23874`), `ds4_session_sync()` invoca il preservatore già esistente con
   `suffix_tokens=0`. Lo zero significa «nessun token della nuova richiesta è
   stato ancora consumato».
2. Il preservatore mantiene l'ABI booleana: `0` è errore, `1` è no-op/priming,
   mentre il nuovo valore vero `2` segnala a `ds4.c` che lo snapshot precedente
   è stato realmente rivalidato e legato alla nuova request. Solo in
   quest'ultimo caso vengono saltati i reset/finalize successivi; la prima
   richiesta continua quindi a imparare e pubblicare normalmente.
3. Al confine, la preservazione rende obbligatorio
   `cuda_moe_route_worker_drain_completed("request-boundary")` anche fuori dal
   solo caso G133 shared. Dopo il drain, il ramo opt-in evita
   `cuda_moe_tiering_report_and_reset()` (`ds4_cuda.cu:33642-33647`) e azzera
   soltanto `g_iq1_promotion.request_used`, che è un throttle realmente
   request-local.
4. A flag spento, la chiamata storica dopo il loop corto resta nella stessa
   posizione e i reset storici vengono eseguiti nello stesso ordine. Le nuove
   letture di ambiente non stampano nulla: output numerico byte-per-byte e
   stderr restano quelli correnti.

## Perché non viene pubblicata una mappa nuova

La patch non chiama né begin né publish dell'arena. Riusa il preservatore
`ds4_gpu_dynamic_arena_observer_preserve_short_suffix()` (`ds4_cuda.cu:16688`),
che ricostruisce soltanto la candidate metadata dalla mappa `active`
autorevole:

- accetta binding `READY` con lo stesso snapshot e la stessa coppia
  slot/content-generation, senza txn, senza blocco e con cardinalità residente
  invariata (`:16717-16738`);
- per dual-sparse richiede ready/non-staged, entrambe le generation uguali,
  cardinalità e FNV della candidate uguali (`:16740-16750`);
- in caso contrario pubblica zero, incrementa il fatal counter e chiude il
  percorso compose (`:16753-16765`);
- dopo l'applicazione della mask ricontrolla snapshot generation e residenza
  (`:16769-16777`).

La patch non cambia nessuno di questi controlli. Cambia soltanto il momento
della chiamata e usa `2` per distinguere, lato chiamante, la preservazione
avvenuta dal no-op della richiesta di priming.

## Stato minimo che deve sopravvivere

Il minimo sicuro non è un sottoinsieme copiato alla cieca, ma l'autorità di
tiering già accoppiata alle generation dei suoi slot. Restano quindi nello
stesso oggetto:

- per ogni entry: `state`, `ram_slot`, `ram_generation`,
  `vram_eligible_after_call`, flag 2-bit/promotion, `frequency`, `last_call`,
  `mass`, `last_weight` e advisory G133 heat/streak;
- l'identità che rende interpretabili le entry: `snapshot_generation`,
  cardinalità del backing, slot riservati, `call_tick`, epoche/budget/knock
  della policy e configurazione;
- i contatori cumulativi, che restano cumulativi e non autorizzano da soli
  alcuna lettura.

Non sopravvive un credito request-local: `g_iq1_promotion.request_used` torna a
zero. L'epoch request continua invece ad avanzare normalmente
(`ds4_cuda.cu:16650-16655`) e l'observer viene riarmato con la nuova
`observer_generation` (`:16657`, `:15792-15805`). Conservare insieme authority
e generation evita di fabbricare una residenza slegata dagli slot reali.

## Invariante anti-byte-stale

Prima della conservazione il route worker precedente deve essere drenato. Da
quel punto, un esperto è leggibile soltanto se resta vera la tupla:

`(snapshot_generation, binding.slot, binding.slot_generation, READY,
slot.layer, slot.expert, slot.content_generation)`.

`cuda_dynamic_arena_binding_valid()` confronta tutta la tupla
(`ds4_cuda.cu:9833-9849`) e ogni copia la rivalida immediatamente prima di
prendere i puntatori (`:9911-9920`). Uno sfratto/riuso cambia stato,
layer/expert o `content_generation`: la vecchia binding viene quindi rifiutata
come miss/fail-closed, mai letta come byte dell'esperto nuovo. Anche il
preservatore conta soltanto binding che passano la stessa funzione. Questo è
l'invariante che impedisce alla richiesta N di leggere byte pubblicati per
N-1 e nel frattempo sfrattati.

## Collaudo richiesto

Non eseguito qui per il vincolo esplicito di non compilare e non avviare
server. Sequenza di accettazione:

1. Applicare con
   `git apply .microbench/turno2fix/turno2fix.patch`, compilare nel normale
   ambiente di collaudo e impostare
   `DS4_CUDA_PRESERVE_ACROSS_REQUESTS=1`.
2. Discriminatore entro 30 s: dopo lo snapshot `1` della prima richiesta, la
   seconda deve emettere una riga
   `result=preserved ... suffix_tokens=0 ... observer_generation=2 ... published_snapshot_generation=1`
   da `ds4_cuda.cu:16780-16797`. È vietata la coppia osservata oggi
   `observer_generation=2,published_snapshot_generation=0`.
3. Eseguire quattro richieste consecutive sullo stesso processo server, due
   famiglie per due turni, con cap piccoli sul precedente riuscito
   (128 token al primo turno, 32 al secondo; non 4000). Per tutte e quattro:
   HTTP riuscito, `choices[0].finish_reason != "error"` e
   `usage.completion_tokens > 0`.
4. Controllo negativo: con flag assente ripetere un caso deterministico e
   confrontare raw response e stderr con il binario baseline. Devono essere
   identici byte-per-byte; non deve comparire alcuna nuova riga.

Il timeout del primo turno STORM e la falla OVERLAPPED/pending discussa in
`adv_turno2` restano cure separate e non sono state modificate. Il gate
funzionale a quattro richieste deve quindi essere eseguito sul baseline in cui
anche quella cura separata è stata accettata; C1 si attribuisce con il
discriminatore generation `2 -> 1`.

## Verifiche statiche e provenienza

- `git apply --check --verbose .microbench/turno2fix/turno2fix.patch`: **OK**
  sul working tree corrente, inclusi i sorgenti untracked.
- Stat patch: 2 file, 68 inserimenti, 17 rimozioni.
- SHA-256 `ds4-p4a/ds4.c` prima:
  `2d97991e6037c434e484ab6a8c8cc2a364e7cf69aa403ad5e6baa815d3dd6e5c`.
- SHA-256 `ds4-p4a/ds4.c` dopo:
  `2d97991e6037c434e484ab6a8c8cc2a364e7cf69aa403ad5e6baa815d3dd6e5c`.
- SHA-256 `ds4-p4a/ds4_cuda.cu` prima:
  `f96582e583ef531dd4102b38134223ff674e77c2b0a37bfd64f3509cbc4e8f37`.
- SHA-256 `ds4-p4a/ds4_cuda.cu` dopo:
  `f96582e583ef531dd4102b38134223ff674e77c2b0a37bfd64f3509cbc4e8f37`.
- SHA-256 `turno2fix.patch`:
  `5cefaf93a664f7c02d73d6bb08de22e06822ed75844ad0792ef7a73ac44cedbc`.

Gli hash sorgente prima/dopo coincidono perché il deliverable è una patch non
applicata, come richiesto. Non è stata eseguita alcuna compilazione né avviato
alcun server.
