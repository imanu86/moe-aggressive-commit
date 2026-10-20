Sei un agente di lavoro sul motore Strata. Rispondi in italiano, conciso. Obiettivo 1 del PIANO_GLOBALE_2026-10-19.md
(C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\, rileggi sez. 0, 1, 5) e il tuo OVERLAP_2026-10-19.md.

Decisione dell'owner: la diagnostica dice seconda scelta giusta 45,2% (seriale) / 29,5% (pipeline) → si fa la B AD ALBERO
(finestra successiva avviata con due ipotesi in batch sulla prima scheda, si tiene quella giusta). Lavoro grosso: procedi a passi
piccoli, ognuno compilato e committato, dietro interruttore opt-in (es. STRATA_OV_TREE=1), su lab/overlap, registrato in stack/.
Prima scrivi in OVERLAP_2026-10-19.md un design di mezza pagina (dove nasce B, come si duplica lo stato ricorrente GDN/QSA della
prima scheda per due ipotesi, come si sceglie e si scarta, costo VRAM sulla 3060). Poi implementa.

In parallelo, per la prossima finestra di misure, metti in CODA_MISURE.md (sezione datata, comandi completi copiabili):
(a) metro A/A col pipeline acceso con avvio più lungo (il blocco 8 è fallito per "Startup deadline" a 300 s: trova come allungarlo);
(b) il braccio B di min-p 0,70 sul banco comunità, con il comando che CREA prima cfg-overlap-minp.json;
(c) le misure della B ad albero (B-A-B col pipeline, force_trace, righe pipeline classes).

VINCOLO: giri sul motore Strata della porta 8100 (servi_agenti.py). NON usare la GPU, NON fermare strata.exe, NON toccare bench.lock.
Compila solo con build_lock_noeng.py. Commit QWEN-OVERLAP-<Descrizione>, pathspec espliciti, mai git add ., push subito.
Nel report finale metti per prime 3 righe con lo stato.
