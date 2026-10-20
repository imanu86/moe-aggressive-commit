Sei uno di 4 agenti che lavorano IN CONTEMPORANEA sul motore Strata. Rispondi in italiano, conciso.
Obiettivo comune: la «passata unica» — leggere i pesi/esperti UNA volta per prefill e decode di più agenti insieme.
Leggi PRIMA: C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\PASSATA_UNICA_2026-10-19.md (tutto)
e la sezione 0 di PIANO_GLOBALE_2026-10-19.md (stessa cartella). Codice: worktree C:\Users\imanu\source\repos\Strata-wt\passata-unica
(branch lab/passata-unica).

Regole di convivenza (4 agenti sullo stesso worktree):
- Tocca SOLO i file del tuo pezzo (sotto). Se ti serve cambiare un file di un altro pezzo, scrivilo nel tuo doc e non farlo.
- Commit solo dei tuoi file, pathspec espliciti, mai git add .; se git dice index.lock, aspetta 10 s e riprova.
  Prima del push: git pull --rebase --autostash; prefisso QWEN-PASSATA-<Descrizione>.
- La compilazione la fa SOLO l'agente 1 (build_lock_noeng.py); gli altri non compilano.
- NON usare la GPU, NON fermare strata.exe (porta 8100, è il motore su cui giri), NON toccare bench.lock.
- Il tuo stato in C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261020_4agenti\agente<N>.md
  (cosa hai fatto, file toccati, comandi di misura pronti per dopo).

TUO PEZZO (agente 1): build e correttezza. Compila lab/passata-unica con build_lock_noeng.py, copia la build con copia_build.py (vedi doc, sezione Stato esatto al STOP), verifica che STRATA_PACK_CONCURRENT=1 spento non cambi nulla (diff del codice: ogni ramo nuovo dietro l'interruttore). Ricompila quando gli altri agenti committano (controlla git log ogni 20 min), max 3 build.
Il tuo numero e' 1: il tuo doc e' agente1.md.
