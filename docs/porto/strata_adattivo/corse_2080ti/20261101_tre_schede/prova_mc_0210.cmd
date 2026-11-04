@echo off
rem Chat multiple 04/11: 0.2.10 + pila con tutte le leve (braccio w), divisione 20 e 22 alternate, 3 e 6 agenti. Replay DSH 3600+1200 s.
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
"%P%" -u coda_multichat.py 20 w
"%P%" -u coda_multichat.py 22 w
"%P%" -u coda_multichat.py 20 w:2
"%P%" -u coda_multichat.py 22 w:2
echo == tutte le chat multiple finite
