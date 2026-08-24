$ErrorActionPreference = 'Continue'
$root     = 'C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\4b4c0194-0c4f-4f6b-8e2c-cb939d8d7daa\scratchpad'
$sampleHwPath = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\sample_hw.ps1'
$hwOut    = 'D:\ds4_work\llama_run'
$hwTag    = 't30_repoint_sortchunk8'
$doneMark = Join-Path $hwOut 't30_repoint_sortchunk8.ALLDONE'

if (Test-Path -LiteralPath $doneMark) { Remove-Item -LiteralPath $doneMark -Force }

# Leve nuove del chirurgo 14 (NOTE_IMPLEMENTAZIONE.md S18.3/S18.4) + gather (precedente ai
# turni 22/28/29): impostate dal CHIAMANTE, esattamente come LLAMA_KV_GATHER nei turni
# precedenti -- nessuna di queste tre e' toccata da Set-SotaEnvironment dentro lo script,
# quindi persistono invariate per tutta la corsa senza bisogno di un parametro dedicato.
$env:LLAMA_KV_GATHER = '1'
$env:LLAMA_CUDA_SORT_CHUNK_MIB = '8'
$env:LLAMA_CUDA_POOL_TRACE = '1'

$hwJob = Start-Job -ScriptBlock {
    param($sampleHwPath, $hwTag, $hwOut)
    for ($i = 0; $i -lt 300; $i++) {
        if (Get-Process -Name llama-server -ErrorAction SilentlyContinue) { break }
        Start-Sleep -Seconds 2
    }
    if (Get-Process -Name llama-server -ErrorAction SilentlyContinue) {
        & $sampleHwPath -Tag $hwTag -OutDir $hwOut -IntervalSeconds 2
    } else {
        "no llama-server appeared within timeout, telemetry skipped"
    }
} -ArgumentList $sampleHwPath, $hwTag, $hwOut

Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] PHASE3 LAUNCH env: LLAMA_KV_GATHER=$env:LLAMA_KV_GATHER LLAMA_CUDA_SORT_CHUNK_MIB=$env:LLAMA_CUDA_SORT_CHUNK_MIB LLAMA_CUDA_POOL_TRACE=$env:LLAMA_CUDA_POOL_TRACE"

& (Join-Path $root 'sota100k_ctx150k_t30.ps1') `
    -Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 `
    -RunLabel 't30_repoint_sortchunk8' -Context 150000 -MaxTokens 8192 -SpecNmax 3 `
    -SpecConf '0.70' -Repliche 1 -CtxCheckpointMinStep 32 -GraphReusePerTaglia 1 `
    -ReasoningBudgetTokens 0 -KvRingVramLid '115000' -KvRingVramCsa '2048' `
    -CacheEspertiSlot '450' -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
$mainExit = $LASTEXITCODE

try {
    Wait-Job $hwJob -Timeout 30 | Out-Null
    Receive-Job $hwJob -ErrorAction SilentlyContinue
    Remove-Job $hwJob -Force -ErrorAction SilentlyContinue
} catch {
    Write-Output "telemetry job cleanup warning (non-fatale): $($_.Exception.Message)"
}

"PHASE3_ALLDONE exit=$mainExit at $([DateTime]::Now.ToString('HH:mm:ss'))" | Set-Content -LiteralPath $doneMark -Encoding UTF8
Write-Output "[$([DateTime]::Now.ToString('HH:mm:ss'))] PHASE3_ALLDONE"
