param(
    [Parameter(Mandatory=$true)][string]$Tag,
    [Parameter(Mandatory=$true)][int]$MaxTokens,
    [Parameter(Mandatory=$true)][int]$Repetitions,
    [Parameter(Mandatory=$true)][bool]$PortoHotSnapshot,
    [Parameter(Mandatory=$true)][int]$SpecNmax,
    [Parameter(Mandatory=$true)][string]$ServerPath,
    [Parameter(Mandatory=$true)][string]$Extra,
    [int]$HealthTimeoutMinutes = 10
)

$runnerPath   = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1'
$sampleHwPath = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\sample_hw.ps1'
$runDir       = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs'

Write-Output "[$(Get-Date -Format 'HH:mm:ss')] AVVIO braccio $Tag  (MaxTokens=$MaxTokens Repetitions=$Repetitions PortoHotSnapshot=$PortoHotSnapshot SpecNmax=$SpecNmax)"
Write-Output "[$(Get-Date -Format 'HH:mm:ss')] ServerPath = $ServerPath"
Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Extra      = $Extra"

$job = Start-Job -ScriptBlock {
    param($runnerPath, $Tag, $MaxTokens, $Repetitions, $PortoHotSnapshot, $SpecNmax, $ServerPath, $Extra)
    & $runnerPath -Tag $Tag -MaxTokens $MaxTokens -Repetitions $Repetitions `
        -PortoHotSnapshot $PortoHotSnapshot -SpecNmax $SpecNmax -ServerPath $ServerPath -Extra $Extra
} -ArgumentList $runnerPath, $Tag, $MaxTokens, $Repetitions, $PortoHotSnapshot, $SpecNmax, $ServerPath, $Extra

$ready = $false
$hwStarted = $false
$deadline = (Get-Date).AddMinutes($HealthTimeoutMinutes)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    if ($job.State -ne 'Running') {
        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] job terminato (stato=$($job.State)) prima che /health rispondesse"
        break
    }
    $p = Get-Process -Name llama-server -ErrorAction SilentlyContinue
    if ($p) {
        try {
            $health = Invoke-WebRequest 'http://127.0.0.1:8100/health' -TimeoutSec 3 -UseBasicParsing
            if ($health.StatusCode -eq 200) {
                $ready = $true
                Write-Output "[$(Get-Date -Format 'HH:mm:ss')] /health OK, avvio sample_hw.ps1"
                break
            }
        } catch {}
    }
}

if ($ready) {
    Start-Process powershell.exe -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $sampleHwPath,
        '-Tag', $Tag, '-OutDir', $runDir, '-IntervalSeconds', '2'
    ) -WindowStyle Hidden
    $hwStarted = $true
} else {
    Write-Output "[$(Get-Date -Format 'HH:mm:ss')] *** ATTENZIONE: /health non raggiunto entro $HealthTimeoutMinutes min o job gia' terminato. sample_hw NON avviato. ***"
}

Wait-Job $job -Timeout 3600 | Out-Null
$state = $job.State
$jobOutput = Receive-Job $job -ErrorAction SilentlyContinue
$jobErr = $job.ChildJobs[0].Error

Write-Output "=== OUTPUT JOB ($Tag) stato_finale=$state ==="
$jobOutput | ForEach-Object { Write-Output $_ }
if ($jobErr -and $jobErr.Count -gt 0) {
    Write-Output "=== ERRORI JOB ($Tag) ==="
    $jobErr | ForEach-Object { Write-Output $_.ToString() }
}
Remove-Job $job -Force -ErrorAction SilentlyContinue

Write-Output "[$(Get-Date -Format 'HH:mm:ss')] FINE braccio $Tag (hw_avviato=$hwStarted, stato_job=$state)"
