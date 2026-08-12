# G132: sostituzione del kernel CPU scalare con il kernel row-parallel

## Esito della lettura

La lettura del mandato e' corretta.

Nel tree corrente il calcolo della lane entra in
`cuda_g132_cpu_lane_forward()` (`ds4-p4a/ds4_cuda.cu:49140` pre-patch).
Gate/up sono calcolati dal ciclo sulle righe a `:49194-49204`; il down dal
ciclo a `:49215-49221`. Ogni ciclo viene eseguito integralmente dal singolo
worker che ha estratto il job a `:49245`: non esiste parallelismo sulle righe.

Il benchmark g29 usa invece:

- `matvec_iq2_xxs_expert_pair_prequant()` a
  `ds4-p4a/ds4.c:12665`, definita a `:4632`, che chiama
  `ds4_parallel_for()` a `:4659`;
- `matvec_q2_k_expert()` a `ds4-p4a/ds4.c:12682`, definita a `:4766`, che
  chiama `ds4_parallel_for()` a `:4788`.

Quindi il confronto 5,75 ms contro 0,97 ms mette effettivamente a confronto
il forward scalare della lane con un kernel diverso, parallelo sulle righe.

## Modifica contenuta in `kernel.patch`

La patch tocca soltanto `ds4-p4a/ds4.c` e
`ds4-p4a/ds4_cuda.cu` quando verra' applicata.

In `ds4.c` espone alla translation unit CUDA tre ingressi C che riusano i
worker matematici gia' esistenti:

- `ds4_g132_quantize_row_q8_K()` (post-patch circa `:4955`) chiama la
  quantizzazione Q8_K gia' usata dal benchmark;
- `ds4_g132_matvec_iq2_xxs_expert_pair_prequant()` (post-patch `:4796`)
  costruisce lo stesso `matvec_iq2_xxs_pair_ctx` e usa
  `matvec_iq2_xxs_pair_worker`;
- `ds4_g132_matvec_q2_k_expert()` (post-patch `:4965`) conserva la semantica
  di `matvec_q2_k_expert`: quantizzazione Q8_K del mid e
  `matvec_q2_k_worker` sul down.

Non viene introdotto un nuovo dot/kernel matematico. Le definizioni scalari
locali CUDA restano nel file come codice non raggiunto dalla lane, ma il
forward non le chiama piu'.

In `ds4_cuda.cu`, il forward post-patch (`:49167`) usa:

1. l'input Q8_K gia' preparato una sola volta per l'intero batch di route;
2. gate/up row-parallel a `:49218`;
3. lo stesso ordine corrente di clamp, SwiGLU e peso:
   `silu(gate) * up * route_weight` per GENERAL, mentre la lane mixed
   mantiene il peso post-down;
4. down Q2_K row-parallel a `:49239`.

Il clamp e' identico: gate ha solo il limite superiore; up ha limite
superiore e inferiore; il clamp e' disabilitato quando `<= 1e-6`.

## Sequenzialita' degli expert e significato di `DS4_G132_CPU_LANE_MAX`

`cuda_g132_cpu_lane_worker_main()` (post-patch `:49252`) e' ora l'unico
orchestratore. Al risveglio reclama tutte le route del layer, quantizza
`host_input` una volta e chiama il forward degli expert in ordine di job.
Un expert deve terminare tutte le passate gate/up, clamp/SwiGLU e down prima
che inizi il successivo.

`worker_count` e' fissato a uno soltanto quando la lane viene inizializzata
(post-patch `:49377`). Il parallelismo effettivo e' dentro il singolo expert:
l'orchestratore piu' gli helper del pool G132 coprono le righe. Il numero di
thread segue lo stesso tetto del pool normale (`DS4_THREADS`, massimo 32 e
default massimo 12).

`DS4_G132_CPU_LANE_MAX` non e' piu' un tetto di expert concorrenti. Rimane,
senza cambiare ammissione o soglie, il massimo numero di route CPU ammissibili
per layer (default 3, clamp strutturale a 8). Quelle route sono eseguite in
sequenza sul pool. Di conseguenza `cpu_wall_ms` cresce approssimativamente
con il numero di route CPU; il bilanciatore esistente confronta ancora il
wall CPU complessivo con il wall GPU e puo' ritirare `target_cpu`, anche fino
a uno. Nessuna modifica e' fatta alla logica di ammissione/residenza.

## Contesa, deadlock e pool scelto

Il pool globale di `ds4.c` non e' multi-submitter. In
`ds4_parallel_for_min_rows()` (`ds4-p4a/ds4.c:788-820`) esiste un solo slot
globale `fn/ctx/n_rows/done`; il mutex viene rilasciato mentre il chiamante
calcola la propria partizione. Un secondo submitter puo' quindi acquisire il
mutex, sovrascrivere contesto e generazione e azzerare `done` prima che il
primo submit sia terminato. Il risultato non e' semplice serializzazione:
sono possibili esecuzione col contesto sbagliato, attesa senza progresso e
deadlock.

Per questo la lane non chiama il pool condiviso dai suoi worker. La patch
aggiunge in `ds4.c` un pool G132 separato (post-patch `:825-944`) con la
stessa partizione per righe. Viene creato soltanto da
`ds4_g132_lane_parallel_init()` (post-patch `:898`) dopo che
`DS4_G132_CPU_LANE=1` ha superato il gate di init, e viene distrutto durante
il release della lane. Il singolo orchestratore e' per costruzione l'unico
submitter di questo pool.

Le letture/staging del runtime non usano questo pool: continuano sui loro
thread/stream esistenti. Non c'e' un lock condiviso con letture, upload o
callback CUDA e quindi non c'e' inversione di priorita' lock-based. Resta
soltanto la normale competizione dello scheduler OS se un altro lavoro CPU
indipendente viene eseguito davvero nello stesso momento; non puo'
corrompere `fn/ctx/done` e non puo' bloccare la lane su un pool posseduto da
quel lavoro.

La scelta del pool separato evita di aggiungere mutex, branch o costi al
normale `ds4_parallel_for()` e quindi non modifica il percorso a lane spenta.

## Telemetria

La riga live `[g132-general-layer]` (post-patch `:50195`) mantiene:

- `cpu_wall_ms`: dal callback di input pronto fino alla fine di tutti gli
  expert CPU sequenziali, inclusa la singola prequantizzazione dell'input;
- `gpu_wall_ms` e le due attese gia' esistenti;
- nuovo `expert_ms`: media del tempo gate/up + clamp/SwiGLU/peso + down per
  expert CPU completato. La prequantizzazione condivisa dell'input e' esclusa,
  come nel benchmark g29; la quantizzazione del mid interna al down e'
  inclusa, come in `matvec_q2_k_expert()`.

`expert_ms` e' aggiunto anche ai summary generale e per-layer (`:49460` e
`:49495`) come media pesata sugli expert CPU, cosi' il confronto diretto e'
con 0,97 ms del bench e 5,75 ms del forward scalare.

## Neutralita' e limiti rispettati

- Il dispatch template `<G73,G132>` non cambia.
- A flag spenti `cuda_g132_cpu_lane_init()` ritorna prima dell'init del pool:
  nessun ramo, thread, lock o submit nuovo nel percorso hot.
- Il percorso Fable/device-side ownership in
  `.microbench/lane_fable/` non e' modificato.
- Nessun Q1/IQ1 e nessuna modifica ad ammissione, residenza, soglie, cache,
  vittime o staging.
- Non sono stati compilati binari, non e' stato avviato `ds4_server` e non
  e' stato toccato `D:\`.

## Verifiche statiche

Eseguite sul tree corrente:

```text
git apply --check --whitespace=error-all .microbench/lane_kernel/kernel.patch
git apply --numstat .microbench/lane_kernel/kernel.patch
```

Esito: applicabile; `200/0` in `ds4-p4a/ds4.c` e `109/45` in
`ds4-p4a/ds4_cuda.cu`.

E' stato inoltre costruito soltanto un postimage temporaneo dentro
`.microbench/lane_kernel/`, usato per verificare gli hash e poi rimosso.
Nessuna compilazione o esecuzione.

## SHA-256

Preimage esatta del tree corrente:

```text
F7104BC315BA25E70F429294675D6EC76F1B81051B5BDED723D2B22385CF6F35  ds4-p4a/ds4.c
5688DCD362DEB80FB25A95715A9EF350CBB87C5F9515B56E1D31D041FFFA51B4  ds4-p4a/ds4_cuda.cu
```

Postimage atteso dopo `git apply`:

```text
3BE7CE5FBBBF83BA5EA33BF73A598E27B10255959C0000B6EECBAA938821E495  ds4-p4a/ds4.c
23CD0CC2C519527677F72416B48408E7CEEEAF990B1DEA45D92FD6E448E844E9  ds4-p4a/ds4_cuda.cu
```

Artefatto patch:

```text
BF22D1BC93C1225931B1CDF93EEBE4EB9BD941235F7AD06E4020E7F7AED84E03  .microbench/lane_kernel/kernel.patch
```
