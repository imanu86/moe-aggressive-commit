# P11 cella 2 - SONDA, non una misura.
#
# Avvia un llama-server con il preset indicato piu' QWEN_WS_DUMP, aspetta che la
# riserva del grafo abbia stampato l'elenco dei nodi, poi lo chiude. Non manda
# nessuna richiesta e non produce nessun numero di velocita': serve solo a leggere
# QUALI tensori del grafo crescono con la profondita' del KV.
#
# Guardia d'istanza unica come avvia_blocco.ps1: se trova un server non suo, si ferma.

param(
    [Parameter(Mandatory = $true)][string] $Preset,
    [string] $Uscita = "D:\ds4_work\p11_work\prove",
    [int]    $AttesaMinuti = 12
)

$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$presetPath = Join-Path (Join-Path (Split-Path -Parent $here) "banco_p0") $Preset
if (-not (Test-Path $presetPath)) { $presetPath = $Preset }
$p = Get-Content $presetPath -Raw | ConvertFrom-Json

$porta = [string]$p.porta
$occupata = netstat -ano | Select-String (":" + $porta + "\s") | Select-String "LISTENING"
if ($occupata) { Write-Output "ERRORE: porta $porta occupata. Non avvio niente."; exit 1 }
$esistenti = Get-Process llama-server -ErrorAction SilentlyContinue
if ($esistenti) { Write-Output "ERRORE: llama-server gia' vivo. Non lo tocco."; exit 1 }
$build = Get-Process -Name "cl","ninja","cmake","nvcc" -ErrorAction SilentlyContinue
if ($build) { Write-Output "ERRORE: build in corso."; exit 1 }
Write-Output "guardia ok"

New-Item -ItemType Directory -Force -Path $Uscita | Out-Null
$stamp  = Get-Date -Format "yyyyMMdd_HHmmss"
$out    = Join-Path $Uscita ("sonda_ws_" + $p.id + "_" + $stamp + ".txt")
$logSrv = Join-Path $Uscita ("sonda_ws_" + $p.id + "_" + $stamp + "_server.log")

$batProd = "C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat"
$apiKey = ([regex]'set "API_KEY=([^"]*)"').Match((Get-Content $batProd -Raw)).Groups[1].Value

$sost = @{
    "{MODEL}" = $p.percorsi.MODEL; "{MMPROJ}" = $p.percorsi.MMPROJ; "{DRAFT}" = $p.percorsi.DRAFT
    "{FFMPEGDIR}" = $p.percorsi.FFMPEGDIR; "{SLOTDIR}" = $p.percorsi.SLOTDIR
    "{LOGFILE}" = $logSrv; "{CONTEXT}" = [string]$p.contesto; "{SLOTS}" = [string]$p.slot_esperti
    "{HOST}" = [string]$p.host; "{PORT}" = $porta; "{APIKEY}" = $apiKey
}
$argomenti = @()
foreach ($a in $p.args) {
    $v = [string]$a
    foreach ($k in $sost.Keys) { $v = $v.Replace($k, $sost[$k]) }
    if ($v -match '\s') { $argomenti += ('"' + $v + '"') } else { $argomenti += $v }
}

foreach ($nome in $p.env.PSObject.Properties.Name) {
    Set-Item -Path ("Env:" + $nome) -Value ([string]$p.env.$nome)
}
$env:QWEN_WS_DUMP = "25"

$exe = Join-Path $p.binari $p.server_exe
$wd  = $p.working_dir
Write-Output ("avvio " + $exe)
$proc = Start-Process -FilePath $exe -ArgumentList $argomenti -WorkingDirectory $wd `
    -RedirectStandardOutput (Join-Path $Uscita ("sonda_" + $stamp + ".out")) `
    -RedirectStandardError  (Join-Path $Uscita ("sonda_" + $stamp + ".err")) `
    -NoNewWindow -PassThru
Write-Output ("PID " + $proc.Id)

$scadenza = (Get-Date).AddMinutes($AttesaMinuti)
$visto = $false
while ((Get-Date) -lt $scadenza) {
    if ($proc.HasExited) { Write-Output "il server e' uscito da solo"; break }
    if (Test-Path $logSrv) {
        $t = Get-Content $logSrv -Raw -ErrorAction SilentlyContinue
        if ($t -and $t.Contains("ws_kv TOTALE")) { $visto = $true; break }
    }
    Start-Sleep -Seconds 5
}
Write-Output ("dump trovato: " + $visto)
if (-not $proc.HasExited) { try { Stop-Process -Id $proc.Id -Force } catch { } }
Start-Sleep -Seconds 3

if (Test-Path $logSrv) {
    Select-String -Path $logSrv -Pattern "ws_dump|ws_kv|demand workspace|compute buffer size" |
        ForEach-Object { $_.Line } | Set-Content -Path $out -Encoding utf8
    Write-Output ("estratto in " + $out)
}
$vivi = Get-Process llama-server -ErrorAction SilentlyContinue
if ($vivi) { Write-Output "ATTENZIONE: llama-server ancora vivo" } else { Write-Output "nessun llama-server" }
