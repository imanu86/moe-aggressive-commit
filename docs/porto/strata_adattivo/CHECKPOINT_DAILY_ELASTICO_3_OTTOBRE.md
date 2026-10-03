# Checkpoint sul Daily elastico — 3 ottobre 2026

**Esito: candidata non validata per il Daily auto/elastico.
Gate breve FAIL; QA estesa FAIL. Nessuna promozione Daily.**
La candidata è soltanto la frequenza 8192 al posto dell'operativa 16384.
Entrambi i bracci contengono già la stessa elastica e la stessa patch di
allineamento checkpoint. Questo confronto non attesta né respinge queste
patch rispetto a upstream e non dimostra una regressione del Daily operativo.
L'obiettivo delle PR riguarda le modifiche di codice usate nel Daily;
questo esperimento di frequenza è un'evidenza distinta.
Misure complete sullo stesso eseguibile operativo 0.1.36, SHA c35505ca.
Non è una nuova patch: cambia soltanto `--prompt-cache-every` da 16384 a 8192.
Il Daily contiene già l'allineamento del fork e sceglie blocchi 8192 in auto:
la prova 6144/6144 del precedente laboratorio non è la configurazione operativa.

## Metodo e configurazione

RTX 2080 Ti modificata a 22 GB, Ryzen 5800X, 96 GB RAM, IQ3_XXS. Stesso pack/profilo,
`--prefill auto --expert-cache auto --elastic`, KV 262144 INT8/residente 32768.
Spec richiesto 4; capacità runtime 6, MTP massimo 4, lookup 3, come nel Daily.
Greedy e ragionamento disattivato nei prompt della prova. Nessun carico di
pressione artificiale o interazione con altre chat. Tutti i ridimensionamenti
dell'elastica sono naturali e registrati; gli slot iniziali non sono fissati.
Tre coppie per profondità, ordine A1/B1, B2/A2, A3/B3; caricamento e warm-up
esclusi dai tempi. Stessa diagnostica first-logits presente in ogni braccio:
il suo costo è incluso nel TTFT, non sono misure SOTA non strumentate.

Prompt fresh/branch 131072 o 250000 token; branch con appendice diversa dello
stesso archivio. Segue un vero turno serializzato, con la risposta precedente
e circa 1000 nuovi token. Il benchmark lungo usa massimo 1024 token e può
terminare per budget: non conta come risposta completa corretta.
Input decode lungo 132260/251188 token, non confondere con capienza KV.
Le guide generate differiscono anche tra due baseline: le velocità di decode
descrivono queste generazioni e non isolano il costo dello stesso testo.

## Tempi mediani A / B

| Contesto iniziale | Fresh TTFT s | Branch TTFT s | Turno successivo TTFT s | Decode lungo t/s |
|---:|---:|---:|---:|---:|
| 131072 | 125.344 / 125.913 | 20.695 / 10.770 | 3.821 / 3.826 | 44.133 / 43.392 |
| 250000 | 342.583 / 344.920 | 10.913 / 11.075 | 4.936 / 5.043 | 40.423 / 41.526 |

I tre campioni, min/max e differenze accoppiate sono nel confronto JSON.
A 131k il branch riusa 114688/122880 token; a 250k entrambe le configurazioni
riusano 245760. Il vantaggio è lavoro evitato dove il prefisso cade tra i due
checkpoint, non un kernel più veloce né un'accelerazione di ogni conversazione.

## Risposte e QA

Oracoli del banco: 36/36; QA estesa: 12/12.
Due fixture retrieval con tre record al 10/50/90%, ripetute: non altrettanti
problemi indipendenti o una stima dell'accuratezza generale.
Il controllo breve valuta 64 posizioni per corpus code/doc/chat e per braccio,
dopo conversazione e guide. Gate originale conservato; le guide differiscono
anche tra baseline, quindi cache/adattamento vedono storie diverse prima dei
test teacher-forced. Questo limite non riguarda il controllo del primo output
del branch, che avviene prima delle guide. Il gate breve non è superato:

- 131072 token, corpus `code`: `top1`.
- 131072 token, primo output `branch`: gate KL/top1.
- 250000 token, corpus `chat`: `top1`.

Il fallimento di vicinanza numerica resta tale anche se gli oracoli passano;
non dimostra da solo un errore nella risposta o una peggiore perplessità.

La QA estesa confronta A/B/A prima di conversazioni e guide, con input fissi:
corpora 512/1024/1024 token, logits completi, 2557 posizioni note per braccio,
ultimo target sconosciuto escluso. Sono le lunghezze del metodo di confronto
usato dal repository; testi locali congelati, non copia del corpus ufficiale.
Stessa politica locale KL/NLL/top1, baseline ripetuta e blocchi 32 token.
Non è una soglia universale upstream. Tutti i risultati brevi restano registrati;
nessuna soglia è stata allargata per trasformare un fallimento in successo.

| Contesto | Corpus | Top1 A/B / A/A | KL p99 A/B | PPL A / B | Gate corpus |
|---:|---|---:|---:|---:|---:|
| 131072 | code | 97.847% / 95.499% | 0.104397 | 2.021782 / 2.042639 | True |
| 131072 | doc | 96.285% / 96.188% | 0.118859 | 1.186400 / 1.230057 | True |
| 131072 | chat | 99.120% / 99.022% | 0.118523 | 1.676540 / 1.646689 | True |
| 250000 | code | 98.043% / 97.847% | 0.071343 | 1.972444 / 1.966896 | True |
| 250000 | doc | 88.563% / 96.676% | 0.358177 | 1.173255 / 1.383102 | False |
| 250000 | chat | 98.827% / 98.534% | 0.041742 | 1.617803 / 1.623546 | True |

Gate completi, intervalli approssimati della NLL, controlli primo output e
baseline in `paired-r2/comparison.json` e `full-qa/comparison.json`.
Fallimenti della QA estesa:

- 131072 token, primo output `fresh`: KL 0.032220, limite 0.010000; top1 invariato.
- 250000 token, `doc`: nll, median_kl, p99_kl, top1.
- 250000 token, `aggregato`: nll, p99_kl, top1.
- 250000 token, primo output `fresh`: KL 0.038391, limite 0.014028; top1 invariato.

La variazione del corpus documentale a 250k è presente anche senza guide
generate prima della misura. La sola divergenza delle guide non spiega quindi
tutti i fallimenti. La causa resta da isolare: questi dati non attestano la
configurazione 8192 per una promozione operativa.
I limiti sono una sola scheda, un pack, due retrieval e tre testi: niente
certificazione della qualità generale o di ogni livello di pressione VRAM.

## Stato operativo e pubblicazione

Tutti i motori propri chiusi. Daily exe/config/server/launcher invariati per SHA;
RAM libera finale 77.12 GiB; VRAM libera circa 17.56 GiB. Nessuna nuova PR o workflow.
RAM libera minima osservata: 23.06 GiB nel banco e 27.41 GiB nella QA.
Temperatura GPU massima registrata: 65 C. VRAM libera campionata fino a
87/31 MiB rispettivamente, con variazioni naturali e nessun errore del motore.
Questi minimi non definiscono una riserva garantita; dati in resource-summary.json.
Il primo avvio fu rifiutato prima del warm-up: 759 MiB liberi contro una riserva richiesta di 800 MiB.
Conservato come tentativo startup-only; riserva successiva di 500 MiB segue il margine
del Daily elastico e non modifica alcuna soglia di qualità.

Il primo staging fu bloccato su `.git/index.lock`. L'accesso completo è stato
successivamente ripristinato. Il commit di pubblicazione sul branch research
autorizzato identifica le evidenze online; il blocco iniziale è storico.

Evidenze: [manifest](corse_2080ti/20261003_checkpoint_daily/manifest.json).
Raw logits e binari esclusi dalla pubblicazione; hash e dimensioni conservati.
