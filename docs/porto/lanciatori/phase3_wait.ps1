$doneMark = 'D:\ds4_work\llama_run\t30_repoint_sortchunk8.ALLDONE'
$maxChecks = 300   # 300 * 15s = 4500s = 75 min (cintura +50% su una stima nominale di ~50 min)
for ($i = 0; $i -lt $maxChecks; $i++) {
    if (Test-Path -LiteralPath $doneMark) {
        Write-Output "MARKER TROVATO dopo $i check ($([math]::Round($i*15/60,1)) min)"
        Get-Content -LiteralPath $doneMark
        break
    }
    $alive = @(Get-Process -Name llama-server -ErrorAction SilentlyContinue).Count
    if ($i % 8 -eq 0) {
        Write-Output "check $i ($([math]::Round($i*15/60,1)) min) : llama-server vivo=$alive"
    }
    Start-Sleep -Seconds 15
}
if (-not (Test-Path -LiteralPath $doneMark)) {
    Write-Output "TIMEOUT: marker non comparso dopo $($maxChecks*15/60) minuti"
}
