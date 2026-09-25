# P0 - un BLOCCO del banco A/B: un processo NUOVO di llama-server, la sequenza di
# fixture, poi chiusura. Un blocco = un processo: `cache_prompt=false` riguarda il
# prefisso/KV e NON azzera la cache degli esperti, quindi ogni lato di una coppia
# deve ripartire da un processo nuovo.
#
# Perche' .ps1 e non .bat: `cmd` rilegge un file batch per posizione in byte, quindi
# modificarlo mentre gira fa riprendere l'esecuzione da un punto sbagliato e puo'
# risuscitare un server (trappola pagata due volte l'8/9). Qui non c'e' nessun .bat
# e nessun `pause`: una finestra ferma su pause e' un secondo server in attesa.
#
# Esempi:
#   .\avvia_blocco.ps1 -Preset preset_A.json -Profilo fumo -Sigilla
#   .\avvia_blocco.ps1 -Preset preset_B.json -Profilo screening -Replica 2
#
# La API key viene letta dal lanciatore di produzione e non viene mai stampata
# ne' scritta in nessun file prodotto da questo script.

param(
    [Parameter(Mandatory = $true)][string] $Preset,
    [string] $Profilo = "fumo",
    [int]    $Replica = 1,
    [string] $Budget = "screening",
    [string] $OutRoot = "D:\ds4_work\banco_p0_run",
    [switch] $Sigilla,
    [switch] $SoloSigillo,   # avvia, sigilla le fixture, chiude: NON e' una misura
    [int]    $AttesaMinuti = 25,
    [string] $Nota = ""
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$presetPath = Join-Path $here $Preset
if (-not (Test-Path $presetPath)) { $presetPath = $Preset }
$p = Get-Content $presetPath -Raw | ConvertFrom-Json

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$staging = Join-Path $OutRoot ("_avvio\" + $stamp + "_" + $p.id)
New-Item -ItemType Directory -Force -Path $staging | Out-Null

# ---------------------------------------------------------------- guardia unica
Write-Output "== guardia d'istanza unica =="
$porta = [string]$p.porta
# Solo LISTENING: dopo un blocco restano decine di socket in TIME_WAIT sulla stessa
# porta per qualche minuto (visto il 14/9). Contarli come "porta occupata" avrebbe
# impedito di lanciare il lato B subito dopo il lato A.
$occupata = netstat -ano | Select-String (":" + $porta + "\s") | Select-String "LISTENING"
if ($occupata) {
    Write-Output "ERRORE: c'e' gia' qualcuno in ascolto sulla porta $porta. Nessun processo verra' terminato."
    $occupata | ForEach-Object { Write-Output ("  " + $_.ToString().Trim()) }
    exit 1
}
$esistenti = Get-Process llama-server -ErrorAction SilentlyContinue
if ($esistenti) {
    Write-Output "ERRORE: esiste gia' un llama-server.exe (PID: $($esistenti.Id -join ', '))."
    Write-Output "Non lo termino: chiudilo tu, poi rilancia. Potrebbe essere quello di produzione."
    exit 1
}
$build = @(Get-Process -Name "cl","ninja","cmake","nvcc" -ErrorAction SilentlyContinue)
# Q36 (25/9): Visual Studio tiene vivi nodi MSBuild riutilizzabili (/nodeReuse:true) anche quando
# non compila. Si blocca solo se consumano CPU (build vera), non per la loro sola presenza.
$msb = @(Get-Process -Name "MSBuild" -ErrorAction SilentlyContinue)
if ($msb.Count -gt 0) {
    Start-Sleep -Seconds 3
    foreach ($m in $msb) {
        $m2 = Get-Process -Id $m.Id -ErrorAction SilentlyContinue
        if ($m2 -and ($m2.CPU - $m.CPU) -gt 0.3) { $build += $m2 }
    }
}
if ($build.Count -gt 0) {
    Write-Output "ERRORE: sembra in corso una compilazione ($($build.Name -join ', ')). Dopo una build la macchina non e' quieta (fino al 15%)."
    exit 1
}
Write-Output "porta $porta libera, nessun llama-server attivo, nessuna build in corso"

# ------------------------------------------------------------------- argomenti
$batProd = "C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat"
$apiKey = ([regex]'set "API_KEY=([^"]*)"').Match((Get-Content $batProd -Raw)).Groups[1].Value
if (-not $apiKey) { Write-Output "ERRORE: API key non trovata nel lanciatore di produzione"; exit 1 }

$logDir = $p.percorsi.LOGDIR
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
if (-not (Test-Path $p.percorsi.SLOTDIR)) { New-Item -ItemType Directory -Force -Path $p.percorsi.SLOTDIR | Out-Null }
$logFile = Join-Path $logDir ("p0_" + $p.etichetta + "_r" + $Replica + "_" + $stamp + ".log")

$sostituzioni = @{
    "{MODEL}"     = $p.percorsi.MODEL
    "{MMPROJ}"    = $p.percorsi.MMPROJ
    "{DRAFT}"     = $p.percorsi.DRAFT
    "{FFMPEGDIR}" = $p.percorsi.FFMPEGDIR
    "{SLOTDIR}"   = $p.percorsi.SLOTDIR
    "{LOGFILE}"   = $logFile
    "{CONTEXT}"   = [string]$p.contesto
    "{SLOTS}"     = [string]$p.slot_esperti
    "{HOST}"      = [string]$p.host
    "{PORT}"      = $porta
    "{APIKEY}"    = $apiKey
}
$argomenti = @()
foreach ($a in $p.args) {
    $v = [string]$a
    foreach ($k in $sostituzioni.Keys) { $v = $v.Replace($k, $sostituzioni[$k]) }
    if ($v -match '\s') { $argomenti += ('"' + $v + '"') } else { $argomenti += $v }
}
# elenco degli argomenti da salvare, con la chiave redatta
$argRedatti = @()
foreach ($a in $argomenti) { $argRedatti += $a.Replace($apiKey, "<REDATTA>") }
Set-Content -Path (Join-Path $staging "args.redacted.txt") -Value ($argRedatti -join " ") -Encoding utf8

# ----------------------------------------------------------------------- avvio
foreach ($nome in $p.env.PSObject.Properties.Name) {
    Set-Item -Path ("Env:" + $nome) -Value ([string]$p.env.$nome)
}
$exe = Join-Path $p.binari $p.server_exe
if (-not (Test-Path $exe)) { Write-Output "ERRORE: eseguibile assente: $exe"; exit 1 }
$wd = $p.working_dir
if (-not (Test-Path $wd)) { New-Item -ItemType Directory -Force -Path $wd | Out-Null }

Write-Output "== avvio processo NUOVO =="
Write-Output ("  exe        : " + $exe)
Write-Output ("  log server : " + $logFile)
Write-Output ("  env        : " + ($p.env.PSObject.Properties.Name -join ", "))
$proc = Start-Process -FilePath $exe -ArgumentList $argomenti -WorkingDirectory $wd `
    -RedirectStandardOutput (Join-Path $staging "server.stdout.txt") `
    -RedirectStandardError  (Join-Path $staging "server.stderr.txt") `
    -NoNewWindow -PassThru
Write-Output ("  PID        : " + $proc.Id)

# --------------------------------------------------------------------- attesa
$intestazioni = @{ Authorization = ("Bearer " + $apiKey) }
$scadenza = (Get-Date).AddMinutes($AttesaMinuti)
$pronto = $false
$tAvvio = Get-Date
while ((Get-Date) -lt $scadenza) {
    if ($proc.HasExited) {
        Write-Output "ERRORE: il server e' uscito durante il caricamento. Ultime righe di stderr:"
        Get-Content (Join-Path $staging "server.stderr.txt") -Tail 25
        exit 1
    }
    try {
        $r = Invoke-RestMethod -Uri ("http://" + $p.host + ":" + $porta + "/health") -Headers $intestazioni -TimeoutSec 5
        if ($r) { $pronto = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
}
if (-not $pronto) {
    Write-Output "ERRORE: server non pronto entro $AttesaMinuti minuti. Lo fermo."
    try { Stop-Process -Id $proc.Id -Force } catch { }
    exit 1
}
$secondiCaricamento = [math]::Round(((Get-Date) - $tAvvio).TotalSeconds, 1)
Write-Output ("pronto dopo " + $secondiCaricamento + " s")

# --------------------------------------------------------------------- sigillo
# Dalla prima chiamata a un eseguibile nativo in poi si scende a "Continue": in
# PowerShell 5.1 lo stderr di un .exe diventa un ErrorRecord e con "Stop" farebbe
# abortire lo script anche quando il comando e' riuscito.
$ErrorActionPreference = "Continue"
if ($Sigilla -or $SoloSigillo) {
    Write-Output "== sigillo delle fixture (ID token dal server in esame) =="
    & python (Join-Path $here "..\banco_p0\sigilla_fixture.py") --url ("http://" + $p.host + ":" + $porta)
    if (-not $?) { Write-Output "ERRORE nel sigillo delle fixture" }
}

# ----------------------------------------------------------------------- banco
$cartella = $null
if ($SoloSigillo) {
    Write-Output "== -SoloSigillo: nessun banco eseguito, questa non e' una misura =="
} else {
    Write-Output "== banco =="
    & python (Join-Path $here "banco_q36.py") --preset $presetPath --profilo $Profilo `
        --replica $Replica --budget $Budget --out $OutRoot `
        --url ("http://" + $p.host + ":" + $porta) --pid-server $proc.Id --log-server $logFile `
        --nota $Nota | Tee-Object -Variable uscita
    $cartella = ($uscita | Select-String "^CARTELLA_CORSA=" | Select-Object -Last 1)
    if ($cartella) { $cartella = $cartella.ToString().Substring("CARTELLA_CORSA=".Length).Trim() }
}

# -------------------------------------------------------------------- chiusura
Write-Output "== chiusura del server =="
# ATTENZIONE (difetto trovato dalla corsa di fumo del 14/9): in Windows PowerShell 5.1
# lo stderr di un eseguibile nativo diventa un ErrorRecord, e con
# $ErrorActionPreference = "Stop" il solo fatto che `taskkill` stampi un avviso fa
# ABORTIRE lo script lasciando il server VIVO. Qui si scende a "Continue" e si manda
# lo stderr di taskkill a nul dentro cmd, senza usare 2>&1 in PowerShell.
$ErrorActionPreference = "Continue"
$modo = "nessuna"
if (-not $proc.HasExited) {
    $null = $proc.CloseMainWindow()          # gentile: nessun effetto senza finestra
    cmd /c ("taskkill /PID " + $proc.Id + " /T >nul 2>nul")
    # Misurato il 14/9: llama-server.exe avviato senza finestra NON reagisce alla
    # richiesta di chiusura, quindi l'attesa gentile finisce sempre nella forzatura.
    # Si tiene comunque il tentativo, ma corto (20 s) per non buttare un minuto
    # a ogni blocco. Non c'e' stato da preservare: ogni blocco e' un processo nuovo.
    $modo = "richiesta_graziosa"
    $limite = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $limite -and -not $proc.HasExited) {
        Start-Sleep -Seconds 3
        $proc.Refresh()
    }
    if (-not $proc.HasExited) {
        Write-Output "  non si e' chiuso da solo: passo alla terminazione forzata"
        try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch { }
        $modo = "stop_process_forzato"
        $limite = (Get-Date).AddSeconds(60)
        while ((Get-Date) -lt $limite -and (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) {
            Start-Sleep -Seconds 3
        }
    }
}
$vivo = [bool](Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)
$chiusura = [pscustomobject]@{
    pid                  = $proc.Id
    modo_chiusura        = $modo
    secondi_caricamento  = $secondiCaricamento
    uscito               = -not $vivo
    codice_uscita        = $(if (-not $vivo) { try { $proc.ExitCode } catch { $null } } else { $null })
    log_server           = $logFile
    porta_libera_dopo    = -not [bool](netstat -ano | Select-String (":" + $porta + "\s") | Select-String "LISTENING")
    processi_residui     = @((Get-Process llama-server -ErrorAction SilentlyContinue).Id)
}
$chiusura | ConvertTo-Json | Set-Content -Path (Join-Path $staging "chiusura.json") -Encoding utf8
$chiusura | Format-List

if ($cartella -and (Test-Path $cartella)) {
    # copia RIPULITA: nessun artefatto di avvio deve poter contenere la chiave
    foreach ($f in Get-ChildItem $staging -File) {
        $dest = Join-Path (Join-Path $cartella "log") $f.Name
        if ($f.Length -gt 0) {
            (Get-Content $f.FullName -Raw).Replace($apiKey, "<REDATTA>") | Set-Content -Path $dest -Encoding utf8
        } else {
            Copy-Item $f.FullName -Destination $dest -Force
        }
    }
    Write-Output ("artefatti di avvio copiati (ripuliti) in " + (Join-Path $cartella "log"))
    Write-Output ("CARTELLA_CORSA=" + $cartella)
}

Write-Output "== stato finale =="
$residui = Get-Process llama-server -ErrorAction SilentlyContinue
if ($residui) { Write-Output ("ATTENZIONE: llama-server ancora attivo: " + ($residui.Id -join ", ")); exit 3 }
Write-Output "nessun llama-server attivo"
$ancora = netstat -ano | Select-String (":" + $porta + "\s") | Select-String "LISTENING"
if ($ancora) { Write-Output "ATTENZIONE: qualcuno e' ancora in ascolto sulla porta $porta"; $ancora | ForEach-Object { Write-Output ("  " + $_.ToString().Trim()) } }
else {
    $attesa = (netstat -ano | Select-String (":" + $porta + "\s") | Select-String "TIME_WAIT").Count
    Write-Output ("porta $porta libera (nessun LISTENING; " + $attesa + " socket in TIME_WAIT, normali e innocui)")
}
