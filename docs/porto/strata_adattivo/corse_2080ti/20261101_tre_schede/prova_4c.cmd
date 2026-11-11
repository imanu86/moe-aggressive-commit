@echo off
rem Banco della tappa 4c (tools/ep_split_test.cpp, docs/EP_SPLIT_PREFILL.md §14): padrona 3080 Ti (0), stadio sulla 2080 Ti (2).
set CUDA_DEVICE_ORDER=PCI_BUS_ID
set CUDA_VISIBLE_DEVICES=0,1,2
set T=C:\Users\imanu\source\repos\Strata-wt\tappa4c\build-sm7586\ep_split_test.exe
set B=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
"%P%" "%B%" ep4c-a -- "%T%" 0 2 8192 0
echo uscita a %errorlevel%
"%P%" "%B%" ep4c-b -- "%T%" 0 2 40000 32768
echo uscita b %errorlevel%
set STRATA_EP_SPLIT_TEST_KV=int8
"%P%" "%B%" ep4c-int8 -- "%T%" 0 2 40000 32768
echo uscita int8 %errorlevel%
set STRATA_EP_SPLIT_TEST_KV=q4
"%P%" "%B%" ep4c-q4 -- "%T%" 0 2 40000 32768
echo uscita q4 %errorlevel%
echo fine banco
