@echo off
rem 12/11: stima delle repliche per le chat multiple. Replay a 3 agenti col motore su una scheda sola: 3080 Ti (r0), poi 2080 Ti (r2).
rem La somma dei token letti al secondo e' il tetto di due repliche autonome (ogni scheda le sue chat).
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py 20 r0 r2
echo == coda finita
