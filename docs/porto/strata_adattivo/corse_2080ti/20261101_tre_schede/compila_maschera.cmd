@echo off
rem 14/11: compila lab/tappa4c + maschera degli esperti residenti (STRATA_RESIDENT_MASK), 4 job, dietro bench_lock
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d C:\Users\imanu\source\repos\Strata-wt\tappa4c
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py COMPILA-MASCHERA -- cmake --build build-sm7586 --target strata -j 4
echo uscita compilazione %errorlevel%
echo == coda finita
