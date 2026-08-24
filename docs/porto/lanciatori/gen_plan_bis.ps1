$ErrorActionPreference = 'Stop'

$requests = New-Object System.Collections.Generic.List[object]

# WARMUP: semina esplicita del campione, fuori verdetto (stessa convenzione della Fase 1)
$requests.Add([ordered]@{ label = 'WARMUP'; porto_cb = [ordered]@{ fork = 2; fork_down_tardi = 0; pf_top = 0 }; n_predict = 64; porto_hot_snapshot = $false })

$curFork = 2
$curDt = 0
$dtIdx = 0
$fkIdx = 0

for ($rep = 1; $rep -le 15; $rep++) {
    for ($j = 1; $j -le 2; $j++) {
        $dtIdx++
        # --- A (dt=0) ---
        $cbA = [ordered]@{ fork_down_tardi = 0 }
        if ($curFork -ne 2) { $cbA['fork'] = 2 }
        $requests.Add([ordered]@{ label = "A${dtIdx}_dt"; porto_cb = $cbA; n_predict = 64; porto_hot_snapshot = $false })
        $curDt = 0; $curFork = 2
        # --- B (dt=1) ---
        $cbB = [ordered]@{ fork_down_tardi = 1 }
        $requests.Add([ordered]@{ label = "B${dtIdx}_dt"; porto_cb = $cbB; n_predict = 64; porto_hot_snapshot = $false })
        $curDt = 1
    }
    $fkIdx++
    # --- A_fk (fork=2), reset dt se serve ---
    $cbAfk = [ordered]@{ fork = 2 }
    if ($curDt -ne 0) { $cbAfk['fork_down_tardi'] = 0 }
    $requests.Add([ordered]@{ label = "A${fkIdx}_fk"; porto_cb = $cbAfk; n_predict = 64; porto_hot_snapshot = $false })
    $curFork = 2; $curDt = 0
    # --- B_fk (fork=1) ---
    $cbBfk = [ordered]@{ fork = 1 }
    $requests.Add([ordered]@{ label = "B${fkIdx}_fk"; porto_cb = $cbBfk; n_predict = 64; porto_hot_snapshot = $false })
    $curFork = 1
}

$plan = [ordered]@{ requests = $requests }
$json = $plan | ConvertTo-Json -Depth 6
$outPath = 'C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\4b4c0194-0c4f-4f6b-8e2c-cb939d8d7daa\scratchpad\plan_triage1bis.json'
$json | Set-Content -LiteralPath $outPath -Encoding UTF8

Write-Output "totale richieste = $($requests.Count) (atteso 91 = 1 warmup + 60 dt + 30 fk)"
Write-Output "coppie dt = $dtIdx (atteso 30), coppie fk = $fkIdx (atteso 15)"
Write-Output "scritto: $outPath"

# stampa le prime 10 e le ultime 10 per revisione rapida
Write-Output "--- prime 10 ---"
$requests | Select-Object -First 10 | ForEach-Object { $_ | ConvertTo-Json -Compress }
Write-Output "--- ultime 10 ---"
$requests | Select-Object -Last 10 | ForEach-Object { $_ | ConvertTo-Json -Compress }
