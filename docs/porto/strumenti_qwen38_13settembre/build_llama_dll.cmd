@echo off
setlocal
set "Q=C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean"
set "TEMP=%Q%\tmp"
set "TMP=%Q%\tmp"
set "GIT_CEILING_DIRECTORIES=%Q%"
set "PATH=C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem;C:\Program Files (x86)\Microsoft Visual Studio\Installer;%PATH%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
set "CMAKE_EXE=C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
"%CMAKE_EXE%" --build "%Q%\build" --target llama --parallel 4
exit /b %ERRORLEVEL%
