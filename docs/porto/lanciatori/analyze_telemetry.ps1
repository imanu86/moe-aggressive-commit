param([Parameter(Mandatory=$true)][string]$Tag)
$runs = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs'
$hw = Import-Csv (Join-Path $runs "$Tag.hw.csv")
function StripUnit($s) { ($s -replace '[^0-9.\-]', '') }
$rows = $hw | ForEach-Object {
    [pscustomobject]@{
        sm   = [double](StripUnit $_.'clocks.sm')
        mem  = [double](StripUnit $_.'clocks.mem')
        pw   = [double](StripUnit $_.'power.draw')
        util = [double](StripUnit $_.'utilization.gpu')
        used = [double](StripUnit $_.'memory.used')
    }
}
$busy = @($rows | Where-Object { $_.util -gt 30 })
Write-Output "campioni totali=$($rows.Count)  campioni util>30=$($busy.Count)"
if ($busy.Count -gt 0) {
    $sm = @($busy.sm | Sort-Object)
    $pw = @($busy.pw | Sort-Object)
    Write-Output ("SM mediano (util>30) = " + $sm[[math]::Floor(($sm.Count-1)/2)] + " MHz  (min " + $sm[0] + ", max " + $sm[-1] + ")")
    Write-Output ("potenza mediana (util>30) = " + $pw[[math]::Floor(($pw.Count-1)/2)] + " W")
} else {
    Write-Output "NESSUN campione con util>30 -- probabile csv senza campo utilization popolato dal probe (nvidia-smi non riporta sempre util per processi esterni); riporto min/max SM su TUTTI i campioni come diagnostica"
    $sm = @($rows.sm | Sort-Object)
    Write-Output ("SM min/mediana/max (tutti) = " + $sm[0] + " / " + $sm[[math]::Floor(($sm.Count-1)/2)] + " / " + $sm[-1] + " MHz")
}
$peakVram = ($rows.used | Measure-Object -Maximum).Maximum
Write-Output "VRAM picco = $peakVram MiB"
$vramMedia = [math]::Round(($rows.used | Measure-Object -Average).Average, 1)
Write-Output "VRAM media = $vramMedia MiB"
$throttleCheck = $hw | Select-Object -ExpandProperty 'clocks.sm' -ErrorAction SilentlyContinue
$cpu = Import-Csv (Join-Path $runs "$Tag.cpu.csv")
$cpuVals = @($cpu | Where-Object { $_.cpu_percent_totale -match '^[0-9.]+$' } | ForEach-Object { [double]$_.cpu_percent_totale })
if ($cpuVals.Count -gt 0) {
    Write-Output ("CPU% media = " + [math]::Round(($cpuVals | Measure-Object -Average).Average, 1) + "  (n=$($cpuVals.Count))")
}
