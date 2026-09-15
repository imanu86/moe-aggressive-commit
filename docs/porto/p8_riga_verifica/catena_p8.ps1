# P8 - la fila delle celle, una dopo l'altra, un processo di llama-server alla volta.
#
# L'attesa di quiete si paga UNA volta sola, prima della prima corsa: le due build
# (nuda e con le leve) sono gia' finite entrambe, e fra una cella e l'altra non si
# compila piu' niente — le quattro leve sono quattro variabili dello stesso binario.
#
#   .\catena_p8.ps1 -QuieteMinuti 15
#   .\catena_p8.ps1 -Preset preset_P8_4_p7.json,preset_P8_5_p7.json -QuieteMinuti 0

param(
    [string[]] $Preset = @(
        "preset_P8_0_p7.json",   # R0  riferimento, MTP spento, binari nudi -> T1
        "preset_P8_1_p7.json",   # R1  riferimento, MTP bozza 1, binari nudi
        "preset_P8_7_p7.json",   # controllo: binario patchato, leve TUTTE spente
        "preset_P8_2_p7.json",   # A
        "preset_P8_3_p7.json",   # A+B
        "preset_P8_4_p7.json",   # A+B+C
        "preset_P8_5_p7.json",   # A+B+C+D1
        "preset_P8_6_p7.json"),  # bozza 2 con tutte le leve
    [int] $QuieteMinuti = 15
)

$ErrorActionPreference = "Continue"
$qui = Split-Path -Parent $MyInvocation.MyCommand.Path
$primo = $true
$esiti = @()

foreach ($p in $Preset) {
    $q = 0
    if ($primo) { $q = $QuieteMinuti; $primo = $false }
    Write-Output ""
    Write-Output ("############ " + $p + "   (" + (Get-Date).ToString("HH:mm:ss") + ") ############")
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $qui "esegui_cella_p8.ps1") `
        -Preset $p -QuieteMinuti $q -Profilo lungo_131k -Budget screening `
        -Nota ("P8 " + $p + " profilo lungo_131k")
    $rc = $LASTEXITCODE
    $esiti += [pscustomobject]@{ preset = $p; codice = $rc; fine = (Get-Date).ToString("HH:mm:ss") }
    if ($rc -ne 0) {
        Write-Output ("FERMO LA CATENA: " + $p + " e' uscito con codice " + $rc)
        break
    }
    $residui = Get-Process llama-server -ErrorAction SilentlyContinue
    if ($residui) {
        Write-Output ("FERMO LA CATENA: llama-server residuo (" + ($residui.Id -join ", ") + ")")
        break
    }
}

Write-Output ""
Write-Output "======== esiti della catena ========"
$esiti | Format-Table -AutoSize | Out-String | Write-Output
