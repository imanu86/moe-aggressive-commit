@echo off
rem 16/11: compila lab/upstream-slot (fork bitaccesscomau pr/slot-read-ahead = PR 5860-5868 su upstream 13eedf552), stesse opzioni di tappa4c, 4 job, dietro bench_lock
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d C:\Users\imanu\source\repos\Strata-wt\upstream-slot
cmake -S . -B build-sm7586 -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_RUNTIME_LIBRARY=Shared -DCMAKE_CUDA_ARCHITECTURES=75;86 -DSTRATA_ENABLE_CUDA=ON -DSTRATA_GEOMETRY=flash_next -DSTRATA_GGML_DIR=D:/ds4_work/strata/Strata/third_party/llama.cpp -DSTRATA_NATIVE_EXPERTS=ON -DSTRATA_MMQ_KQUANTS=ON -DSTRATA_MMQ_TQ_OVERLAY=ON -DSTRATA_BUILD_TESTS=OFF -DSTRATA_WERROR=OFF "-DCMAKE_CUDA_COMPILER=C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.6/bin/nvcc.exe"
echo uscita configurazione %errorlevel%
"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\bench_lock.py COMPILA-UPSTREAM-SLOT -- cmake --build build-sm7586 --target strata -j 4
echo uscita compilazione %errorlevel%
echo == coda finita
