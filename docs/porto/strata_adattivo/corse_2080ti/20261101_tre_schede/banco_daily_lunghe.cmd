@echo off
rem 16/11: Daily a due server sulla prova a turni con chat lunghe (64K e 128K), com e e con --batch 2
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
set C=D:\ds4_work\strata\lab_runs\maschera_20261114
"%P%" -u banco_daily.py D1lung %C%\cfg-d1.json turni:2-64000,turni:2-128000
"%P%" -u banco_daily.py D2lung %C%\cfg-d2.json turni:2-64000,turni:2-128000
echo == coda finita
