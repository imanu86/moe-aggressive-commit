@echo off
rem 12/11: come prova_mc_batch1 (26, 202 s) con STRATA_PREFILL_BW_GBS=13.1: la 26 aveva misurato 3,9 GB/s per la 2080 Ti e la 3060 non ha mai letto
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set MC_SAVE_TEXT=1
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py auto v2
echo == coda finita
