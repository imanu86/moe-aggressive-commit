# B - dispatch e finestra

## 1. Significato dei contatori

- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:1795-1809`, `:2316-2318`): `n_graphs` conta i grafi arrivati con successo in fondo a `ggml_backend_sched_compute_splits` mentre la sonda e' attiva; `n_splits` conta gli split elaborati e anche lo split CPU gia' affidato al worker, contato prima del `continue` a `:2000-2004`.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2039-2189`): `us_ingressi` misura sul thread scheduler l'intero ciclo di preparazione degli input dello split, comprese attese, copie, gather e selezione degli esperti.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:1956-1964`, `:2039-2189`): `us_sync` misura soltanto le `ggml_backend_synchronize` chiamate tramite `sync_profilato`; e' interamente **ANNIDATO** in `us_ingressi`. Le attese su eventi dentro il ciclo degli input contribuiscono a `us_ingressi`, ma non a `us_sync`.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2192-2205`): `us_calc_cpu` e `us_calc_altro` misurano il wall time host dentro `ggml_backend_graph_compute_async`, classificato rispettivamente come backend CPU o non-CPU; per ogni chiamata i due contatori sono mutuamente esclusivi.
- **LETTO NEL CODICE** (`ggml/src/ggml-cpu/ggml-cpu.cpp:170-190`): sul backend CPU la chiamata esegue `ggml_graph_compute` prima di tornare, quindi `us_calc_cpu` comprende il calcolo CPU bloccante effettuato dal thread scheduler.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2254-2297`): `us_dispatch` misura il blocco host che verifica il pattern di overlap e, quando applicabile, accoda le D2H, crea o registra l'evento e spedisce il lavoro al worker; non misura il completamento asincrono delle operazioni pubblicate.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2039-2189`, `:2192-2297`): `us_dispatch` e' **FUORI** da `us_ingressi`; i due intervalli sono **DISGIUNTI** sul thread scheduler.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2528-2550`): `us_sched_sync` misura il wall time host della `ggml_backend_sched_synchronize` finale associata a grafi pendenti, includendo il join difensivo del worker e le synchronize di tutti i backend.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:1956-1964`, `:2528-2550`): `us_sched_sync` e' **DISGIUNTO** da `us_sync`: il primo avvolge la synchronize finale, il secondo e' contato soltanto dentro `us_ingressi`.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2530-2545`): `n_sched_sync` conta le chiamate finali profilate; una chiamata puo' chiudere piu' grafi, quindi la stampa espone `n_sched_sync / n_graphs` come `chiamate/grafo`.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2024-2028`): `us_join` misura soltanto quanto il thread scheduler attende il worker nei join dentro il ciclo degli split; il join di coda a `:2307-2313` resta fuori.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2073-2077`): `n_join_async` conta le copie di ritorno accodate tramite `set_tensor_async`; e' un conteggio, non una durata.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:1809`, `:2546-2548`): `n_graphs_stampa` memorizza il numero cumulativo di grafi all'ultima stampa e permette di emettere il rapporto dopo almeno altri 50 grafi.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:1032-1034`, `:2316-2318`, `:2530-2545`): `sched->profilo_grafi_da_sync` conta i grafi completati ma non ancora associati a una synchronize finale profilata; dopo quella synchronize viene riportato a zero.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2335`): lo scheduler e' allocato con `calloc(1, ...)`, quindi `profilo_grafi_da_sync` parte da zero.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:887-914`): `n_lavori` conta i lavori completati dal worker; `us_attesa_ev` misura l'attesa dell'evento produttore, `us_calcolo` il calcolo CPU del worker e `us_attesa_lav` lo spin o parcheggio fra un lavoro e il successivo.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:887-914`): i tre timer del worker sono disgiunti sul thread worker, ma possono sovrapporsi temporalmente ai timer del thread scheduler.

### Disgiunzione, annidamento e somme

- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2011-2297`, `:2528-2550`): sul solo thread scheduler, `us_join + us_ingressi + us_calc_cpu + us_calc_altro + us_dispatch + us_sched_sync` somma regioni disgiunte e produce un **subtotale host** delle sole regioni nominate.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:1956-1964`, `:2039-2189`): aggiungere anche `us_sync` conta due volte quella durata, perche' `us_sync` e' gia' compreso in `us_ingressi`.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:887-914`): aggiungere al subtotale scheduler anche `us_attesa_ev`, `us_calcolo` e `us_attesa_lav` somma tempi di due thread che possono sovrapporsi.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2299-2313`): anche il subtotale scheduler senza doppio conteggio non e' l'intero wall time, perche' restano fuori bookkeeping, record degli eventi ordinari e join di coda.
- **IPOTESI**: chi somma indiscriminatamente tutte le durate stampate ottiene un aggregato con `us_sync` contato due volte e con sovrapposizioni fra scheduler e worker; quel numero non rappresenta ne' wall time, ne' tempo CPU, ne' tempo GPU e non ha un significato prestazionale diretto.

## 2. Formato della riga nuova

- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:1825-1837`): la prima riga usa esattamente questa stringa di formato C:

```c
"sched-profilo: %lld grafi, %.1f split/grafo, per grafo: ingressi %.3f ms (di cui sync %.3f), calc CPU %.3f ms, calc altri %.3f ms, dispatch %.3f ms, sched-sync %.3f ms (%.3f chiamate/grafo)\n"
```

- **IPOTESI**: esempio concreto non misurato:

```text
sched-profilo: 50 grafi, 35.0 split/grafo, per grafo: ingressi 4.500 ms (di cui sync 2.000), calc CPU 0.800 ms, calc altri 3.000 ms, dispatch 0.200 ms, sched-sync 20.000 ms (1.000 chiamate/grafo)
```

- **IPOTESI**: nell'esempio il tempo non-sync dentro gli ingressi vale `4.500 - 2.000 = 2.500 ms`; il subtotale host disgiunto della prima e della seconda riga, includendo un ipotetico `join (sched) 5.000 ms`, vale `4.500 + 0.800 + 3.000 + 0.200 + 20.000 + 5.000 = 33.500 ms`. I `2.000 ms` di `sync` non si aggiungono di nuovo.

## 3. GPU piu' lenta oppure host che aspetta di piu'

- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2192-2205`, `:2528-2550`): `us_calc_altro` misura la durata host della chiamata di sottomissione al backend, mentre `us_sched_sync` misura la durata host trascorsa nella synchronize finale.
- **LETTO NEL CODICE** (`ggml/src/ggml-cuda/ggml-cuda.cu:4854`, `:4972-4978`): il percorso CUDA puo' terminare con `cudaGraphLaunch` e tornare senza sincronizzare l'esecuzione GPU.
- **LETTO NEL CODICE** (`ggml/src/ggml-cuda/ggml-cuda.cu:3164-3167`): la synchronize del backend CUDA chiama `cudaStreamSynchronize`; il lavoro GPU accodato puo' quindi riemergere nel wall time di `us_sync` o `us_sched_sync`.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2254-2297`, `:2528-2550`): `us_dispatch` e `us_sched_sync` chiudono due buchi della contabilita' host, ma nessuno dei due misura direttamente la durata device.
- **IPOTESI**: **no**, con `us_dispatch` e `us_sched_sync` non si riesce ancora a separare "la GPU ci mette di piu'" da "l'host o il driver aspetta di piu'". Un aumento di `us_sched_sync` e' compatibile con entrambe le cause.
- **LETTO NEL CODICE** (`ggml/src/ggml-cuda/ggml-cuda.cu:6020`): gli eventi CUDA creati oggi dallo scheduler usano `cudaEventDisableTiming` e non forniscono un elapsed time device.
- **IPOTESI**: per decidere servirebbero coppie dedicate di eventi CUDA con timing abilitato, registrate sullo stream prima e dopo il lavoro e lette dopo una synchronize gia' necessaria; con piu' stream servirebbe anche ricostruire la critical path. Un profiler CUDA esterno potrebbe fornire la stessa separazione.

## 4. `LLAMA_OVERLAP_FINESTRA`

- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:1903-1909`, `:1972-1975`): `LLAMA_OVERLAP_FINESTRA` ha default 0, i valori negativi diventano 0 e la leva viene letta soltanto quando l'overlap e' attivo.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2255-2262`, `:2290`): dallo split produttore N il dispatch assegna al worker lo split CPU N+2 e richiede che N+1 sia sul medesimo backend del produttore.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2000-2004`): quando il loop raggiunge lo split CPU N+2 gia' affidato al worker, esegue `continue` prima di calcolare `e_cpu`; quello split non forza il join.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2012-2020`): `e_cpu` resta effettivamente nel ramo `finestra > 0` e forza il join al primo **ulteriore** split CPU, indipendentemente dal valore della finestra.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2016-2020`): sugli split successivi non-CPU, invece, `e_cpu` e' falso e il join dipende realmente dal tetto `split_id > split_spedito + finestra` oppure da una dipendenza vera dal grafo del worker.
- **IPOTESI**: la frase "il successivo split CPU e' sempre tre split dopo" non e' garantita dal codice dello scheduler; richiede il layout di uno specifico grafo o un dump degli split. Il codice garantisce soltanto N+2 per lo split spedito e il join al primo ulteriore split CPU.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2000-2020`): l'affermazione assoluta "la finestra non puo' funzionare cosi' com'e' scritta" e' **FALSA**. `e_cpu` limita la profondita' raggiungibile quando arriva un altro split CPU, ma la finestra puo' far avanzare gli split non-CPU indipendenti che lo precedono.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:803-808`, `:2012-2020`): `e_cpu` e' mantenuto perche' il backend CPU e il suo threadpool devono avere un solo proprietario; rimuoverlo consentirebbe allo scheduler di entrare nel backend CPU mentre il worker lo usa.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2012-2020`): non e' stata applicata alcuna correzione a `LLAMA_OVERLAP_FINESTRA`; la condizione resta quella letta prima della modifica di contabilita' della sonda.
- **LETTO NEL CODICE** (`ggml/src/ggml-backend.cpp:2016-2020`): con `LLAMA_OVERLAP_FINESTRA=0` resta il ramo originale `(split_id > split_spedito || e_cpu)`, quindi il comportamento di default e' invariato.

## Riassunto finale

1. **LETTO NEL CODICE**: `us_dispatch` misura il dispatch host ed e' fuori da `us_ingressi`.
2. **LETTO NEL CODICE**: `us_sched_sync` misura la synchronize finale ed e' disgiunto da `us_sync`.
3. **LETTO NEL CODICE**: `us_sync` e' annidato in `us_ingressi` e non va sommato due volte.
4. **LETTO NEL CODICE**: i timer del worker possono sovrapporsi ai timer dello scheduler.
5. **LETTO NEL CODICE**: la somma corretta dei timer scheduler e' un subtotale host, non tutto il wall time.
6. **LETTO NEL CODICE**: la riga nuova espone dispatch, sched-sync e chiamate finali per grafo.
7. **IPOTESI**: i nuovi timer host non separano durata GPU e attesa host o driver.
8. **IPOTESI**: per separarle servono eventi CUDA con timing o un profiler device.
9. **LETTO NEL CODICE**: `e_cpu` limita la finestra al primo ulteriore split CPU ma non la annulla.
10. **LETTO NEL CODICE**: nessun fix finestra e' stato applicato e il default `FINESTRA=0` resta invariato.
