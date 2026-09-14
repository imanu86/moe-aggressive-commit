# FreeToken e Bonsai: verifica sul nostro Qwen

13 settembre 2026. RTX 3060 12 GB, Ryzen 5800X, 96 GB DDR4, Windows. Target invariato: 50 t/s di generazione generale e prefill oltre 400 t/s, distinguendo le lunghezze del contesto.

## Stato e decisione

La priorità concordata è FreeToken e le ottimizzazioni del motore attuale. Il doppio formato Q3/GPU + Q4/CPU resta un'ipotesi successiva. L'utente intende un Q4 pubblicato dello stesso modello, non una riconversione dei pesi Q3. Non è stato avviato il download completo Q4 e non è stato eseguito un confronto prestazionale Q4/Q3.

I 39,19 t/s precedenti misuravano copia di codice già presente nel prompt, aiutata dall'n-gram. Il dato precedente di risposta libera era 25,08 t/s. Questa verifica aggiunge prove di cache e componenti CPU, **nessuna nuova misura di generazione del modello completo**.

## Compatibilità FreeToken

Sorgenti ispezionati: `FlashML-org/FreeToken`, commit `953565667f3141c90d0f0eb469bb2655d2407140`.

FreeToken è pertinente perché coordina cache esperti, copie alla GPU e calcolo CPU. La sua documentazione elenca Qwen3.8 Flash Next con checkpoint FP8/NVFP4. Il percorso GGUF del commit verificato, però, registra soltanto Gemma4: il nostro Qwen UD-IQ3_XXS non è caricabile direttamente. [Modelli](https://github.com/FlashML-org/FreeToken/blob/953565667f3141c90d0f0eb469bb2655d2407140/docs/models.md), [registro GGUF](https://github.com/FlashML-org/FreeToken/blob/953565667f3141c90d0f0eb469bb2655d2407140/python/freetoken/models/gguf/config.py#L17-L21).

La PR #131 amplia il GGUF e aggiunge Qwen3.5 MoE; alla verifica era aperta. Non costituisce supporto verificato del nostro Flash Next. [PR #131](https://github.com/FlashML-org/FreeToken/pull/131).

Il motore CPU di FreeToken accetta BF16, NVFP4, MXFP4, DS_FP4 e Q4_0. Non offre il percorso CPU IQ2_S/IQ4_NL del nostro modello, anche se alcuni di questi tipi compaiono nei kernel CUDA. [Formati CPU](https://github.com/FlashML-org/FreeToken/blob/953565667f3141c90d0f0eb469bb2655d2407140/python/freetoken/moe/cpu_executor.py#L71-L72).

La politica ibrida manda parte dei miss alla GPU e calcola gli altri sulla CPU. Nel codice attuale la calibrazione preferita usa le bande misurate **durante l'esecuzione concorrente**, con frazione di fetch `PCIe_overlap / (PCIe_overlap + CPU_overlap)`. Il rapporto fra misure separate è un fallback. Serve quindi una prova di concorrenza sul nostro hardware; non basta conoscere la banda teorica della RAM. [Calibrazione](https://github.com/FlashML-org/FreeToken/blob/953565667f3141c90d0f0eb469bb2655d2407140/python/freetoken/moe/bench_profile.py#L162-L190).

## Prima verifica: la LRU non migliora questa traccia

Replay della traccia già acquisita: 36.913 piani, SHA256 `690d7c26e248d05a83f244c477e5d55fe644b40d481c3c90ebb9f63ea9861212`.

Il simulatore della politica attuale riproduce tutti i miss registrati: zero differenze. Si confrontano una LRU per strato e una LRU globale ideale con lo stesso budget di payload, 6.078.464.000 byte. I gruppi nella traccia identificano 95 incarnazioni successive di cache su **48 strati fisici**, non 95 cache simultanee: i cambi di gruppo invalidano le vecchie voci senza aumentare la memoria disponibile.

| Politica | Hit rate caldo | Payload dei miss nel tratto caldo |
|---|---:|---:|
| Attuale, frequenza decaduta + recenza, 64 slot/strato | **75,55%** | **163,81 GB** |
| LRU, 64 slot/strato | 74,59% | 170,23 GB |
| LRU globale, allocazione ideale a pari byte | 74,82% | 168,51 GB |

Il tratto caldo esclude i primi 64 piani di ogni incarnazione senza azzerarne lo stato. La LRU globale è un confronto di politica, non un'emulazione identica del kernel FreeToken: assume impacchettamento variabile senza padding, usa pareggio per ID nei batch e non simula costi GPU o CPU. Anche in questa versione favorevole non supera la politica attuale sulla traccia. Nessuna conversione di questi risultati in t/s.

## Seconda verifica: CPU con i pesi originali

Sono stati estratti, senza modificarne un byte, 128 esperti dello strato 0 dal GGUF locale. Il manifest registra offset, forme e hash per riprodurre l'estrazione senza scaricare nuovi modelli.

- Gate e up: IQ2_S, `[2560, 640, 512]`, 524.800 byte per esperto e per banca.
- Down: IQ4_NL, `[640, 2560, 512]`, 921.600 byte per esperto.
- Totale: 1.971.200 byte per esperto completo. Gli estratti di 128 esperti occupano circa 240,6 MiB nelle tre banche, oltre la cache L3 della CPU.

Il primo banco misura le moltiplicazioni singole. Il secondo costruisce la catena `gate/up → SiLU × up → down` con gli stessi kernel GGML CPU della build locale, threadpool persistente e conteggio thread configurato esplicitamente. Ruota gli ID su 128 esperti, usa attivazioni sintetiche, 10 iterazioni di riscaldamento e 1.000 cronometrate. Tre processi ripetuti per combinazione; tabella con mediana delle tre mediane.

| Esperti CPU per chiamata | 4 thread | 8 thread | 16 thread |
|---|---:|---:|---:|
| 1 | 0,0872 ms | 0,0849 ms | **0,0707 ms** |
| 2 | 0,2494 ms | **0,1737 ms** | 0,1918 ms |
| 4 | 0,3203 ms | **0,3202 ms** | 0,3614 ms |
| 10 | 0,7873 ms | **0,7754 ms** | 0,8657 ms |

Sono durate CPU della catena, non latenza del layer completo o del token. Mancano trasferimenti di attivazioni, sincronizzazione CUDA, competizione con la GPU, router, aggregazione pesata e shared expert. Non sono i kernel fusi di FreeToken. La verifica numerica confronta gli output dell'ultima iterazione con un riferimento dequantizzato; NRMSE massimo osservato 0,009453, sotto la soglia 0,05. Questo controllo individua errori grossolani della sonda, non dimostra equivalenza generale del modello.

Il codice CPU attivo riporta AVX2 presente e AVX-VNNI assente. Su questa sonda, più thread non migliorano sempre il risultato. A 8 thread, la banda effettiva della catena è circa 23–25 GB/s: vicina ai circa 25,7 GB/s della precedente sonda PCIe, prima di contesa e handshake. Non emerge un ampio margine gratuito per spostare tutti i miss sulla CPU; resta da verificare un percorso fuso per pochi esperti in parallelo.

## Terza verifica: sincronizzazione CUDA su Windows

La sonda nativa prova `cuStreamWriteValue64` e `cuStreamWaitValue64` sullo stesso puntatore host mappato usato da FreeToken. Scrive 1, attende un valore maggiore o uguale a 1 e sincronizza: tutte le chiamate hanno successo e il flag letto è 1. Non è necessario escludere a priori questo meccanismo sulla nostra installazione Windows.

Una seconda prova confronta un graph vuoto con un graph seriale di 96 callback vuote, 30 lanci ciascuno: mediane 0,000500 ms e 0,067350 ms, differenza 0,066850 ms, circa 0,696 microsecondi per nodo. Il graph contiene soltanto callback senza lavoro: **non misura** D2H/H2D, coordinatore CPU, contesa, attese degli esperti o il graph completo di FreeToken. Anche la prova dei flag non dimostra l'intera integrazione. I commenti del progetto riportano costi di callback più alti su altre configurazioni; non li adottiamo come misure della nostra macchina. [Handshake FreeToken](https://github.com/FlashML-org/FreeToken/blob/953565667f3141c90d0f0eb469bb2655d2407140/python/freetoken/moe/cpu_executor.py#L32-L50).

La compilazione della sonda CUDA è riuscita con un warning di collegamento CRT, conservato nel log; l'esecuzione ha concluso con successo.

## Cosa prendere da Bonsai

Bonsai usa pesi binari/ternari e kernel dedicati a quei formati. Nel nostro sorgente è già presente il dot product Q1_0 AVX2; gli esperti del Qwen usano altre rappresentazioni. Copiare quel kernel non accelera automaticamente IQ2_S o IQ4_NL. Il lavoro VNNI su Q2_0 riguarda istruzioni che il 5800X non possiede. [Bonsai](https://github.com/PrismML-Eng/Bonsai-demo/blob/main/README.md#upstream-status-for-binary), [Q1 CPU](https://github.com/ggml-org/llama.cpp/pull/21636), [Q2 VNNI](https://github.com/ggml-org/llama.cpp/pull/26348).

## Ordine dei prossimi interventi

1. Per la pista FreeToken, provare un esecutore CPU fuso per IQ2_S/IQ4_NL e misurarlo insieme alle copie GPU, includendo handshake e fusione dei risultati. Iniziare con uno o pochi esperti per chiamata; selezionare la frazione solo dai tempi osservati.
2. Conservare la politica cache attuale finché una prova su più tracce non giustifica un cambiamento. Lo streaming del prefill con due buffer è già implementato localmente: il progetto FreeToken offre un confronto d'architettura, non un guadagno ancora da sommare.
3. Valutare checkpoint ai confini di ragionamento/tool output per evitare il ricalcolo dei prefissi dopo le modifiche della chat. Il nostro server ha già checkpoint del contesto e confini dei messaggi utente; il lavoro utile riguarda le parti ancora mancanti. Il risparmio di token ricalcolati va distinto dai t/s di prefill freddo. [Disegno FreeToken](https://arxiv.org/html/2608.16157v1#S3.SS1).
4. Proseguire sulle moltiplicazioni CUDA Q6_K e sulla verifica speculativa, già individuate nel profilo precedente. La prova con un Q4 pubblicato resta un esperimento separato e rinviato.

Nessuna sostituzione del motore di produzione, nessun nuovo server completo avviato e nessun risultato di 50 t/s ottenuto in questa verifica.
