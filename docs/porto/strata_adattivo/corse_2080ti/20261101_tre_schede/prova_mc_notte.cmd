@echo off
rem 12/11 notte: chat multiple col testo salvato. 0.2.13.1 (x) e 0.2.9 (u) a 6 agenti con la divisione 20, poi i due server (s0 senza, s1 con STRATA_PEER_BATCH) a 3 e 6 agenti.
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set MC_SAVE_TEXT=1
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py 20 x:2
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py 20 u:2
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py 20 s0 s1 s1:2
echo == tutte le chat multiple finite
