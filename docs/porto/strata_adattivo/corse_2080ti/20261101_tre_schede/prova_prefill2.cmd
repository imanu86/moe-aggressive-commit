@echo off
rem Banco della lettura del prompt col secondo server (tools/peer_prefill2_test.cpp, docs/PEER_PREFILL2.md):
rem prima la padrona contro se stessa (0 0), poi server 3060 (1) e 2080 Ti (2). Sotto bench.lock.
set CUDA_DEVICE_ORDER=PCI_BUS_ID
set CUDA_VISIBLE_DEVICES=0,1,2
set T=C:\Users\imanu\source\repos\Strata-wt\upsync-v0.2.9\build-sm7586\peer_prefill2_test.exe
set B=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
"%P%" "%B%" prefill2-stessa -- "%T%" 0 0
echo uscita stessa %errorlevel%
"%P%" "%B%" prefill2-3060 -- "%T%" 0 1
echo uscita 3060 %errorlevel%
"%P%" "%B%" prefill2-3060-grande -- "%T%" 0 1 2048 64 4
echo uscita 3060-grande %errorlevel%
"%P%" "%B%" prefill2-2080 -- "%T%" 0 2
echo uscita 2080 %errorlevel%
echo fine banco
