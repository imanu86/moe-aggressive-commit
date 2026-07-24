[CmdletBinding()]
param(
    [switch]$CpuOnly
)

$ErrorActionPreference = "Stop"

$cmake = "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
$ninja = "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe"
$cl = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\cl.exe"
$nvcc = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe"
$vsDevCmd = "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"
$vsInstaller = "C:\Program Files (x86)\Microsoft Visual Studio\Installer"
$buildDir = Join-Path $PSScriptRoot "build"

foreach ($path in @($cmake, $ninja, $cl, $vsDevCmd)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required tool not found: $path"
    }
}
if (-not $CpuOnly -and -not (Test-Path -LiteralPath $nvcc -PathType Leaf)) {
    throw "CUDA 12.6 compiler not found: $nvcc"
}

# Import the x64 MSVC/Windows SDK environment without relying on a caller's shell.
$env:Path = "$vsInstaller;$env:Path"
$environmentDump = & $env:ComSpec /d /s /c "`"$vsDevCmd`" -no_logo -arch=x64 -host_arch=x64 >nul && set"
if ($LASTEXITCODE -ne 0) {
    throw "VsDevCmd failed with exit code $LASTEXITCODE"
}
foreach ($line in $environmentDump) {
    if ($line -match "^([^=]+)=(.*)$") {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
    }
}

$cudaBuildSetting = if ($CpuOnly) { "OFF" } else { "ON" }
$configure = @(
    "-S", $PSScriptRoot,
    "-B", $buildDir,
    "-G", "Ninja",
    "-DCMAKE_BUILD_TYPE=Release",
    "-DCMAKE_MAKE_PROGRAM=$ninja",
    "-DCMAKE_CXX_COMPILER=$cl",
    "-DAUDIT0_BUILD_CUDA=$cudaBuildSetting"
)
if (-not $CpuOnly) {
    $configure += "-DCMAKE_CUDA_COMPILER=$nvcc"
    $configure += "-DCMAKE_CUDA_ARCHITECTURES=86"
}

& $cmake @configure
if ($LASTEXITCODE -ne 0) {
    throw "CMake configure failed with exit code $LASTEXITCODE"
}

$targets = if ($CpuOnly) { @("audit0_cpu") } else { @("audit0_cpu", "audit0_gpu") }
$buildArguments = @("--build", $buildDir, "--config", "Release", "--target") + $targets
& $cmake @buildArguments
if ($LASTEXITCODE -ne 0) {
    throw "Build failed with exit code $LASTEXITCODE"
}

Write-Host "Built: $(Join-Path $buildDir 'audit0_cpu.exe')"
if (-not $CpuOnly) {
    Write-Host "Built (do not run for CPU-only audit collection): $(Join-Path $buildDir 'audit0_gpu.exe')"
}
