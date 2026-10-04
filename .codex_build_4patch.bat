@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 (
  echo VCVARS_FAIL
  exit /b 1
)

set "CMAKE=C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
set "BUILD=C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-p4a\build-native"

echo BUILD_START %TIME%
"%CMAKE%" --build "%BUILD%" --target ds4_server
if errorlevel 1 (
  echo BUILD_FAIL %TIME%
  exit /b 1
)
echo BUILD_OK %TIME%
