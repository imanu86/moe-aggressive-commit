Sei un agente di lavoro sul motore Strata. Rispondi in italiano, conciso. Riprendi l'Obiettivo 1 del PIANO_GLOBALE_2026-10-19.md
(C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\, rileggi sez. 0, 1, 5).

La tua «CODA 20 OTTOBRE» (blocchi 8-14 di CODA_MISURE.md) è stata eseguita il 20/10 02:24-03:32 (Jump connesso). Output di ogni
comando, in ordine: C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_locale\misura_ov2.log
(righe "== n ora comando"). Corse in corse_2080ti\20261004_routed_keep\DET-ov2-*\ e corse_2080ti\20261019_banco_comunita\COMM-ov-minp-*\.
Nota: almeno un bab_verdict è finito con FileNotFoundError (braccio mancante o fallito: scopri quale e perché dai log della corsa);
la A/A col pipeline acceso ha dato -3,4% (metro rumoroso: tienine conto); un B-A-B ha dato +17,4% (verifica a quale leva
corrisponde, che le righe `pipeline classes` confermino e che i force_trace siano identici: un +17% può essere un artefatto).

Compiti:
1. Leggi tutto, applica i criteri del piano, scrivi esiti e decisioni in OVERLAP_2026-10-19.md e nei campi measured di stack/.
   Per min-p 0,70 riporta i t/s 4K/32K/128K dei tre bracci comunità e se i testi divergono.
2. Se una leva passa i criteri, preparane la config di prova (copia, mai toccare il Daily) e mettila in CODA_MISURE.md
   (sezione nuova datata) con la conferma richiesta dal piano. Poi prosegui col passo di solo codice successivo del piano.

VINCOLO: giri sul motore Strata della porta 8100 (servi_agenti.py). NON usare la GPU, NON fermare strata.exe, NON toccare bench.lock.
Compila solo con build_lock_noeng.py. Commit QWEN-OVERLAP-<Descrizione>, pathspec espliciti, mai git add ., push subito.
Nel report finale metti per prime 3 righe con i numeri chiave.
