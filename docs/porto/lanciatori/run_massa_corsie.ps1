# run_massa_corsie.ps1 -- Passo 5 (mandato supplementare del coordinatore): MASSA_CORSIE.
# Config campione V0 (K=2, nmax3, warm-restore, leve nuove SPENTE: niente calendario/piano/
# k_adattivo) + LLAMA_CACHE_ESPERTI_MASSA_CORSIE=1 (default runner = '0', confermato dal log
# v0_k2_subtract: "corsie=0" -- quindi questa e' una leva realmente mai accesa finora).
$ErrorActionPreference = 'Stop'
$workDir  = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work'
$runsDir  = Join-Path $workDir 'runs'
$scratch  = 'C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\4b4c0194-0c4f-4f6b-8e2c-cb939d8d7daa\scratchpad'
$tag      = 'massa_corsie_b1'

$base = 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
$extra = "$base;PORTO_HOT_MASK=15;LLAMA_CACHE_ESPERTI_MASSA_CORSIE=1"

Write-Output "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') AVVIO $tag ==="
Write-Output "Extra = $extra"

Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $scratch 'telemetry_wait_and_run.ps1'),
    '-Tag', $tag, '-OutDir', $runsDir, '-TimeoutMin', '10'
)

& (Join-Path $workDir 'run_porto_hot.ps1') `
    -Tag $tag -MaxTokens 1200 -Repetitions 4 `
    -PortoHotSnapshot $true -SpecNmax 3 `
    -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe' `
    -Extra $extra

Write-Output "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') FINE $tag (script tornato) ==="
