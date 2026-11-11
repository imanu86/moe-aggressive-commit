@echo off
rem Banco bit per bit delle tre correzioni del secondo server (docs/PEER_FUSED2.md §11): salto a vuoto, righe q8_1 pubblicate dalla padrona.
rem Primo server 2080 Ti (2), secondo 3060 (1), padrona finta sulla 3080 Ti (0). Sotto bench.lock.
set CUDA_DEVICE_ORDER=PCI_BUS_ID
set CUDA_VISIBLE_DEVICES=0,1,2
set T=C:\Users\imanu\source\repos\Strata-wt\upsync-v0.2.13\build-sm7586\peer_fused_test.exe
set B=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
"%P%" "%B%" peer-fused-uno -- "%T%" 2 --primary 0
echo uscita uno %errorlevel%
"%P%" "%B%" peer-fused2-misto -- "%T%" 2 --primary 0 --second 1
echo uscita due-misto %errorlevel%
"%P%" "%B%" peer-fused2-skip -- "%T%" 2 --primary 0 --second 1 --skip
echo uscita skip %errorlevel%
"%P%" "%B%" peer-fused2-skip0 -- "%T%" 2 --primary 0 --second 1 --skip --skip-delay 0
echo uscita skip %errorlevel%
"%P%" "%B%" peer-fused2-stage -- "%T%" 2 --primary 0 --second 1 --stage
echo uscita stage %errorlevel%
"%P%" "%B%" peer-fused2-skip-stage -- "%T%" 2 --primary 0 --second 1 --skip --stage --skip-delay 200
echo uscita skip-stage %errorlevel%
"%P%" "%B%" peer-fused2-uniforme -- "%T%" 2 18 42 512 64 20 7 --primary 0 --second 1 --skip --stage --skip-delay 200
echo uscita uniforme %errorlevel%


set T=C:\Users\imanu\source\repos\Strata-wt\upsync-v0.2.13\build-sm7586\peer_prefill2_test.exe
"%P%" "%B%" prefill2-stessa -- "%T%" 0 0
echo uscita stessa %errorlevel%
"%P%" "%B%" prefill2-3060 -- "%T%" 0 1
echo uscita 3060 %errorlevel%
"%P%" "%B%" prefill2-3060-grande -- "%T%" 0 1 2048 64 4
echo uscita 3060-grande %errorlevel%
"%P%" "%B%" prefill2-2080 -- "%T%" 0 2
echo uscita 2080 %errorlevel%


set T=C:\Users\imanu\source\repos\Strata-wt\upsync-v0.2.13\build-sm7586\mmvq_il_parity.exe
set CUDA_VISIBLE_DEVICES=2
set STRATA_SM75_PERF=1
"%P%" "%B%" il-parita-2080 -- "%T%"
echo uscita 2080 %errorlevel%
set CUDA_VISIBLE_DEVICES=0
"%P%" "%B%" il-parita-3080 -- "%T%"
echo uscita 3080 %errorlevel%


set STRATA_SM75_PERF=
set CUDA_VISIBLE_DEVICES=0,2
"%P%" "%B%" ep-split -- C:\Users\imanu\source\repos\Strata-wt\upsync-v0.2.13\build-sm7586\ep_split_test.exe
echo uscita ep-split %errorlevel%
echo fine banco
