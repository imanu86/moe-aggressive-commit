# Main e daily riallineati a Strata0.1.36 — 2 ottobre2026

**Completati PR upstream, port delle candidate, tre prove modello, pubblicazione
main e release, installazione operativa e verifica dell'avvio.** Il daily usa
`build-0136-daily`, con KV262144/int8/resident32768, riserva1393MiB, cache
auto/elastica e MTP. Quantizzazione intermedia seriale; il port parallelo e'
disponibile opt-in. Nessun carico artificiale, nessuna interazione con altre chat.

## PR e vera base main

Metodo di validazione pubblico e lacune ancora aperte:
[STANDARD_TEST_UPSTREAM.md](corse_2080ti/20261002_port_0136/STANDARD_TEST_UPSTREAM.md).
Il prossimo gate di qualità comprende teacher forcing (logits/KL/perplexity)
e risposte finali verificabili, prima dello sweep delle bozze. Non ancora eseguito.

PR [#512](https://github.com/Niko1221/Strata/pull/512) **aperta in bozza**, branch
remoto autorizzato `imanu86:prefill-topk-active-bound`, commit42131caf. Dopo
l'apertura su0.1.35, upstream e' avanzato a0.1.36. Integrata la nuova main nella
PR senza riscrivere la storia, preservando i cluster sm90+. La PR e' mergeable
e contiene soltanto4file: dispatch, header, harness e CMake. Nessun commento o
review al controllo del2/10. Le vecchie negazioni di accesso sono state risolte
dai permessi concessi dall'utente; nessuna approvazione ulteriore richiesta.

La bozza resta tale perche' manca un A/B/A modello della PR isolata sulla nuova
base. Le16parita' sono ripetute sulla0.1.36; le misure causali+6,83% riportate
nel corpo della PR appartengono al daily0.1.31. Le prove della combinazione del
fork non vengono presentate come prova della PR isolata.

Fork [main729eb4a](https://github.com/imanu86/Strata-2080Ti/commit/729eb4a14c0a102cf7a57149e8e3fd93a9d18a5f)
basato su upstream `36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca` (0.1.36).
Importato il **tree completo** della nuova base con il port locale, oltre a
conservarne l'ascendenza: il vecchio fork aveva antenati0.1.34 ma core0.1.31,
quindi un merge dei soli nuovi commit non avrebbe riallineato tutti i sorgenti.
17file core diversi da upstream; tutti gli altri sorgenti corrispondono alla
base. Le differenze di fine riga rispetto al vecchio snapshot sono conservate
come byte del nuovo export testato; nessuna riscrittura della storia pubblicata.

## Patch e scelta operativa

- Cache elastica a due zone/VMM, core fisso e coda rotante, checkpoint allineati,
  buffer host per chunk massimo, HC/GDN prefill FP16 e dequant vettoriale sm75
  conservati. Predicato sm75 per dispositivo/thread, BF16X2 upstream opt-in
  preservato. #315 e commit asincrono gia' in upstream: usate quelle versioni.
- Top-k riusa `qsa_block_topk(..., active_blocks)` upstream. Limite attivo solo
  su CUDA sm75; strideKV invariato, fallback oltre33792blocchi e per limiti non
  validi, decode/grafi senza bound fisso. Cluster upstream sm90+ conservati.
- [#463](https://github.com/Niko1221/Strata/pull/463): sola attesa
  `apply_pending(true)` prima delle finestre di verifica serve/CLI. Evita che la
  scelta CPU/GPU dipenda dal sondaggio dei caricamenti ancora in corso. Non
  importata la doppia attesa evento del diff, ne' il tracing dell'autore.
- [#500](https://github.com/Niko1221/Strata/pull/500): task disgiunti per coppia
  esperto/token sul pool esistente e barriera prima delle down; stessi
  quantizzatori, incluso Q2_0 nativo AVX2. **Default spento**:
  `STRATA_PARALLEL_INTERMEDIATE_QUANT=1` abilita il confronto; il JSON daily
  imposta0. Il vantaggio osservato nel decode e' solo0,37%, con MTP/cache/testi
  diversi; pool+plan finale11,631→12,136ms (+4,34%). Nessun beneficio CPU
  convincente: non viene abilitato nel profilo operativo.
- La nuova0.1.36 comprende esperti prefill fusi Q2/IQ, che richiedono sm80+;
  decode cluster sm90+. Sono presenti ma indisponibili sulla2080Ti. Non
  dichiarare i guadagni RTX5070 per Turing. CH16, BPW, #439 e workflow esclusi.

## Prove sul modello e record osservato

RTX2080Ti modificata22GB, Ryzen5800X AVX2,96GB RAM, Windows/CUDA12.6/PCIe3,
IQ3_XXS, cache auto/elastica, spec4/minp0,5/MTP. Ogni motore e' stato avviato
separatamente: prompt freddo131248, poi131239 con131072riusati;2x1024output,
tutte le6richieste concluse con `finish=length`.

| Motore | Prefill freddo131248 t/s | TTFT s | Decode aggregato2x1024 t/s | Slot elastici iniziali |
|---|---:|---:|---:|---:|
| Daily0.1.31 riferimento | 974.05 | 135.494 | 41.255 | 6592 |
| 0.1.36 seriale, operativo | 972.68 | 135.655 | 40.123 | 6786 |
| 0.1.36 parallela, opt-in | 970.60 | 135.981 | 40.272 | 6034 |

**Miglior prefill osservato a131k:974,05t/s sul daily precedente.** La candidata
seriale fa972,68t/s. Il precedente risultato validato era886,38t/s; il riferimento
prima del top-k era831,20/828,26. Anche il vecchio exe e' piu' rapido in questa
sessione, quindi il salto non e' attribuito alle nuove patch. Questi sono nuovi
campioni della prestazione osservata, non una nuova misura causale di speedup.

Cache iniziale6592/6786/6034slot, crescita/riduzione reale durante i turni.
Altre app: CPUmedia0,93/0,67/0,67core. RAMminima circa20GiB durante i modelli.
MTP, hit rate, output e pressione desktop variabili; decode −2,74% sul singolo
confronto seriale col riferimento non viene attribuito alla nuova base senza
un controllo ripetuto. Nessuna qualita' generale dedotta dal banco: i1024token
sono budget di throughput e le risposte sono ragionamento troncato a `length`.
La capacita' runtime262144 e' distinta dalla profondita' testata131248.
Retrieval250022 e decode250091 storici appartengono a0.1.31/f469; **non ripetuti
sulla0.1.36**, cosi' come non e' stata ripresa la vecchia conversazione20k→250k.

## Correttezza delle risposte e bozze

La nuova config non ha uno sweep del limite MTP: `spec=6/mtp_max=4` significa
fino3bozzeMTP e5lookup, finestre comprendenti il token corrente. Il vecchio
minp0,3 aveva peggiorato45,1→43,2t/s. Tutti i6output131k sono ragionamenti
troncati a1024, non risposte finali verificate. Letti i2output seriali, temi
pertinenti ma esempi intermedi GiB/GB da correggere. Dettagli e prossime prove
separate: [CORRETTEZZA_E_BOZZE.md](corse_2080ti/20261002_port_0136/CORRETTEZZA_E_BOZZE.md).
Nessun reviewer esterno e nessuna nuova corsa avviata.

## Compilazione e correttezza

Build CMake/Ninja completa Release, MSVC14.44.35207, CUDA12.6, arch75,
runtime CUDA condiviso, esperti CPU nativi, ggml fissato a
`3cf03257f219afbe7334045ff7c6a06ac68c627d`. Anche la candidata0.1.35 era stata
compilata, poi sostituita dal port0.1.36 prima delle prove modello.

- Top-k CMake0.1.36:16/16ID bitwise, contesti1111..262144, pareggi/zeri/code,
  query1/8/255/256/257 e limiti invalidi/confine33792.
- Pool nativo:64/64output bitwise/finiti, esperti reali gu/down17/20 e21/42,
  token1..8, batch1/3/9/97,2worker e host-works off/on. I file pool/kernel CPU
  di0.1.36 sono gli stessi della candidata0.1.35 usata nel test; nessuna libreria
  CPU Strata vecchia li sostituisce. Non testato il Q2 storico AVX512, testato
  Q2_0 nativo usato da questo modello AVX2.
- HC CMake: `gr_parity --selftest`, zero errori, dimensioni2560/4/320, multiT8,
  replay grafi e contratti BF16/FP32/native. Test server upstream:100/100PASS.
- `check_source.py`:575file attualiPASS e hash del manifest storico conservato;
  test configuratorePASS; patch completa applicabile all'export upstream intatto.
  Nessuna nuova whitespace nel port rispetto alla base, tenendo conto dei CRLF.

## Installazione, pubblicazione e ripristino

Entrambi i checkout sono **main/729eb4a14c0a102cf7a57149e8e3fd93a9d18a5f**:
`C:\Users\imanu\source\repos\Strata-2080Ti` e
`D:\ds4_work\strata\Strata`. Commit con trailer Codex, push immediato.

Exe operativo `D:\ds4_work\strata\Strata\build-0136-daily\strata.exe`:
`c35505ca79b790bd37ed7073fcadd399dd30d1b88e85bb99a6eb24a52d945d0a`.
Server `D:\ds4_work\strata\Strata\build-0136-daily\source\serve\server.py`, hash `73f90f417e9207811fdc47e5e6240f69bbde0f61ff027b9e0d8cb7b7bb2f4d81`.
JSONcanonico e BATDesktop/copie repository aggiornati e byte-identici.
Il nuovo test `--config-template` usa il JSON reale per lo smoke, spostando
soltanto porta/cwd/log nel laboratorio. Avvio **40.72s PASS**,
versione0.1.36, capienza262144, cache elastica6904slot. Nessun prompt dello
smoke; terminati soltanto supervisore e motore della prova.

Backup `D:\ds4_work\strata\ripristini\20261002_191326_0136_main_daily`: bundle Git completo, vecchia build0131/f469,
JSON e BAT, copie dei file non tracciati. I due grandi dump DMP sono conservati
con hard link sullo stesso volume e restano anche al percorso originale.
Tutti i48file non tracciati preservati; build0131 originale resta disponibile.
Per ripristinare solo il runtime: ricopiare JSON e BAT dal backup; puntano alla
build0131 e al suo server conservati. Non serve riscrivere main per il rollback
del lanciatore. Backup pubblicazione in `strata-main-alignment/recovery-main-*`.

Release [v0.1.36-sm75-20261002-r1](https://github.com/imanu86/Strata-2080Ti/releases/tag/v0.1.36-sm75-20261002-r1) pubblicata sul commit729eb4a.
ZIP20.66MB: exe e PDB esatti, manifest, validazione, licenza/crediti/requisiti;
hashZIP `5694e4d00ef075ba8d938914936de1adb7104beb92656a89af3792090570c59c`. Release0.1.31 precedente conservata;
manifest storico byte-identico in `source-manifest-0131.json`. Actions ancora
disabilitato e nessun workflow aggiunto.

Evidenze riproducibili: [`corse_2080ti/20261002_port_0136/`](corse_2080ti/20261002_port_0136/),
log3bracci, output, metricheCPU/cache/MTP, hash, patch completa, build e100test
server, smoke installato e pubblicazione. Preparazione locale in
`C:\Users\imanu\Documents\Codex\2026-10-01\https-github-com-imanu86-moe-aggressive\strata-main-alignment`.

Restano candidate separate #385DMA/stager, #453ring MTPprefill(KVint8 da validare),
#487sondaPCIe; eventuale port dei nuovi kernel fusi a istruzioni disponibili su
Turing richiede una nuova implementazione e prove numeriche. Nessun test futuro
avviato o pianificato da questo aggiornamento.
