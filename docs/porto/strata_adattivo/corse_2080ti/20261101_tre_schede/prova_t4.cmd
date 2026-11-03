@echo off
rem Banco del passaggio di stato della tappa 4 (tools/ep_split_test.cpp): padrona 3080 Ti, peer 2080 Ti, poi con K/V residente. Sotto bench.lock.
set CUDA_DEVICE_ORDER=PCI_BUS_ID
set CUDA_VISIBLE_DEVICES=0,2
set T=C:\Users\imanu\source\repos\Strata-wt\upsync-v0.2.9\build-sm7586\ep_split_test.exe
set B=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
"%P%" "%B%" ep-split-test -- "%T%" 0 1 8192 0
echo uscita streaming %errorlevel%
"%P%" "%B%" ep-split-test2 -- "%T%" 0 1 8192 4096
echo uscita residente %errorlevel%
