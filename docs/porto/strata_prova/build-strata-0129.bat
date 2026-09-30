@echo off
rem Compilazione di Strata 0.1.29 + patch del fork per la 2080 Ti (sm_75) e la 3060 (sm_86), 30/9/2026.
rem Come build-strata.bat, ma in una cartella separata (build-0129; build e build-sm75 della 0.1.21 restano). Dalla 0.1.27
rem l'originale accetta sm_75 senza opzioni sperimentali (CMakeLists.txt rifiuta solo sotto 75).
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
set "S=D:\ds4_work\strata\Strata"
"%S%\.venv\Scripts\cmake.exe" -G Ninja "-DCMAKE_MAKE_PROGRAM=%S%\.venv\Scripts\ninja.exe" -S "%S%" -B "%S%\build-0129" -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF "-DCMAKE_CUDA_ARCHITECTURES=75;86" -DCMAKE_CUDA_RUNTIME_LIBRARY=Shared "-DCMAKE_CUDA_COMPILER=C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.6/bin/nvcc.exe" "-DSTRATA_GGML_DIR=%S%\third_party\llama.cpp" || exit /b 1
"%S%\.venv\Scripts\cmake.exe" --build "%S%\build-0129" --target strata -j 8 && exit /b 0
echo   (la build si e' fermata - secondo tentativo, come setup.py)
"%S%\.venv\Scripts\cmake.exe" --build "%S%\build-0129" --target strata -j 8 || exit /b 1
