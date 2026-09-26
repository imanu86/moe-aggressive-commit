@echo off
setlocal
REM Compile only. Never execute validator here; parent owns all GPU operations.
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" -vcvars_ver=14.44
if errorlevel 1 exit /b %errorlevel%
set "LAB=D:\ds4_work\qwen4b_kernel_lab"
set "CUDA=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6"
python "%LAB%\make_occ12_unit.py"
if errorlevel 1 exit /b %errorlevel%
"%CUDA%\bin\nvcc.exe" -std=c++17 -O2 -use_fast_math -extended-lambda --cudart shared ^
 --generate-code=arch=compute_86,code=[compute_86,sm_86] ^
 -DGGML_SHARED -DGGML_BACKEND_SHARED -DGGML_CUDA_PEER_MAX_BATCH_SIZE=128 -DGGML_SCHED_MAX_COPIES=4 ^
 -Xcompiler="/EHsc /MD /O2 /Ob2 /DNDEBUG /Zc:preprocessor" -Xptxas=-v ^
 -I"%LAB%\source\ggml\include" -I"%LAB%\source\ggml\src" -I"%LAB%\source\ggml\src\ggml-cuda" ^
 "%LAB%\evidence\unit_occ12.cu" "%LAB%\build\ggml\src\ggml-base.lib" ^
 -o "%LAB%\evidence\unit_occ12.exe"
exit /b %errorlevel%
