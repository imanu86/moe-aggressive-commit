# Piano CPU/GPU verso 50 t/s e prefill oltre 400

Versione 1.0, 14 settembre 2026. Stato: **piano documentato; integrazione nel server da iniziare**. Responsabile tecnico: agente principale; agenti economici per analisi circoscritte e review indipendenti. Una sola modifica al percorso critico e un solo benchmark prestazionale alla volta.

Questo documento governa la prossima integrazione sperimentale. [Protocollo delle misure](PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md) e [registro di avanzamento e decisioni](REGISTRO_CPU_GPU_14_SETTEMBRE.md) fanno parte dello stesso piano. I criteri numerici sotto sono **soglie di lavoro proposte**, fissate prima delle prove; non risultati già ottenuti né una garanzia di raggiungere 50 t/s.

**Obiettivo e punto di partenza.** Portare nel server il lavoro concorrente di pochi esperti CPU e della GPU, conservando i pesi GGUF correnti. Misurare poi quanto resta del divario verso 20 ms per token accettato, equivalenti a 50 t/s di generazione. Per il prefill, consolidare oltre 400 t/s a 32k e perseguirlo anche a 131k; 250k rimane un'estensione successiva con un proprio risultato, senza estrapolazioni.

| Evidenza verificata | Implicazione per il piano |
|---|---|
| Risposta libera: 25,08 t/s nella configurazione combinata; altro assetto: 27,26 | Riferimenti storici con configurazioni differenti. P0 deve costruire un A/B nuovo e omogeneo. |
| Copia di codice: 39,19 t/s | Banco separato, favorito dagli n-grammi; non è il riferimento della risposta libera. |
| Prefill freddo: 414,83 t/s a 32k; 357,61 a 131k | Il target è già osservato a 32k, non a 131k. |
| Tre miss, due esperti CPU, quattro core: 337 -> 242 microsecondi | Risultato di un blocco, con 16 invocazioni prima della sincronizzazione. Il server deve confermarlo. |
| Controlli a invocazione singola: vantaggio con maggiore variabilità | Confrontare quattro e sei core alla cadenza reale; nessun conteggio universale deciso dal microbench. |
| CPU fusa bit-identica al riferimento CPU nei casi verificati; diversa dalla CUDA | Servono controlli numerici e di qualità; l'identità del testo non basta come unico criterio. |
| Formati e forme compatibili in 47/48 strati | Primo perimetro: IQ2_S gate/up, IQ4_NL down. Strato 2 IQ3_S resta sulla GPU. |
| Cache attuale: 75,55% hit caldi; LRU ideale a pari memoria non migliore | Conservare la regola di frequenza decaduta/recenza; cambiare esplicitamente solo l'ammissione dei miss CPU. |

Le fonti sono il [rapporto del prototipo](FREETOKEN_IBRIDO_13_SETTEMBRE.md), il [rapporto FreeToken/Bonsai](FREETOKEN_BONSAI_13_SETTEMBRE.md), il [rapporto delle prestazioni complete](C:/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/VERSO_50_TPS_400_PREFILL_13_SETTEMBRE_CODEX.md) e i rispettivi archivi di prove del 13 settembre. Il motore FreeToken completo non è stato eseguito su questo GGUF. Download Q4, doppie copie di pesi e nuovi formati restano rinviati.

**Architettura iniziale scelta.** Il primo percorso attivo riguarda un token, una sequenza, una GPU, al massimo due esperti CPU per strato, con pesi originali già nella RAM pinnata. Un pool condiviso dal contesto serve gli strati in sequenza; niente pool di quattro/sei thread per ciascuno dei 48 strati. Il coordinatore ha buffer persistenti e un proprietario seriale; tra richieste e durante il prefill deve poter dormire.

La GPU determina le richieste logiche e distingue hit, miss da caricare e miss da calcolare sulla CPU. La CPU riceve attivazione, ID e pesi di routing tramite memoria mappata e callback brevi; mentre lavora, la GPU carica e calcola il proprio insieme. I contributi CPU pesati vengono aggiunti una volta sola dopo la riduzione degli esperti GPU. Shared expert, router e resto del blocco mantengono il proprio percorso.

Il primo ramo richiede forme/tipi supportati, banche contigue separate e SiLU, senza LoRA, bias o scale aggiuntive degli esperti, gate/up uniti o pesatura prima dell'FFN. Gli altri casi usano il percorso precedente prima di modificare il piano. Queste guardie vanno controllate nel modello effettivo, non dedotte dal solo nome commerciale.

Per la prima integrazione teniamo le dieci righe GPU e la topologia del graph fisse. Una route servita dalla CPU usa sul lato GPU uno slot valido già disponibile, con **peso GPU zero**; gli ID e i pesi originali restano separati per il calcolo CPU e per la contabilità della cache. Questo evita di introdurre subito ID negativi o un nuovo significato di `src[3]` nei kernel. La GPU farà calcoli fittizi su quelle righe: il loro costo deve essere misurato, perché il prototipo riduceva realmente il numero di righe GPU. Se il costo giustifica un altro intervento, solo dopo P4 si aggiunge una maschera verificata che salti il calcolo prima di leggere i pesi.

La maschera si applica dopo l'eventuale normalizzazione e scala originali del routing: **i pesi GPU rimanenti non vengono rinormalizzati**. Si verifica anche che le fusioni CUDA della riduzione consumino il nuovo tensore mascherato. Il punto della somma CPU è `moe_out` dopo la pesatura delle righe e la loro riduzione, prima del ritorno di `build_moe_ffn` e quindi prima dello shared expert in [qwen4exp.cpp](C:/Users/imanu/Documents/Codex/2026-09-09/c-users-imanu-source-repos-moe/work/qwen38_clean/source/src/models/qwen4exp.cpp). Il contributo CPU non passa una seconda volta nella moltiplicazione per i pesi degli esperti.

Il limite iniziale di due esperti CPU lascia almeno una route GPU reale da usare come riferimento valido. Se una futura generalizzazione elimina questa proprietà, deve introdurre un percorso apposito; non può riutilizzare implicitamente lo slot zero.

Il selettore deve rendere espliciti sia il numero sia l'identità dei miss CPU. In P3 usa un ordine deterministico documentato per isolare l'integrazione; P4 può confrontarlo con una scelta basata su costo e riuso osservati. Saltare l'ammissione di un esperto richiesto spesso può annullare il risparmio del passo corrente: la sequenza completa di richieste decide, non il solo numero di miss.

P2 produce anche una tabella delle allocazioni per contesto, strato, numero di token e graph conservato: byte teorici, picchi misurati e momento del rilascio. Si riusano i pesi host originali e si limita il numero di buffer persistenti; il codice non deve accumulare un nuovo buffer per ogni replay. Non si riducono gli slot della cache o il margine di memoria del prefill per nascondere una nuova allocazione. P6 misura esplicitamente l'interazione con staging, rollback e memoria a 131k.

**Invarianti che non possono essere violati.**

1. `richieste uniche = hit GPU + miss GPU + miss CPU`. I conteggi di coppie token/esperto sono separati da quelli degli esperti unici.
2. Un esperto CPU non riceve un'ammissione GPU fittizia. Solo trasferimenti effettivamente completati possono diventare residenti nelle tre banche.
3. Tutte le richieste logiche partecipano alla frequenza/decadimento con la semantica attuale; recenza degli slot e ammissione riguardano solo slot validi. La classifica LFU non viene sostituita da LRU.
4. Hit correnti protetti, mapping expert/slot reciproco, tre banche riferite allo stesso esperto; nessun dato parzialmente caricato può essere consumato.
5. Ogni coppia token/esperto contribuisce esattamente una volta con il peso originale. Le copie dei pesi possono essere deduplicate, il calcolo su token diversi no.
6. Nessun callback usa API CUDA o attende un mutex trattenuto dal thread che aspetta il graph. Buffer e proprietari vivono fino al completamento degli utilizzatori CPU e GPU e alla distruzione dei graph che li referenziano.
7. Un errore durante un job invalida la richiesta: non si restituiscono zeri come risultato e non si dichiara completato un trasferimento. Il fallback GPU è scelto prima dell'invio per i casi non supportati; il recupero da un errore in volo richiede annullamento e pulizia espliciti.

Un dettaglio verificato nel codice impone P1: `moe_grouped_plan_decode()` applica l'ammissione del piano precedente **alla chiamata successiva**. Non basta ridurre il gather: vanno separati ammissioni, aggiornamenti di frequenza e route CPU anche in quella fase differita.

Il contratto concreto di P1 mantiene gli ID logici originali in ingresso: classifica hit/miss, partiziona i miss CPU/GPU **prima dell'assegnazione degli slot e del gather**, poi produce separatamente job CPU, ammissioni GPU e ID GPU rimappati. Gli array di trasferimento e commit contengono solo miss GPU; gli aggiornamenti logici di frequenza conservano anche quelli CPU. Solo negli ID di calcolo GPU una route CPU viene sostituita con lo slot di una route GPU reale della richiesta corrente, protetto dal piano e con tutte le banche pronte prima del consumo. Non si usa uno slot arbitrario e non si riserva capacità aggiuntiva della cache. Sostituire gli ID originali prima della contabilità logica perderebbe informazione; azzerare solo il peso dopo il vecchio planner continuerebbe invece a trasferire tutti i miss.

| Fase | Lavoro concreto | Consegna e condizione per proseguire |
|---|---|---|
| **P0 — Base riproducibile** | Snapshot del sorgente sperimentale attuale e build separata; manifest di binari, preset e modello; congelare prompt/token/template; preparare il banco A/B e il controllo del carico macchina. | Preset A/B leggibili, input identici, baseline nuova e variabilità note. Nessuna sostituzione di `bin_prod`. |
| **P1 — Contratto e simulatore della cache** | Specificare richieste logiche, miss CPU/GPU, ammissioni differite e recenza. Estendere il simulatore indipendente e i contatori; testare cambi di vittima, saturazione, riuso e invalidazione delle incarnazioni della cache. | Con CPU=0: riproduzione dei 36.913 piani storici senza differenze. Con CPU>0: nessun residente fantasma, stessi invarianti nel riferimento e nel kernel; non si pretende lo stesso hit rate della vecchia ammissione. |
| **P2 — Esecutore e durata degli oggetti** | Adattare il prototipo a un'interfaccia host esplicita; unico pool per contesto, buffer persistenti, job con generazione/stato, attesa inattiva fuori decode, errore/cancel/teardown. Verificare puntatori host e alias device reali senza duplicare i pesi. | Parità col riferimento CPU sui casi supportati, nessuna chiamata concorrente allo stesso pool; prove di cancellazione, cambio contesto e distruzione senza stallo o riuso anticipato. |
| **P3 — Un solo strato nel server, MTP spento** | Prima modalità diagnostica che confronta il contributo CPU col percorso GPU completo, poi modalità attiva con righe fittizie a peso GPU zero. Cattura/replay reali e fallback dello strato 2. | Matematica e cache corrette su route reali, graph riutilizzato, zero NaN/errori; feature spenta neutra. Le misure diagnostiche non sono benchmark di velocità. |
| **P4 — Decode completo a un token** | Estendere ai 47 strati supportati. Provare limiti CPU 0/1/2 e quattro/sei core; misurare anche la contesa con thread server e banda RAM. Selezionare un preset prima della conferma A/B. | Banco completo e qualità superati; miglioramento utile rispetto al controllo della stessa build, misurato senza profiler. Se il guadagno scompare, localizzare il costo prima di estendere il sistema. |
| **P5 — MTP e interazione n-gram** | Portare il contratto a due/tre token, mantenendo conteggi di esperti unici e job per token distinti. Verificare accettazione totale, rifiuto parziale/totale, rollback, cambio forma del graph e transizione prefill/decode. | Stati KV/ricorrenti coerenti dopo rifiuto e replay; nessun riuso di un job vecchio; target e draft distinti. Il massimo di tre token resta invariato. |
| **P6 — Conferma e scelta del preset** | A/B abbinato con MTP acceso e spento; prosa, ragionamento e codice nuovo; copia/rename separati; prefill 32k/131k, più turni e pressione memoria. Stabilità prolungata solo del candidato finale. | Rapporto conclusivo con risultati validi, fallimenti e incertezza; confronto qualità/velocità; rollback verificato. La promozione usa un preset separato e la procedura di cambio esplicitamente concordata. |
| **P7 — Divario residuo verso 50/400** | Riprofilare il candidato sul percorso critico reale. Selezionare la prossima leva tra matvec Q6_K residenti, costo della verifica speculativa e batch/staging del prefill lungo. | Una nuova ipotesi e un A/B isolato per volta. Il guadagno del blocco CPU non viene moltiplicato per tutto il modello. |

```mermaid
flowchart LR
    P0["P0: baseline"] --> P1["P1: cache"]
    P1 --> P2["P2: esecutore"]
    P2 --> P3["P3: uno strato"]
    P3 --> P4["P4: decode completo"]
    P4 --> P5["P5: MTP"]
    P5 --> P6["P6: conferma"]
    P6 --> P7["P7: divario residuo"]
```

P1 e la preparazione delle fixture di qualità possono essere studiati in parallelo; le modifiche a cache/graph e i benchmark restano seriali. L'agente principale integra e decide. Le review economiche verificano invarianti o risultati circoscritti; non eseguono benchmark simultanei e non promuovono preset autonomamente.

**Interfacce e file da toccare.** Le posizioni sono quelle lette il 14 settembre; prima delle modifiche si verifica il manifest.

| Punto | Responsabilità prevista |
|---|---|
| [llama-graph.cpp:2062](C:/Users/imanu/Documents/Codex/2026-09-09/c-users-imanu-source-repos-moe/work/qwen38_clean/source/src/llama-graph.cpp:2062) | Preservare ID/pesi originali; peso GPU mascherato distinto; aggiunta del contributo CPU nel punto corretto della riduzione. |
| [moe-demand.cuh:226](C:/Users/imanu/Documents/Codex/2026-09-09/c-users-imanu-source-repos-moe/work/qwen38_clean/source/ggml/src/ggml-cuda/moe-demand.cuh:226) | Collegamento cache demand, tre banche, preparazione job, gather dei soli miss GPU e dipendenze fra stream. |
| [fork-moe-kernels.cuh:217](C:/Users/imanu/Documents/Codex/2026-09-09/c-users-imanu-source-repos-moe/work/qwen38_clean/source/ggml/src/ggml-cuda/fork-moe-kernels.cuh:217) | Ammissione differita, frequenza, mapping e rappresentazione esplicita dei miss CPU. |
| [ggml-cuda.cu:3666](C:/Users/imanu/Documents/Codex/2026-09-09/c-users-imanu-source-repos-moe/work/qwen38_clean/source/ggml/src/ggml-cuda/ggml-cuda.cu:3666) | Invalidazione dei graph e rilascio della memoria transitoria; rispetto della cattura esistente. |
| [fused_cpu.hpp](C:/Users/imanu/Documents/Codex/2026-09-13/rip/work/freetoken_hybrid/fused_cpu.hpp) | Base dell'esecutore; ownership seriale, quantizzazione delle attivazioni, barriere, somma e gestione dell'inattività. |

P2 deve scegliere il confine d'interfaccia più piccolo compatibile con i backend esistenti: il CUDA backend programma il graph; un contratto host possiede il pool e offre submit/wait/status. La lettura della struttura interna del backend fatta dal microbenchmark non diventa un'API del server. Nessuna disattivazione globale dei CUDA graph: quella della sonda serviva solo alla sua cattura esterna.

Le opzioni di controllo saranno introdotte e documentate in P3: abilitazione, elenco strati, massimo esperti CPU, core, diagnostica. **Non esistono ancora flag CLI/env dell'integrazione**; il nome verrà fissato nella patch. Default spento; riavvio del processo richiesto per cambiare questi parametri nella prima versione.

**Come fermare una pista senza perdere lavoro.** Corruzione della cache, stallo, NaN o errore di memoria interrompono subito la cella e aprono una voce nel registro. Nessun benchmark lungo prima di correggere il difetto. Se dopo una conferma omogenea il vantaggio completo è sotto il 3% o indistinguibile dal rumore, si conserva il risultato e si passa alla leva successiva, senza continuare ad aggiungere complessità alla CPU. Fra 3% e 5% la decisione resta aperta e dipende dal costo e dalla stabilità. Per candidare il preset all'uso si cerca almeno il 5% sul banco libero, intervallo di confidenza favorevole e qualità invariata secondo il protocollo.

L'ottimizzazione CPU può migliorare un risultato senza completare l'obiettivo. Il traguardo 50 t/s sarà dichiarato soltanto sulla batteria di generazione libera definita nel protocollo; i risultati per contesto e per tipo di risposta resteranno visibili. Il prefill a 131k e l'eventuale 250k avranno verifiche separate.

**Documentazione permanente.** Il repository contiene la copia canonica di piano, protocollo e registro in `docs/porto`. Ogni sessione aggiorna fase, modifiche, comandi riproducibili senza credenziali, manifest, prove valide/non valide e prossimo passo. Gli artefatti grezzi sono immutabili per run; il riepilogo non sovrascrive i dati. L'handoff punta sempre allo stato più recente. Le copie in `outputs` sono quelle consegnate all'utente.
