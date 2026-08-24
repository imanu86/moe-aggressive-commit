$ErrorActionPreference = 'Stop'

$runnerB = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1'
$sampleHw = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\sample_hw.ps1'
$outDir = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs'
$tag = 'adk_sonda_v3'
$serverLog = Join-Path $outDir "$tag.server.log"

$extra = 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;PORTO_HOT_MASK=15;LLAMA_CACHE_ESPERTI_K_ADATTIVO=1;LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE=D:\ds4_work\adk\adk_trace_v2_b1200_k2_nmax3_20260817.cestrc;LLAMA_CACHE_ESPERTI_CALENDARIO_PIANO=D:\ds4_work\adk\adk_piano_v3_b1200_k2_nmax3_20260817.portcal;LLAMA_CACHE_ESPERTI_K_ADATTIVO_DUMP_EP=1;LLAMA_CACHE_ESPERTI_CALENDARIO_ASYNC=0'

Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] ORCHESTRA: lancio job runner B, tag=$tag"

$job = Start-Job -ScriptBlock {
    param($runnerB, $tag, $extra)
    & $runnerB -Tag $tag -MaxTokens 1200 -Repetitions 4 `
        -PortoHotSnapshot $true -SpecNmax 3 `
        -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe' `
        -Extra $extra
} -ArgumentList $runnerB, $tag, $extra

# Poll finche' il log del server non mostra 'listening', poi avvia la telemetria
$hwStarted = $false
for ($i = 0; $i -lt 180; $i++) {
    if (-not $hwStarted -and (Test-Path $serverLog)) {
        $hit = Select-String -Path $serverLog -Pattern 'listening on http' -ErrorAction SilentlyContinue
        if ($hit) {
            Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] ORCHESTRA: server in ascolto, avvio sample_hw.ps1"
            Start-Process -FilePath 'powershell.exe' `
                -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File', $sampleHw, '-Tag', $tag, '-OutDir', $outDir, '-IntervalSeconds', '2') `
                -WindowStyle Hidden
            $hwStarted = $true
        }
    }
    if ($job.State -ne 'Running') {
        Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] ORCHESTRA: job runner B terminato (stato=$($job.State))"
        break
    }
    Start-Sleep -Seconds 5
}

Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] ORCHESTRA: attendo completamento job (Wait-Job)..."
Wait-Job -Job $job | Out-Null
Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] ORCHESTRA: job concluso, stato=$($job.State)"
Write-Output "===== OUTPUT JOB RUNNER B ====="
Receive-Job -Job $job
Write-Output "===== FINE OUTPUT JOB ====="
Remove-Job -Job $job
Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] ORCHESTRA: FATTO"
