@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 (
  echo VCVARS_FAIL
  exit /b 1
)

set "VALIDATE=C:\Users\imanu\source\repos\moe-aggressive-commit\.codex_validate_g73"
set "DS4BUILD=D:\ds4_work\wt-g73-open\build"
set "CUDA=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6"

echo COMPILE_START %TIME%
"%CUDA%\bin\nvcc.exe" -forward-unknown-to-host-compiler ^
  -DNOMINMAX -DWIN32_LEAN_AND_MEAN -D_CRT_SECURE_NO_WARNINGS -D_WIN32_WINNT=0x0601 ^
  -ID:\ds4_work\wt-g73-open\src\platform -ID:\ds4_work\wt-g73-open\src\win32 ^
  -D_WINDOWS -Xcompiler=" /EHsc" -Xcompiler="-O2 -Ob2" -DNDEBUG -std=c++17 ^
  "--generate-code=arch=compute_80,code=[compute_80,sm_80]" ^
  "--generate-code=arch=compute_86,code=[compute_86,sm_86]" ^
  "--generate-code=arch=compute_89,code=[compute_89,sm_89]" ^
  "--generate-code=arch=compute_90,code=[compute_90,sm_90]" ^
  -Xcompiler=-MD -Xcompiler=/W3 -MD ^
  -MT "%VALIDATE%\ds4_cuda.q1fix.obj" ^
  -MF "%VALIDATE%\ds4_cuda.q1fix.d" ^
  -x cu -c "%VALIDATE%\ds4_cuda.cu" ^
  -o "%VALIDATE%\ds4_cuda.q1fix.obj" ^
  -Xcompiler=-Fd"%VALIDATE%\ds4_cuda.q1fix.pdb",-FS
if errorlevel 1 (
  echo NVCC_FAIL %TIME%
  exit /b 1
)

lib.exe /nologo /machine:x64 ^
  /out:"%VALIDATE%\ds4_cuda.q1fix.lib" ^
  "%VALIDATE%\ds4_cuda.q1fix.obj"
if errorlevel 1 (
  echo LIB_FAIL %TIME%
  exit /b 1
)

echo LINK_START %TIME%
link.exe /nologo ^
  "%DS4BUILD%\CMakeFiles\ds4_server.dir\ds4_server.c.obj" ^
  /out:"%VALIDATE%\ds4_server.q1fix.exe" ^
  /implib:"%VALIDATE%\ds4_server.q1fix.lib" ^
  /pdb:"%VALIDATE%\ds4_server.q1fix.pdb" ^
  /version:0.0 /machine:x64 /INCREMENTAL:NO ^
  "%DS4BUILD%\ds4.lib" ^
  "%VALIDATE%\ds4_cuda.q1fix.lib" ^
  "%CUDA%\lib\x64\cudart.lib" ^
  "%CUDA%\lib\x64\cublas.lib" ^
  ws2_32.lib bcrypt.lib ^
  "%DS4BUILD%\ds4_bake.lib" ^
  "%DS4BUILD%\ds4_platform.lib" ^
  "%CUDA%\lib\x64\cublasLt.lib" ^
  cudadevrt.lib cudart_static.lib ^
  kernel32.lib user32.lib gdi32.lib winspool.lib shell32.lib ^
  ole32.lib oleaut32.lib uuid.lib comdlg32.lib advapi32.lib ^
  /LIBPATH:"%CUDA%\lib\x64"
if errorlevel 1 (
  echo LINK_FAIL %TIME%
  exit /b 1
)

echo BUILD_OK %TIME%
