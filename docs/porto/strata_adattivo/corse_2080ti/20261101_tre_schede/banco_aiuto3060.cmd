@echo off
rem 16/11 D: divisione 20 + serie slot (V2slot, riserva 730) con la 3060 come cache di esperti di aiuto (3500 esperti)
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
set C=D:\ds4_work\strata\lab_runs\maschera_20261114
set BANCO_SRC=C:\Users\imanu\source\repos\Strata-wt\upstream-slot
"%P%" -u banco_daily.py H2slot %C%\cfg-v2slotrh.json standard,turni:2
echo == coda finita
