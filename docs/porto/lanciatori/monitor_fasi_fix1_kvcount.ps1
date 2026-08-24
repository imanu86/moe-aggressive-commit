# monitor_fasi_fix1_kvcount.ps1 -- SOLA LETTURA. Emette una riga su stdout ad ogni
# passaggio di fase del braccio fix1_kvcount (fine r1/r2/r3, DONE, o errore), poi esce.
# Non tocca il banco: legge solo launcher.out (UTF-16LE) e la coda del .server.log (ASCII).

$outFile = 'D:\ds4_work\llama_run\fix1_kvcount.launcher.out'
$log     = 'D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_fix1_kvcount_f2_b2048.server.log'

$patterns = @(
    'loading sota_', 'loaded sota_', 'repliche richieste',
    'r=1/3 request start', 'r=1 request complete', 'r=1 usage', 'r=1 timings', 'r=1 finish=', 'r=1 p1=',
    'r=2/3 request start', 'r=2 request complete', 'r=2 usage', 'r=2 timings', 'r=2 finish=', 'r=2 p1=',
    'r=3/3 request start', 'r=3 request complete', 'r=3 usage', 'r=3 timings', 'r=3 finish=', 'r=3 p1=',
    '^shutdown:', '^DONE tag=', 'REQUEST FAILED', 'NO SHAPE LOADED', 'load failed'
) -join '|'

$seen = 0
$doneSeen = $false
$lastErr = ''

function Emit([string] $s) {
    [Console]::Out.WriteLine($s)
    [Console]::Out.Flush()
}

Emit "MONITOR AVVIATO $(Get-Date -Format 'HH:mm:ss') -- osservo $outFile"

while (-not $doneSeen) {
    if (Test-Path -LiteralPath $outFile) {
        $lines = @(Get-Content -LiteralPath $outFile -Encoding Unicode -ErrorAction SilentlyContinue)
        if ($lines.Count -gt $seen) {
            $new = $lines[$seen..($lines.Count - 1)]
            foreach ($l in $new) {
                if ($l -match $patterns) {
                    Emit "[$(Get-Date -Format 'HH:mm:ss')] $l"
                }
                if ($l -match '^DONE tag=') { $doneSeen = $true }
            }
            $seen = $lines.Count
        }
    }
    if (Test-Path -LiteralPath $log) {
        $errHit = Get-Content -LiteralPath $log -Tail 400 -ErrorAction SilentlyContinue |
            Select-String -Pattern 'CUDA error|GGML_ASSERT|invalid index|out of memory' | Select-Object -Last 1
        if ($errHit -and $errHit.Line -ne $lastErr) {
            Emit "[$(Get-Date -Format 'HH:mm:ss')] *** ERRORE RILEVATO NEL LOG: $($errHit.Line) ***"
            $lastErr = $errHit.Line
            $doneSeen = $true
        }
    }
    if (-not $doneSeen) { Start-Sleep -Seconds 25 }
}
Emit "MONITOR: fine osservazione $(Get-Date -Format 'HH:mm:ss')"
