@echo off
rem 15/11: profilo del passo con 1 e 4 richieste (server), --batch-mtp sui server, divisione a strati 20 con --batch 4 (spenta, maschera 2, maschera 2 + --batch-mtp a gruppo unico)
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
set C=D:\ds4_work\strata\lab_runs\maschera_20261114
"%P%" -u banco_daily.py P1prof %C%\cfg-p1.json comunita:1
"%P%" -u banco_daily.py P4prof %C%\cfg-p4.json standard
"%P%" -u banco_daily.py P4mtp %C%\cfg-p4mtp.json standard
"%P%" -u banco_daily.py S4off %C%\cfg-s4.json standard
"%P%" -u banco_daily.py S4m2 %C%\cfg-s4m2.json standard
"%P%" -u banco_daily.py S4m2mtp %C%\cfg-s4m2mtp.json standard
echo == coda finita
