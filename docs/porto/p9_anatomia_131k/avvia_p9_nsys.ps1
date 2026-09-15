# P9 - una corsa DIAGNOSTICA: llama-server avviato sotto `nsys launch`, sequenza
# `lungo_131k` del banco P0, due finestre di cattura aperte dentro il decode.
#
# Non e' un benchmark: il profilatore e' attaccato per tutta la corsa e i ms/token
# che ne escono vanno confrontati solo con se' stessi. Il riferimento senza
# profilatore e' la corsa P8 R0 del 15/9 (37,906 ms/token a 131k, MTP spento).
#
# Guardia: porta libera, nessun llama-server, nessuna build, nessuna sessione nsys.
# Se trova un server che non e' suo, si ferma senza terminare niente.

param(
    [string] $Preset = "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_p0\preset_P8_0_p7.json",
    [string] $OutRoot = "D:\ds4_work\banco_p0_run",
    [string] $Sessione = "p9anat",
    [string] $Profila = "L01,L02",
    [double] $AttesaS = 8.0,
    [double] $FinestraS = 4.0,
    [int]    $AttesaMinuti = 25,
    [string] $Etichetta = "p9_anatomia_131k"
)

$ErrorActionPreference = "Stop"
$nsys = "C:\Program Files\NVIDIA Corporation\Nsight Systems 2024.5.1\target-windows-x64\nsys.exe"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$banco = "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_p0"
$p = Get-Content $Preset -Raw | ConvertFrom-Json

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$run = Join-Path $OutRoot ($stamp + "_P9_" + $Etichetta)
New-Item -ItemType Directory -Force -Path $run | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $run "log") | Out-Null

# ---------------------------------------------------------------- guardia
Write-Output "== guardia d'istanza unica =="
$porta = [string]$p.porta
$occupata = netstat -ano | Select-String (":" + $porta + "\s") | Select-String "LISTENING"
if ($occupata) {
    Write-Output "ERRORE: qualcuno e' in ascolto sulla porta $porta. Non termino niente."
    $occupata | ForEach-Object { Write-Output ("  " + $_.ToString().Trim()) }
    exit 1
}
$esistenti = Get-Process llama-server -ErrorAction SilentlyContinue
if ($esistenti) { Write-Output "ERRORE: esiste gia' un llama-server.exe (PID $($esistenti.Id -join ', ')). Non lo termino."; exit 1 }
$build = Get-Process -Name "cl","ninja","cmake","nvcc","MSBuild" -ErrorAction SilentlyContinue
if ($build) { Write-Output "ERRORE: compilazione in corso ($($build.Name -join ', '))."; exit 1 }
Write-Output "porta $porta libera, nessun llama-server, nessuna build"

# ---------------------------------------------------------------- argomenti
$batProd = "C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat"
$apiKey = ([regex]'set "API_KEY=([^"]*)"').Match((Get-Content $batProd -Raw)).Groups[1].Value
if (-not $apiKey) { Write-Output "ERRORE: API key non trovata"; exit 1 }

$logDir = $p.percorsi.LOGDIR
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
if (-not (Test-Path $p.percorsi.SLOTDIR)) { New-Item -ItemType Directory -Force -Path $p.percorsi.SLOTDIR | Out-Null }
$logFile = Join-Path $logDir ("p9_" + $Etichetta + "_" + $stamp + ".log")

$sost = @{ "{MODEL}" = $p.percorsi.MODEL; "{MMPROJ}" = $p.percorsi.MMPROJ; "{DRAFT}" = $p.percorsi.DRAFT
           "{FFMPEGDIR}" = $p.percorsi.FFMPEGDIR; "{SLOTDIR}" = $p.percorsi.SLOTDIR; "{LOGFILE}" = $logFile
           "{CONTEXT}" = [string]$p.contesto; "{SLOTS}" = [string]$p.slot_esperti
           "{HOST}" = [string]$p.host; "{PORT}" = $porta; "{APIKEY}" = $apiKey }
$argApp = @()
foreach ($a in $p.args) {
    $v = [string]$a
    foreach ($k in $sost.Keys) { $v = $v.Replace($k, $sost[$k]) }
    if ($v -match '\s') { $argApp += ('"' + $v + '"') } else { $argApp += $v }
}
$exe = Join-Path $p.binari $p.server_exe
if (-not (Test-Path $exe)) { Write-Output "ERRORE: eseguibile assente: $exe"; exit 1 }

# riga di comando salvata SEMPRE con la chiave redatta
$argRed = @(); foreach ($a in $argApp) { $argRed += $a.Replace($apiKey, "<REDATTA>") }
Set-Content -Path (Join-Path $run "log\args.redacted.txt") `
    -Value ("nsys launch --session-new=$Sessione -t cuda --cuda-graph-trace=node " + $exe + " " + ($argRed -join " ")) -Encoding utf8

foreach ($nome in $p.env.PSObject.Properties.Name) { Set-Item -Path ("Env:" + $nome) -Value ([string]$p.env.$nome) }
$wd = $p.working_dir
if (-not (Test-Path $wd)) { New-Item -ItemType Directory -Force -Path $wd | Out-Null }

# ---------------------------------------------------------------- avvio nsys
Write-Output "== avvio del server SOTTO nsys launch (sessione $Sessione) =="
$argNsys = @("launch", "--session-new=$Sessione", "-t", "cuda", "--cuda-graph-trace=node", $exe) + $argApp
$proc = Start-Process -FilePath $nsys -ArgumentList $argNsys -WorkingDirectory $wd `
    -RedirectStandardOutput (Join-Path $run "log\server.stdout.txt") `
    -RedirectStandardError  (Join-Path $run "log\server.stderr.txt") `
    -NoNewWindow -PassThru
Write-Output ("  PID nsys   : " + $proc.Id)
Write-Output ("  log server : " + $logFile)

$h = @{ Authorization = ("Bearer " + $apiKey) }
$scadenza = (Get-Date).AddMinutes($AttesaMinuti)
$pronto = $false
$t0 = Get-Date
while ((Get-Date) -lt $scadenza) {
    if ($proc.HasExited) {
        Write-Output "ERRORE: il processo e' uscito durante il caricamento. stderr:"
        Get-Content (Join-Path $run "log\server.stderr.txt") -Tail 30
        exit 1
    }
    try { $r = Invoke-RestMethod -Uri ("http://" + $p.host + ":" + $porta + "/health") -Headers $h -TimeoutSec 5
          if ($r) { $pronto = $true; break } } catch { }
    Start-Sleep -Seconds 5
}
if (-not $pronto) { Write-Output "ERRORE: server non pronto. Lo fermo."; try { Stop-Process -Id $proc.Id -Force } catch {}; exit 1 }
$sCar = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
Write-Output ("pronto dopo " + $sCar + " s")

$pidServer = (Get-Process llama-server -ErrorAction SilentlyContinue | Select-Object -First 1).Id
Write-Output ("  PID llama-server : " + $pidServer)

# ---------------------------------------------------------------- corsa
$ErrorActionPreference = "Continue"
Write-Output "== sequenza lungo_131k, cattura nsys dentro il decode =="
& python (Join-Path $here "sonda_p9.py") --url ("http://" + $p.host + ":" + $porta) `
    --preset $Preset --out $run --nsys $nsys --sessione $Sessione `
    --profila $Profila --attesa-s $AttesaS --finestra-s $FinestraS `
    --pid-server $pidServer --log-server $logFile

# ---------------------------------------------------------------- chiusura
Write-Output "== chiusura =="
if ($pidServer) {
    cmd /c ("taskkill /PID " + $pidServer + " /T >nul 2>nul")
    $lim = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $lim -and (Get-Process -Id $pidServer -ErrorAction SilentlyContinue)) { Start-Sleep -Seconds 3 }
    if (Get-Process -Id $pidServer -ErrorAction SilentlyContinue) {
        try { Stop-Process -Id $pidServer -Force -ErrorAction SilentlyContinue } catch {}
        Start-Sleep -Seconds 10
    }
}
if (-not $proc.HasExited) { try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {} }
& $nsys shutdown --session=$Sessione | Out-Null

Write-Output "== stato finale =="
$residui = Get-Process llama-server -ErrorAction SilentlyContinue
if ($residui) { Write-Output ("ATTENZIONE: llama-server ancora attivo: " + ($residui.Id -join ", ")) } else { Write-Output "nessun llama-server attivo" }
$nsRes = Get-Process nsys -ErrorAction SilentlyContinue
if ($nsRes) { Write-Output ("ATTENZIONE: nsys ancora attivo: " + ($nsRes.Id -join ", ")) } else { Write-Output "nessun nsys attivo" }
& $nsys sessions list
$anc = netstat -ano | Select-String (":" + $porta + "\s") | Select-String "LISTENING"
if ($anc) { Write-Output "ATTENZIONE: qualcuno in ascolto sulla porta $porta" } else { Write-Output "porta $porta libera" }

# artefatti di avvio ripuliti dalla chiave
foreach ($f in Get-ChildItem (Join-Path $run "log") -File) {
    if ($f.Length -gt 0 -and $f.Extension -in @(".txt", ".log")) {
        (Get-Content $f.FullName -Raw).Replace($apiKey, "<REDATTA>") | Set-Content -Path $f.FullName -Encoding utf8
    }
}
Write-Output ("CARTELLA_CORSA=" + $run)
