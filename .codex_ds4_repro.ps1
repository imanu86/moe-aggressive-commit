param(
    [ValidateSet('Sidecar', 'Baseline')]
    [string]$Mode,
    [string]$ExecutablePath = 'D:\ds4_work\wt-g73-open\build\ds4_server.exe',
    [string]$Tag,
    [int]$Port = 8000,
    [string]$OutputDir = 'D:\ds4_work\g73_gate\codex_runs'
)

$ErrorActionPreference = 'Stop'
if (-not $Tag) {
    $Tag = ('{0}_{1}' -f $Mode.ToLowerInvariant(), (Get-Date -Format 'yyyyMMdd_HHmmss'))
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

Get-ChildItem Env: |
    Where-Object Name -Like 'DS4_*' |
    ForEach-Object {
        Remove-Item -LiteralPath ('Env:{0}' -f $_.Name) -ErrorAction SilentlyContinue
    }
. 'D:\ds4_work\wt-g73-open\tests\g73_open.env.ps1'

$env:DS4_MODEL_BYTES = '86720111488'
$env:DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB = '2'
$env:DS4_CUDA_Q8_F16_CACHE_RESERVE_MB = '4096'
$env:DS4_CUDA_PREFILL_VRAM_SEED_TOTAL = '160'
$env:DS4_CUDA_PREFILL_VRAM_SEED_FLOOR_PER_LAYER = '4'
$env:DS4_CUDA_RELEASE_PREFILL_SCRATCH = '1'
$env:DS4_CUDA_KV_MANAGED = '1'
$env:DS4_G130_U1_ATTRIBUTION = '1'
$env:DS4_G130_U1_SHUTDOWN_TOKEN =
    (Get-Content -LiteralPath 'D:\ds4_work\g73_gate\.shutdown_token' -Raw).Trim()
$env:DS4_METAL_PREFILL_CHUNK = '768'
$env:DS4_G73_OPEN = '0'

if ($Mode -eq 'Sidecar') {
    $env:DS4_Q1_0_PROMOTION_SSD_WRAP = '1'
    $env:DS4_Q1_0_EXPERT_SIDECAR =
        'D:/ds4_work/q1_pilot_data/sidecar_L15_prod.gguf'
    $env:DS4_Q1_0_LAYER_FIRST = '15'
    $env:DS4_Q1_0_LAYER_LAST = '15'
    $env:DS4_Q1_0_SELECTED_LOAD = '1'
}

$stdoutPath = Join-Path $OutputDir "$Tag.stdout.log"
$stderrPath = Join-Path $OutputDir "$Tag.server.log"
$responsePath = Join-Path $OutputDir "$Tag.response.txt"
$arguments = @(
    '-m', '"C:\ds4-models\ds4-2bit.gguf"',
    '--cuda',
    '-c', '8192',
    '-n', '1024',
    '--mtp-draft', '1',
    '--host', '127.0.0.1',
    '--port', "$Port"
)

$process = $null
$requestSucceeded = $false
$responseText = ''
$completionTokens = 0
$requestSeconds = 0.0
try {
    $process = Start-Process -FilePath $ExecutablePath `
        -ArgumentList $arguments `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden -PassThru
    try {
        $process.PriorityClass =
            [System.Diagnostics.ProcessPriorityClass]::Idle
    } catch {}
    Write-Output (
        'SERVER_STARTED pid={0} load_priority={1}' -f
        $process.Id, $process.PriorityClass)

    $deadline = [DateTime]::UtcNow.AddMinutes(10)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $process.Refresh()
        if ($process.HasExited) {
            throw "server exited during startup code=$($process.ExitCode)"
        }
        if (Test-Path -LiteralPath $stderrPath) {
            $log = Get-Content -LiteralPath $stderrPath -Raw
            if ($log -match 'listening on') {
                $ready = $true
                break
            }
            if ($log -match 'failed to create|aborting') {
                throw 'server startup failure in log'
            }
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) {
        throw 'server startup deadline exceeded'
    }
    try {
        $process.PriorityClass =
            [System.Diagnostics.ProcessPriorityClass]::Normal
    } catch {}
    Write-Output (
        'SERVER_READY decode_priority={0}' -f $process.PriorityClass)

    $body = @{
        model = 'ds4'
        messages = @(
            @{
                role = 'user'
                content = "Genera una pagina HTML completa single-file per una startup AI 'NeuraForge', stile cyberpunk neon: head con CSS interno (variabili, gradient, dark theme), header con nav, hero, 3 feature card, tabella prezzi 3 tier, form contatti con validazione JS, footer. Codice completo e commentato, chiudi con </html>."
            }
        )
        max_tokens = 120
        temperature = 0.7
        seed = 1
        stream = $false
    } | ConvertTo-Json -Depth 6 -Compress

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $result = Invoke-RestMethod -Method Post `
            -Uri "http://127.0.0.1:$Port/v1/chat/completions" `
            -ContentType 'application/json' -Body $body -TimeoutSec 3600
        $stopwatch.Stop()
        $requestSucceeded = $true
        $requestSeconds = $stopwatch.Elapsed.TotalSeconds
        $completionTokens = [int]$result.usage.completion_tokens
        $responseText = [string]$result.choices[0].message.content
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($responsePath, $responseText, $utf8)
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $hash = (
                $sha.ComputeHash($utf8.GetBytes($responseText)) |
                    ForEach-Object { $_.ToString('x2') }
            ) -join ''
        } finally {
            $sha.Dispose()
        }
        Write-Output (
            'HTTP_RESULT=success elapsed_s={0:F3} tokens={1} e2e_tps={2:F3} html_closed={3} response_sha256={4}' -f
            $requestSeconds,
            $completionTokens,
            ($completionTokens / $requestSeconds),
            $responseText.ToLowerInvariant().Contains('</html>'),
            $hash)
    } catch {
        $stopwatch.Stop()
        $requestSeconds = $stopwatch.Elapsed.TotalSeconds
        Write-Output (
            'HTTP_RESULT=failure elapsed_s={0:F3} error={1}' -f
            $requestSeconds, $_.Exception.Message)
    }

    try {
        $shutdownBody = @{
            token = $env:DS4_G130_U1_SHUTDOWN_TOKEN
        } | ConvertTo-Json -Compress
        Invoke-RestMethod -Method Post `
            -Uri "http://127.0.0.1:$Port/__g130_u1_shutdown" `
            -ContentType 'application/json' -Body $shutdownBody `
            -TimeoutSec 10 | Out-Null
    } catch {}
    if (-not $process.WaitForExit(120000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Write-Output 'SERVER_FORCED_STOP=1'
    }
} finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}

$serverLog = ''
if (Test-Path -LiteralPath $stderrPath) {
    $serverLog = Get-Content -LiteralPath $stderrPath -Raw
}
$decodeMs = @(
    [regex]::Matches($serverLog, 'decode_ms=([0-9.]+)') |
        ForEach-Object { [double]$_.Groups[1].Value }
)
if ($decodeMs.Count -gt 20) {
    $steady = @($decodeMs[20..($decodeMs.Count - 1)] | Sort-Object)
    $middle = [int][Math]::Floor($steady.Count / 2)
    if (($steady.Count % 2) -eq 0) {
        $median = ($steady[$middle - 1] + $steady[$middle]) / 2.0
    } else {
        $median = $steady[$middle]
    }
    Write-Output (
        'SERVER_DECODE samples={0} steady_median_ms={1:F3} steady_tps={2:F3}' -f
        $decodeMs.Count, $median, (1000.0 / $median))
} else {
    Write-Output ('SERVER_DECODE samples={0}' -f $decodeMs.Count)
}
Write-Output ('STDERR={0}' -f $stderrPath)
Write-Output ('RESPONSE={0}' -f $responsePath)
@(
    'CUDA Q1_0 routed-expert sidecar installed',
    '\[q1-0-sidecar\]',
    'expert tiering preparation failed',
    'decode route unavailable',
    'finish=error',
    'gen='
) | ForEach-Object {
    [regex]::Matches($serverLog, "(?m)^.*$_.*$") |
        ForEach-Object { $_.Value }
}

if (-not $requestSucceeded) {
    exit 2
}
