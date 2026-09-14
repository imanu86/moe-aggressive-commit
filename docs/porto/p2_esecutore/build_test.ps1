# P2 - avvio della compilazione della prova host-only.
#
# ESEGUITO il 14 settembre 2026 a macchina libera: compila al primo tentativo e
# la batteria da 74 controlli passa a 4 e a 6 thread, con pesi sintetici
# (K=512 e --full K=2560) e con i pesi veri del prototipo (--weights).
# Esito completo in ESITO_COMPILAZIONE_P2_14_SETTEMBRE.md. Per ripetere le sole
# prove di corsa in ciclo: .\cicla_corse.ps1 -Giri 50 -Thread 4,6
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

# Il .cmd si chiama con ErrorActionPreference a 'Continue', e NON e' una
# distrazione: e' la correzione di un difetto trovato il 14 settembre.
#
# Windows PowerShell 5.1 avvolge OGNI riga di stderr di un eseguibile nativo in
# un ErrorRecord (NativeCommandError). Con 'Stop' attivo, una sola riga di
# stderr fa terminare il lanciatore ANCHE SE la compilazione e' riuscita e il
# codice di uscita e' 0. Su questa macchina succede davvero: vcvarsall.bat
# stampa «"vswhere.exe" non e' riconosciuto...» — avviso innocuo, perche' la
# cartella dell'Installer non e' nel PATH — e poi imposta l'ambiente e ritorna 0.
# Prima della correzione il .ps1 moriva li', e il .cmd lanciato a mano compilava:
# i due lanciatori, che il progetto vuole EQUIVALENTI, non lo erano.
#
# L'autorita' sull'esito resta il codice di uscita, controllato subito sotto.
$saved = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try   { & "$here\build_test.cmd" }
finally { $ErrorActionPreference = $saved }
if ($LASTEXITCODE -ne 0) { throw "compilazione fallita (codice $LASTEXITCODE)" }

$argv = @("--threads", "$Threads")
if ($Full)                        { $argv += "--full" }
if ($Experts -gt 0)               { $argv += @("--experts", "$Experts") }
if ($Weights -ne "")              { $argv += @("--weights", $Weights) }

Write-Host "eseguo: test_esecutore.exe $($argv -join ' ')"
& "$here\test_esecutore.exe" @argv
exit $LASTEXITCODE
