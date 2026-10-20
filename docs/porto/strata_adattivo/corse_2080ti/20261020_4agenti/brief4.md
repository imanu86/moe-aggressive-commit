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

TUO PEZZO (agente 4): misura. Prepara in corse_2080ti/20261019_passata_unica/ i comandi B-A-B (letture_concorrenti.py, coda_lc.sh, coda_replay_pu.sh) aggiornati alla build che fara' l'agente 1, piu' un banco con 4 agenti a prompt di lunghezze diverse (2k, 8k, 30k, 90k di contesto, 1-4k nuovi) che legge e scrive in contemporanea; criteri: tempo totale delle 4 letture, t/s decode degli altri durante, token identici. NON eseguire: scrivi i comandi nel tuo doc.
Il tuo numero e' 4: il tuo doc e' agente4.md.
