# Un braccio del confronto A/B sulla sparse flash attention.
#   .\arm_sparse.ps1 -Sfa 0 -Ctx 32000
# Ferma qualunque server, avvia lo SPERIMENTALE con la manopola richiesta, aspetta che
# sia pronto, misura il PREFILL (prompt_tps) e lascia il server acceso per l'ispezione.
param(
    [int]    $Sfa = 0,
    [int]    $Ctx = 32000,
    [int]    $MaxTokens = 64,
    [string] $Mtp = "0",
    [int]    $Slots = 64
)

$scratch = "C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\caacd61a-a05f-4e65-8c73-192af1c868f4\scratchpad"
$logdir  = "C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_server_logs_sperimentali"

$p = Get-Process llama-server -ErrorAction SilentlyContinue
if ($p) { $p | Stop-Process -Force; Start-Sleep -Seconds 6 }

$env:QWEN4EXP_SPARSE_FA = "$Sfa"
$env:MOE_SLOTS          = "$Slots"
$env:DRAFT_EXPERTS      = "ram"

$pr = Start-Process -FilePath "cmd.exe" `
    -ArgumentList '/c', ('"C:\Users\imanu\Desktop\avvia Qwen38 SPERIMENTALE.bat" ' + $Mtp) `
    -RedirectStandardOutput "$scratch\arm_sfa$Sfa.out" -RedirectStandardError "$scratch\arm_sfa$Sfa.err" `
    -NoNewWindow -PassThru

$deadline = (Get-Date).AddMinutes(9); $ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:8100/v1/models" -Headers @{Authorization="Bearer Sticazzi86"} -TimeoutSec 4
        if ($r) { $ready = $true; break }
    } catch { }
    if ($pr.HasExited -and -not (Get-Process llama-server -ErrorAction SilentlyContinue)) {
        Write-Output "LANCIATORE USCITO - ultime righe:"
        Get-Content "$scratch\arm_sfa$Sfa.err" -Tail 15
        exit 1
    }
    Start-Sleep -Seconds 5
}
if (-not $ready) { Write-Output "NON PRONTO entro il tempo"; exit 1 }

Write-Output ("=== braccio QWEN4EXP_SPARSE_FA=$Sfa  contesto=$Ctx  slot=$Slots  mtp=$Mtp")
& python "$scratch\banco_http.py" --ctx-tokens $Ctx --max-tokens $MaxTokens --turns 1 --temperature 0 --label "sfa${Sfa}_ctx${Ctx}"

$log = Get-ChildItem "$logdir\*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Output ("log: " + $log.Name)
