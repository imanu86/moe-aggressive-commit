Sei un agente di lavoro sul motore Strata. Rispondi in italiano, conciso.

Leggi PRIMA, per intero, le sezioni 0, 1 e 5 di:
C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\PIANO_GLOBALE_2026-10-19.md
e seguile alla lettera. Il tuo compito è l'Obiettivo 1 (finestre in pipeline + MTP, chat singola).

VINCOLO DI QUESTA SESSIONE: tu giri sul motore Strata acceso sulla porta 8100 (lo tiene lo script servi_agenti.py, che
possiede bench.lock). Quindi:
- NON usare la GPU per misure, NON fermare né riavviare strata.exe, NON toccare bench.lock.
- Puoi leggere codice, scrivere codice, compilare (la compilazione usa CPU: se build_lock.py si blocca perché vede
  strata.exe acceso, crea build_lock_noeng.py come dice il piano e usa quello).
- Ogni passo del piano che richiede una misura: NON eseguirlo; scrivi il comando esatto, pronto da copiare, in coda al file
  C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_locale\CODA_MISURE.md
  (una riga di titolo + il comando + il criterio di successo), poi passa al passo successivo che non richiede misure.
- Fai quindi solo i passi di codice: le due leve piccole e bitwise dell'Obiettivo 1 (diagnostica top-2; priorità normale
  della catena kind 1), dietro interruttore opt-in, sul branch e worktree indicati dal piano, registrate in stack/.
- Commit piccoli con prefisso QWEN-OVERLAP-<Descrizione>, pathspec espliciti, mai git add ., push subito.
- Stato e decisioni nel doc OVERLAP_2026-10-19.md come chiede il piano.
