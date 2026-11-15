@echo off
rem 15/11 sera: divisione a strati su tre schede (3080 Ti, 2080 Ti, 3060) con maschera =2 e --batch; riferimento divisione 20 su due schede
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
set C=D:\ds4_work\strata\lab_runs\maschera_20261114
"%P%" -u banco_daily.py U4a %C%\cfg-u4a.json standard,carico:1-2-4
"%P%" -u banco_daily.py U4b %C%\cfg-u4b.json standard,carico:1-2-4
"%P%" -u banco_daily.py S4ref %C%\cfg-s4m2.json carico:1-2-4
"%P%" -u banco_daily.py U6a %C%\cfg-u6a.json carico:1-3-6
"%P%" -u banco_daily.py S6 %C%\cfg-s6.json carico:1-3-6
echo == coda finita
