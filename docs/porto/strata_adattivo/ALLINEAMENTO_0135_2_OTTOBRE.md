# Preparazione storica0.1.35 del2ottobre

**Superata dall'allineamento0.1.36 completato**:
[rapporto corrente](ALLINEAMENTO_0136_2_OTTOBRE.md).
Le precedenti negazioni di accesso sono risolte; build0.1.35 completa riuscita.
PR [#512](https://github.com/Niko1221/Strata/pull/512) aperta e aggiornata sulla
nuova base, fork/main e daily0.1.36 pubblicati/installati. Seguono i dettagli
del port preparatorio0.1.35 e dei banchi numerici conservati nelle evidenze.

## Riallineamento dei sorgenti

Il fork pubblicato ha antenati fino a upstream0.1.34, ma il suo tree core e'
lo snapshot0.1.31 validato, non quello0.1.34. Un merge dei soli commit successivi
non riallineerebbe i file sovrascritti. Eseguito quindi un confronto a tre vie
fra base reale0.1.31 `9259cad4cfa3543cd3b8decab5962672b968c649`, sorgenti locali
validati e main upstream0.1.35. Gli export di laboratorio non sono nuovi
checkout, worktree o branch Git.

Conservati cache a due zone e VMM, core non prestabile/ne' sostituibile,
ridimensionamento della coda con isteresi, riallineamento dei checkpoint,
buffer host dimensionati per il chunk massimo, HC/GDN prefill FP16 e
dequantizzazione vettoriale sm75. Il predicato FP16 ora segue il dispositivo
del thread anche quando cambia: un'altra scheda non eredita il primo sm75.

#315 e commit asincrono #284 sono gia' in upstream: mantenute le implementazioni
upstream, inclusi `wait_commit()` e l'evento di completamento. Conservato
l'opt-in BF16X2 upstream aggiungendo l'output FP16 come parametro separato;
se richiesto, BF16X2 continua a scegliere il proprio percorso numerico.
Non importati CH16, BPW, #439 o workflow.

Il top-k riusa l'API upstream `qsa_block_topk(..., active_blocks)`, senza
aggiungere l'API separata del vecchio fork. CUDA upstream ignora il parametro
per una regressione RTX5070: la candidata abilita il limite solo su sm75,
mantiene stride e kernel, fallback oltre33792blocchi e per limiti non validi,
e mantiene il percorso di capienza per decode e grafi catturati.

## Due nuove candidate

- [#463](https://github.com/Niko1221/Strata/pull/463): importata la correzione
  di ordinamento `apply_pending(true)` prima delle due finestre di verifica,
  serve e CLI. Evita che la scelta CPU/GPU degli esperti dipenda da una query
  non bloccante sugli ultimi caricamenti. Non importate la doppia attesa di
  evento del diff, il tracing o il cambiamento del dump logits. Compilazione
  host controllata; riproducibilita' sul modello e costo dell'attesa da misurare.
- [#500](https://github.com/Niko1221/Strata/pull/500): quantizzazione degli
  intermedi per coppia (esperto, token) sul pool gia' esistente. I task
  scrivono buffer disgiunti; la fase precedente termina prima della
  pubblicazione e la nuova fase termina prima delle proiezioni down.
  Un task usa il percorso seriale. **Default spento** nella candidata:
  `STRATA_PARALLEL_INTERMEDIATE_QUANT=1` abilita il confronto. Stessi
  quantizzatori dei percorsi precedenti, incluso Q2_0 nativo sul Ryzen AVX2.

Le altre candidate restano da provare separatamente: #385 DMA/stager, #453
prefill MTP con ring (KV int8 non provato dall'autore), #487 sonda PCIe.
Le percentuali misurate da altri non sono previsioni per questa macchina.

## Verifiche eseguite

Windows, RTX2080Ti modificata22GB, Ryzen5800X AVX2, MSVC14.44, CUDA12.6, sm75.
Tre prove numeriche distinte, senza motore/server completo o carichi hog:

| Prova | Risultato e perimetro |
|---|---|
| Top-k 0.1.35 | **16/16 PASS**, ID selezionati bitwise; stride65538, contesti1111..262144, pareggi, zeri, code parziali, query1/8/255/256/257, limiti non validi e confine registri |
| Pool #500 | **64/64 PASS**, output finiti e bitwise seriali; esperti reali dagli strati0 e20 del nostro GGUF, gu/down17/20 e21/42, token1..8, batch1/3/9/97, 2worker, host che lavora acceso/spento, alternanza seriale/parallela ripetuta |
| HC upstream | **gr_parity --selftest PASS**, zero errori; dimensioni2560/4/320, lancio multi-T8 e replay di grafi, contratti BF16/FP32/native |

Il test del pool compila i sorgenti CPU della candidata; usa solo le librerie
ggml-cpu/base gia' compilate della dipendenza locale fissata a
`3cf03257f219afbe7334045ff7c6a06ac68c627d`. Nessun kernel CPU della vecchia
libreria Strata sostituisce il pool modificato. Non esercita il percorso Q2
storico che richiede AVX512; esercita il Q2_0 **nativo**, usato dal modello.

MSVC syntax-only PASS per `prefill.cpp`, `expert_cache.cpp`, `verify.cpp` e
`generate.cpp`; compilazione in oggetto CUDA PASS per kernel prefill e
dequantizzazione. Top-k e HC compilati/linkati direttamente con nvcc, pool
con cl. In seguito ai permessi concessi, la build CMake completa0.1.35 e' riuscita.
Le prove modello sono state eseguite sulla nuova0.1.36, descritta nel rapporto corrente. Gli errori iniziali di link dei banchi
diretti sono stati risolti includendo le loro dipendenze.

La GPU era gia' impegnata (~35%,8358MiB al campione iniziale): queste sono
prove di correttezza, **nessun t/s o guadagno SOTA dedotto**. Questo checkpoint descrive solo le prime prove numeriche. Le successive
prove modello0.1.36 sono nel rapporto corrente; la curva conversazionale non e' stata ripresa.
Nessuna interazione con altre chat.
