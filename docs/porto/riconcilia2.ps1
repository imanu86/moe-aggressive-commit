# Continua la riconciliazione sul worktree ds4-0731-merge GIA' esistente,
# senza ricrearlo: dentro c'e' la risoluzione a mano del conflitto moeio.
#
# Correzione rispetto al primo tentativo: il generatore. `cmake -B dir` senza -G
# sceglie Visual Studio, che e' multi-config e IGNORA CMAKE_BUILD_TYPE: il
# risultato era un binario Debug da 12,6 MB in build-verify\Debug\. ds4-port usa
# Ninja + Release (7,1 MB). Misurare un runtime CUDA in Debug non ha senso.
param(
    [string[]]$Restanti = @('vittima','tiering'),
    [switch]$SoloBuild
)
$ErrorActionPreference = 'Continue'
$R  = 'C:\Users\imanu\source\repos\moe-aggressive-commit'
$wm = "$R\ds4-0731-merge"
$vcvars = 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'

function Costruisci([string]$etichetta) {
    $bat = Join-Path $env:TEMP "b2_$etichetta.bat"
    @"
@echo off
call "$vcvars" >nul 2>&1
cd /d "$wm"
if not exist build-ninja cmake -S . -B build-ninja -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-ninja --parallel 6
exit /b %ERRORLEVEL%
"@ | Set-Content -LiteralPath $bat -Encoding ASCII
    $log = "$R\docs\porto\b2_$etichetta.log"
    $t = Get-Date
    & cmd.exe /c $bat *> $log
    $code = $LASTEXITCODE
    $sec = ((Get-Date) - $t).TotalSeconds
    Write-Output ("    build {0} in {1:N0}s   -> docs\porto\b2_$etichetta.log" -f $(if ($code -eq 0) {'OK'} else {"FALLITA (exit $code)"}), $sec)
    if ($code -ne 0) {
        Get-Content $log -Raw -Encoding Unicode -EA SilentlyContinue |
            ForEach-Object { $_ -split "`n" } |
            Where-Object { $_ -match 'error [A-Z]?\d+|nvcc fatal|FAILED' } |
            Select-Object -First 10 | ForEach-Object { Write-Output ("      " + $_.Trim()) }
    }
    return ($code -eq 0)
}

# il build Visual Studio del primo tentativo e' Debug: via
if (Test-Path "$wm\build-verify") {
    "  rimuovo il build Visual Studio (Debug) del primo tentativo"
    Remove-Item -Recurse -Force "$wm\build-verify"
}

"=== BUILD DI CONTROLLO: base + prefill + moeio ==="
$ok = Costruisci 'prefill_moeio'
if (-not $ok) { "*** si ferma qui: la risoluzione del conflitto moeio non compila ***"; exit 1 }
if ($SoloBuild) { exit 0 }

foreach ($b in $Restanti) {
    "`n=== MERGE $b ==="
    git -C $wm merge --no-edit "port/v2-$b" 2>&1 | Select-Object -Last 2 | ForEach-Object { "    $_" }
    $u = @(git -C $wm diff --name-only --diff-filter=U)
    if ($u.Count -gt 0) {
        "    CONFLITTO su:"; $u | ForEach-Object { "      $_" }
        "    merge lasciato aperto, risolvere a mano"
        exit 2
    }
    "    merge pulito"
    if (-not (Costruisci $b)) { "    *** rotto da $b ***"; exit 3 }
}

"`n=== ESITO ==="
"  tutti e quattro i rami dentro, e compila in Release."
$e = Get-ChildItem "$wm\build-ninja" -Recurse -Filter 'ds4-server.exe' -EA SilentlyContinue | Select-Object -First 1
if ($e) { "  binario: {0}  {1:N1} MB" -f $e.FullName, ($e.Length/1MB) }
git -C $wm log --oneline port/upstream-substrate..HEAD | ForEach-Object { "    $_" }
