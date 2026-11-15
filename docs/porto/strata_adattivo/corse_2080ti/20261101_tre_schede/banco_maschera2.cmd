@echo off
rem 14/11 giro 2: ricompila (maschera =2 solo scrittura, domanda pesata), poi riserva 3060 a 4500 perche' il secondo server parta: off, m2, m2 senza domanda, off, m2
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d C:\Users\imanu\source\repos\Strata-wt\tappa4c
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
"%P%" C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py COMPILA-MASCHERA2 -- cmake --build build-sm7586 --target strata -j 4
if errorlevel 1 (echo compilazione fallita & echo == coda finita & exit /b 1)
echo compilazione ok
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set C=D:\ds4_work\strata\lab_runs\maschera_20261114
"%P%" -u banco_daily.py R1off %C%\cfg-r2-off.json comunita:2
"%P%" -u banco_daily.py R1m2 %C%\cfg-r2-m2.json comunita:2
"%P%" -u banco_daily.py R1m2nodem %C%\cfg-r2-m2nodem.json comunita:2
"%P%" -u banco_daily.py R2off %C%\cfg-r2-off.json comunita:2
"%P%" -u banco_daily.py R2m2 %C%\cfg-r2-m2.json standard,comunita:2
echo == coda finita
