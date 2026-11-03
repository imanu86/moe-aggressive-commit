@echo off
rem Banco bit per bit delle tre correzioni del secondo server (docs/PEER_FUSED2.md §11): salto a vuoto, righe q8_1 pubblicate dalla padrona.
rem Primo server 2080 Ti (2), secondo 3060 (1), padrona finta sulla 3080 Ti (0). Sotto bench.lock.
set CUDA_DEVICE_ORDER=PCI_BUS_ID
set CUDA_VISIBLE_DEVICES=0,1,2
set T=C:\Users\imanu\source\repos\Strata-wt\upsync-v0.2.9\build-sm7586\peer_fused_test.exe
set B=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
"%P%" "%B%" peer-fused-uno -- "%T%" 2 --primary 0
echo uscita uno %errorlevel%
"%P%" "%B%" peer-fused2-misto -- "%T%" 2 --primary 0 --second 1
echo uscita due-misto %errorlevel%
"%P%" "%B%" peer-fused2-skip -- "%T%" 2 --primary 0 --second 1 --skip
echo uscita skip %errorlevel%
"%P%" "%B%" peer-fused2-stage -- "%T%" 2 --primary 0 --second 1 --stage
echo uscita stage %errorlevel%
"%P%" "%B%" peer-fused2-skip-stage -- "%T%" 2 --primary 0 --second 1 --skip --stage
echo uscita skip-stage %errorlevel%
"%P%" "%B%" peer-fused2-uniforme -- "%T%" 2 18 42 512 64 20 7 --primary 0 --second 1 --skip --stage
echo uscita uniforme %errorlevel%
echo fine banco
