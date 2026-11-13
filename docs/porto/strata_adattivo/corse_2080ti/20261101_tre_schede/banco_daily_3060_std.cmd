@echo off
rem 13/11: Daily 0.2.13 4c con lo schermo 8K sulla 3060, i due banchi della comunita' di oggi: protocollo standard-v1 (con 4 richieste insieme), poi la suita rapida + 32K
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u banco_daily.py D2standard3060 D:\ds4_work\strata\Strata\strata-02131-4c-daily-schermo3060.json standard,rapido
echo == coda finita
