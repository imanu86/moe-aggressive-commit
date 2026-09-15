# P10 cella 3 - genera `p10_cella3.patch`: il diff del file toccato rispetto allo stato
# DOPO la cella 2, conservato in `D:\ds4_work\p8_work\prove\p10_c3_base` (copia fatta
# PRIMA di qualunque modifica di questa cella).
#
# `diff -d` (GNU diff di Git per Windows) cerca il diff piu' piccolo.

$ErrorActionPreference = "Continue"
$diff = "C:\Program Files\Git\usr\bin\diff.exe"
if (-not (Test-Path $diff)) { $diff = "diff" }
$base = "D:\ds4_work\p8_work\prove\p10_c3_base"
$src  = "D:\ds4_work\p8_work\source"
$out  = "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\p10_token_singolo\p10_cella3.patch"

$file = @(
    @{ rel = "ggml/src/ggml-cuda/mmvq.cu"; nome = "mmvq.cu" }
)

$righe = @()
foreach ($f in $file) {
    $a = Join-Path $base $f.nome
    $b = Join-Path $src ($f.rel -replace "/", "\")
    if (-not (Test-Path $a)) { Write-Output ("ERRORE: manca la base " + $a); exit 1 }
    if (-not (Test-Path $b)) { Write-Output ("ERRORE: manca il file " + $b); exit 1 }
    $d = & $diff -d -u --label ("a/" + $f.rel) --label ("b/" + $f.rel) $a $b
    if ($LASTEXITCODE -gt 1) { Write-Output ("ERRORE: diff fallito su " + $f.rel); exit 1 }
    if ($d) { $righe += $d }
}
# UTF-8 SENZA BOM: un BOM in testa a un diff lo rende inapplicabile.
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($out, [string[]]$righe, $utf8)
Write-Output ("scritto " + $out + " (" + $righe.Count + " righe)")
