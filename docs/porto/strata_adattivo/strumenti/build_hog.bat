@echo off
rem 30/9: sm_75 (2080 Ti) e sm_86 (3060) nello stesso eseguibile
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe" -O2 -gencode arch=compute_75,code=sm_75 -gencode arch=compute_86,code=sm_86 -o D:\ds4_work\strata\hog.exe "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\strumenti\hog.cu"
