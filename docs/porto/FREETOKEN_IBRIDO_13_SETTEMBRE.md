# FreeToken: prova dell'esecutore CPU fuso con la GPU

13 settembre 2026 — RTX 3060 12 GB, Ryzen 5800X, 96 GB DDR4, Windows build 26200, driver NVIDIA 596.21, CUDA Toolkit 12.6.

**Il prototipo funziona e individua una variante promettente:** pochi esperti sulla CPU, RAM pinnata accessibile direttamente dalla GPU e callback per coordinare i due lavori. Con tre esperti mancanti, due sulla CPU hanno ridotto il tempo del blocco testato da circa **337 a 242 microsecondi**, con quattro core fisici. Sono **tempi di un blocco MoE**, non nuovi t/s del modello completo.

La variante con copie D2H/H2D esplicite e flag del driver è risultata più lenta del riferimento. La sola fusione del calcolo CPU non basta: il risultato positivo dipende dal percorso di comunicazione e dalla sovrapposizione con la GPU.

Il riferimento di generazione libera resta quello precedente, **25,08 t/s**. I **39,19 t/s** erano copia di codice favorito dagli n-grammi. Questa prova non modifica i risultati precedenti di prefill e non dimostra il raggiungimento di 50 t/s. Nessun download Q4 eseguito, nessun nuovo server completo avviato, nessuna modifica ai binari di produzione.

Il progetto di riferimento è FreeToken, commit `953565667f3141c90d0f0eb469bb2655d2407140`: l'idea ripresa è avviare la CPU e svolgere in parallelo trasferimenti e calcolo GPU. Il prototipo usa i kernel quantizzati della nostra build GGML. Non è un'esecuzione del motore FreeToken. [Esecutore FreeToken](https://github.com/FlashML-org/FreeToken/blob/953565667f3141c90d0f0eb469bb2655d2407140/python/freetoken/moe/cpu_executor.py).

**Che cosa è stato implementato e verificato.** Un pool persistente di thread accorpa `gate + up → SiLU × up → down → somma pesata`. Ogni thread usa un processore logico appartenente a un core fisico diverso. Un coordinatore riceve le attivazioni, attiva il pool e comunica la disponibilità del risultato alla GPU.

Si usano 128 esperti originali dello strato 0, estratti senza requantizzazione: IQ2_S per gate/up, IQ4_NL per down; 1.971.200 byte per esperto, circa 240,6 MiB complessivi. I test ruotano gli esperti mancanti su un insieme più grande della cache L3, con 128 attivazioni sintetiche di diversa ampiezza e pesi di routing non uniformi.

Il confronto CPU con GGML è bit-identico nei casi verificati: output dei singoli esperti e somma pesata, errore massimo zero, anche nella verifica aggiunta con tre esperti. La fusione, isolata, non supera sistematicamente GGML: per esempio tre esperti a sei thread richiedono circa 209 µs contro 189 µs del riferimento. Il confronto CPU include nel riferimento anche la copia delle attivazioni e degli ID; non è una misura del solo kernel aritmetico.

Il banco CUDA include preparazione degli ID, caricamento dei miss con il kernel gather esistente, tre moltiplicazioni GGML, attivazione, comunicazione CPU/GPU e somma finale in VRAM. L'intero blocco viene catturato in un CUDA graph. I flag del driver funzionano anche durante questa cattura; sul banco misurato le callback risultano però più convenienti.

**Risultati confermati.** Tre processi per configurazione, alternando l'ordine baseline/ibrido. La tabella riporta la mediana delle tre mediane, con 80 gruppi cronometrati di 16 invocazioni seriali. Queste 16 invocazioni non sono un batch di 16 token: servono ad ammortizzare la sincronizzazione host. Tutte le righe usano RAM pinnata mappata e callback.

| Esperti mancanti | Esperti CPU | Core CPU | Baseline GPU | Ibrido | Riduzione del tempo |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 6 | 186,1 µs | 163,7 µs | 12,1% |
| 2 | 2 | 6 | 262,0 µs | 186,1 µs | 29,0% |
| 3 | 2 | 6 | 337,2 µs | 253,5 µs | 24,8% |
| 3 | 2 | 4 | 337,1 µs | 242,0 µs | 28,2% |
| 4 | 3 | 6 | 414,4 µs | 269,2 µs | 35,1% |

L'ultima riga è più variabile: le tre mediane ibride sono 266,8, 335,4 e 269,2 µs. Anche tre esperti CPU con tre miss sono meno stabili; quattro esperti CPU possono regredire. Il candidato prudente è quindi **uno o due esperti CPU**, con scelta basata sui costi misurati. Quattro core sono migliori nel gruppo di 16 invocazioni con tre miss; il banco non giustifica un conteggio thread universale.

I controlli con sincronizzazione dopo **ogni singola invocazione** mantengono un vantaggio, ma con più rumore: due miss/due esperti CPU/sei core passano da 269,7 a 209,9 µs; tre miss/due esperti CPU/sei core da 345,5 a 263,1 µs. Un controllo separato a quattro core e tre miss dà mediane ibride di 254,1, 271,3 e 314,3 µs contro baseline di 352,0, 352,0 e 359,0 µs. Per scegliere i thread conta quindi anche la cadenza reale del server.

**Da dove viene il vantaggio.** A tre miss e due esperti CPU, sei core, la baseline è circa 337 µs:

| Comunicazione e ordine | Tempo ibrido |
|---|---:|
| Copie esplicite + flag CUDA | 387,7 µs |
| RAM mappata + flag CUDA | 279,2 µs |
| Copie esplicite + callback | 308,1 µs |
| RAM mappata + callback, lavoro concorrente | **253,5 µs** |
| RAM mappata + callback, CPU completata prima della GPU | 339,5 µs |

Il controllo seriale perde il beneficio. Non basta alleggerire i trasferimenti: occorre che la CPU lavori mentre la GPU serve gli altri esperti. I numeri della sonda precedente con callback vuote non vanno usati come costo di questo protocollo completo.

**Correttezza e copertura.** Gli output ibridi sono finiti e vengono confrontati con lo stesso insieme di esperti e gli stessi pesi calcolati interamente dalla GPU. CPU e CUDA quantizzano diversamente le attivazioni, quindi non sono bit-identici: nella conferma, il peggior NRMSE per singola attivazione è circa 0,00841; nel candidato con tre miss/due esperti CPU è 0,00634. La soglia 0,05 del banco rileva errori grossolani e non costituisce un criterio di qualità del modello.

La directory dei tensori GGUF conferma le stesse forme e combinazioni di quantizzazione in **47 strati su 48**. Lo strato 2 usa IQ3_S, codice 21, per gate/up e richiede un'estensione o il percorso GPU. Questo verifica la compatibilità dei formati, non la velocità o la qualità su tutti gli strati.

La traccia storica comprende 33.747 piani dopo il warmup, tutti a un token: media 2,445 miss. I casi con uno–quattro miss sono 20.963, **62,12%** del tratto caldo; includendo zero miss si arriva all'82,89%. È una ragione per approfondire questa ottimizzazione, non una proiezione di t/s. La prova impone i miss e non simula l'effetto degli esperti CPU sull'ammissione nella cache.

**Passaggio ancora necessario nel server.** Il prototipo resta separato. L'integrazione sperimentale deve preservare la politica LFU, senza segnare residente un esperto calcolato sulla CPU ma mai copiato in VRAM; mantenere buffer e topologia del graph validi per ogni replay; gestire errori e annullamento del coordinatore; conservare un percorso GPU per zero lavoro CPU e formati non supportati. Il supporto MTP richiede ID e somme distinti per ciascuno dei due–tre token: deduplicare i pesi trasferiti non equivale a deduplicare il calcolo.

Solo dopo questi passaggi ha senso misurare generazione libera, token/qualità e prefill sul server completo. Il guadagno del blocco non può essere esteso direttamente a router, shared expert, attenzione, moltiplicazioni dense residenti o all'intera generazione. Il pool del prototipo attende attivamente e occupa core CPU anche fra i job: anche questo costo va gestito nel server.

Codice, istruzioni di replica, griglie esplorative, 45 prove di conferma, controlli aggiuntivi, manifest e metadati sono in `freetoken_ibrido_evidence.zip`. L'archivio esclude pesi, DLL e configurazioni dei server.
