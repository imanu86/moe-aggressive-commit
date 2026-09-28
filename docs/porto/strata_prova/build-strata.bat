@echo off
rem Compilazione locale del motore Strata (28/9/2026): come setup.py build_engine, ma con il CUDA 12.6 gia' installato
rem (setup.py accetta CUDA >= 12.0 per le GPU sotto sm_120) e senza scaricare il motore precompilato.
rem CMAKE_CUDA_RUNTIME_LIBRARY=Shared: il sorgente linka ovunque CUDA::cudart (DLL); col default Static di CMake il
rem link di strata.exe prendeva anche cudart_static.lib e falliva con LNK2005/LNK1169 (simboli definiti due volte).
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
set "S=D:\ds4_work\strata\Strata"
"%S%\.venv\Scripts\cmake.exe" -G Ninja "-DCMAKE_MAKE_PROGRAM=%S%\.venv\Scripts\ninja.exe" -S "%S%" -B "%S%\build" -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF -DCMAKE_CUDA_ARCHITECTURES=86 -DCMAKE_CUDA_RUNTIME_LIBRARY=Shared "-DCMAKE_CUDA_COMPILER=C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.6/bin/nvcc.exe" "-DSTRATA_GGML_DIR=%S%\third_party\llama.cpp" || exit /b 1
"%S%\.venv\Scripts\cmake.exe" --build "%S%\build" --target strata -j 8 && exit /b 0
echo   (la build si e' fermata - secondo tentativo, come setup.py)
"%S%\.venv\Scripts\cmake.exe" --build "%S%\build" --target strata -j 8 || exit /b 1
