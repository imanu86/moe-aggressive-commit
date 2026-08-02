# Una coda di run a variabile singola, uno dopo l'altro, senza sorveglianza.
# 900 token: ~8 campioni in regime, che bastano (deviazione dei chunk ~1%).
param([int]$Tokens = 900, [int]$Ctx = 10000)
$ErrorActionPreference = 'Continue'
$R = 'C:\Users\imanu\source\repos\moe-aggressive-commit'

# Ogni voce e' UNA variabile cambiata rispetto al braccio G.
$prove = @(
  @{ nome = 'clock1000';  ov = @{ 'DS4_EXPERT_TIER_CLOCK_CALLS' = '1000' } },
  @{ nome = 'clock2000';  ov = @{ 'DS4_EXPERT_TIER_CLOCK_CALLS' = '2000' } },
  @{ nome = 'gate2';      ov = @{ 'DS4_EXPERT_TIER_MIN_FREQUENCY' = '2'
                                  'DS4_EXPERT_TIER_CLOCK_CALLS'   = '1000' } },
  @{ nome = 'packedcopy'; ov = @{ 'DS4_CUDA_MOE_ROUTE_PACKED_COPY' = '1' } }
)

foreach ($p in $prove) {
  Write-Host ("=== {0}  ({1}) ===" -f $p.nome, (Get-Date -Format 'HH:mm:ss'))
  & "$R\docs\porto\braccio.ps1" -Arm G -Tokens $Tokens -Ctx $Ctx -Override $p.ov 2>&1 |
      Select-Object -Last 3
  Start-Sleep -Seconds 20      # quiete fra i bracci: la standby si assesta
}
Write-Host "=== CODA FINITA ==="
