@echo off
rem Banco di parita' delle moltiplicazioni intrecciate (mmvq_il_parity) sulla 0.2.10 con la richiesta #5137: 2080 Ti (sm_75), poi 3080 Ti.
set CUDA_DEVICE_ORDER=PCI_BUS_ID
set T=C:\Users\imanu\source\repos\Strata-wt\upsync-v0.2.10\build-sm7586\mmvq_il_parity.exe
set B=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
set CUDA_VISIBLE_DEVICES=2
set STRATA_SM75_PERF=1
"%P%" "%B%" il-parita-2080 -- "%T%"
echo uscita 2080 %errorlevel%
set CUDA_VISIBLE_DEVICES=0
"%P%" "%B%" il-parita-3080 -- "%T%"
echo uscita 3080 %errorlevel%
echo fine banco
