# Controllo delle risposte e limiti di bozza — 2 ottobre

Le tre corse sono prove di throughput, non un esame di correttezza del modello.
Per tutti i6casi principali:1024token generati, `finish=length`, content vuoto,
ragionamento non vuoto. Nessuna risposta finale e' stata ottenuta o valutata.
I100testserver sono mock e non verificano la qualita' del modello.
Il top-k bitwise e il pool bitwise verificano le operazioni cambiate; HC ha il
suo gate numerico. Nessuna seconda chat/reviewer e' stata coinvolta.

Letti manualmente i due ragionamenti della candidata seriale. L01 affronta il
rapporto esperti/PCIe/compute richiesto, L02 descrive LRU/LFU con decadimento,
localita'/cambiofase e simulazione offline. Entrambi si interrompono prima
della risposta finale: nessun voto di accuratezza. Gli esempi intermedi diL01
hanno anche un'ambiguita' GiB/GB:48*384MiB sono18GiB, mentre il ragionamento
scrive18,4GiB;48*1,75*192MiB sono15,75GiB, non16,1GiB. Sono ragionamenti
parziali e gli esempi erano richiesti inventati; non inferire un errore dei
kernel da questi numeri ne' promuoverli come risposte corrette.

Config attuale: `--spec 4 --spec-min-p 0.5`, lookup default3.
Il motore aumenta la capienza del verificatore a6 per il prompt lookup, mentre
mantiene `mtp_max=4`. Le finestre comprendono il token corrente: **fino a3bozze
MTP**, oppure **5da lookup**, non6bozzeMTP. Il limite reale puo' essere minore
per probabilita'/policy. Questa config0.1.36 non ha uno sweep spec4/6/8.
Il precedente test minp0,3 aveva dato43,2contro45,1t/s e37%accettazione delle
bozze aggiunte: riguarda una versione precedente, non prova la nuova config.

Metodo pubblico upstream e lacune del daily: [STANDARD_TEST_UPSTREAM.md](STANDARD_TEST_UPSTREAM.md).
Prima delle nuove bozze, aggiungere il confronto teacher-forced con logits,
KL e perplexity su testi fissi, oltre alle risposte finali verificabili.

Prossima verifica da fare separatamente: richieste con soluzioni verificabili,
output sufficiente a `finish=stop`, controllo risposta finale e, se utile,
confronto con decode non speculativo. Poi sweep del limite MTP4/6/8 tenendo
KV/cache/probabilita' costanti, misurando token/s, accettazioni, righe verificate
e tempo per riga. Nessuna nuova corsa avviata da questa annotazione.
