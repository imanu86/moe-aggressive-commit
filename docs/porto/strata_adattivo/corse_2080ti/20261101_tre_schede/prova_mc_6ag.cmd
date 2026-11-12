@echo off
rem 12/11: rifacimento della corsa a 6 agenti coi due server (STRATA_PEER_BATCH=1), interrotta alle 02:44 dal riavvio di Windows Update.
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set MC_SAVE_TEXT=1
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py 20 s1:2
echo == coda finita
