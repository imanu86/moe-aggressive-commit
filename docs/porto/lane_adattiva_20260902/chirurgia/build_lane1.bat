@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 ( echo VCVARS_FAIL & exit /b 1 )
set "PATH=C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%"
echo BUILD_START %TIME%
cmake --build D:\llama-subtract\build --target ggml-base ggml-cpu ggml-cuda --parallel 8
if errorlevel 1 ( echo BUILD_FAIL %ERRORLEVEL% %TIME% & exit /b 1 )
echo BUILD_OK %TIME%
editbin /STACK:67108864 D:\llama-subtract\build\bin\llama-server.exe >nul
editbin /STACK:67108864 D:\llama-subtract\build\bin\llama-cli.exe >nul
echo EDITBIN_OK