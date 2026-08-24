$ErrorActionPreference = 'Stop'
$root    = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work'
$tag     = 't30_confscale_b160_nmax5_conf0_20260824'
$hwOut   = 'D:\ds4_work\llama_run'
$sampleHw = Join-Path $root 'sample_hw.ps1'

$hwJob = Start-Job -ScriptBlock {
    param($sampleHw, $tag, $hwOut)
    for ($i = 0; $i -lt 150; $i++) {
        if (Get-Process -Name llama-server -ErrorAction SilentlyContinue) { break }
        Start-Sleep -Seconds 2
    }
    if (Get-Process -Name llama-server -ErrorAction SilentlyContinue) {
        & $sampleHw -Tag $tag -OutDir $hwOut -IntervalSeconds 2
    } else {
        "no llama-server appeared within timeout, telemetry skipped"
    }
} -ArgumentList $sampleHw, $tag, $hwOut

Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] PHASE2 START tag=$tag"
& (Join-Path $root 'run_porto_hot.ps1') -Tag $tag -MaxTokens 160 -Repetitions 1 `
    -PortoHotSnapshot $false -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe' `
    -SpecNmax 5 -SpecConf '0' `
    -Extra 'LLAMA_SPEC_CONF_LOG=1'

try {
    Wait-Job $hwJob -Timeout 30 | Out-Null
    Receive-Job $hwJob -ErrorAction SilentlyContinue
    Remove-Job $hwJob -Force -ErrorAction SilentlyContinue
} catch {
    Write-Output "telemetry job cleanup warning (non-fatale): $($_.Exception.Message)"
}
Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] PHASE2_DONE"
