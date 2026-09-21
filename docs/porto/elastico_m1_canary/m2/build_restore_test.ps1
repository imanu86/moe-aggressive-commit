# Compila ed esegue il test d'integrazione di ggml_cuda_ram_restore_all().
# Header dell'overlay M2; librerie e DLL del build O2 di Codex usate in SOLA LETTURA.
$ErrorActionPreference = "Stop"
$m2  = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$old = "C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920"
$base = Join-Path $old "build\ggml\src\ggml-base.lib"
$cpu  = Get-ChildItem -Path (Join-Path $old "build") -Recurse -Filter ggml-cpu.lib | Select-Object -First 1 -ExpandProperty FullName
if (!(Test-Path $base) -or !$cpu) { throw "ggml-base.lib / ggml-cpu.lib non trovate nel build O2" }
$vcvars = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
$source = Join-Path $PSScriptRoot "ram_store_restore_test.cpp"
$output = Join-Path $PSScriptRoot "ram_store_restore_test.exe"
$object = Join-Path $PSScriptRoot "ram_store_restore_test.obj"
$includes = @("$old\source\ggml\include", "$old\source\ggml\src", "$m2\source-overlay\ggml\src\ggml-cuda") | ForEach-Object { "/I`"$_`"" }
$command = "call `"$vcvars`" >nul && cl /nologo /std:c++17 /EHsc /O2 /MD $($includes -join ' ') `"$source`" /Fo:`"$object`" /Fe:`"$output`" `"$base`" `"$cpu`" psapi.lib"
cmd /d /s /c $command
if ($LASTEXITCODE -ne 0) { Write-Output "COMPILAZIONE FALLITA ($LASTEXITCODE)"; exit $LASTEXITCODE }
$env:PATH = (Join-Path $old "build\bin") + ";" + $env:PATH
& $output
Write-Output "uscita del test: $LASTEXITCODE"
exit $LASTEXITCODE
