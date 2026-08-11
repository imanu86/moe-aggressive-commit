@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 ( echo VCVARS_FAIL & exit /b 1 )
set "NVCC=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe"
"%NVCC%" -O3 -arch=sm_86 "%~dp0blocco.cu" -o "%~dp0blocco.exe"
if errorlevel 1 ( echo BUILD_FAIL & exit /b 1 )
echo BUILD_OK
