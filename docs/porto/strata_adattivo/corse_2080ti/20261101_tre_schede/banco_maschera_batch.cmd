@echo off
rem 14/11: chat multiple con la maschera. Daily (riserva 3060 4500) + --batch 4: protocollo standard con 4 domande insieme, maschera spenta e solo in scrittura, alternate
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
set C=D:\ds4_work\strata\lab_runs\maschera_20261114
"%P%" -u banco_daily.py B1off %C%\cfg-b4-off.json standard
"%P%" -u banco_daily.py B1m2 %C%\cfg-b4-m2.json standard
"%P%" -u banco_daily.py B2off %C%\cfg-b4-off.json standard
"%P%" -u banco_daily.py B2m2 %C%\cfg-b4-m2.json standard
echo == coda finita
