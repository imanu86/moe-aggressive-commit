@echo off
rem 13/11: banco della comunita' (4K/32K/128K, 3 corse) sul Daily 0.2.13 4c con lo schermo 8K sulla 3060. Confronto: FT3 (schermo sulla 2080 Ti).
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u banco_daily.py D1schermo3060 D:\ds4_work\strata\Strata\strata-02131-4c-daily-schermo3060.json 3
echo == coda finita
