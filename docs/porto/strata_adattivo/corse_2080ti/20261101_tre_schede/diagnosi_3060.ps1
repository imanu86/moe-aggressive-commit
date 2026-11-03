# Fotografia in sola lettura della 3060 quando «lavora sempre e male»: da lanciare PRIMA di riavviare.
# Scrive diagnosi_3060_<ora>.txt accanto allo script: schede, motori GPU per processo, programmi sospetti, schermo.
$qui = Split-Path -Parent $MyInvocation.MyCommand.Path
$f = Join-Path $qui ("diagnosi_3060_{0}.txt" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
& {
    Get-Date -Format 'dd/MM/yyyy HH:mm:ss'
    'avvio Windows ' + (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('dd/MM HH:mm')
    & 'C:\Windows\System32\nvidia-smi.exe' --query-gpu=index,name,utilization.gpu,utilization.encoder,utilization.decoder,encoder.stats.sessionCount,pstate,clocks.gr,clocks.mem,power.draw,memory.used,temperature.gpu,pcie.link.gen.current,pcie.link.width.current,clocks_throttle_reasons.active --format=csv
    '--- motori GPU per processo (3 campioni)'
    foreach ($i in 1..3) {
        Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | ForEach-Object {
            if ($_.Name -match 'pid_(\d+)_(luid_\w+?)_phys.*engtype_(.*)$' -and $_.UtilizationPercentage -gt 1) {
                '{0} pid {1} {2} {3} {4}%' -f (Get-Process -Id $Matches[1] -ErrorAction SilentlyContinue).Name, $Matches[1], $Matches[2], $Matches[3], $_.UtilizationPercentage
            }
        }
        '-'
        Start-Sleep -Milliseconds 700
    }
    '--- memoria GPU per processo'
    Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory | ForEach-Object {
        if ($_.Name -match 'pid_(\d+)_(luid_\w+?)_phys' -and $_.DedicatedUsage -gt 100MB) {
            '{0} pid {1} {2} {3:N0} MB' -f (Get-Process -Id $Matches[1] -ErrorAction SilentlyContinue).Name, $Matches[1], $Matches[2], ($_.DedicatedUsage / 1MB)
        }
    }
    '--- programmi'
    foreach ($n in 'dwm','JumpConnect','JumpDesktop','MSIAfterburner','RTSS','CGControl','strata','obs64','nvcontainer','NVIDIA Share','Teams','chrome','msedge') {
        $p = @(Get-Process $n -ErrorAction SilentlyContinue)
        if ($p.Count) { '{0}: {1} processi, CPU {2:N0} s, {3:N1} GB' -f $n, $p.Count, ($p | Measure-Object CPU -Sum).Sum, (($p | Measure-Object WorkingSet64 -Sum).Sum / 1GB) }
    }
    '--- schermo'
    Add-Type 'using System;using System.Runtime.InteropServices;public class GD{[DllImport("user32.dll")]public static extern IntPtr GetDC(IntPtr h);[DllImport("gdi32.dll")]public static extern int GetDeviceCaps(IntPtr d,int i);[DllImport("user32.dll")]public static extern bool SetProcessDPIAware();}'
    [GD]::SetProcessDPIAware() | Out-Null
    $d = [GD]::GetDC([IntPtr]::Zero)
    '{0}x{1} a {2} Hz' -f [GD]::GetDeviceCaps($d, 118), [GD]::GetDeviceCaps($d, 117), [GD]::GetDeviceCaps($d, 116)
    'HAGS ' + (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' -Name HwSchMode -ErrorAction SilentlyContinue).HwSchMode
    '--- eventi del driver nelle ultime 6 ore'
    Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'nvlddmkm', 'Display'; StartTime = (Get-Date).AddHours(-6) } -ErrorAction SilentlyContinue | Select-Object -First 15 | ForEach-Object { '{0:HH:mm:ss} {1} {2}' -f $_.TimeCreated, $_.ProviderName, $_.Id }
} *> $f
"scritto $f"
