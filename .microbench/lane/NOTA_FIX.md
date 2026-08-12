# Correzione lane G132: split consumer su route CPU non pubblicate

## Causa trovata

La causa non è l'installazione anticipata della specializzazione
`cuda_moe_route_worker<false, true>` in sé. Quella specializzazione è necessaria:
il worker è l'unico punto che possiede già i byte host esatti della route e può
decidere, prima dell'H2D, di lasciare una route alla CPU. L'assegnazione del
puntatore funzione durante `cuda_g73_route_dispatch_init()` non lancia il worker,
non accoda copie e non modifica alcuno stream.

Il difetto è l'incompatibilità fra quella decisione e il consumer split:

- `ds4-p4a/ds4_cuda.cu:40610` ammette una miss nella lane CPU; il `continue`
  immediatamente successivo lascia intenzionalmente non pubblicati i suoi
  `route_ptrs` device, che restano zero, e salta l'H2D dei 7.077.888 byte;
- `ds4-p4a/ds4_cuda.cu:46835-46840` riconosceva il piano G132 soltanto con
  `!use_split_fused && !use_split_hit_miss`;
- con uno split attivo si entra invece in `ds4-p4a/ds4_cuda.cu:47918`;
  i kernel hit partono correttamente mentre il worker lavora, ma dopo
  `finish()` i kernel miss a `:48086` e `:48110` continuavano a considerare
  miss anche le route già assegnate alla CPU e dereferenziavano i loro
  `route_ptrs == 0`.

Questa è una causa device concreta dell'`illegal memory access`. Non è il
calcolo scalar CPU, il join o il bilanciatore.

## Perché il log mostrava `calls=0`

`calls=0` non significa che nessun tentativo route sia iniziato:

- `seq=1` nella quarantena prova che la prima richiesta route era già stata
  pubblicata;
- `general_calls` viene incrementato solo a
  `ds4-p4a/ds4_cuda.cu:49913`, dentro `cuda_g132_cpu_lane_wait_and_join()`,
  dopo il completamento di entrambi i lati.

Nel ramo split difettoso il piano veniva creato dal worker, ma la lane non
veniva mai agganciata dal consumer e quindi non poteva arrivare al join che
incrementa `general_calls`. Il kernel miss dereferenziava prima il puntatore
nullo.

L'errore su `q8_0_pair0` non localizza il guasto nel model staging:
`cudaEventRecord()`/`cudaMalloc()` stavano riportando l'errore asincrono e
sticky prodotto dal kernel precedente sul contesto CUDA. Analogamente,
`route upload stream quarantine ... cancel-and-join` è la conseguenza della
query di uno stream nello stesso contesto già avvelenato, non la sorgente
dell'accesso fuori limite.

## Correzione

`fix.patch` conserva lo split e conserva la concorrenza CPU/GPU; non disabilita
né il worker G132 né il percorso split.

Dopo `cuda_moe_gpu_resident_routes_finish()` e solo se il worker ha realmente
pubblicato `route_cpu_plan.cpu_count != 0`, il consumer split:

1. trasferisce il piano nella lane e avvia la copia input/worker CPU;
2. lancia sullo stream 0 un piccolo kernel che azzera in `split_down` gli slot
   CPU e aggiunge `cpu_mask` a `device_route_hit_mask`;
3. lascia invariati i kernel split esistenti.

L'ordine dello stream garantisce che i kernel hit, già accodati, vedano la
maschera originale. I successivi kernel miss vedono invece le route CPU come
“non GPU-miss” e quindi non dereferenziano i puntatori non pubblicati. Il
reducer split-fused legge zero per quegli slot; il reducer non-fused somma gli
stessi zeri. Infine il normale join G132 aggiunge il parziale CPU.

Il punto di aggancio split è stato quindi spostato al primo istante in cui
coesistono entrambe le prove necessarie: `finish()` ha completato il worker e
`cpu_count` certifica almeno una route effettivamente assegnata. Prima di quel
momento la patch non tocca `device_route_hit_mask`, `split_down`, model staging
o upload stream.

Le route CPU continuano a uscire dalla copia `route_transient_*`: il
`continue` nel worker non cambia e nessun expert CPU attraversa il bus.
Ammissione, residenza, soglie, vittime e dimensionamento cache non sono
modificati. Non viene introdotto alcun percorso Q1/IQ1.

La telemetria `g132-general-summary` è conservata e aggiunge
`split_masks`: viene incrementato soltanto dopo un piano CPU non vuoto e dopo
il lancio della prima mutazione split. Un valore maggiore di zero prova quindi
che lo stato condiviso split è stato modificato solo in risposta a route CPU
effettivamente assegnate.

## Neutralità

Con `G132=false` tutti i nuovi blocchi nel launch restano eliminati da
`if constexpr`; il kernel ausiliario non viene lanciato e il nuovo contatore
resta zero. Il percorso a flag spenti certificato da L0 non cambia. Anche con
G132 acceso, le richieste senza route CPU conservano integralmente il percorso
split preesistente.

## Verifiche eseguite

Come richiesto, non sono stati compilati binari, non è stato avviato
`ds4_server` e non è stato toccato `D:\`.

Sono state eseguite soltanto verifiche statiche:

```text
git apply --check --whitespace=error-all .microbench/lane/fix.patch
git apply --numstat .microbench/lane/fix.patch
```

Esito: patch applicabile al tree corrente; `95` righe aggiunte e `1` rimossa in
`ds4-p4a/ds4_cuda.cu`.

## SHA-256

Preimage esatta sulla quale è stato prodotto il diff:

```text
7CC4377593E054D9BD4FFB97A4091F351FE9FAD3FB8C6B89276D0A1534D0029D  ds4-p4a/ds4_cuda.cu
```

Artefatto consegnato:

```text
7435637BD6F12F09CC7A2AE524A83A350CF6E439AFF2B32A2E9AEA8F432A30F2  .microbench/lane/fix.patch
```
