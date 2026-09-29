@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe" -O2 -arch=sm_86 -o D:\ds4_work\strata\hog.exe "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\strumenti\hog.cu"

