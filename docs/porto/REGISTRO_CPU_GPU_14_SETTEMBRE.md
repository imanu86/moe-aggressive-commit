# Registro CPU/GPU

Aggiornato il 14 settembre 2026, versione 1.0. Documenti correnti: [piano](PIANO_CPU_GPU_14_SETTEMBRE.md), [protocollo](PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md). Copie canoniche nel repository `moe-aggressive-commit/docs/porto`; copie di consegna in `outputs`.

**Stato corrente:** prototipo del 13 settembre completato; pianificazione dell'integrazione completata; **P0 da avviare**. In questa sessione sono stati letti sorgenti e prove e scritti documenti. Non sono stati modificati motore, binari, launcher o modello; non sono stati lanciati benchmark o server.

**Prossima azione precisa:** creare baseline e build sperimentale separata, congelare le fixture del banco, verificare che A/B usi gli stessi input e misurare la variabilità del controllo. Poi specificare e verificare il piano cache CPU/GPU in P1.

| Fase | Stato | Dipendenza |
|---|---|---|
| Prototipo e audit 13/9 | COMPLETATO | Prove nel rapporto e nello ZIP storico |
| Piano/protocollo 14/9 | COMPLETATO | Richiesta dell'utente di pianificare e documentare |
| P0 — Baseline e fixture | DA AVVIARE | Nessuna |
| P1 — Contratto cache | DA AVVIARE | P0 |
| P2 — Esecutore/lifetime | DA AVVIARE | P1 |
| P3 — Uno strato reale | DA AVVIARE | P2 |
| P4 — Decode completo | DA AVVIARE | P3 |
| P5 — MTP | DA AVVIARE | P4 |
| P6 — Conferma/preset | DA AVVIARE | P5 |
| P7 — Divario residuo | DA AVVIARE | P6 oppure chiusura motivata della pista CPU |

**Decisioni attive.**

| ID | Decisione | Motivo e prova | Riesame |
|---|---|---|---|
| D01 | Pesi originali, Q4 rinviato | Priorità esplicita dell'utente; prototipo già utile senza conversioni | Solo come esperimento distinto successivo |
| D02 | RAM mappata + callback come candidato | Conferma: 253,5 microsecondi contro 387,7 con copie/flag, caso tre miss/due CPU/sei core | Se il server mostra un costo diverso |
| D03 | Uno/due esperti CPU iniziali; quattro/sei core da confrontare | Tre/quattro esperti CPU più variabili; differenze tra replay raggruppati e singoli | Dopo P4 |
| D04 | Frequenza/recenza attuale; ammissioni CPU separate | Cache reale già validata; commit differito nel piano CUDA | P1 deve dimostrare gli invarianti |
| D05 | MVP con righe GPU valide e peso zero per le route CPU | Forma del graph stabile e nessun ID negativo; richiede nuova misura del lavoro GPU fittizio | Maschera MMVQ solo se necessaria dopo P4 |
| D06 | MTP spento nella prima integrazione | Il prototipo copre un token; evitare di confondere cache, rollback e speculazione | P5 |
| D07 | Strato 2 sulla GPU | Gate/up IQ3_S, codice 21; altri 47 strati IQ2_S, codice 22 | Estensione separata dopo validazione |
| D08 | Fixture immutabili e nuovo A/B | Il filler del banco deriva dai sorgenti; i vecchi 25,08/27,26 differiscono anche per preset | Sempre |
| D09 | Un solo pool per contesto, attesa inattiva fuori decode | Il pool della sonda occupa core anche a riposo; no moltiplicazione per strato | P2 e prova prefill |
| D10 | Nessun numero del microbench diventa t/s generali | 39,19 era copia; 337->242 riguarda un blocco; profiler non additivo | Sempre |

**Rischi e verifiche aperte.** Residenti fantasma nel commit differito (P1); costo delle righe GPU fittizie e callback quando CPU=0 (P3/P4); contesa RAM e core (P4); variazione del comportamento libero dovuta all'aritmetica CPU/GPU (P3–P6); riferimenti a buffer nei graph e annullamento in volo (P2/P5); memoria di prefill e ritorno al decode (P5/P6). Il protocollo stabilisce come rilevarli, non li dichiara già risolti.

**Review del piano, 14/9:** riesaminati i punti di integrazione e il banco con agenti economici e verifica finale del principale sui sorgenti. Precisati il partizionamento prima dell'assegnazione degli slot/gather, la conservazione degli ID logici, l'alias verso una route GPU reale protetta e il merge CPU dopo la riduzione e prima dello shared expert. Sono decisioni progettuali revisionate, non patch eseguite. Scartata l'etichetta impropria "baseline FreeToken": i 25,08 t/s appartengono al nostro server precedente.

**Evidenze già disponibili.** [Rapporto CPU/GPU](FREETOKEN_IBRIDO_13_SETTEMBRE.md), [prove CPU/GPU](freetoken_ibrido_evidence.zip), [audit FreeToken/Bonsai](FREETOKEN_BONSAI_13_SETTEMBRE.md), [prove audit](freetoken_bonsai_evidence.zip). La conferma del prototipo contiene 45 prove, più controlli aggiuntivi; non è una conferma del server completo.

**Voce da aggiungere a ogni avanzamento.** Data e fase; ipotesi; ID della modifica/revisione; file toccati; configurazioni confrontate; link ai run validi e invalidi; risultato e limite; decisione (proseguire/correggere/chiudere); regressioni aperte; stato dei processi avviati; prossima azione. Una fase è COMPLETATA solo quando la sua consegna e i criteri di uscita sono verificati. Se si scopre un errore di misura, rettificare esplicitamente il riepilogo conservando il run originale.

**Rollback previsto:** opzione ibrida spenta e riavvio sul preset sperimentale di riferimento; se il percorso spento non è neutro, ritorno al binario/snapshot di P0. Non si sostituisce il launcher di uso quotidiano durante l'integrazione. Il rollback è un test da eseguire in P6, non ancora una prova superata.
