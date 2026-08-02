# Riconcilia i quattro rami di porto su 0731 e verifica che compili.
#
# I quattro Codex non possono committare da soli: il sandbox workspace-write li
# limita alla radice -C, ma i metadati di un worktree stanno in
# ds4-p4a/.git/worktrees/<nome>, che e' fuori. Committa il coordinatore.
#
# Ordine di merge scelto per superficie crescente sul file piu' conteso
# (ds4_cuda.cu, toccato da tutti e quattro):
#   prefill  -> quasi tutti file suoi (dynamic_arena.cu, prefill_observer.cu, ds4_gpu.h)
#   moeio    -> due file
#   vittima  -> sei file ma diff piccola
#   tiering  -> 954 righe sul file piu' conteso, per ultimo
#
# Build vera a OGNI passo: un conflitto risolto male si scopre subito e non a
# fine catena, quando non si sa piu' chi l'ha rotto.
param(
    [switch]$SoloCommit,           # committa i rami e basta, niente merge
    [switch]$SaltaBuild,           # merge senza compilare (sconsigliato)
    [string]$RamoMerge = 'port/v2-merge'
)
# PowerShell 5.1 trasforma i warning di git su stderr in errori terminanti: con
# 'Stop' il primo "LF will be replaced by CRLF" ferma tutto. Controllo
# $LASTEXITCODE a mano dove conta.
$ErrorActionPreference = 'Continue'
$R    = 'C:\Users\imanu\source\repos\moe-aggressive-commit'
$Base = 'port/upstream-substrate'
$Ordine = @('prefill','moeio','vittima','tiering')
$vcvars = 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'

function Costruisci([string]$dir, [string]$etichetta) {
    if ($SaltaBuild) { "    build saltata"; return $true }
    $bat = Join-Path $env:TEMP "build_$etichetta.bat"
    @"
@echo off
call "$vcvars" >nul 2>&1
cd /d "$dir"
if not exist build-verify cmake -S . -B build-verify -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-verify --parallel 6
exit /b %ERRORLEVEL%
"@ | Set-Content -LiteralPath $bat -Encoding ASCII
    $log = Join-Path $R "docs\porto\build_$etichetta.log"
    $t = Get-Date
    & cmd.exe /c $bat *> $log
    $ok = ($LASTEXITCODE -eq 0)
    $sec = ((Get-Date) - $t).TotalSeconds
    "    build {0} in {1:N0}s   -> docs\porto\build_$etichetta.log" -f $(if ($ok) {'OK'} else {"FALLITA (exit $LASTEXITCODE)"}), $sec
    if (-not $ok) {
        Select-String -LiteralPath $log -Pattern 'error C\d{4}|LNK\d{4}|nvcc fatal|Error' |
            Select-Object -First 8 | ForEach-Object { "      $($_.Line.Trim())" }
    }
    return $ok
}

# ---------- 1. committa i quattro rami ----------
"=== COMMIT DEI RAMI ==="
foreach ($b in $Ordine) {
    $w = Join-Path $R "ds4-0731-$b"
    if (-not (Test-Path $w)) { "  $b : worktree assente, salto"; continue }
    $sporco = @(git -C $w status --porcelain | Where-Object { $_ -notmatch 'MANDATO\.md|NOTA_BUILD\.md|build\.bat|build-verify/|PORTO\.md' })
    if (-not $sporco) { "  $b : niente da committare"; continue }
    git -C $w add -A -- . ':!build-verify' ':!MANDATO.md' ':!NOTA_BUILD.md' ':!build.bat' 2>&1 | Out-Null
    git -C $w add -f PORTO.md 2>&1 | Out-Null
    $stat = (git -C $w diff --cached --shortstat).Trim()
    git -C $w commit -q -m "port(v2-$b): variabili della nostra politica su 0731

Portate dal fork ../ds4-p4a, additive e spente di default: a variabile
d'ambiente assente il comportamento di upstream resta invariato.
Rapporto in PORTO.md con file:riga per ciascuna.

$stat

Co-Authored-By: Codex <noreply@openai.com>"
    "  $b : $stat  -> $(git -C $w log --oneline -1)"
}
if ($SoloCommit) { "solo-commit richiesto, mi fermo"; exit 0 }

# ---------- 2. merge sequenziale, con build a ogni passo ----------
"`n=== MERGE SU $RamoMerge ==="
$wm = Join-Path $R 'ds4-0731-merge'
if (Test-Path $wm) {
    git -C $R\ds4-p4a worktree remove --force "$wm" 2>&1 | Out-Null
}
git -C "$R\ds4-p4a" worktree add "$wm" -b $RamoMerge $Base 2>&1 | Select-Object -Last 1 | ForEach-Object { "  $_" }

if (-not (Costruisci $wm 'base')) {
    "*** LA BASE NON COMPILA: fermo qui, il problema precede il merge ***"; exit 1
}

$falliti = @()
foreach ($b in $Ordine) {
    "`n  --- merge $b ---"
    $out = git -C $wm merge --no-edit "port/v2-$b" 2>&1
    if ($LASTEXITCODE -ne 0) {
        "    CONFLITTO:"
        git -C $wm diff --name-only --diff-filter=U | ForEach-Object { "      $_" }
        "    lascio il merge aperto: risolvere e poi rilanciare con -RamoMerge $RamoMerge"
        $falliti += $b
        break
    }
    "    merge pulito"
    if (-not (Costruisci $wm $b)) { $falliti += $b; "    *** rotto da $b ***"; break }
}

"`n=== ESITO ==="
if ($falliti.Count -eq 0) {
    "  tutti e quattro i rami dentro, e compila."
    "  binario: $wm\build-verify\ds4-server.exe"
    git -C $wm log --oneline $Base..HEAD | ForEach-Object { "    $_" }
} else {
    "  fermato su: $($falliti -join ', ')"
}
