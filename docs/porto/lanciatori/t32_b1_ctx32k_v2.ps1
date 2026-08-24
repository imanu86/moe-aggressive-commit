$ErrorActionPreference = 'Stop'
$root     = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work'
$scratch  = 'C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\4b4c0194-0c4f-4f6b-8e2c-cb939d8d7daa\scratchpad'
$tag      = 'sota_ctx150000_densefa_stage_hc5_t32_b1_ctx32k_v2_f2_b2048'
$hwOut    = 'D:\ds4_work\llama_run'
$sampleHw = Join-Path $root 'sample_hw.ps1'

$hwJob = Start-Job -ScriptBlock {
    param($sampleHw, $tag, $hwOut)
    for ($i = 0; $i -lt 300; $i++) {
        if (Get-Process -Name llama-server -ErrorAction SilentlyContinue) { break }
        Start-Sleep -Seconds 2
    }
    if (Get-Process -Name llama-server -ErrorAction SilentlyContinue) {
        & $sampleHw -Tag $tag -OutDir $hwOut -IntervalSeconds 2
    } else {
        "no llama-server appeared within timeout, telemetry skipped"
    }
} -ArgumentList $sampleHw, $tag, $hwOut

Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] T32_B1_CTX32K_V2 START tag=$tag"

$env:LLAMA_KV_GATHER = '1'
$env:LLAMA_CUDA_SORT_CHUNK_MIB = '8'

& (Join-Path $scratch 'p1b_conf.ps1') -Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 `
    -RunLabel 't32_b1_ctx32k_v2' -PrefixChars 91200 -Context 150000 -MaxTokens 8192 -SpecNmax 3 -SpecConf 0.70 `
    -Repliche 1 -CtxCheckpointMinStep 32 -GraphReusePerTaglia 1 -ReasoningBudgetTokens 0 `
    -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'

try {
    Wait-Job $hwJob -Timeout 30 | Out-Null
    Receive-Job $hwJob -ErrorAction SilentlyContinue
    Remove-Job $hwJob -Force -ErrorAction SilentlyContinue
} catch {
    Write-Output "telemetry job cleanup warning (non-fatale): $($_.Exception.Message)"
}
Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] T32_B1_CTX32K_V2_DONE"
