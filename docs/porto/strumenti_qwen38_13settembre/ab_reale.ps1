# Prova REALE di qualita': sparse flash attention accesa contro spenta.
# Non misura la velocita' (quella e' in ab_long.ps1): qui si giudicano le RISPOSTE.
# MTP spento di proposito: la sparse agisce solo nel prefill, quindi spegnere la
# speculazione non nasconde nulla, e mette la macchina nel regime deterministico
# dove una differenza di risposta e' attribuibile alla leva.
param(
    [int] $Ctx = 131072
)

$scratch = "C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\caacd61a-a05f-4e65-8c73-192af1c868f4\scratchpad"
$logdir  = "C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_server_logs_sperimentali"

foreach ($sfa in @(1, 0)) {
    Write-Output ("######## PROVA REALE  QWEN4EXP_SPARSE_FA=$sfa  contesto=$Ctx ########")

    $p = Get-Process llama-server -ErrorAction SilentlyContinue
    if ($p) { $p | Stop-Process -Force; Start-Sleep -Seconds 6 }

    $env:QWEN4EXP_SPARSE_FA = "$sfa"
    $env:MOE_SLOTS          = "64"
    $env:DRAFT_EXPERTS      = "ram"

    $pr = Start-Process -FilePath "cmd.exe" `
        -ArgumentList '/c', '"C:\Users\imanu\Desktop\avvia Qwen38 SPERIMENTALE.bat" 0' `
        -RedirectStandardOutput "$scratch\reale_sfa$sfa.out" -RedirectStandardError "$scratch\reale_sfa$sfa.err" `
        -NoNewWindow -PassThru

    $deadline = (Get-Date).AddMinutes(9); $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:8100/v1/models" -Headers @{Authorization="Bearer Sticazzi86"} -TimeoutSec 4
            if ($r) { $ready = $true; break }
        } catch { }
        if ($pr.HasExited -and -not (Get-Process llama-server -ErrorAction SilentlyContinue)) {
            Write-Output "LANCIATORE USCITO:"; Get-Content "$scratch\reale_sfa$sfa.err" -Tail 15; break
        }
        Start-Sleep -Seconds 5
    }
    if (-not $ready) { Write-Output "NON PRONTO, salto questo braccio"; continue }

    & python "$scratch\prova_reale.py" --ctx-tokens $Ctx --label "sfa$sfa"

    $log = Get-ChildItem "$logdir\*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Write-Output "-- attivazione nel log (vuoto = mai attivata):"
    Get-Content $log.FullName | Select-String -Pattern "sparse FA 256" | ForEach-Object { $_.Line }
    Write-Output ""
}

$p = Get-Process llama-server -ErrorAction SilentlyContinue
if ($p) { $p | Stop-Process -Force; Write-Output "server fermato" }

Write-Output "######## CONFRONTO ########"
$f1 = "$scratch\prova_reale_sfa1.json"
$f0 = "$scratch\prova_reale_sfa0.json"
if ((Test-Path $f1) -and (Test-Path $f0)) {
    $a = Get-Content $f0 -Raw | ConvertFrom-Json   # spenta
    $b = Get-Content $f1 -Raw | ConvertFrom-Json   # accesa

    Write-Output "AGHI (profondita': spenta / accesa)"
    for ($i = 0; $i -lt $a.esiti.Count; $i++) {
        if ($a.esiti[$i].tipo -ne 'ago') { continue }
        $pa = [int]($a.esiti[$i].profondita * 100)
        $ra = $(if ($a.esiti[$i].trovato) { "TROVATO" } elseif ($a.esiti[$i].troncato) { "PERSO(tronc)" } else { "PERSO" })
        $rb = $(if ($b.esiti[$i].trovato) { "TROVATO" } elseif ($b.esiti[$i].troncato) { "PERSO(tronc)" } else { "PERSO" })
        Write-Output ("  {0,3}%  {1,-13} / {2,-13}  atteso: {3}" -f $pa, $ra, $rb, $a.esiti[$i].atteso)
        if ($a.esiti[$i].trovato -ne $b.esiti[$i].trovato) {
            Write-Output ("        spenta -> " + $a.esiti[$i].mostrato.Substring(0, [Math]::Min(220, $a.esiti[$i].mostrato.Length)))
            Write-Output ("        accesa -> " + $b.esiti[$i].mostrato.Substring(0, [Math]::Min(220, $b.esiti[$i].mostrato.Length)))
        }
    }

    $na = ($a.esiti | Where-Object { $_.trovato }).Count
    $nb = ($b.esiti | Where-Object { $_.trovato }).Count
    Write-Output ""
    Write-Output ("totale aghi: spenta $na, accesa $nb")
    Write-Output ""
    $ta = ($a.esiti | Where-Object { $_.tipo -eq 'tecnica' }).mostrato
    $tb = ($b.esiti | Where-Object { $_.tipo -eq 'tecnica' }).mostrato
    Write-Output "--- DOMANDA TECNICA, sparse SPENTA:"; Write-Output $ta
    Write-Output ""
    Write-Output "--- DOMANDA TECNICA, sparse ACCESA:"; Write-Output $tb
} else {
    Write-Output "manca uno dei due esiti"
}
