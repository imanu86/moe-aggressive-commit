@echo off
rem 12/11 mattina: la 2080 Ti (22 GB, x16) come scheda principale. Replay a 3 agenti: divisione a strati `2,0` con split auto (y),
rem poi due server 3080 Ti + 3060 come s3 (v). Confronto: divisione `0,2` 242 s, due server s3 666 s.
cd /d C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261101_tre_schede
set MC_SAVE_TEXT=1
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -u coda_multichat.py auto y v
echo == coda finita
