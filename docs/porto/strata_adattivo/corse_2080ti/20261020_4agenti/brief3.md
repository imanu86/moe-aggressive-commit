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

TUO PEZZO (agente 3): il server Python, source/serve/server.py del worktree: oggi impone una lettura di prompt alla volta. Fai in modo che con STRATA_PACK_CONCURRENT=1 più richieste in lettura arrivino insieme al motore (coda, raccolta delle letture concorrenti entro pochi ms), senza toccare il percorso senza interruttore.
Il tuo numero e' 3: il tuo doc e' agente3.md.
