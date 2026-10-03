@echo off
rem Strata daily validata il 3/10/2026: 0.1.38 + sm75/elastica + top-k #603 + checkpoint tail #614; grid rimossa, quantizzazione seriale.
rem Cache esperti auto/elastica a due zone, riserva 1393 MiB, KV int8 262144 con residenti 32768, MTP.
rem Sorgenti completi e server della build: D:\ds4_work\strata\Strata\build-0138-daily\source.
rem Misure e ripristino: docs/porto/strata_adattivo/ALLINEAMENTO_0138_GRID_RIMOSSA_3_OTTOBRE.md.
rem Porta 8100 su 127.0.0.1; chiave API dalla variabile STRATA_API_KEY, mai salvata qui.
setlocal
tasklist /FI "IMAGENAME eq strata.exe" /NH | findstr /I /C:"strata.exe" >nul
if not errorlevel 1 (
  echo Strata e' gia' in esecuzione: chiudi l'altra finestra prima di lanciarne un'altra.
  pause
  exit /b 1
)
tasklist /FI "IMAGENAME eq llama-server.exe" /NH | findstr /I /C:"llama-server.exe" >nul
if not errorlevel 1 (
  echo Un llama-server e' gia' in esecuzione ^(il daily?^): chiudilo prima, la VRAM non basta per due.
  pause
  exit /b 1
)
set "S=D:\ds4_work\strata\Strata"
if not exist "%S%\build-0138-daily\strata.exe" (
  echo ERRORE: manca %S%\build-0138-daily\strata.exe
  pause
  exit /b 1
)
"%S%\.venv\Scripts\python.exe" "%S%\build-0138-daily\source\serve\server.py" --engine strata --config "%S%\strata-2080ti-sota.json" --host 127.0.0.1 --port 8100
if errorlevel 1 pause
