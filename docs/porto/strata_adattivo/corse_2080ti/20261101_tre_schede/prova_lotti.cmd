@echo off
rem Banco del mega-kernel per piu' richieste (lab/server-lotti, docs/PEER_FUSED2.md §12): finestre larghe e banchi di prima.
set CUDA_DEVICE_ORDER=PCI_BUS_ID
set CUDA_VISIBLE_DEVICES=0,1,2
set STRATA_EXP_MODE=8
set T=C:\Users\imanu\source\repos\Strata-wt\server-lotti\build-sm7586\peer_fused_test.exe
set B=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
"%P%" "%B%" lotti-uno -- "%T%" 2 --primary 0
echo uscita uno %errorlevel%
"%P%" "%B%" lotti-max8 -- "%T%" 2 --max-t 8
echo uscita max8 %errorlevel%
"%P%" "%B%" lotti-due-skip-stage -- "%T%" 2 --primary 0 --second 1 --skip --stage
echo uscita due-skip-stage %errorlevel%
"%P%" "%B%" lotti-wide-uno -- "%T%" 2 --wide
echo uscita wide-uno %errorlevel%
"%P%" "%B%" lotti-wide-due -- "%T%" 2 --second 1 --wide
echo uscita wide-due %errorlevel%
"%P%" "%B%" lotti-wide-due-skip-stage -- "%T%" 2 --second 1 --primary 0 --wide --skip --stage
echo uscita wide-due-skip-stage %errorlevel%
"%P%" "%B%" lotti-wide-64 -- "%T%" 2 --second 1 --wide --max-t 64
echo uscita wide-64 %errorlevel%
echo fine banco
