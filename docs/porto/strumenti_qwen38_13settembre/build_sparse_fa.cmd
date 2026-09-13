@echo off
setlocal
REM Ricompila la parte CUDA (i 21 file di istanza della flash attention MMA si rifanno
REM perche' abbiamo toccato fattn-mma-f16.cuh) piu' llama e il server.
set "Q=C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean"
set "TEMP=%Q%\tmp"
set "TMP=%Q%\tmp"
set "GIT_CEILING_DIRECTORIES=%Q%"
set "PATH=C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem;C:\Program Files (x86)\Microsoft Visual Studio\Installer;%PATH%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
set "CMAKE_EXE=C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
echo === avvio build: %DATE% %TIME%
"%CMAKE_EXE%" --build "%Q%\build" --target ggml-cuda llama llama-server --parallel 4
set "RC=%ERRORLEVEL%"
echo === fine build: %DATE% %TIME%  codice %RC%
exit /b %RC%
