@echo off
rem 16/11: serie PR 5860-5868 (fork bitaccesscomau pr/slot-read-ahead, build lab/upstream-slot) sulla divisione 20 a due schede,
rem senza e con le bozze negli slot; riferimento della nostra pila (S4m2, tappa4c) solo sui turni
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
set C=D:\ds4_work\strata\lab_runs\maschera_20261114
set BANCO_SRC=C:\Users\imanu\source\repos\Strata-wt\upstream-slot
set BANCO_NOTE=OktoCGC lab: upstream 13eedf552 + PR 5860-5868 (bitaccesscomau pr/slot-read-ahead), divisione 20
"%P%" -u banco_daily.py V4base %C%\cfg-v4base.json standard,carico:1-2-4,turni:2
"%P%" -u banco_daily.py V4slot %C%\cfg-v4slot.json standard,carico:1-2-4,turni:2
"%P%" -u banco_daily.py V2slot %C%\cfg-v2slot.json standard,turni:2
set BANCO_SRC=
set BANCO_NOTE=
"%P%" -u banco_daily.py S4m2t %C%\cfg-s4m2.json turni:2
echo == coda finita
