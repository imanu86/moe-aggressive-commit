# Avvia il server Qwen3.8-Flash-Next nella configurazione SOTA misurata (preset X4 di P11)
# e lo LASCIA ATTIVO per l'uso (non e' un banco). Regole: istanza unica, nessun .bat, nessun pause.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File avvia_sota.ps1
#   powershell ... -File avvia_sota.ps1 -Preset preset_V3_p10.json   (altra configurazione)
#   powershell ... -File avvia_sota.ps1 -BindHost 127.0.0.1           (solo locale)
param(
    [string]$Preset = "preset_X4_p11.json",
    [string]$BindHost = "0.0.0.0",   # come il lanciatore di produzione
    [int]$Porta = 8100
)
$ErrorActionPreference = "Continue"
$qui = Split-Path -Parent $MyInvocation.MyCommand.Path
$presetPath = Join-Path $qui $Preset
if (-not (Test-Path $presetPath)) { Write-Output "ERRORE: preset assente: $presetPath"; exit 1 }
$p = Get-Content $presetPath -Raw -Encoding utf8 | ConvertFrom-Json

# ------------------------------------------------------------ guardia istanza unica
$ascolto = netstat -ano | Select-String -Pattern ("\:" + $Porta + "\s+.*LISTENING")
if ($ascolto) {
    Write-Output "ERRORE: la porta $Porta e' gia' in ascolto. Non lo termino: chiudilo tu, poi rilancia."
    Write-Output $ascolto
    exit 1
}
$vivo = Get-Process -Name "llama-server" -ErrorAction SilentlyContinue
if ($vivo) {
    Write-Output "ERRORE: esiste gia' un llama-server (PID $($vivo.Id -join ', ')). Chiudilo tu, poi rilancia."
    exit 1
}

# ------------------------------------------------------------------- argomenti
$batProd = "C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat"
$apiKey = ([regex]'set "API_KEY=([^"]*)"').Match((Get-Content $batProd -Raw)).Groups[1].Value
if (-not $apiKey) { Write-Output "ERRORE: API key non trovata nel lanciatore di produzione"; exit 1 }

$logDir = $p.percorsi.LOGDIR
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
if (-not (Test-Path $p.percorsi.SLOTDIR)) { New-Item -ItemType Directory -Force -Path $p.percorsi.SLOTDIR | Out-Null }
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir ("sota_" + $p.id + "_" + $stamp + ".log")

$sostituzioni = @{
    "{MODEL}"     = $p.percorsi.MODEL
    "{MMPROJ}"    = $p.percorsi.MMPROJ
    "{DRAFT}"     = $p.percorsi.DRAFT
    "{FFMPEGDIR}" = $p.percorsi.FFMPEGDIR
    "{SLOTDIR}"   = $p.percorsi.SLOTDIR
    "{LOGFILE}"   = $logFile
    "{CONTEXT}"   = [string]$p.contesto
    "{SLOTS}"     = [string]$p.slot_esperti
    "{HOST}"      = $BindHost
    "{PORT}"      = [string]$Porta
    "{APIKEY}"    = $apiKey
}
$argomenti = @()
foreach ($a in $p.args) {
    $v = [string]$a
    foreach ($k in $sostituzioni.Keys) { $v = $v.Replace($k, $sostituzioni[$k]) }
    if ($v -match '\s') { $argomenti += ('"' + $v + '"') } else { $argomenti += $v }
}

# ----------------------------------------------------------------------- avvio
foreach ($nome in $p.env.PSObject.Properties.Name) {
    Set-Item -Path ("Env:" + $nome) -Value ([string]$p.env.$nome)
}
$exe = Join-Path $p.binari $p.server_exe
if (-not (Test-Path $exe)) { Write-Output "ERRORE: eseguibile assente: $exe"; exit 1 }
$wd = $p.working_dir
if (-not (Test-Path $wd)) { New-Item -ItemType Directory -Force -Path $wd | Out-Null }

Write-Output "== avvio SOTA Qwen ($($p.id): $($p.etichetta)) =="
Write-Output ("  exe   : " + $exe)
Write-Output ("  host  : " + $BindHost + ":" + $Porta)
Write-Output ("  log   : " + $logFile)
Write-Output ("  env   : " + ($p.env.PSObject.Properties.Name -join ", "))
# finestra propria: il server resta vivo quando questo script termina; chiuderla = spegnere il server
$proc = Start-Process -FilePath $exe -ArgumentList $argomenti -WorkingDirectory $wd -PassThru
Write-Output ("  PID   : " + $proc.Id)

# --------------------------------------------------------------------- attesa
$intestazioni = @{ Authorization = ("Bearer " + $apiKey) }
$t0 = Get-Date
$pronto = $false
while (((Get-Date) - $t0).TotalSeconds -lt 900) {
    if ($proc.HasExited) { Write-Output "ERRORE: il server e' uscito (codice $($proc.ExitCode)). Vedi $logFile"; exit 1 }
    try {
        $r = Invoke-RestMethod -Uri ("http://127.0.0.1:" + $Porta + "/health") -Headers $intestazioni -TimeoutSec 5
        if ($r.status -eq "ok") { $pronto = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
}
if (-not $pronto) { Write-Output "ERRORE: nessuna readiness entro 15 minuti. Vedi $logFile"; exit 1 }
$sec = [int]((Get-Date) - $t0).TotalSeconds
Write-Output ("PRONTO in " + $sec + " s: http://" + $BindHost + ":" + $Porta + "  (PID " + $proc.Id + ")")
exit 0
