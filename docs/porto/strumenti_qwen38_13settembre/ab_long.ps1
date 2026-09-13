# Confronto A/B della sparse flash attention a CONTESTO LUNGO.
# A 32k la leva e' attiva ma non compra nulla (337,2-337,9 accesa contro 337,6-338,2 spenta).
# Qui si va dove l'attenzione pesa di piu': se anche a 131k il guadagno e' zero, la leva e' morta.
# Ordine: prima ACCESA, poi SPENTA. Ogni braccio riavvia il server (stesso binario).
# Esito 13/9 a 131072: spenta 249,78 t/s (525,5 s), accesa 294,95 (445,1 s) = +18,1%,
# testi identici. Il guadagno cresce con la profondita': il punto operativo vero e' 250k.
param(
    [int] $Ctx = 131072
)

$scratch = "C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\caacd61a-a05f-4e65-8c73-192af1c868f4\scratchpad"
$logdir  = "C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_server_logs_sperimentali"
$ctx     = $Ctx

foreach ($sfa in @(1, 0)) {
    Write-Output ("######## CONTESTO $ctx  QWEN4EXP_SPARSE_FA=$sfa  ########")
    & powershell -NoProfile -ExecutionPolicy Bypass -File "$scratch\arm_sparse.ps1" `
        -Sfa $sfa -Ctx $ctx -MaxTokens 64 -Mtp 0 -Slots 64
    $log = Get-ChildItem "$logdir\*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Write-Output "-- riga della sparse nel log (vuoto = mai attivata):"
    Get-Content $log.FullName | Select-String -Pattern "sparse FA 256" | ForEach-Object { $_.Line }
    # conserva il testo con un nome che non venga sovrascritto dal braccio successivo
    $src = "$scratch\testo_sfa${sfa}_ctx${ctx}_t1.txt"
    if (Test-Path $src) { Copy-Item $src "$scratch\testo_long_sfa$sfa.txt" -Force }
    Write-Output ""
}

Write-Output "######## CONFRONTO DEI TESTI ########"
$a = "$scratch\testo_long_sfa0.txt"
$b = "$scratch\testo_long_sfa1.txt"
if ((Test-Path $a) -and (Test-Path $b)) {
    $ta = Get-Content $a -Raw
    $tb = Get-Content $b -Raw
    if ($ta -ceq $tb) {
        Write-Output "testi IDENTICI a 131k"
    } else {
        $n = 0
        while ($n -lt [Math]::Min($ta.Length, $tb.Length) -and $ta[$n] -ceq $tb[$n]) { $n++ }
        Write-Output ("testi DIVERSI: prefisso comune " + $n + " caratteri su " + $ta.Length + "/" + $tb.Length)
    }
} else {
    Write-Output "manca uno dei due testi"
}

$p = Get-Process llama-server -ErrorAction SilentlyContinue
if ($p) { $p | Stop-Process -Force; Write-Output "server fermato" }
