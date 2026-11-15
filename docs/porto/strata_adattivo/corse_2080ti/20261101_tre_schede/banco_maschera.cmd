@echo off
rem 14/11: maschera degli esperti residenti. Stesso exe (tappa4c + maschera), config Daily schermo 3060: off, on, off, on (banco comunita' 4K/32K/128K, 2 corse)
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
"%P%" -u banco_daily.py M1off D:\ds4_work\strata\lab_runs\maschera_20261114\cfg-maschera-off.json comunita:2
"%P%" -u banco_daily.py M1on D:\ds4_work\strata\lab_runs\maschera_20261114\cfg-maschera-on.json comunita:2
"%P%" -u banco_daily.py M2off D:\ds4_work\strata\lab_runs\maschera_20261114\cfg-maschera-off.json comunita:2
"%P%" -u banco_daily.py M2on D:\ds4_work\strata\lab_runs\maschera_20261114\cfg-maschera-on.json standard,comunita:2
echo == coda finita
