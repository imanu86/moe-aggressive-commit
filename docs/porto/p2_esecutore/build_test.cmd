@echo off
rem P2 - compilazione della prova host-only dell'esecutore CPU.
rem Stesso metodo di freetoken_hybrid\build.cmd: cl.exe con le .lib della build
rem privata GGML e le DLL corrispondenti copiate accanto all'eseguibile.
rem
rem LIBRERIE: NON serve Synchronization.lib. WaitOnAddress/WakeByAddressAll sono
rem risolte a caldo con LoadLibraryA/GetProcAddress (moe_cpu_executor.cpp,
rem `sync_api`), quindi il binario non ha nessuna dipendenza statica da quella
rem libreria e gira anche dove l'API non esiste (ripiego su Sleep(1)).
rem <synchapi.h> arriva comunque via <windows.h>: le sue dichiarazioni restano
rem inutilizzate ed e' voluto. Se un giorno si passasse al collegamento statico,
rem la riga da aggiungere e' `Synchronization.lib` nella sezione /link QUI e la
rem stessa nota in build_test.ps1.
rem
rem NON ESEGUITO nella fase di progetto: sulla macchina gira una misura di
rem baseline. Lanciarlo solo nella fase di compilazione concordata.
setlocal
cd /d "%~dp0"

set "QROOT=C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean"
set "VCVARS=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"

if not exist "%QROOT%\build\ggml\src\ggml-cpu.lib" (
    echo build GGML non trovata in %QROOT%\build
    exit /b 1
)

call "%VCVARS%" >nul
if errorlevel 1 exit /b 1

rem /utf-8: i sorgenti hanno commenti in italiano con em-dash, virgolette basse e
rem disegni a caratteri di riquadro (la macchina a stati in moe_cpu_executor.h).
rem Senza /utf-8 MSVC li legge nella codepage di sistema: nel caso peggiore una
rem sequenza multibyte che finisce con il byte 0x5C spezza una riga di commento.
cl /nologo /std:c++17 /utf-8 /O2 /EHsc /MD /W4 ^
   /I"%QROOT%\source\ggml\include" /Isrc ^
   src\test_esecutore.cpp src\moe_cpu_executor.cpp src\moe_cpu_host_memory_plain.cpp ^
   /link "%QROOT%\build\ggml\src\ggml-cpu.lib" ^
         "%QROOT%\build\ggml\src\ggml-base.lib" ^
         "%QROOT%\build\ggml\src\ggml.lib" ^
   /OUT:test_esecutore.exe
if errorlevel 1 exit /b 1

rem moe_cpu_host_memory_cuda.cpp NON viene compilato qui: richiede
rem ggml-backend.h e i proc-address del backend CUDA, che il test host-only non
rem usa. Si compila in P3, insieme al motore.

copy /y "%QROOT%\build\bin\ggml-cpu.dll"  . >nul
copy /y "%QROOT%\build\bin\ggml-base.dll" . >nul
copy /y "%QROOT%\build\bin\ggml.dll"      . >nul

echo compilato: test_esecutore.exe
echo esecuzione rapida  : test_esecutore.exe --threads 4
echo esecuzione completa: test_esecutore.exe --full --threads 4
echo con i pesi veri    : test_esecutore.exe --weights PERCORSO_cpu_quant_audit --threads 4
echo.
echo nota: T12/T13/T15 usano ritardi iniettati (120-300 ms) e thread
echo       concorrenti. La batteria dura qualche secondo in piu' della prima
echo       stesura ed e' normale.
