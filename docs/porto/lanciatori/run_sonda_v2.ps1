# run_sonda_v2.ps1 -- Passo 4/4: SONDA v2 (adk_sonda_v2).
#
# DEVIAZIONE [S] DALLA LETTERA DEL MANDATO, MOTIVATA -- verificata sul codice, non assunta:
# il mandato dice "identica a T2 ma piano v2 al posto del v1". Letto alla lettera cambierebbe
# SOLO CALENDARIO_PIANO, lasciando CALENDARIO_TRACE=v1. Verificato pero' su cache-esperti.cu
# che l'aggancio del replay (righe 5638-5674, "il primo gruppo") confronta `c.calendario`,
# popolato SOLO da CALENDARIO_TRACE -- CALENDARIO_PIANO non entra MAI in quel confronto (serve
# solo a scadenza_ep, la tabella deadline di K_ADATTIVO). E la riscrittura di chiave[] quando
# armato (righe 5752-5759, `chiave[i] = piano.stati[i]`) legge anch'essa da `c.calendario`, cioe'
# da CALENDARIO_TRACE, non da CALENDARIO_PIANO. Tenere CALENDARIO_TRACE=v1 avrebbe quindi
# riprodotto la STESSA traccia mai armata (posizione=0/27778 fisso) gia' vista 3 volte
# (adk_sonda_piano del turno 7, S1, T2 di questo turno) -- costruire il piano v2 sarebbe stato
# inutile per il cancello (a). Interpretato quindi "piano v2" come il PACCHETTO trace+piano v2
# (come lo chiama lo stesso mandato nel preambolo: "trace+piano v1" / "trace+piano v2" sempre
# in coppia) -- CALENDARIO_TRACE e CALENDARIO_PIANO passano ENTRAMBI a v2. Riportare questa
# scelta esplicitamente nel verbale: se il coordinatore intendeva altro, il braccio va rifatto.
#
# Per il resto identica a T2: stesso K_ADATTIVO=1, stesso CALENDARIO_ASYNC=1, SENZA la variabile
# di registrazione TRACCIA (non serve piu' registrare, il trace v2 e' gia' su disco).
$ErrorActionPreference = 'Stop'
$workDir  = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work'
$runsDir  = Join-Path $workDir 'runs'
$scratch  = 'C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\4b4c0194-0c4f-4f6b-8e2c-cb939d8d7daa\scratchpad'
$tag      = 'adk_sonda_v2'

$base = 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
$extra = "$base;PORTO_HOT_MASK=15;LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE=D:\ds4_work\adk\adk_trace_v2_b1200_k2_nmax3_20260817.cestrc;LLAMA_CACHE_ESPERTI_CALENDARIO_PIANO=D:\ds4_work\adk\adk_piano_v2_b1200_k2_nmax3_20260817.portcal;LLAMA_CACHE_ESPERTI_CALENDARIO_ASYNC=1;LLAMA_CACHE_ESPERTI_K_ADATTIVO=1"

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
