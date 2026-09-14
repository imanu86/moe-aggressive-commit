# Verso 50 t/s e prefill oltre 400 — 13 settembre 2026

Macchina: RTX 3060 12 GB, Ryzen 5800X, 96 GB DDR4, Windows. Modello Qwen3.8 Flash Next UD-IQ3_XXS, cache di 64 esperti per strato. Questa nota prosegue il controllo della cache descritto in RIPRESA_CACHE_13_SETTEMBRE.md.

## Risultato e limiti

Il prefill ha superato 400 t/s a 32k anche con MTP attivo: **414,83 t/s** su 32.139 token, cache del prompt vuota, batch 2048 e staging asincrono. La configurazione contiene anche GDN a tile e n-gram con due stati di rollback. Questo valore non dimostra oltre 400 a 131k o 250k.

Con MTP attivo, batch 4096 e il kernel GDN sperimentale, lo stesso banco da 32k ha dato 390,93 t/s di prefill e 27,26 t/s in generazione su 768 token. Questi numeri sono misure complete del server, non la velocità di un singolo kernel.

La copia di codice raggiunge **39,19 t/s** e la modifica di un identificatore **37,76 t/s**, contro 30,39 e 30,57 del riferimento MTP. Entrambe producono esattamente lo stesso prefisso di codice del riferimento, su 1024 token di output. Sono prove troncate al budget, non riscritture complete del file.

Il traguardo dei **50 t/s di generazione generale resta aperto**. Nel banco di risposta libera a 32k la configurazione combinata ha dato 25,08 t/s, sotto il riferimento da 27,26. La risposta generata differisce e i due batch non sono uguali: questo non isola la causa della regressione. Dimostra però che non è corretto raccomandare la configurazione come accelerazione generale.

| Configurazione | Caso | Prefill t/s | Generazione t/s |
|---|---|---:|---:|
| MTP, GDN, batch 4096 | 32k, 768 token generati | 390,93 | 27,26 |
| MTP + n-gram + rollback + staging, batch 2048 | 32k, 768 token generati | **414,83** | 25,08 |
| MTP, GDN, batch 4096 | Copia, 1024 token | 392,85 | 30,39 |
| MTP + n-gram attivo, batch 2048 | Copia, 1024 token | 342,19 | 34,93 |
| MTP + n-gram + rollback + staging, batch 2048 | Copia, 1024 token | **406,36** | **39,19** |
| MTP, GDN, batch 4096 | Rinomina, 1024 token | 404,05 | 30,57 |
| MTP + n-gram attivo, batch 2048 | Rinomina, 1024 token | 360,72 | 33,85 |
| MTP + n-gram + rollback + staging, batch 2048 | Rinomina, 1024 token | **430,25** | **37,76** |

Il controllo n-gram usa `QWEN_PREFETCH_EXPERTS=2`: gli stessi grandi graph di prefill sono disabilitati, ma i pesi seguono il percorso di copia precedente. Nel successivo binario lo staging ha ricevuto una correzione sul padding, attiva solo nel ramo sperimentale. Questi test del server non sono un confronto A/B perfettamente isolato di ogni singola leva.

### Contesto lungo e recupero delle informazioni

La prova completa a 131k ha misurato **357,61 t/s su 131.310 token effettivi**, `cache_n=0`, in 367,19 secondi di prefill. Il riempimento contiene 131.072 token prima delle istruzioni e dei cinque fatti aggiunti. Tutte le cinque risposte finali recuperano il fatto richiesto, nelle posizioni nominali 5/25/50/75/95%, senza troncamento. Le posizioni sono inserite per frazione di caratteri, non sono percentuali esatte dei token. Le domande successive riusano il prompt e non vanno trattate come altre misure di prefill freddo.

Il riferimento storico dell'handoff era 294,95 t/s a 131k con MTP spento: il nuovo valore è circa il 21% maggiore, ma cambia anche il prompt di prova e non è un A/B isolato. I **400 t/s a 131k/250k non sono raggiunti**. A 120k restavano circa 1,2 GiB di VRAM libera durante il prefill; in decode a 131k circa 664 MiB. Non si è verificato il crollo osservato nel tentativo a batch 8192.

La domanda tecnica aggiuntiva ha consumato 768 token nel ragionamento senza risposta finale: è **inconclusiva**, non un gate di qualità superato. Un retry con thinking disattivato ha cambiato il template, invalidando il prompt cache; è stato fermato durante il nuovo prefill. Non costituisce una misura. Il test 5/5 dimostra il recupero di questi fatti; non dimostra l'equivalenza generale del modello su ragionamento e codice lungo.

## Cosa è stato misurato

Le richieste usano greedy, seed 1234, una sola sequenza e `cache_prompt=false`. Il conteggio `cache_n=0` è conservato nei risultati. I test di codice diretti disattivano il thinking; i primi test con thinking attivo avevano consumato quasi tutto il budget nel ragionamento e non costituiscono una misura valida della copia.

Il passaggio batch 2048 → 4096 ha dato 327,33 → 410,48 t/s nel banco 32k senza MTP. Il riferimento 2048 era avviato dal wrapper Nsight, con raccolta disattivata: il confronto non isola perfettamente il solo batch. Il riferimento storico dell'handoff era circa 337,5 t/s.

Il tentativo batch 8192 a 131k è stato interrotto: la velocità cumulativa iniziale era circa 483 t/s a 24.618 token, ma il successivo blocco ha richiesto 51,18 secondi contro circa 16,8. La workspace CUDA era salita a 7.451 MiB e la memoria libera rilevata a circa 394 MiB. La velocità cumulativa a 32.810 token era scesa a 319,70 t/s. È compatibile con pressione di VRAM/paging WDDM; non è una misura riuscita a 131k. Un batch grande fisso non è una soluzione sufficiente per il contesto lungo.

## Quattro interventi concreti

### Kernel Gated DeltaNet a tile

Il port parte dal kernel pubblico di [pwilkin, commit 964c6f2f0](https://github.com/pwilkin/llama.cpp/commit/964c6f2f0). L'abilitazione locale è `QWEN_GDN_TILED=1`, con controlli sulla GPU SM86, dimensione di stato 128, 48 teste V/16 QK, una sequenza, assenza di KDA, lunghezza 16–8192 e stati di rollback 1–5. Il default è spento.

Il microbenchmark usa il kernel originale locale e quello a tile, q/k normalizzati, stato iniziale non nullo e lo stride reale del tensore V. Verifica output e tutti gli stati intermedi, compresi tile incompleti. Nei casi eseguiti la differenza massima è zero. A 2048 token il kernel passa da circa 12 a 7 ms; a 8192 da circa 49,2 a 27,4 ms. Il guadagno del singolo kernel è circa 1,7–1,8×. Non va moltiplicato per l'intero modello: GDN occupava circa il 10,45% del tempo sommato dei kernel nel profilo prefill a 2k.

### Correzione del draft n-gram corto

Il ramo `ngram-simple` rifiutava una proposta se `copy_max < size_ngram`. Con N=12 e M=2 la condizione era sempre vera: zero proposte, pur con parametri accettati dal CLI. La patch permette una continuazione non vuota anche se è più corta della finestra cercata.

Il test CPU riproduce il difetto sul codice originale e verifica la libreria ricompilata: con una storia ripetuta e ultimo token 2, sia N=12/M=2 sia N=2/M=2 restituiscono `[3,4]`. Il test del server controlla anche che vengano effettivamente generati e accettati draft n-gram. La vecchia corsa `mtp_ngram2` va conservata come controllo con più stati allocati, non come prova della velocità di un n-gram funzionante.

### Stato di rollback coerente con il draft n-gram

La configurazione degli stati ricorrenti considerava solo la lunghezza del draft MTP, pari a 1. Con n-gram da 2, il server salvava quindi un checkpoint host di circa 112,57 MiB prima di ogni verifica di due proposte. La patch `QWEN_NGRAM_ROLLBACK=1` riserva due stati per i soli n-gram brevi da 1–2 token. Le configurazioni normali con n-gram da 48 non vengono allargate.

Otto test CPU coprono l'attivazione, la disattivazione, il caso senza n-gram, la conservazione di una riserva MTP più grande e il limite sui draft lunghi. Il log del modello conferma `n_rs_seq=2`: il buffer RS CUDA passa da 225,14 a 337,71 MiB, cioè **112,57 MiB aggiuntivi**. Le API recurrent, hybrid-index e GDN supportano il rollback di due token. Nel test di copia l'output e i conteggi 684 draft/676 accettati restano identici. Il costo non attribuito dalle quattro fasi del profiler scende da circa 11–12 a circa 1–2 ms per ciclo stabile, in linea con l'eliminazione del checkpoint per le proposte brevi.

### Trasferimento asincrono degli esperti nel prefill

L'idea è documentata nel [fork thecodacus](https://github.com/thecodacus/llama.cpp/tree/fable5/prefetch-experts), che misura un altro modello, più piccolo. Non si trasferiscono qui i suoi guadagni percentuali. I pesi host del nostro modello risultavano già allocati come CUDA_Host: aggiungere pinning non era una nuova ottimizzazione.

Il prototipo locale usa due buffer CUDA temporanei, circa 645 MiB complessivi, e un secondo stream sullo stesso device. Avvia la copia di un tensore di esperti prima di attendere il calcolo precedente. Eventi CUDA proteggono upload, consumo e riutilizzo. A fine valutazione libera i buffer, prima del ripristino della cache esperti di decode. Il percorso è limitato a grandi MUL_MAT_ID con 512 esperti, pesi host immutabili e nessuna callback.

`QWEN_PREFETCH_EXPERTS=1` abilita lo staging; `=2` è il controllo con gli stessi graph di prefill disattivati ma senza staging; `=0` mantiene il percorso precedente. I graph CUDA dei piccoli batch di decode restano disponibili. Disabilitare i graph interessati è necessario perché la cache locale dei graph può riusare puntatori a buffer che al termine dell'eval vengono liberati.

Il primo tentativo è terminato con un assert sul padding: l'API dei tensori non permette di scrivere oltre la dimensione logica. Il trasferimento ora descrive l'intera allocazione come un tensore di byte, includendo la coda azzerata. Il test piccolo usa tre pesi Q4_0 distinti con padding, tutti i 512 esperti e tre valutazioni: le nove impronte degli output coincidono fra staging e controllo, con verifica numerica indipendente. Nel modello completo il log conferma lo staging di **144 tensori / 46.375 MiB per blocco**, e il rilascio del ring a ogni valutazione.

## Perché la cache da sola non porta a 50

Il controllo precedente ha risolto il presunto divario fra simulatore e runtime: sullo stesso trace i piani coincidono e il hit rate caldo reale è circa 75,55%, non 41%. Non c'è un recupero gratuito di oltre 30 punti percentuali nascosto nei contatori.

Una sonda con quantità nota di dati ha misurato circa 25,71 GB/s utili col kernel gather e 24,40 GB/s con copie CUDA ordinarie. In entrambi i casi il contatore PCIe riportava valori sensibilmente maggiori. Non è corretto ricavare i miss della cache invertendo quel contatore. Le due chiamate di upload per strato servono banche diverse, non dimostrano una doppia copia degli stessi tre tensori.

Il profilo decode a contesto corto attribuisce il 24,48% del tempo sommato dei kernel agli upload degli esperti, il 22,99% alle moltiplicazioni Q6_K, il 9,85% alle IQ2_S e il 7,93% all'attenzione. Sono percentuali di durate sommate, con sovrapposizioni: non sono una scomposizione additiva del tempo reale. Il profiler rallenta inoltre la generazione, perciò i t/s dichiarati provengono dai test senza raccolta attiva.

## Sequenza di lavoro verso 50

1. Consolidare prefill a 32k, 131k e 250k con prompt freddo, distinguendo MTP acceso e spento. La prossima leva è scegliere il batch in funzione del contesto e della workspace disponibile, combinando batch più grandi all'inizio con staging e batch più piccoli in profondità. Il limite di VRAM va rispettato per l'intero prompt.
2. Conservare l'n-gram come percorso per copia/modifica quando l'accettazione è alta, con MTP come fallback. Misurare separatamente prosa e ragionamento, dove il testo precedente può non offrire continuazioni utili.
3. Ridurre il costo della verifica a più token. Il percorso veloce locale ha guardie a tre token in più componenti: cache esperti, CUDA MMVQ, costruzione del grafo, pool dell'indexer e rollback. Allungare soltanto il draft farebbe ricadere nel percorso costoso. Estendere a 5–6 token richiede un intervento coordinato e confronti di correttezza sul rifiuto parziale dei draft.
4. Profilare i grandi matvec Q6_K residenti, separando output head e proiezioni, e migliorare il riuso dei pesi fra le righe di verifica. Dopo la correzione del rollback il target decode domina il ciclo dei test di codice. Queste misure decidono dove intervenire prima di cambiare quantizzazione o ridurre la qualità del modello.

Per la risposta libera occorre anche una bozza più accurata: l'accettazione MTP nel banco attuale è circa 70–75%. Allungare il draft non garantisce più token utili. Un confronto fra testa MTP condivisa e non condivisa, oppure un draft addestrato meglio, va giudicato per accettazione a ogni posizione e tempo complessivo, non per il solo costo della testa.

Il criterio di successo in generazione è 20 ms per token accettato, misurato sull'intera risposta. Un picco del kernel, un batch iniziale veloce o un benchmark sintetico ad accettazione forzata non soddisfano l'obiettivo.

## Stato dei file

Le patch sono sperimentali. I binari `bin_prod` e il lanciatore di produzione non sono stati aggiornati. Non sono stati creati commit o PR. Il pacchetto di evidenze contiene risultati, sorgenti dei test validati, patch e aggregati del profiler; esclude i launcher con chiave API e i report Nsight grezzi che possono contenere argomenti del processo.

Artefatti: `speed_results.json`, `speed_evidence.zip`, `gdn_tiled.patch`, `ngram_short_draft.patch`, `ngram_rollback.patch`, `prefill_staging.patch`. Le patch sono relative al fork privato usato nella sessione e sono state verificate con `git apply --reverse --check` contro il sorgente modificato. Il file JSON conserva gli hash dei binari e dei sorgenti di partenza; lo ZIP contiene un manifest SHA-256 e la licenza del codice upstream riutilizzato. Tutti i server di prova avviati in questa sessione sono stati arrestati.
