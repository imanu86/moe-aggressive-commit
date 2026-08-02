# Una coda di run a variabile singola, uno dopo l'altro, senza sorveglianza.
# 900 token: ~8 campioni in regime, che bastano (deviazione dei chunk ~1%).
param([int]$Tokens = 900, [int]$Ctx = 10000)
$ErrorActionPreference = 'Continue'
$R = 'C:\Users\imanu\source\repos\moe-aggressive-commit'

# Ogni voce e' UNA variabile cambiata rispetto al braccio G.
$prove = @(
  @{ nome = 'budget6';       ov = @{ 'DS4_EXPERT_TIER_REPLACEMENT_BUDGET' = '6' } },
  @{ nome = 'budget2';       ov = @{ 'DS4_EXPERT_TIER_REPLACEMENT_BUDGET' = '2' } },
  @{ nome = 'clock1000_b6';  ov = @{ 'DS4_EXPERT_TIER_CLOCK_CALLS'        = '1000'
                                     'DS4_EXPERT_TIER_REPLACEMENT_BUDGET' = '6' } }
)

foreach ($p in $prove) {
  Write-Host ("=== {0}  ({1}) ===" -f $p.nome, (Get-Date -Format 'HH:mm:ss'))
  & "$R\docs\porto\braccio.ps1" -Arm G -Tokens $Tokens -Ctx $Ctx -Override $p.ov 2>&1 |
      Select-Object -Last 3
  Start-Sleep -Seconds 20      # quiete fra i bracci: la standby si assesta
}
Write-Host "=== CODA FINITA ==="
