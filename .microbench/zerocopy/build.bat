@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 ( echo VCVARS FAILED & exit /b 1 )
set NVCC="C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe"
cd /d "%~dp0"
%NVCC% -O3 -arch=sm_86 -lineinfo -o zerocopy_bench.exe zerocopy_bench.cu %NVCC_EXTRA%
if errorlevel 1 ( echo BUILD FAILED & exit /b 1 )
echo BUILD OK
exit /b 0
