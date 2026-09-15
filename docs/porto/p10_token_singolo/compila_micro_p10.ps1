# P10 cella 3 - compila il microbanco isolato del kernel iq2_s.
# Non tocca l'albero P8: compila un .cu autonomo che include solo ggml-common.h.
param(
    [string]$Sorgente = "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\p10_token_singolo\micro_iq2s_p10.cu",
    [string]$Uscita   = "D:\ds4_work\p8_work\prove\micro_iq2s_p10.exe"
)

$ErrorActionPreference = "Continue"
$nvcc   = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe"
$vcvars = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
$inc    = "D:\ds4_work\p8_work\source\ggml\src"
$tmpdir = "D:\ds4_work\p8_work\tmp"

New-Item -ItemType Directory -Force -Path (Split-Path $Uscita) | Out-Null
New-Item -ItemType Directory -Force -Path $tmpdir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$bat = @"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
set "TEMP=$tmpdir"
set "TMP=$tmpdir"
"$nvcc" -O3 -std=c++17 -arch=sm_86 -lineinfo -I"$inc" "$Sorgente" -o "$Uscita"
exit /b %ERRORLEVEL%
"@
$tmpBat = Join-Path $env:TEMP ("p10c3_micro_" + $stamp + ".cmd")
Set-Content -Path $tmpBat -Value $bat -Encoding ASCII
& cmd /c "`"$tmpBat`"" 2>&1 | Write-Output
$rc = $LASTEXITCODE
Remove-Item -Force $tmpBat -ErrorAction SilentlyContinue
Write-Output "codice di uscita: $rc"
exit $rc
