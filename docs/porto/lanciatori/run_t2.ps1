# run_t2.ps1 -- Passo 2/4: T2 (adk_trace_v2), traccia a punto fisso.
# Config sonda COMPLETA del turno 7 (K_ADATTIVO=1, piano v1 caricato, ASYNC=1)
# + registrazione TRACCIA nuova attiva, UNA richiesta sola (capture).
$ErrorActionPreference = 'Stop'
$workDir  = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work'
$runsDir  = Join-Path $workDir 'runs'
$scratch  = 'C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\4b4c0194-0c4f-4f6b-8e2c-cb939d8d7daa\scratchpad'
$tag      = 'adk_trace_v2'

$base = 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
$extra = "$base;PORTO_HOT_MASK=15;LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE=D:\ds4_work\adk\adk_trace_b1200_k2_nmax3_20260817.cestrc;LLAMA_CACHE_ESPERTI_CALENDARIO_PIANO=D:\ds4_work\adk\adk_piano_b1200_k2_nmax3_20260817.portcal;LLAMA_CACHE_ESPERTI_CALENDARIO_ASYNC=1;LLAMA_CACHE_ESPERTI_K_ADATTIVO=1;LLAMA_CACHE_ESPERTI_TRACCIA=D:\ds4_work\adk\adk_trace_v2_b1200_k2_nmax3_20260817.cestrc"

Write-Output "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') AVVIO $tag ==="
Write-Output "Extra = $extra"

Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $scratch 'telemetry_wait_and_run.ps1'),
    '-Tag', $tag, '-OutDir', $runsDir, '-TimeoutMin', '10'
)

& (Join-Path $workDir 'run_porto_hot.ps1') `
    -Tag $tag -MaxTokens 1200 -Repetitions 1 `
    -PortoHotSnapshot $true -SpecNmax 3 `
    -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe' `
    -Extra $extra

Write-Output "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') FINE $tag (script tornato) ==="
