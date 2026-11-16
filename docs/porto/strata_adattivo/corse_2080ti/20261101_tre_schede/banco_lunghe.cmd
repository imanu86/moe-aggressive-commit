@echo off
rem 16/11 C: serie PR 5860-5868 con conversazioni lunghe (primo turno 64K e 128K), riserva 2080 Ti 730
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
set C=D:\ds4_work\strata\lab_runs\maschera_20261114
set BANCO_SRC=C:\Users\imanu\source\repos\Strata-wt\upstream-slot
"%P%" -u banco_daily.py L4base %C%\cfg-v4baser.json turni:2-64000,turni:2-128000
"%P%" -u banco_daily.py L2slot %C%\cfg-v2slotr.json turni:2-64000,turni:2-128000
echo == coda finita
