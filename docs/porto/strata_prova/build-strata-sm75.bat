@echo off
rem Compilazione di Strata per la RTX 2080 Ti (Turing, sm_75) e la 3060 (sm_86) nello stesso binario, 30/9/2026.
rem Come build-strata.bat, ma in una cartella separata (build-sm75: la build sm_86 resta com'e') e con l'opzione
rem sperimentale dell'originale STRATA_EXPERIMENTAL_SM75 (CMakeLists.txt rifiuta le schede sotto sm_80 senza di essa;
rem docs/MULTI_GPU.md: pensata per la 2080 Ti come seconda scheda del layer split).
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
set "S=D:\ds4_work\strata\Strata"
"%S%\.venv\Scripts\cmake.exe" -G Ninja "-DCMAKE_MAKE_PROGRAM=%S%\.venv\Scripts\ninja.exe" -S "%S%" -B "%S%\build-sm75" -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF "-DCMAKE_CUDA_ARCHITECTURES=75;86" -DSTRATA_EXPERIMENTAL_SM75=ON -DCMAKE_CUDA_RUNTIME_LIBRARY=Shared "-DCMAKE_CUDA_COMPILER=C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.6/bin/nvcc.exe" "-DSTRATA_GGML_DIR=%S%\third_party\llama.cpp" || exit /b 1
"%S%\.venv\Scripts\cmake.exe" --build "%S%\build-sm75" --target strata -j 8 && exit /b 0
echo   (la build si e' fermata - secondo tentativo, come setup.py)
"%S%\.venv\Scripts\cmake.exe" --build "%S%\build-sm75" --target strata -j 8 || exit /b 1
