@echo off
rem 12/11: due server con la 2080 Ti principale, una richiesta alla volta (--batch 1). Confronto: stessa corsa con --batch 4, 271 s.
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set MC_SAVE_TEXT=1
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py auto v1
echo == coda finita
