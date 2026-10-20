Sei un agente di lavoro sul motore Strata. Rispondi in italiano, conciso. Riprendi l'Obiettivo 1 del
C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\PIANO_GLOBALE_2026-10-19.md (rileggi sez. 0, 1, 5).

Le misure della tua CODA_MISURE.md (passi 1.0-1.3) sono state eseguite il 20/10 01:00-01:52 (Jump connesso):
- verdetti B-A-B: C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_locale\bab_*.txt
  (A0, nsw, stg, minp, prio; NOTA: chiamate con B per primo, leggi il segno come dice il piano)
- corse: C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\DET-ov-*\ (engine.log,
  force_trace.txt); la diagnostica top-2 è in DET-ov-top2\engine.log.

Compiti:
1. Leggi verdetti e diagnostica top-2 (N2/(N2+N3)), applica i criteri del piano, scrivi esiti e decisioni in OVERLAP_2026-10-19.md
   e nel registro stack/ (campi measured delle patch 19 e 20). Ricorda: il banco DET forza le finestre, quindi NON vede cambi di
   accettazione (min-p): per min-p serve il banco della comunità (passo 1.5), da mettere in CODA_MISURE.md.
2. Prosegui col passo successivo del piano che richiede solo codice (es. la B ad albero se la soglia top-2 la apre; altrimenti la
   leva successiva indicata dal piano). Le misure: comandi pronti in coda a CODA_MISURE.md (sezione nuova datata 20/10), NON eseguirle.

VINCOLO: giri sul motore Strata della porta 8100 (servi_agenti.py). NON usare la GPU, NON fermare strata.exe, NON toccare bench.lock.
Compila solo con build_lock_noeng.py. Commit QWEN-OVERLAP-<Descrizione>, pathspec espliciti, mai git add ., push subito.
