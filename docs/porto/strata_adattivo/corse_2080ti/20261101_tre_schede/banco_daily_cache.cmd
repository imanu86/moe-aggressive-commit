@echo off
rem 16/11: Daily una alla volta con cache delle conversazioni 10240 MiB e 3 posti, chat da 128K
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
set C=D:\ds4_work\strata\lab_runs\maschera_20261114
"%P%" -u banco_daily.py D1cache %C%\cfg-d1c.json turni:2-128000
echo == coda finita
