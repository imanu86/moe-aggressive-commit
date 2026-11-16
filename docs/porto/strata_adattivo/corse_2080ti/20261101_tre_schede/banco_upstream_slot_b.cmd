@echo off
rem 16/11 B: serie PR 5860-5868 con le bozze negli slot ma senza lettura nello slot e senza chat trattenuta nello slot
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
set C=D:\ds4_work\strata\lab_runs\maschera_20261114
set BANCO_SRC=C:\Users\imanu\source\repos\Strata-wt\upstream-slot
set BANCO_NOTE=OktoCGC lab: upstream 13eedf552 + PR 5860-5868, STRATA_SLOT_READ=0 STRATA_PARALLEL_STICKY_S=0, divisione 20
set STRATA_SLOT_READ=0
set STRATA_PARALLEL_STICKY_S=0
"%P%" -u banco_daily.py V2slotB %C%\cfg-v2slotb.json standard,turni:2
"%P%" -u banco_daily.py V4slotB %C%\cfg-v4slotb.json standard,turni:2
echo == coda finita
