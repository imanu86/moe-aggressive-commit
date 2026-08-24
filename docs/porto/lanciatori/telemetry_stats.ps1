param([string]$Tag)
$csv = "C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\$Tag.hw.csv"
$rows = Import-Csv $csv
function NumOnly([string]$s) {
    if ($s -match '([0-9]+(\.[0-9]+)?)') { return [double]$Matches[1] }
    return $null
}
$parsed = @($rows | ForEach-Object {
    [pscustomobject]@{
        sm   = NumOnly $_.'clocks.sm'
        pw   = NumOnly $_.'power.draw'
        util = NumOnly $_.'utilization.gpu'
        vram = NumOnly $_.'memory.used'
    }
})
$busy = @($parsed | Where-Object { $_.util -ne $null -and $_.util -gt 50 })
Write-Output "tag=$Tag  campioni_totali=$($rows.Count)  campioni_busy(util>50)=$($busy.Count)"
if ($busy.Count -gt 0) {
    $sm = @($busy | ForEach-Object { $_.sm } | Sort-Object)
    $pw = @($busy | ForEach-Object { $_.pw } | Sort-Object)
    $vram = @($busy | ForEach-Object { $_.vram } | Sort-Object)
    $medIdx = [math]::Floor(($sm.Count - 1) / 2)
    Write-Output "  SM: min=$($sm[0])  mediana=$($sm[$medIdx])  max=$($sm[-1])"
    Write-Output "  power: min=$($pw[0])  mediana=$($pw[$medIdx])  max=$($pw[-1])"
    Write-Output "  vram_used: min=$($vram[0])  max=$($vram[-1])"
    $sotto1500 = @($sm | Where-Object { $_ -lt 1500 })
    Write-Output "  campioni_sotto_1500MHz=$($sotto1500.Count) / $($sm.Count)"
}
