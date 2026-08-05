@echo off
REM ===========================================================================
REM  AVVIA_WEBUI.bat -- Open WebUI davanti a DeepSeek
REM
REM  Da lanciare DOPO AVVIA.bat, quando il server del modello e' pronto.
REM  Da' cronologia salvata sul server (non nel browser), ricerca web
REM  integrata, e la possibilita' di collegare piu' modelli.
REM ===========================================================================

REM --- LE MANOPOLE ------------------------------------------------------------

REM Dove sta il modello. Se cambi porta in AVVIA.bat, cambiala anche qui.
set MODELLO_URL=http://127.0.0.1:8080/v1

REM Porta della web UI e indirizzo.
set PORTA=3000
set INDIRIZZO=0.0.0.0

REM Autenticazione. False = nessun login (comodo in casa).
REM Mettila a True se apri la porta oltre la rete locale.
set AUTENTICAZIONE=False

REM --- FINE DELLE MANOPOLE ----------------------------------------------------

set BASE=C:\openwebui
set OPENAI_API_BASE_URL=%MODELLO_URL%
set OPENAI_API_KEY=locale
set WEBUI_AUTH=%AUTENTICAZIONE%
set ENABLE_OLLAMA_API=False
set DATA_DIR=%BASE%\data

echo.
echo   modello    %MODELLO_URL%
echo   interfaccia  http://%INDIRIZZO%:%PORTA%
echo.
echo   Il primo avvio impiega un paio di minuti.
echo.

"%BASE%\venv\Scripts\open-webui.exe" serve --host %INDIRIZZO% --port %PORTA%

echo.
echo   Interfaccia terminata.
pause
