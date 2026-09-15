# P8 - una cella: attesa di quiete, guardia, blocco del banco a 131k, analisi.
#
# Non avvia mai un secondo server: la guardia d'istanza unica e' dentro
# avvia_blocco.ps1 e questo script si ferma se la trova gia' violata.
#
#   .\esegui_cella_p8.ps1 -Preset preset_P8_1_p7.json -QuieteMinuti 15
#
# -QuieteMinuti: attesa dalla fine dell'ultima build (regola del 8/9: dopo una
# build la macchina non e' quieta, fino al 15%). 0 = nessuna attesa.

param(
    [Parameter(Mandatory = $true)][string] $Preset,
    [int]    $QuieteMinuti = 0,
    [string] $Profilo = "lungo_131k",
    [string] $Budget = "screening",
    [int]    $Replica = 1,
    [string] $Nota = ""
)

$ErrorActionPreference = "Continue"
$banco = "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_p0"

if ($QuieteMinuti -gt 0) {
    Write-Output ("== attesa di quiete: " + $QuieteMinuti + " minuti dalla build ==")
    $fine = (Get-Date).AddMinutes($QuieteMinuti)
    while ((Get-Date) -lt $fine) {
        Start-Sleep -Seconds 60
        $resta = [math]::Ceiling(($fine - (Get-Date)).TotalMinutes)
        Write-Output ("   restano ~" + $resta + " min")
    }
}

Write-Output "== guardia prima dell'avvio =="
$vivi = Get-Process llama-server -ErrorAction SilentlyContinue
if ($vivi) { Write-Output ("ERRORE: llama-server vivo (PID " + ($vivi.Id -join ", ") + "). Non avvio."); exit 1 }
$ascolto = netstat -ano | Select-String ":8100\s" | Select-String "LISTENING"
if ($ascolto) { Write-Output "ERRORE: qualcuno in ascolto sulla 8100. Non avvio."; exit 1 }
$build = Get-Process -Name "cl","ninja","cmake","nvcc","MSBuild" -ErrorAction SilentlyContinue
if ($build) { Write-Output ("ERRORE: build in corso (" + ($build.Name -join ", ") + "). Non avvio."); exit 1 }
Write-Output "guardia superata"

Write-Output ("== blocco: " + $Preset + " profilo " + $Profilo + " budget " + $Budget + " ==")
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $banco "avvia_blocco.ps1") `
    -Preset $Preset -Profilo $Profilo -Budget $Budget -Replica $Replica -Nota $Nota
$rc = $LASTEXITCODE

Write-Output "== stato finale =="
$residui = Get-Process llama-server -ErrorAction SilentlyContinue
if ($residui) { Write-Output ("ATTENZIONE: llama-server ancora attivo: " + ($residui.Id -join ", ")) }
else { Write-Output "nessun llama-server attivo" }
Write-Output ("codice avvia_blocco: " + $rc)
exit $rc
