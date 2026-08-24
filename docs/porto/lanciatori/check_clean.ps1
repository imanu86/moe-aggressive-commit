$p = @(Get-Process -Name llama-server, llama-cli -ErrorAction SilentlyContinue)
Write-Output "processi_llama=$($p.Count)"
$g = (& nvidia-smi --query-gpu=memory.used,memory.free,clocks.sm,power.draw --format=csv,noheader,nounits)
Write-Output "gpu=$g"
foreach ($port in 8099,8100) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($c) { Write-Output "porta $port OCCUPATA da PID $($c.OwningProcess)" }
    else    { Write-Output "porta $port libera" }
}
