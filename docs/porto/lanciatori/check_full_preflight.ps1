$p = @(Get-Process -Name llama-server, llama-cli -ErrorAction SilentlyContinue)
Write-Output "processi_llama=$($p.Count)"
$g = (& nvidia-smi --query-gpu=name,clocks.sm,clocks.mem,power.draw,memory.used,memory.free,pcie.link.gen.gpucurrent,pcie.link.width.current,clocks_throttle_reasons.active --format=csv,noheader,nounits)
Write-Output "gpu=$g"
$ram = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)
Write-Output "ram_libera_gb=$ram"
foreach ($port in 8099,8100) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($c) { Write-Output "porta $port OCCUPATA da PID $($c.OwningProcess)" }
    else    { Write-Output "porta $port libera" }
}
Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -in 'C','D' } |
    ForEach-Object { Write-Output "disco_$($_.Name)_gb=$([math]::Round($_.Free/1GB,1))" }
$up = [math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes, 1)
Write-Output "uptime_min=$up"
