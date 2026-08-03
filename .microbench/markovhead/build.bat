@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 ( echo VCVARS FAILED & exit /b 1 )
cd /d "%~dp0"
cl /nologo /O2 /EHsc /std:c++17 /I D:\llama-dspark\ggml\include markov_bench.cpp ^
   /link /LIBPATH:D:\llama-dspark\build\ggml\src /LIBPATH:D:\llama-dspark\build\ggml\src\ggml-cuda ^
   ggml.lib ggml-base.lib ggml-cpu.lib ggml-cuda.lib /OUT:markov_bench.exe
if errorlevel 1 ( echo BUILD FAILED & exit /b 1 )
echo BUILD OK
exit /b 0
