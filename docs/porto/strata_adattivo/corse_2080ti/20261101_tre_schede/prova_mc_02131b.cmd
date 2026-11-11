@echo off
rem Chat multiple 11/11 notte: 0.2.13.1 + leve (braccio x), divisione 20 contro 22, 3 e 6 agenti.
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py 22 x
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py 20 x:2
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py 22 x:2
echo == tutte le chat multiple finite
