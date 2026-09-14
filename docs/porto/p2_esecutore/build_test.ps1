# P2 - avvio della compilazione della prova host-only.
#
# NON ESEGUIRE finche' la misura di baseline occupa la macchina.
# Un .bat modificato a caldo puo' risuscitare un processo (memoria del progetto:
# «un .bat letto per offset risuscita il server»): il lanciatore resta questo .ps1
# e il .cmd non va toccato mentre gira.

param(
    [switch]$Full,
    [int]$Threads = 4,
    [string]$Weights = ""
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

& "$here\build_test.cmd"
if ($LASTEXITCODE -ne 0) { throw "compilazione fallita (codice $LASTEXITCODE)" }

$argv = @("--threads", "$Threads")
if ($Full)                        { $argv += "--full" }
if ($Weights -ne "")              { $argv += @("--weights", $Weights) }

Write-Host "eseguo: test_esecutore.exe $($argv -join ' ')"
& "$here\test_esecutore.exe" @argv
exit $LASTEXITCODE
