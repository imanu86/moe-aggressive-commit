@echo off
rem 12/11 notte: due server con --batch 4, lettura a pezzi grandi (s2) e K/V residente a 16K per slot (s3), 3 agenti.
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set MC_SAVE_TEXT=1
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py 20 s2 s3
echo == tutte le chat multiple finite
