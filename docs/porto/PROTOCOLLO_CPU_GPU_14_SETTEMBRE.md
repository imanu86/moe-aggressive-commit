# Protocollo di verifica CPU/GPU

Versione 1.0, 14 settembre 2026. Parte del [piano](PIANO_CPU_GPU_14_SETTEMBRE.md). **Nessun nuovo benchmark viene dichiarato da questo protocollo.** I test sotto vanno eseguiti nelle rispettive fasi; le soglie sono criteri iniziali di lavoro, non limiti scientificamente universali.

**Base comune e input immutabili.** In P0 si salvano manifest del modello e dei suoi shard, hash binari/sorgenti/preset, driver/toolkit, topologia CPU, thread/affinità, batch/ubatch, contesto, slot esperti, template, thinking, seed, campionamento e modalità speculative. Il modello resta quello corrente, senza Q4 aggiuntivo. Una build precedente viene archiviata; A/B usa lo stesso preset salvo la funzione sotto esame.

Il banco esistente costruisce parte del contesto leggendo i sorgenti: questi cambieranno durante l'implementazione. P0 deve quindi **materializzare una volta testo, ID token e hash dei prompt**. Le due varianti leggono quelle fixture identiche. Non si rigenera il filler da sorgenti modificati e non si cambia template per disattivare il thinking fra i lati di un A/B.

`cache_prompt=false` riguarda il riuso del prefisso/KV e **non azzera automaticamente la cache degli esperti**. Per ogni blocco A/B si riparte da un processo nuovo o da un reset esplicito già verificato, con lo stesso primer e la stessa sequenza di richieste. Si separano: caricamento del modello, prima richiesta, decode dopo prefill, conversazione calda. Un eventuale vantaggio dovuto alla diversa ammissione degli esperti è reale, ma va misurato su una sequenza uguale, non attribuito solo al kernel.

**Matrice dei confronti.**

| Confronto | Configurazione | Domanda |
|---|---|---|
| N | Binario prima della patch / nuova build con ibrido spento | È neutro il percorso disattivato? |
| D | Stessa nuova build, ibrido spento/acceso, MTP e n-gram spenti | Quanto vale la CPU nel decode a un token? |
| M | Stessa nuova build, ibrido spento/acceso, MTP acceso e stessi parametri | Il guadagno sopravvive alla verifica speculativa? |
| G | Come M, con n-gram e rollback identici sui due lati | Ci sono interazioni o regressioni nelle copie e nei cambi turno? |
| P | Ibrido spento/acceso a 32k e 131k, stesso batch e staging | Pool e buffer interferiscono col prefill, anche se la CPU MoE è esclusa? |

I 25,08/27,26 t/s e i 39,19 t/s del 13 settembre sono riferimenti storici; non sostituiscono uno dei lati della matrice. In particolare non esiste una "baseline FreeToken" del modello completo.

**Batteria minima.** La selezione è congelata in P0 con un ID per caso e una rubrica di correttezza. I budget di token in vigore sono quelli della decisione **D11** nella tabella delle decisioni del [registro](REGISTRO_CPU_GPU_14_SETTEMBRE.md) (1024 in screening / 1536 in conferma per i liberi, 768 per qualità strutturata e contesto lungo), non i 512/768 della tabella sotto.

| Insieme | Casi e taglie | Uso |
|---|---|---|
| Libero | Otto consegne: tre di prosa/spiegazione, due di ragionamento verificabile, tre di codice nuovo con test; contesto corto e 32k. Budget 512 token in screening, 768 in conferma. | Metriche primarie del decode. Nessuna risposta attesa già contenuta nel prompt. |
| Copia/modifica | Copia e rinomina con gli stessi input fissi del banco precedente, 1024 token. | Diagnostica n-gram separata, mai media insieme alla risposta libera. |
| Qualità strutturata | Almeno 20 casi totali con JSON, codice, vincoli e recupero di informazioni; includere gli otto casi liberi e cinque fatti a contesto lungo. | Esattezza e regressioni; i casi diagnostici brevi non definiscono i 50 t/s. |
| Numerico | Attivazioni/route reali su strati iniziali, intermedi e finali; zero/uno/due job CPU, pesi zero e non uniformi, hit/miss misti, ID ai limiti. | CPU vs riferimento CPU, ibrido vs GPU, stato cache. |
| MTP | Uno/due/tre token; stesso esperto su token diversi; accettazione piena, rifiuto parziale/totale e ripartenza. | Somme per token, KV/stati ricorrenti, ammissioni e graph corretti. |
| Prefill | Circa 32k e 131k token effettivi, prompt freddo e risposta breve; 250k solo dopo stabilità a 131k. | Velocità integrale, memoria, qualità di recupero. |

L'output troncato nel solo ragionamento non supera la qualità. Un caso che termina presto viene conservato con token effettivi e stato di fine; non si selezionano a posteriori soltanto risposte lunghe o fortunate. I test numerici in teacher forcing fissano la continuazione per isolare il calcolo; le risposte autoregressive servono invece a misurare il comportamento reale, che può cambiare fra CPU e GPU.

**Numero di prove e isolamento.** Screening: tre coppie di processi A/B, alternando l'ordine, con due richieste di riscaldamento identiche e lo stesso ordine delle fixture. P4 seleziona un solo candidato fra quattro/sei core e uno/due esperti CPU prima della conferma. Conferma: almeno cinque coppie indipendenti sul candidato selezionato; eventuali estensioni sono motivate da variabilità o errori, non dal desiderio di ottenere un numero migliore. Prefill lungo: tre coppie iniziali a ogni lunghezza; estendere se vicino alla soglia o rumoroso.

Ogni processo misura la stessa sequenza completa. Il processo/coppia è l'unità indipendente: 80 gruppi di replay o più richieste dello stesso server non diventano 80 prove indipendenti. Calcolare il rapporto per coppia, la mediana e un intervallo bootstrap al 95% sulle coppie; con cinque coppie l'incertezza va esplicitata. Riportare anche i singoli valori. I percentili di piccoli campioni non sono una garanzia sulle code di latenza.

Benchmark seriali, nessun altro server avviato dal banco e nessuna compilazione o sonda concorrente. Registrare uso CPU/GPU, clock/temperature e pressione memoria; non terminare attività dell'utente per migliorare il risultato. Se il carico rende una coppia non confrontabile, conservarla come invalida con motivo e ripetere l'intera coppia. Rilevare prestazioni senza profiler; Nsight è una sessione diagnostica separata.

**D14 e D15 (registrate il 14/9, vedi tabella delle decisioni del [registro](REGISTRO_CPU_GPU_14_SETTEMBRE.md)).** L'ordine delle prove è vincolato da **D14**: si lancia PRIMA il candidato B contro il riferimento già noto; se B mostra il vantaggio, il lato A non si esegue; se non lo mostra, si esegue anche A per distinguere una regressione generale da una specifica del candidato — niente batterie di controllo lunghe senza un candidato pronto. Questo ha chiuso la misura di variabilità della baseline di P0 dopo tre blocchi invece del programma completo di D12. Per **D15**, con `--reasoning on` e i budget di screening la rubrica di qualità sui liberi non è applicabile finché il testo finale è vuoto: la qualità dei liberi si valuta solo in conferma (P6), lo screening misura la sola velocità.

**Metriche obbligatorie.**

| Ambito | Dati da conservare |
|---|---|
| Generazione | Token accettati finali, durata di generazione che include draft/verifica/attese CPU, `predicted_n`, timing server originale, durata totale HTTP, motivo di fine. Separare token di ragionamento e testo finale quando disponibili. |
| Esperienza chat | TTFT del primo delta generato e del primo testo finale visibile, latenza totale del turno, append/secondo turno e riuso del prefisso. I chunk SSE non sono token. |
| Prefill | `prompt_n` effettivo, `cache_n`, tempo totale del prompt, batch/ubatch, t/s integrali. Nessun picco dei primi blocchi sostituisce la misura completa. |
| CPU/GPU | Coppie token/esperto CPU, unici mancanti GPU/CPU, byte realmente caricati, attese, ricatture del graph e motivo dei fallback. Strumentazione dettagliata solo diagnostica. |
| MTP | Draft proposti/accettati per tipo e, dove possibile, posizione; numero di verifiche, rollback e token finali utili. Il tempo dei draft rifiutati resta nel denominatore. |
| Memoria/stabilità | Picchi RAM/pinned/VRAM, minimo margine VRAM, page fault/paging se osservabile, OOM, timeout, errori CUDA, CPU a riposo e dopo il prefill. |
| Qualità | Output completo e hash, esito delle rubriche/test, NLL quando misurata, errori numerici per caso/strato. L'hash è prova di identità, non una misura generale di qualità. |

Il throughput di un insieme è `somma(token accettati) / somma(tempo di generazione)`, non la media aritmetica dei t/s dei casi. Prima di usare il timing del server, verificare che includa realmente CPU, coordinamento e speculazione confrontandolo con l'orologio della richiesta. Se il campo esistente esclude una fase, correggere lo strumento: non dichiarare 50 sulla sola durata dei matmul. La stima client fra chunk rimane una metrica distinta e dichiarata approssimata.

Il PCIe esposto dal driver è diagnostico: il test precedente ha mostrato che non coincide direttamente col payload dei pesi. Non si ricava il tasso di hit dividendo quel contatore per la dimensione degli esperti.

**Criteri di uscita, da applicare insieme.**

| Verifica | Criterio iniziale |
|---|---|
| Stato e memoria | Zero mapping invalidi/residenti fantasma/doppie somme, NaN, accessi invalidi, stalli e OOM nella batteria. Un errore strutturale ferma subito la cella. |
| Funzione spenta | Output e stato cache del percorso precedente invariati nei casi deterministici; costo non superiore all'1% oltre il rumore misurato. |
| CPU vs CPU | Identità nei percorsi con lo stesso ordine aritmetico; ogni differenza nuova va spiegata e confrontata prima di cambiare la tolleranza. |
| CPU/GPU numerico | Per gli stessi fixture del prototipo non peggiorare senza spiegazione l'errore verificato. La soglia NRMSE 0,05 della sonda è solo un rilevatore di guasti, non un gate di qualità del modello. |
| Qualità del modello | Nessuna nuova violazione dei casi esatti. Valutazione delle risposte libere con rubrica congelata e confronto cieco rispetto al preset. In teacher forcing, target iniziale: aumento NLL media non oltre 0,01 nat/token su almeno 4096 token fissi, con CPU realmente attiva e incertezza riportata. Un risultato inconclusivo non è un pass. |
| Decode utile | Almeno +5% sull'aggregato libero contro la stessa build con CPU spenta, intervallo del confronto sopra 1 e nessuna regressione sistematica oltre il 5% in un dominio/contesto senza spiegazione. È una soglia di adozione, non il target finale. |
| MTP | Qualità e stati corretti; variazioni di accettazione oltre 2 punti percentuali da indagare. L'accettazione da sola non decide: contano token utili/tempo e qualità. |
| Prefill | Regressione non superiore al 3% rispetto al controllo omogeneo, tenendo conto del rumore. Oltre 400 a 32k e 131k viene dichiarato separatamente e soltanto dopo il completamento delle rispettive prove fredde. |
| Stabilità finale | Almeno 30 minuti con sequenza riproducibile di richieste, annullamento, secondo turno, cambio taglia e prefill/decode; memoria che torna al livello previsto dopo la pulizia. Solo sul candidato che ha superato i test brevi. |

La misura NLL deve esercitare il ramo CPU: un tool di perplexity che usa soltanto grandi batch GPU non valida questa modifica. Se manca un percorso adeguato, adattare prima il banco a token fissati e contare i job CPU. Un accordo top-1 alto o il recupero 5/5 di fatti non sostituisce le altre verifiche.

Per dichiarare **50 t/s** consolidati: candidato validato, cinque coppie indipendenti, mediana dell'aggregato libero almeno 50 t/s al contesto dichiarato e limite inferiore dell'intervallo al 95% almeno 50; risultati per ogni consegna e contesto pubblicati. Se la mediana supera 50 ma l'intervallo attraversa la soglia, si riporta il risultato come ancora incerto. Se solo alcuni casi superano 50, si dichiara quello. I token di ragionamento conteggiati dal motore restano visibili come tali; non si presenta quella velocità come sola scrittura della risposta finale.

**Strumenti da riusare, con adattamenti espliciti.**

- [run_http.py](C:/Users/imanu/Documents/Codex/2026-09-13/rip/work/speed_target/run_http.py) e [banco_fresh.py](C:/Users/imanu/Documents/Codex/2026-09-13/rip/work/speed_target/banco_fresh.py): attesa readiness, HTTP e timing; aggiungere fixture congelate, preset comuni, stato cache e metriche richieste. La chiave viene letta localmente e mai esportata.
- [bench_code.py](C:/Users/imanu/Documents/Codex/2026-09-13/rip/work/speed_target/bench_code.py): copia/rename e output, tenuti fuori dal punteggio libero.
- [replay_cache.py](C:/Users/imanu/Documents/Codex/2026-09-13/rip/work/freetoken_audit/replay_cache.py): riferimento della politica attuale; estendere con l'ammissione CPU senza perdere il controllo CPU=0.
- [cpu_test.cpp](C:/Users/imanu/Documents/Codex/2026-09-13/rip/work/freetoken_hybrid/cpu_test.cpp) e [overlap_probe.cu](C:/Users/imanu/Documents/Codex/2026-09-13/rip/work/freetoken_hybrid/overlap_probe.cu): controlli numerici e di comunicazione; aggiungere route/attivazioni reali e le forme del server, senza sostituirli a un test completo.
- [collect_results.py](C:/Users/imanu/Documents/Codex/2026-09-13/rip/work/speed_target/collect_results.py): modello per aggregazione e manifest; usare una nuova destinazione, non rigenerare le vecchie evidenze sopra gli originali.

**Formato per ogni run.** Cartella univoca `data_ora_fase_variante_replica`, con `manifest.json`, `config.redacted.json`, `prompts.json`, `results.jsonl`, output, log puliti, eventuale `failure.json` e riepilogo. Le directory e lo schema verranno creati dal banco P0: qui sono una specifica, non file di test già prodotti. Campi minimi: ID run/preset/prompt, revisione e hash, forma token, CPU cap/core, stato cache, MTP/ngram, conteggi/tempi originali, metriche derivate, qualità, memoria, validità e motivo di esclusione.

Conservare tutti i tentativi, compresi timeout e prove interrotte; archivi con manifest SHA256. Escludere API key, launcher non ripuliti e tracce contenenti credenziali. Prima di chiudere una sessione, collegare le prove al registro, aggiornare l'handoff e verificare i link. Le soglie cambiano solo con una nuova decisione motivata registrata **prima** di rieseguire il candidato.
