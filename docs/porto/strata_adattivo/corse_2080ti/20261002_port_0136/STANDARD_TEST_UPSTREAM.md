# Metodo di validazione upstream — controllo del 2 ottobre 2026

Fonti fissate al commit `36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca`, base
del daily 0.1.36. Questa ricognizione non avvia nuovi test del modello.

## Cosa risulta dal materiale pubblico

Non emerge un unico protocollo pubblico obbligatorio per tutti i contributori.
Il [report RTX 3090/EPYC](https://github.com/Niko1221/Strata/blob/36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca/bench/results/2026-09-29-rtx3090-epyc-milan/README.md)
si dichiara preliminare, usa un harness locale e chiede prompt e metodo upstream.
Il [CMake](https://github.com/Niko1221/Strata/blob/36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca/CMakeLists.txt)
segnala che la suite completa e alcuni microbenchmark non sono inclusi nel
rilascio pubblico dei sorgenti. Questo limita la riproduzione integrale;
non dimostra l'assenza di un protocollo interno.

### Parità dei kernel

Il [test fused IQ](https://github.com/Niko1221/Strata/blob/36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca/tests/cuda/prefill_fused_iq_test.cpp)
confronta i kernel con una referenza in doppia precisione, usando i
dequantizzatori ggml, e con il percorso MMQ precedente. Quando cambia
l'arrotondamento non richiede uguaglianza bitwise: in quel test l'errore RMS
deve essere al massimo 1,5 volte quello di MMQ e l'errore della riga peggiore
al massimo 2 volte. Sono soglie di quel kernel, non soglie universali.
Copre formati diversi, routing sbilanciato, esperti senza righe, token zero,
indirizzi e dimensioni diverse. Il test richiede sm80+: sulla nostra sm75
non va contato come eseguito. Per trasformazioni che preservano esattamente
l'operazione, la nostra verifica bitwise resta appropriata.

### Qualità del modello

Il [confronto cache CPU/GPU](https://github.com/Niko1221/Strata/blob/36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca/bench/results/2026-09-27-cache-parity/README.md)
usa `strata --dump-logits` in teacher forcing: entrambe le configurazioni
vedono gli stessi token di tre testi congelati (codice, documento, chat).
Confronta top-1, divergenza KL e perplexity su 2.557 posizioni. Il top-1 può
cambiare per candidati quasi equivalenti senza peggioramento significativo
della perplexity. Le percentuali osservate non sono un gate generale.

Le [note tecniche](https://github.com/Niko1221/Strata/blob/36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca/docs/DETAILS.md)
riportano che KV q4 passa i needle test ma peggiora la perplexity del 8–12%
sui documenti lunghi. Il retrieval da solo non certifica la qualità generale.

### Prestazioni

Il report RTX 3090 registra versione, hardware, quantizzazione, KV, cache,
MTP, impostazioni di generazione e token effettivi. Usa tre ripetizioni per
cella e ne pubblica la mediana, insieme ai conteggi delle uscite anticipate.
Le sue comparazioni con il benchmark upstream restano dichiarate indicative
perché corpus e harness differiscono. È un esempio di metodo riproducibile,
non una prescrizione universale di tre ripetizioni.

## Conseguenza per il nostro daily

Completati: parità top-k, pool CPU bitwise, gate numerico HC, build e test
server mock. Le tre corse 131k misurano throughput: tutte le sei generazioni
si fermano al limite di 1.024 token durante il ragionamento. Non hanno una
risposta finale valutata; non segnare un PASS di qualità del modello.

Da fare prima di promuovere ulteriori guadagni o aumentare le bozze:

1. Confronto teacher-forced tra daily di riferimento e 0.1.36 su testi fissi,
   con stesso modello/tokenizer e logit/KL/perplexity; definire in anticipo
   il criterio rispetto al riferimento, senza inventare una soglia upstream.
2. Risposte complete a problemi con soluzione verificabile, con controllo
   della risposta finale e confronto con decode non speculativo dove utile.
3. Solo dopo, sweep MTP con parametri controllati e ripetizioni: velocità,
   accettazione, righe verificate e qualità; distinguere profondità reale del
   prompt, capienza KV e riuso della cache.

Sono prossime verifiche proposte, non prove già effettuate o prenotate.
