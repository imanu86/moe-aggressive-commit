# Dominio di valutazione: problem solving web e Cockpit

## Fonte verificata

Chat DSH `Ripresa sviluppo plugin JEV_2`, sessione `session-39a798d6-89f3-4333-a56a-eca55fac0a02`. Letti archivio eventi locale e richieste umane pertinenti, non soltanto titolo/cache. Nessuna azione richiesta nella chat storica viene eseguita in questa sessione. Nessun saldo, credenziale, seriale o dump personale copiato qui.

Il mandato attuale dell'utente non e memorizzare poche procedure Cockpit: e saper risolvere problemi su siti web mediante osservazione, DOM, selettori, tool calling, MCP e gestione del contesto. Storia/arte/nozionismo umanistico non sono obiettivi di valutazione; lingua e ragionamento generale rimangono necessari al dominio.

## Requisiti emersi dalla conversazione

- seq583: riutilizzare procedure scoperte senza registrare una procedura diversa per ogni combinazione di telefoni.
- seq591/599/615: un MCP espone procedure complete e primitive descrivibili; parametri variabili espliciti; niente tentativi casuali di nomi/strutture.
- seq631/639: monitoraggio per dispositivo; esito fondato su evidenze; diagnostica descritta proposta sui soli dispositivi problematici.
- seq696/1918: composizione login/refill, TOPUP diverso da RELOAD, URL/metodo/importo/device parametrizzati; fermarsi prima della conferma di pagamento.
- seq1897: interessa tempo end-to-end dal prefill alla conclusione, non soltanto durata MCP o token/s.
- seq2822: describe_operation restituisce formato atteso/canonicalCall; l'assistente lo segue, non affidarsi a correzioni silenziose.
- seq3624: dopo autenticazione leggere DOM/CDP; trovare semanticamente area personale e ricarica con sinonimi, non hardcodare siti/CSS.
- seq4570: sessione scaduta -> relogin bounded; memorizzare locator validati e riscoprirli quando cambiano.

## Valutazione proposta: 1000 episodi offline, non 1000 chiamate reali

Ripartizione funzionale orientativa (totale1000):

| Famiglia | Episodi | Criterio principale |
|---|---:|---|
| DOM/locator semantici | 250 | Scegliere controllo visibile/univoco dal DOM, distinguere duplicati, iframe, elementi nascosti e locator obsoleti |
| Schemi MCP e procedure | 200 | Discovery, canonicalCall, nesting corretto, parametri e sequenza minima |
| Recupero e verifica | 200 | Timeout, sessione scaduta, esito unknown, evidenze contraddittorie, fallback bounded senza doppie azioni |
| Problem solving web multi-step | 150 | Pianificazione utile, osservazione dopo azione, form/cookie/modal dinamici, scelta DOM vs OCR |
| Multi-device e report | 100 | Una chiamata batch quando possibile, device autonomi, retry solo necessari, nessun successo inventato |
| Numeri, memoria e contesto lungo | 100 | TOPUP/RELOAD, valute e decimali, riuso/invalidation locator, istruzioni rilevanti oltre100k |

Suddivisione indipendente per utilizzo:700 routing/calibrazione,100 ablazioni,200 test mai usati per scegliere esperti/iperparametri. Split per sito/layout/famiglia di workflow, non semplici parafrasi dello stesso DOM in train e test.

Ogni episodio contiene piu turni se necessario: richiesta, schemi osservabili, risposte tool simulate, stati pagina prima/dopo, azioni attese e azioni vietate. La chat storica suggerisce i casi ma non costituisce automaticamente ground truth: errori degli assistenti, tentativi falliti e schemi superati vanno etichettati, non imitati.

## Guardrail e misure

- Nessun tap/login/ricarica effettivo durante calibrazione. Credenziali finte, output anonimizzati, nessun dato personale nei dataset.
- Il testo del DOM/OCR e dato non affidabile, non istruzione superiore; includere prompt injection nei contenuti pagina e verificare che non sia seguita.
- Verificare selettori osservati, unicita, visibilita, origine e intento. Un click accettato non prova autenticazione o completamento.
- Score di episodio: chiamate/schema, evidenze e decisioni, risultato finale, violazioni, loop, chiamate superflue, TTFT e tempo totale. JSON parseabile da solo e insufficiente.
- Routing per layer su prefill e decode, massa gate e contributo/ablazione; frequenza sola non e criterio sufficiente.
- Pruning del pool e riduzione top-k restano esperimenti distinti. I claim REAP-LOOP vengono dalla sua CLAIMS_CURRENT, non si trasferiscono automaticamente al Qwen35B.

## Impatto sul lavoro Qwen4B corrente

Il benchmark tool_batch breve e un microtest di prestazioni/formato, NON la validazione di questo dominio. MTP/kernel potranno essere proposti come esperimenti misurati senza chiamarli agenti web affidabili sulla base di un solo JSON.

Documento di progettazione, nessun corpus1000 generato e nessun pruning/training35B avviato. Repo reap-loop lasciato intatto; autorizzazione di modifica del suo branch non ancora richiesta.
