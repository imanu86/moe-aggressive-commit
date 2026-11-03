@echo off
rem Banco bit per bit del mega-kernel a due server (tools/peer_fused_test.cu --second, docs/PEER_FUSED2.md):
rem primo server 2080 Ti (2), secondo 3060 (1), padrona finta sulla 3080 Ti (0). Sotto bench.lock.
rem Prima il riferimento a un server (deve restare PASS), poi due server misto e uniforme.
set CUDA_DEVICE_ORDER=PCI_BUS_ID
set CUDA_VISIBLE_DEVICES=0,1,2
set T=C:\Users\imanu\source\repos\Strata-wt\upsync-v0.2.9\build-sm7586\peer_fused_test.exe
set B=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
"%P%" "%B%" peer-fused-uno -- "%T%" 2 --primary 0
echo uscita uno %errorlevel%
"%P%" "%B%" peer-fused2-misto -- "%T%" 2 --primary 0 --second 1
echo uscita due-misto %errorlevel%
"%P%" "%B%" peer-fused2-uniforme -- "%T%" 2 18 42 512 64 20 7 --primary 0 --second 1
echo uscita due-uniforme %errorlevel%
echo fine banco
