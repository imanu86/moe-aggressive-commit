$ErrorActionPreference = 'Stop'
$env:LLAMA_KV_GATHER = '1'
$env:LLAMA_KV_GATHER_BATTITO = '30'
$env:LLAMA_KV_RING_VRAM_LID = '300000'
$env:LLAMA_KV_RING_VRAM_CSA = '0'
& 'C:\Users\imanu\Documents\Codex\2026-08-14\ds4-porto-20tps\work\sota100k_ctx150k.ps1' `
  -Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 -RunLabel 't23_repoint' `
  -BlockDenseCpu 0 -Packetizer -1 -PrefixChars 0 -Context 150000 -MaxTokens 8192 `
  -SpecNmax 3 -Repliche 1 -CtxCheckpointMinStep 32 -ReasoningBudgetTokens 0 `
  -GraphReusePerTaglia 1 -KvRingBattito 5 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
