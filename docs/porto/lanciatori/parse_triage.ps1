param(
    [Parameter(Mandatory = $true)][string] $Tag,
    [Parameter(Mandatory = $true)][string] $PlanPath,
    [string] $OutDir = 'C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\4b4c0194-0c4f-4f6b-8e2c-cb939d8d7daa\scratchpad\cb_runs'
)
$ErrorActionPreference = 'Stop'

$plan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
$summaryPath = Join-Path $OutDir "$Tag.summary.json"
$logPath = Join-Path $OutDir "$Tag.server.log"
$summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
$logLines = Get-Content -LiteralPath $logPath

Write-Output "=== richieste nel piano: $($plan.requests.Count) -- risultati nel summary: $($summary.results.Count) ==="
$badStatus = $summary.results | Where-Object { $_.http_status -ne 200 }
if ($badStatus) {
    Write-Output "ATTENZIONE: richieste non-200:"
    $badStatus | ForEach-Object { Write-Output ("  {0} -> status={1} err={2}" -f $_.label, $_.http_status, $_.err_body) }
}

# Trova tutte le righe "eval time" (decode) in ordine, con il numero di task e t/s
$evalMatches = @()
for ($i = 0; $i -lt $logLines.Count; $i++) {
    if ($logLines[$i] -match 'task\s+(\d+)\s*\|\s*eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens\s*\(\s*([\d.]+)\s*ms per token,\s*([\d.]+)\s*tokens per second\)') {
        $evalMatches += [pscustomobject]@{
            idx = $i; task = [int]$Matches[1]; eval_ms = [double]$Matches[2]; n_tok = [int]$Matches[3]
            ms_per_tok = [double]$Matches[4]; tg_tps = [double]$Matches[5]
        }
    }
}
# Trova tutte le righe "draft acceptance"
$accMatches = @()
for ($i = 0; $i -lt $logLines.Count; $i++) {
    if ($logLines[$i] -match 'task\s+(\d+)\s*\|\s*draft acceptance\s*=\s*([\d.]+)\s*\(\s*(\d+)\s*accepted\s*/\s*(\d+)\s*generated\),\s*mean len\s*=\s*([\d.]+)') {
        $accMatches += [pscustomobject]@{
            idx = $i; task = [int]$Matches[1]; p1 = [double]$Matches[2]; acc = [int]$Matches[3]; gen = [int]$Matches[4]; mean_len = [double]$Matches[5]
        }
    }
}
# Trova tutte le righe "prompt eval time"
$promptMatches = @()
for ($i = 0; $i -lt $logLines.Count; $i++) {
    if ($logLines[$i] -match 'task\s+(\d+)\s*\|\s*prompt eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens\s*\(\s*([\d.]+)\s*ms per token,\s*([\d.]+)\s*tokens per second\)') {
        $promptMatches += [pscustomobject]@{ idx = $i; task = [int]$Matches[1]; prompt_tps = [double]$Matches[5]; prompt_tok = [int]$Matches[3] }
    }
}
# Trova le righe di cambio/vigore control-block e le catture
$cbLines = @()
for ($i = 0; $i -lt $logLines.Count; $i++) {
    if ($logLines[$i] -match '^\S*\s*[EWI]?\s*control-block ->|porto-cb: epoca=\d+ (IN VIGORE|richiesta)') {
        $cbLines += [pscustomobject]@{ idx = $i; text = $logLines[$i] }
    }
}

Write-Output ("eval matches={0} acc matches={1} prompt matches={2} cb lines={3}" -f $evalMatches.Count, $accMatches.Count, $promptMatches.Count, $cbLines.Count)

$rows = @()
for ($k = 0; $k -lt $plan.requests.Count; $k++) {
    $label = $plan.requests[$k].label
    $ev = if ($k -lt $evalMatches.Count) { $evalMatches[$k] } else { $null }
    $ac = if ($k -lt $accMatches.Count) { $accMatches[$k] } else { $null }
    $pr = if ($k -lt $promptMatches.Count) { $promptMatches[$k] } else { $null }
    # cattura: cerca la riga "IN VIGORE" con indice subito prima della riga eval corrispondente e dopo la precedente
    $rows += [pscustomobject]@{
        n        = $k + 1
        label    = $label
        porto_cb = ($plan.requests[$k].porto_cb | ConvertTo-Json -Compress)
        task     = if ($ev) { $ev.task } else { $null }
        tg_tps   = if ($ev) { $ev.tg_tps } else { $null }
        prompt_tps = if ($pr) { $pr.prompt_tps } else { $null }
        p1       = if ($ac) { $ac.p1 } else { $null }
        acc      = if ($ac) { $ac.acc } else { $null }
        gen      = if ($ac) { $ac.gen } else { $null }
        mean_len = if ($ac) { $ac.mean_len } else { $null }
    }
}
$rows | Format-Table -AutoSize | Out-String -Width 200 | Write-Output

$outCsv = Join-Path $OutDir "$Tag.parsed.csv"
$rows | Export-Csv -LiteralPath $outCsv -NoTypeInformation -Encoding UTF8
Write-Output "CSV scritto: $outCsv"

# Stampa anche le righe control-block per verifica manuale (witness di ricattura)
Write-Output "=== witness control-block (prime 80 righe trovate) ==="
$cbLines | Select-Object -First 80 | ForEach-Object { Write-Output $_.text }
