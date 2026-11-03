# Riavvia il solo dispositivo della RTX 3060 (schermo e OktoCGControl), con una fotografia prima e una dopo.
# Chiede i diritti di amministratore (finestra di Controllo account utente). Lo schermo si spegne per qualche secondo.
$qui = Split-Path -Parent $MyInvocation.MyCommand.Path
$id = 'PCI\VEN_10DE&DEV_2504&SUBSYS_40E21458&REV_A1\6&1D288762&0&0010020A'   # la 3060 attiva, bus PCI 6 (nvidia-smi 06:00), letta il 03/11
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $qui 'diagnosi_3060.ps1')
    Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$($MyInvocation.MyCommand.Path)`"" -Wait
    Start-Sleep -Seconds 10
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $qui 'diagnosi_3060.ps1')
    'Fatto: le due fotografie sono nella cartella delle prove.'
    Start-Sleep -Seconds 5
    exit
}
$log = Join-Path $qui 'riavvia_3060.log'
"$(Get-Date -Format 'dd/MM HH:mm:ss') riavvio $id" | Out-File $log -Append -Encoding utf8
& pnputil /restart-device "$id" 2>&1 | Out-File $log -Append -Encoding utf8
