$ErrorActionPreference = 'Stop'
& 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' `
  -Tag 't21_conf_c_b1200_r1_20260818' -MaxTokens 1200 -Repetitions 4 -PortoHotSnapshot 1 -SpecNmax 3 -SpecConf '0' `
  -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;PORTO_HOT_MASK=15;LLAMA_CONF_PRENORM=1' `
  -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
