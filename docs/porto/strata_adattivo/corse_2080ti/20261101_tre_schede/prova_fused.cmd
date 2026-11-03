@echo off
rem Banco bit per bit del mega-kernel (tools/peer_fused_test.cu): server sulla 2080 Ti, padrona finta sulla 3080 Ti. Sotto bench.lock.
rem Prima il modello misto (le 10 coppie di tipi del pack), poi l'uniforme IQ3_XXS/Q2_0 di controllo.
set CUDA_DEVICE_ORDER=PCI_BUS_ID
set CUDA_VISIBLE_DEVICES=0,2
set T=C:\Users\imanu\source\repos\Strata-wt\upsync-v0.2.9\build-sm7586\peer_fused_test.exe
set B=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py
set P=C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe
"%P%" "%B%" peer-fused-misto -- "%T%" 1 --primary 0
echo uscita misto %errorlevel%
"%P%" "%B%" peer-fused-uniforme -- "%T%" 1 18 42 512 64 20 7 --primary 0
echo uscita uniforme %errorlevel%
