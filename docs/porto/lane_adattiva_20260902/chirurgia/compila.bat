@echo off
setlocal
rem lane-adattiva (2/9) -- compilazione ISOLATA in scratch. Nessun link, nessuna
rem DLL, nessuna scrittura in D:\llama-subtract (usato solo in SOLA LETTURA per
rem gli include). Una sola arch: sm_86.
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 ( echo VCVARS_FAIL & exit /b 1 )

set "SP=C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\47178466-5d2e-4455-9f5c-7b7df5918069\scratchpad\chirurgia_lane"
set "CUDA=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6"
set "TREE=D:\llama-subtract"
set "STAGE=%1"

echo === STADIO %STAGE% : nvcc cache-esperti.cu  %TIME%
"%CUDA%\bin\nvcc.exe" -forward-unknown-to-host-compiler ^
  -DGGML_BACKEND_BUILD -DGGML_BACKEND_SHARED -DGGML_CUDA_PEER_MAX_BATCH_SIZE=128 ^
  -DGGML_CUDA_USE_GRAPHS -DGGML_SCHED_MAX_COPIES=4 -DGGML_SHARED ^
  -D_CRT_SECURE_NO_WARNINGS -D_XOPEN_SOURCE=600 -Dggml_cuda_EXPORTS ^
  -I"%SP%\comp%STAGE%" ^
  -I"%TREE%\ggml\src" -I"%TREE%\ggml\include" -I"%TREE%\ggml\src\ggml-cuda" ^
  -isystem "%CUDA%\include" ^
  -D_WINDOWS -Xcompiler=" /EHsc" -Xcompiler="-O2 -Ob2" -DNDEBUG -std=c++17 ^
  "--generate-code=arch=compute_86,code=[compute_86,sm_86]" ^
  -Xcompiler=-MD -use_fast_math -extended-lambda -Xcompiler /Zc:preprocessor ^
  -x cu -c "%SP%\comp%STAGE%\cache-esperti.cu" ^
  -o "%SP%\log\cache-esperti.s%STAGE%.obj"
if errorlevel 1 ( echo NVCC_FAIL %TIME% & exit /b 1 )
echo NVCC_OK %TIME%
exit /b 0
