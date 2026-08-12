# Diagnosi della tempesta di sfratti

## Verdetto

Il meccanismo non è un reset del driver, un contatore LRU corrotto o un ciclo
`for (;;)` che resta bloccato dentro una singola allocazione. È un **LRU ciclico
di capacità, reso bistabile dal percorso pool/riserve**:

1. Un token percorre tutti i layer e richiede in ordine praticamente lo stesso
   insieme di pesi backbone (`ds4-p4a/ds4.c:15576-15602`; l'output head aggiunge
   le richieste finali a `ds4-p4a/ds4.c:15605-15613`). Le proiezioni
   dell'indexer sono anch'esse richieste nel percorso del layer
   (`ds4-p4a/ds4.c:14004-14043`).
2. Ogni miss arriva a `cuda_model_range_ptr`, che prova la fd-cache
   (`ds4-p4a/ds4_cuda.cu:4345-4383`), poi a
   `cuda_model_stream_alloc` (`ds4-p4a/ds4_cuda.cu:9084-9103`).
3. L'allocator applica 2048 MiB alle richieste normali
   (`ds4-p4a/ds4_cuda.cu:8325-8333`, `ds4-p4a/ds4_cuda.cu:8971-8974`,
   `ds4-p4a/ds4_cuda.cu:8992-8997`), ma applica la riserva hot da 256 MiB
   **solo** quando `what == "indexer_f16"`
   (`ds4-p4a/ds4_cuda.cu:9094-9103`). Tutti gli altri pesi non-MoE sono
   classificati `pinned/backbone`, ma non ricevono la riserva hot
   (`ds4-p4a/ds4_cuda.cu:9094-9096`, `ds4-p4a/ds4_cuda.cu:9172-9175`).
4. Esiste però una seconda via di ammissione: un buffer pronto, della stessa
   taglia, viene restituito dal pool **prima** di `cudaMemGetInfo` e prima del
   test della riserva (`ds4-p4a/ds4_cuda.cu:8975-8977`). Questa via scavalca
   entrambe le soglie.
5. Se quel riuso esatto non è disponibile all'ingresso della funzione, sotto
   soglia l'allocator libera un solo buffer parcheggiato
   (`ds4-p4a/ds4_cuda.cu:8998-8999`) oppure sfratta una sola vittima
   (`ds4-p4a/ds4_cuda.cu:9000-9002`, `ds4-p4a/ds4_cuda.cu:9064-9076`).
   Lo sfratto non restituisce VRAM: registra un evento e sposta il buffer nel
   pool (`ds4-p4a/ds4_cuda.cu:8844-8857`,
   `ds4-p4a/ds4_cuda.cu:8893-8910`). Al giro successivo il codice torna a
   `cudaMemGetInfo`, ma **non riprova `cuda_stream_pool_take`**, perché il
   `take` è fuori dal `for (;;)`; quindi il buffer appena sfrattato viene
   normalmente passato a `cuda_stream_pool_reclaim`, sincronizzato se
   necessario e realmente liberato (`ds4-p4a/ds4_cuda.cu:8875-8890`,
   `ds4-p4a/ds4_cuda.cu:8975-9001`).

Questa asimmetria crea due stati raggiungibili con la stessa configurazione.
Nel ramo sano, la storia iniziale del pool/delle residenze consente abbastanza
riusi senza nuova `cudaMalloc` da oltrepassare la soglia di ammissione e portare
il working set vivo a circa **6,87 GiB**. Da quel momento sono tutti hit:
`cuda_model_range_ptr` aggiorna solo il tick e restituisce il puntatore
(`ds4-p4a/ds4_cuda.cu:4345-4357`), quindi il ciclo di reclaim non viene più
chiamato. Nel ramo malato, reclaim e nuova `cudaMalloc` mantengono
`g_model_range_bytes` a circa **6,63 GiB**, circa 0,24 GiB sotto il working set
osservato. Il token finisce dopo avere sfrattato la sua testa per caricarne la
coda; il token successivo richiede subito la testa, sfratta la coda e ripete
indefinitamente. Il commento del probe descrive correttamente l'oscillazione
intra-token `evict-to-pool -> reclaim -> malloc`
(`ds4-p4a/ds4_cuda.cu:121-145`).

La riga colpevole primaria è quindi
**`ds4-p4a/ds4_cuda.cu:8975-8977`**: il riuso del pool è fuori dal ciclo ed è
anche una via di ammissione che non applica la stessa policy della
`cudaMalloc`. Le righe che trasformano questa asimmetria in una rotazione
perpetua sono `ds4-p4a/ds4_cuda.cu:8998-9002` e
`ds4-p4a/ds4_cuda.cu:9072-9076`. La riserva hot applicata al solo indexer
(`ds4-p4a/ds4_cuda.cu:9094-9103`) rende il confine ancora più stretto e
dipendente dall'ordine.

Il trigger iniziale esatto (quale evento/bucket fosse pronto nel primo giro)
non è registrato nei run forniti: il probe che stampa
`stream_pool_bytes_at_min`, `model_range_bytes_at_min` e
`stream_pool_bytes_max` è opt-in (`ds4-p4a/ds4_cuda.cu:171-175`,
`ds4-p4a/ds4_cuda.cu:31273-31309`). I log provano però il ramo raggiunto e il
suo tetto; non serve attribuirlo a stato esterno persistente.

## Prova dai contatori

Il primo token è di popolamento in entrambi i mondi, quindi il solo numero di
sfratti del token 1 non discrimina:

| run | token 1 | token 2 | token 3 | stato del contatore `g_model_range_bytes` |
|---|---:|---:|---:|---|
| `FD3_controllo` | 938 sfratti | 1094 | 1136 | chiude il token 1 a 6,63 GiB e il token 2 riparte subito con miss/sfratti (`D:\ds4_work\lane_ab\runs\FD3_controllo\server.stderr.log:3270-3290`, confine token a `:3272`) |
| `X_fd0bis` sano | 928 | 0 | 0 | arriva a 6,87 GiB entro il token 1; nel token 2 restano solo 41 richieste da 0,00 MiB e nessuno sfratto (`D:\ds4_work\lane_ab\runs\X_fd0bis\server.stderr.log:3185-3239`) |
| `X_purga1` sano | 923 | 681 | 0 | chiude il token 1 a 6,77 GiB, completa l'assestamento a 6,87 nel token 2 e dal token 3 non sfratta (`D:\ds4_work\lane_ab\runs\X_purga1\server.stderr.log:3249-3269`, confini a `:3251`, `:4671`, `:4673`) |
| `X_izc1`, variante 600/token | 956 | 971 | 69 | raggiunge 6,87 GiB al token 3, resta fermo ai token 4-5, poi riapre il ciclo al token 6; i confini iniziali sono `D:\ds4_work\lane_ab\runs\X_izc1\server.stderr.log:3177`, `:5167`, `:5316` |
| `FD1_shared220` sano | 0 | 0 | 0 | nessun nuovo sfratto dopo `decode-start`; il totale resta 243 (`D:\ds4_work\lane_ab\runs\FD1_shared220\server.stderr.log:1523`, `:1731`, `:1741`, `:1743`, `:6760`) |
| `FD2_sharedded` sano | 0 | 0 | 0 | nessun nuovo sfratto dopo `decode-start`; il totale resta 289 (`D:\ds4_work\lane_ab\runs\FD2_sharedded\server.stderr.log:1571`, `:1818`, `:1829`, `:1831`, `:6848`) |

I conteggi sopra sono differenze del contatore verboso
`g_model_evict_count`, incrementato a ogni vittima
(`ds4-p4a/ds4_cuda.cu:9075-9079`), fra due righe `[g130-attrib]`. Il valore
`total ... GiB` stampato dopo ogni caricamento è direttamente
`g_model_range_bytes` (`ds4-p4a/ds4_cuda.cu:9177-9186`).

Nota di riconciliazione: nei file indicati dalla consegna,
`FD1_shared220` non ha 2110 sfratti totali ma 243; il valore 2110 in
`D:\ds4_work\lane_ab\REPORT.md:50` appartiene a `FB1_drain4`, mentre la sezione
`FD1_shared220` riporta 243 a `D:\ds4_work\lane_ab\REPORT.md:139`. Questa
discrepanza nominale non cambia il meccanismo, ma evita di attribuire al run
shared un assestamento avvenuto in un altro braccio.

**Discriminatore più precoce:** la prima separazione universale nei log forniti
è `g_model_range_bytes` **alla fine del token 2**. Le tempeste piene sono ancora
sotto il working set completo (al token 1 chiudono fra 6,63 e 6,69 GiB e poi
ricadono sul plateau di 6,63); anche la variante da 600/token è ancora a circa
6,80 GiB. Entrambi i sani comparabili sono invece a 6,87 GiB entro il token 2:
`X_fd0bis` già dal token 1, `X_purga1` dopo il suo secondo giro. La sola fine
del token 1 non basta a classificare `X_purga1`, perciò anticipare il verdetto
di un token sarebbe un falso positivo. Non sono discriminatori precoci
affidabili né
`vram_free_at_decode_start` né gli sfratti pre-decode: per esempio
`X_purga1` sano parte con 108 sfratti, lo stesso valore di `X_FD3bis` e
`X_FD3ter` malati; i rispettivi stati sono in
`D:\ds4_work\lane_ab\runs\X_purga1\server.stderr.log:1211` e
`D:\ds4_work\lane_ab\runs\X_FD3bis\server.stderr.log:1211`.

Il secondo discriminatore, più semplice da usare come guardiano, è il delta
per-token di `g_model_evict_count`/`backbone_reloads` al token 2:
`+1094..1138` nel malato contro `0` in `X_fd0bis`, `+681` e poi zero in
`X_purga1`, e zero subito nei due run shared. Il paging a ~965 MB/s viene dopo:
quando il token 2 sta già rileggendo circa 7 GiB, non è la causa che sceglie il
ramo.

### Byte per sfratto e prova del ping-pong

Tolti i grandi sfratti di startup già presenti alla riga `decode-start`, i sei
run da ~1100/token sfrattano in decode **6,365-6,375 MiB per evento**. Esempio
`FD3_controllo`: dal `decode-start`
(`D:\ds4_work\lane_ab\runs\FD3_controllo\server.stderr.log:1217`) al
`request-end` (`:67548`) ci sono 32.958 sfratti e 220.303.354.160 byte:
6,375 MiB/sfratto. La misura aggregata da ~39,4 GB in due token contiene anche
i primi enormi `tensor-span` di circa 1 GiB
(`D:\ds4_work\lane_ab\runs\FD3_controllo\server.stderr.log:27-30`), perciò
non va divisa ciecamente per il conteggio totale per stimare la granularità
del regime.

`backbone_reloads` è una prova forte che non si stanno semplicemente eliminando
range morti. Allo sfratto l'offset esatto viene inserito in un set
(`ds4-p4a/ds4_cuda.cu:8726-8729`); una reload è contata solo se lo stesso
offset ricompare, e allora viene rimosso dal set
(`ds4-p4a/ds4_cuda.cu:8754-8763`, chiamata a
`ds4-p4a/ds4_cuda.cu:9177-9180`). Nei sei run pieni, sottraendo i valori di
`decode-start`, il rapporto `reloads/evictions` è 0,9994-1,0012. In
`FD3_controllo` il finale è 33.003 reload contro 33.072 sfratti totali e
221.034.407.864 byte ricaricati
(`D:\ds4_work\lane_ab\runs\FD3_controllo\server.stderr.log:67548`).
Poiché il set deduplicherebbe due sfratti dello stesso offset senza reload
intermedia, il rapporto quasi unitario dice precisamente
**sfratto -> nuova richiesta dello stesso offset -> reload**, non perdita
progressiva di un insieme mai più usato.

## Correzione minima proposta (non implementata)

Correzione minima alla riga realmente difettosa:

- portare la ricerca del bucket esatto dentro il `for (;;)` di
  `cuda_model_stream_alloc` e ripeterla dopo
  `cuda_model_range_evict_to_pool`. Sotto pressione, se esiste un buffer della
  taglia richiesta ma il suo evento non è ancora pronto, attendere **quello
  stesso evento e riusare il buffer**, invece di farlo attendere a
  `cuda_stream_pool_reclaim`, liberarlo e rifare una `cudaMalloc`
  (`ds4-p4a/ds4_cuda.cu:8975-8978`,
  `ds4-p4a/ds4_cuda.cu:9075-9076`). È lo stesso wait che il reclaim esegue già
  quando nessun evento è pronto (`ds4-p4a/ds4_cuda.cu:8884-8889`), quindi non
  introduce una sincronizzazione che il ramo malato non paghi già.

Questo rende deterministico il riuso che oggi dipende dallo stato del pool
all'ingresso della funzione e permette al ramo malato di raggiungere lo stesso
working set già dimostrato fisicamente possibile dai run sani. Va mantenuto il
fence-evento: `cuda_stream_pool_take` restituisce già solo buffer il cui evento
è completo (`ds4-p4a/ds4_cuda.cu:8860-8872`).

Come piccola chiusura di policy, nello stesso change va evitato che due vie di
ammissione abbiano limiti diversi: o il pool è conteggiato esplicitamente come
memoria reclaimable nel test della riserva, oppure il chiamante passa
`is_hot` (tutto il backbone) e non il solo predicato `indexer_f16` al parametro
`hot_weight` (`ds4-p4a/ds4_cuda.cu:9094-9103`). La seconda opzione è la
modifica più corta e, in questa configurazione, 256 MiB lasciano oltre il
deficit osservato di ~0,24 GiB; richiede però verificare che il trasporto
transiente degli esperti mantenga il proprio headroom. Il fix essenziale resta
il retry/trasferimento del buffer nel ciclo: elimina la dipendenza dalla storia
anche senza cambiare la quantità configurata di riserva.

Per la verifica futura, il guardiano deve campionare a ogni token almeno
`g_model_range_bytes`, `g_stream_pool_bytes`, delta
`g_model_evict_count`, delta `backbone_reloads` e
`backbone_reload_bytes`. I punti di stampa esistono già nel probe
(`ds4-p4a/ds4_cuda.cu:31273-31309`) e nella riga vram-prio
(`ds4-p4a/ds4_cuda.cu:31407-31423`).

## Ipotesi escluse leggendo il codice

- **Loop locale infinito/non convergente:** escluso. Ogni reclaim rimuove
  esattamente un elemento dal pool e ne decrementa i byte
  (`ds4-p4a/ds4_cuda.cu:8877-8890`); ogni eviction rimuove esattamente un
  range vivo (`ds4-p4a/ds4_cuda.cu:8895-8910`). Una singola chiamata termina
  con `cudaMalloc`, con `NULL` se non ci sono vittime, oppure dopo avere
  esaurito un insieme finito (`ds4-p4a/ds4_cuda.cu:8978-9002`,
  `ds4-p4a/ds4_cuda.cu:9046-9063`). È la successione di chiamate del token a
  non convergere globalmente.

- **Saturazione/azzeramento del tick:** escluso. `g_model_tick` è un
  `uint64_t` inizializzato una volta a zero
  (`ds4-p4a/ds4_cuda.cu:1273`), incrementato su ogni hit
  (`ds4-p4a/ds4_cuda.cu:4350-4356`) e su ogni inserimento
  (`ds4-p4a/ds4_cuda.cu:9172-9175`); nel file non esiste un'altra
  assegnazione. Il calcolo di `tick-4` è protetto dall'underflow
  (`ds4-p4a/ds4_cuda.cu:8781-8788`). A questi conteggi l'overflow a 64 bit è
  irraggiungibile. I range diventano tutti eleggibili perché un giro completo
  produce molto più di quattro tick, non perché il contatore si azzeri:
  il filtro è esattamente `last_used_tick <= floor`
  (`ds4-p4a/ds4_cuda.cu:8790-8803`).

- **Bug audit 01-B2, fallback `streamed=0`: escluso nel tree consegnato e nei
  log.** Il fallback corrente controlla la stessa riserva prima della
  `cudaMalloc` (`ds4-p4a/ds4_cuda.cu:4452-4475`) e inserisce il range con
  `streamed=1`, tick corrente e classificazione pinned coerente
  (`ds4-p4a/ds4_cuda.cu:4503-4515`). Inoltre `PIN EXHAUSTED` viene emesso solo
  con `DS4_CUDA_PIN_BACKBONE=1` (`ds4-p4a/ds4_cuda.cu:9002-9008`,
  `ds4-p4a/ds4_cuda.cu:9046-9060`); i log forniti dichiarano
  `pin_backbone=0` e non contengono né `PIN EXHAUSTED`, né `fallback refused`,
  né righe `CUDA cached` del fallback (esempio
  `D:\ds4_work\lane_ab\runs\FD3_controllo\server.stderr.log:1217`,
  `:67548`). Quindi quel bug restringerebbe il pool in una revisione vecchia,
  ma non spiega questa campagna su questo sorgente.

- **Errore di `cudaMemGetInfo` che scatena mass-eviction:** escluso dal
  controllo esplicito: un errore ritorna `NULL` senza scegliere vittime
  (`ds4-p4a/ds4_cuda.cu:8978-8985`). Le righe finali hanno
  `mem_status=ok`, per esempio
  `D:\ds4_work\lane_ab\runs\FD3_controllo\server.stderr.log:67548`.

- **Reset dei range a ogni token:** escluso. `g_model_ranges`, indice e byte
  vengono azzerati insieme solo da `cuda_model_range_release_all`
  (`ds4-p4a/ds4_cuda.cu:9285-9311`), chiamata nel cleanup o quando cambia la
  mappa del modello (`ds4-p4a/ds4_cuda.cu:9429`,
  `ds4-p4a/ds4_cuda.cu:17564-17573`), non nel decode loop
  (`ds4-p4a/ds4.c:15576-15614`).

- **La riserva da 2048 MiB protegge tutti i consumatori:** falso per
  costruzione, quindi esclusa come garanzia. Protegge soltanto la via
  `cudaMalloc` dello stream allocator
  (`ds4-p4a/ds4_cuda.cu:8971-8997`). Il riuso pool ritorna prima del check
  (`ds4-p4a/ds4_cuda.cu:8975-8977`); l'indexer usa la riserva hot
  (`ds4-p4a/ds4_cuda.cu:9094-9103`); lo slab resident-expert usa una propria
  riserva predefinita di 0,5 GiB
  (`ds4-p4a/ds4_cuda.cu:32649-32660`,
  `ds4-p4a/ds4_cuda.cu:39913-39924`) e poi una `cudaMalloc` diretta
  (`ds4-p4a/ds4_cuda.cu:40103-40115`). Lo slab è anche fuori da
  `g_model_ranges`, perciò `cuda_model_pick_victim` non può sceglierlo
  (`ds4-p4a/ds4_cuda.cu:8350-8359`). Questo spiega perché
  `evict_expert=0` non dimostri assenza di pressione esperti: dimostra soltanto
  assenza di range expert streammati eleggibili nel registro visto dal
  selettore.

Conclusione operativa: **ciò che impedisce l'assestamento è il deficit stabile
di circa 0,24 GiB nel set di range vivi, mantenuto dal percorso
reclaim/free/malloc sotto la riserva normale; la scansione LRU per token
trasforma quel piccolo deficit in ~1.100 sfratti e ~7 GiB di reload a ogni
token.** Il mondo sano non ha più capacità fisica: ha raggiunto, tramite la via
pool che bypassa il check, uno stato residente che il ramo malloc/reclaim non
riesce più a costruire.
