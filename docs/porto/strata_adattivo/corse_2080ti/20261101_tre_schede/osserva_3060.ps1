# Sola lettura, ogni 30 secondi: uso della 3060, traffico sul riser, decodifica video, chi la usa in disegno.
# Serve a capire da dove vengono i picchi all'80% anche con Jump chiuso. File osserva_3060.csv accanto allo script.
$qui = Split-Path -Parent $MyInvocation.MyCommand.Path
$f = Join-Path $qui 'osserva_3060.csv'
$intest = 'ora,uso_3060,dec_3060,mem_3060_mib,pstate,riser_rx_mbs,riser_tx_mbs,cgcontrol_3d,dwm_3d,jump_3d,altri_3d,jump_aperto'
if (-not (Test-Path $f) -or -not ((Get-Content $f -TotalCount 1) -match 'riser')) { $intest | Out-File $f -Encoding utf8 }
while (-not (Test-Path (Join-Path $qui 'STOP_OSSERVA'))) {
    $s = (& 'C:\Windows\System32\nvidia-smi.exe' -i 1 --query-gpu=utilization.gpu,utilization.decoder,memory.used,pstate --format=csv,noheader,nounits) -split ',\s*'
    $t = (& 'C:\Windows\System32\nvidia-smi.exe' dmon -i 1 -s t -c 1 | Where-Object { $_ -notmatch '^#' } | Select-Object -Last 1) -split '\s+' | Where-Object { $_ }
    $u = @{ CGControl = 0; dwm = 0; JumpConnect = 0; altri = 0 }
    Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | ForEach-Object {
        if ($_.Name -match 'pid_(\d+)_.*engtype_3D$' -and $_.UtilizationPercentage -gt 0) {
            $n = (Get-Process -Id $Matches[1] -ErrorAction SilentlyContinue).Name
            if ($u.ContainsKey($n)) { $u[$n] += $_.UtilizationPercentage } else { $u['altri'] += $_.UtilizationPercentage }
        }
    }
    $jump = [int](@(Get-PnpDevice -Class Display -Status OK -ErrorAction SilentlyContinue | Where-Object FriendlyName -match 'Jump').Count -gt 0)
    '{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10},{11}' -f (Get-Date -Format 'dd/MM HH:mm:ss'), $s[0], $s[1], $s[2], $s[3], $t[1], $t[2], $u['CGControl'], $u['dwm'], $u['JumpConnect'], $u['altri'], $jump | Out-File $f -Append -Encoding utf8
    Start-Sleep -Seconds 30
}
Remove-Item (Join-Path $qui 'STOP_OSSERVA') -ErrorAction SilentlyContinue
