@echo off
rem Strata SOTA del 30/9/2026 sulla RTX 2080 Ti: originale 0.1.29 + patch del fork 0001-0005
rem (cache esperti elastica a due zone: nucleo fisso + coda di al massimo 6 GiB che ruota e cala a passi),
rem riserva di VRAM all'avvio 1393 MiB, contesto 139264, KV int8 in streaming, bozza MTP.
rem Misure: ~44-45 t/s sui prompt corti con OktoCGControl acceso; 4.096 token in 96 s con 4 GB presi da un altro
rem programma (docs/porto/strata_adattivo/RISULTATI_2080TI_30_SETTEMBRE.md nel repo moe-aggressive-commit).
rem Configurazione: D:\ds4_work\strata\Strata\strata-2080ti-sota.json. Porta 8100 SOLO su questo PC (127.0.0.1).
rem Chiave API: il server usa da solo la variabile d'ambiente STRATA_API_KEY, se esiste (questo file non la contiene).
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
if not exist "%S%\build-0129\strata.exe" (
  echo ERRORE: manca %S%\build-0129\strata.exe
  pause
  exit /b 1
)
"%S%\.venv\Scripts\python.exe" "%S%\serve\server.py" --engine strata --config "%S%\strata-2080ti-sota.json" --host 127.0.0.1 --port 8100
if errorlevel 1 pause
