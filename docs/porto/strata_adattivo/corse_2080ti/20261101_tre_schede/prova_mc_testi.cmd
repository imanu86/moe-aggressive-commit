@echo off
rem 12/11 notte: 6 agenti con il testo delle risposte salvato, 0.2.13.1 (x) contro 0.2.9 (u), divisione 20: le risposte da 2-4 token della copia di B.
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set MC_SAVE_TEXT=1
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py 20 x:2
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py 20 u:2
echo == tutte le chat multiple finite
