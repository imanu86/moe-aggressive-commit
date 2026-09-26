@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" -vcvars_ver=14.44
if errorlevel 1 exit /b %errorlevel%
set "PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin;%PATH%"
set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6"
set "CMAKE=C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
"%CMAKE%" -S D:\ds4_work\qwen4b_kernel_lab\source -B D:\ds4_work\qwen4b_kernel_lab\build -G Ninja ^
 -DCMAKE_MAKE_PROGRAM="C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe" ^
 -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=86 ^
 -DCMAKE_CUDA_COMPILER="C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.6/bin/nvcc.exe" ^
 -DCUDAToolkit_ROOT="C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.6" ^
 -DBUILD_SHARED_LIBS=ON -DGGML_BACKEND_DL=OFF -DGGML_CUDA=ON ^
 -DGGML_CUDA_GRAPHS=ON -DGGML_CUDA_FA=ON -DGGML_CUDA_FA_ALL_QUANTS=OFF ^
 -DGGML_CUDA_FORCE_MMQ=OFF -DGGML_CUDA_FORCE_CUBLAS=OFF -DGGML_CUDA_COMPRESSION_MODE=size ^
 -DGGML_CUDA_NO_VMM=OFF -DGGML_CUDA_NO_PEER_COPY=OFF -DGGML_CUDA_PEER_MAX_BATCH_SIZE=128 ^
 -DGGML_NATIVE=ON -DGGML_AVX=OFF -DGGML_AVX2=OFF -DGGML_SSE42=OFF -DGGML_BMI2=OFF ^
 -DGGML_LTO=OFF -DGGML_BUILD_TESTS=OFF -DGGML_BUILD_EXAMPLES=OFF ^
 -DLLAMA_BUILD_COMMON=OFF -DLLAMA_BUILD_SERVER=OFF -DLLAMA_BUILD_TOOLS=OFF ^
 -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_MTMD=OFF -DLLAMA_BUILD_UI=OFF ^
 -DLLAMA_BUILD_APP=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_CURL=OFF
if errorlevel 1 exit /b %errorlevel%
"%CMAKE%" --build D:\ds4_work\qwen4b_kernel_lab\build --target ggml-cuda --parallel 4
exit /b %errorlevel%
