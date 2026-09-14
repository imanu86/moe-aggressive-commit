# P2 - avvio della compilazione della prova host-only.
#
# NON ESEGUIRE finche' la misura di baseline occupa la macchina.
# Un .bat modificato a caldo puo' risuscitare un processo (memoria del progetto:
# «un .bat letto per offset risuscita il server»): il lanciatore resta questo .ps1
# e il .cmd non va toccato mentre gira.
#
# LIBRERIE: nessuna in piu' rispetto a build_test.cmd. In particolare NON serve
# Synchronization.lib: WaitOnAddress/WakeByAddressAll sono risolte a caldo con
# LoadLibraryA/GetProcAddress (moe_cpu_executor.cpp, `sync_api`), con ripiego su
# Sleep(1) se l'API non c'e'. <synchapi.h> arriva via <windows.h> e le sue
# dichiarazioni restano inutilizzate: e' voluto. Questo file e build_test.cmd
# devono restare equivalenti — la compilazione avviene tutta nel .cmd, qui si
# passano solo gli argomenti di esecuzione.

param(
    [switch]$Full,
    [int]$Threads = 4,
    [int]$Experts = 0,
    [string]$Weights = ""
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

& "$here\build_test.cmd"
if ($LASTEXITCODE -ne 0) { throw "compilazione fallita (codice $LASTEXITCODE)" }

$argv = @("--threads", "$Threads")
if ($Full)                        { $argv += "--full" }
if ($Experts -gt 0)               { $argv += @("--experts", "$Experts") }
if ($Weights -ne "")              { $argv += @("--weights", $Weights) }

Write-Host "eseguo: test_esecutore.exe $($argv -join ' ')"
& "$here\test_esecutore.exe" @argv
exit $LASTEXITCODE
