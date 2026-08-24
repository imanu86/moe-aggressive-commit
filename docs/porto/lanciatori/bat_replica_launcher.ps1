# bat_replica_launcher.ps1 -- replica ESATTA di "avvia ds4 locale.bat" (bonificato 23/8),
# per isolare il costo di jinja+template+reasoning e delle sonde diagnostiche.
# Uso: powershell -NoProfile -File bat_replica_launcher.ps1 -Tag <tag> -ProbesOn:$false|$true

param(
    [Parameter(Mandatory = $true)][string] $Tag,
    [bool] $ProbesOn = $false,
    [int] $MaxTokens = 512
)

$ErrorActionPreference = 'Stop'

# stesso fix di run_porto_hot.ps1 per il duplicato PATH/Path che fa fallire Start-Process
$portoPath = $env:Path
[Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
[Environment]::SetEnvironmentVariable('Path', $portoPath, 'Process')

$bin    = 'D:\llama-subtract\build\bin\llama-server.exe'
$run    = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs'
$model  = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$draft  = 'D:\ds4-models\DSpark-draft-Q2K.gguf'
$tmpl   = 'D:\llama-subtract\models\templates\deepseek-ai-DeepSeek-V4-Flash-0731.jinja'
$promptPath = 'D:\ds4_work\llama_run\jprompt.txt'
$port   = 8100
$apiKey = 'Stigrangazzi86!11235813'
$otd    = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$ot     = 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped'

New-Item -ItemType Directory -Force -Path $run | Out-Null
if (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) {
    throw 'Un processo llama-cli/llama-server e'' gia'' attivo.'
}

# --- igiene: rimuovi qualunque residuo di sessione precedente che il bat NON imposta ---
foreach ($v in @('PORTO_SPEC_NMAX','PORTO_SPEC_CONF_MIN','LLAMA_KV_PAD','LLAMA_KV_RING_BATTITO',
                 'LLAMA_DSV4_PREFILL_FATTN_Q_TILE','GGML_CUDA_DISABLE_GRAPHS',
                 'GGML_SCHED_PROFILO','GGML_CUDA_GRAPH_STATS')) {
    Remove-Item "Env:\$v" -ErrorAction SilentlyContinue
}

# --- Configurazione cache/speculazione del ledger (copiata 1:1 dal bat) ---
$env:LLAMA_CACHE_ESPERTI_BATCH = '8'
$env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
$env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
$env:LLAMA_CACHE_ESPERTI_CURA = '0'
$env:LLAMA_CACHE_ESPERTI_FORK = '2'
$env:LLAMA_CACHE_ESPERTI_FORK_BLOCCHI = '8'
$env:LLAMA_CACHE_ESPERTI_FORK_RIUSA_SLOT = '0'
$env:LLAMA_CACHE_ESPERTI_LRU = '1'
$env:LLAMA_CACHE_ESPERTI_MASSA = '2'
$env:LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE = '0'
$env:LLAMA_CACHE_ESPERTI_MASSA_CORSIE = '0'
$env:LLAMA_CACHE_ESPERTI_DMA = '0'
$env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'
$env:LLAMA_CACHE_ESPERTI_SCUDO = '0'
$env:LLAMA_CACHE_ESPERTI_SLOT = '473'
$env:LLAMA_CACHE_ESPERTI_SFRATTO_PAR = '1'
$env:LLAMA_CACHE_ESPERTI_FORK_SALTA_COPIA_PARITA = '0'
$env:LLAMA_CACHE_ESPERTI_W = '0'
$env:LLAMA_CACHE_BOZZA_SLOT = '12'

$env:LLAMA_ACCEPTMOE = '1'
$env:LLAMA_ACCEPTMOE_COMPATTA = '1'
$env:LLAMA_ACCEPTMOE_ESATTE = '1'
$env:LLAMA_ACCEPTMOE_SOGLIA = '0.75'
$env:LLAMA_SPEC_CONF_ESENTA_POS0 = '1'
$env:LLAMA_SPEC_DRAFT_TOPK = '1'

$env:LLAMA_DSV4_HC_FUSO = '5'
$env:LLAMA_MAPPED_IBRIDO = '1'
$env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
$env:LLAMA_OVERLAP_ASYNC = '1'
$env:LLAMA_OVERLAP_BATCH_MAX = '3'
$env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'
$env:LLAMA_OVERLAP_K = '2'
$env:LLAMA_OVERLAP_PIN = '1'
$env:LLAMA_KV_RING = '1'
$env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
# LLAMA_KV_PAD e LLAMA_KV_RING_BATTITO: il bat li mette a vuoto (equivalente ad assenti in cmd) -> non impostati
$env:LLAMA_KV_ROLLBACK_PARZIALE = '1'
$env:LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
$env:LLAMA_VRAM_A_FASI = '2'
$env:LLAMA_VRAM_A_FASI_CALDO = '0'
$env:LLAMA_VRAM_A_FASI_UB = '64'
$env:LLAMA_VRAM_A_FASI_MIN = '0'
$env:LLAMA_VRAM_A_FASI_MARGINE = '0'
$env:LLAMA_VRAM_ZAVORRA = '0'
$env:LLAMA_OVERLAP_JOIN_ASYNC = '0'
$env:LLAMA_DSV4_INDEXER_FUSO = '1'
$env:LLAMA_GRAPH_REUSE_PER_TAGLIA = '1'
$env:LLAMA_MMQ_X_IDS = '64'
$env:LLAMA_DSV4_MASK_F16_INPUT = '0'
$env:LLAMA_CUDA_FATTN_BLOCK_SPARSE = '0'
$env:LLAMA_DSV4_PREFILL_LAYER_STAGING = '1'
$env:LLAMA_DSV4_PREFILL_LAYER_EXECUTOR = '0'
$env:LLAMA_DSV4_PREFILL_LAYER_SPLIT = '0'
$env:LLAMA_DSV4_PREFILL_FFN_SUPEROP = '0'
$env:LLAMA_DSV4_PREFILL_MOE_UB = '2048'
# LLAMA_DSV4_PREFILL_FATTN_Q_TILE: vuoto nel bat -> non impostato
$env:GGML_SCHED_OFFLOAD_PACCHETTI = '0'
$env:LLAMA_CKPT_CRONO = '0'

$env:GGML_CUDA_GRAPH_OPT = '0'
# GGML_CUDA_DISABLE_GRAPHS: resta ASSENTE (grafi accesi), come nel bat

if ($ProbesOn) {
    $env:GGML_SCHED_PROFILO = '1'
    $env:GGML_CUDA_GRAPH_STATS = '1'
}
# altrimenti restano ASSENTI (spente), come nel bat bonificato

$serverLog = Join-Path $run "$Tag.server.log"
$serverOut = Join-Path $run "$Tag.server.out"
$summaryPath = Join-Path $run "$Tag.summary.json"

$argsServer = @(
    '-m', $model, '-md', $draft, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', '3', '--spec-draft-ubatch-size', '16',
    '--spec-draft-conf-min', '0.80',
    '-otd', $otd, '-ngl', '99', '-ot', $ot,
    '-t', '7', '-c', '150000', '-b', '2048', '-ub', '2048', '-np', '1',
    '--jinja', '--reasoning', 'on', '--reasoning-preserve',
    '--chat-template-file', $tmpl,
    '--no-mmap', '--no-host', '--cache-ram', '0', '-cms', '32',
    '--host', '0.0.0.0', '--port', "$port", '--api-key', $apiKey, '-lv', '4'
)

Add-Type -Namespace '' -Name PortoHotConsole2 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Stop-BatReplicaServer($Process) {
    if ($null -eq $Process -or $Process.HasExited) { return 'gia-uscito' }
    $via = 'ctrl-c'
    [void][PortoHotConsole2]::FreeConsole()
    if ([PortoHotConsole2]::AttachConsole([uint32]$Process.Id)) {
        [void][PortoHotConsole2]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][PortoHotConsole2]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][PortoHotConsole2]::FreeConsole()
        [void][PortoHotConsole2]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    } else {
        $via = 'AttachConsole-fallita'
    }
    $Process.WaitForExit(60000) | Out-Null
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force
        $via = "$via -> RISERVA Stop-Process"
    }
    return $via
}

$proc = $null
$hwProc = $null
try {
    Write-Output "[$Tag] avvio server..."
    $proc = Start-Process -FilePath $bin -ArgumentList $argsServer -WindowStyle Hidden -PassThru `
        -RedirectStandardError $serverLog -RedirectStandardOutput $serverOut

    $headers = @{ Authorization = "Bearer $apiKey" }
    $ready = $false
    for ($i = 0; $i -lt 180; $i++) {
        Start-Sleep -Seconds 5
        if ($proc.HasExited) { break }
        try {
            $health = Invoke-WebRequest "http://127.0.0.1:$port/health" -Headers $headers -TimeoutSec 3 -UseBasicParsing
            if ($health.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
    }
    if (-not $ready) { throw 'Server non pronto entro 15 minuti.' }
    Write-Output "[$Tag] server pronto dopo $(($i+1)*5) s."

    # telemetria standard SS6.8, avviata dopo /health OK
    $hwProc = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-File',
        'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\sample_hw.ps1',
        '-Tag', $Tag, '-OutDir', $run, '-IntervalSeconds', '2'
    ) -WindowStyle Hidden -PassThru

    $prompt = [IO.File]::ReadAllText($promptPath, [Text.Encoding]::UTF8)
    $bodyObject = @{
        messages = @(@{ role = 'user'; content = $prompt })
        max_tokens = $MaxTokens
        temperature = 0
        cache_prompt = $true
        porto_hot_snapshot = $false
        stream = $false
    }
    $corpo = [Text.Encoding]::UTF8.GetBytes(($bodyObject | ConvertTo-Json -Compress -Depth 5))

    $sw = [Diagnostics.Stopwatch]::StartNew()
    $response = Invoke-RestMethod "http://127.0.0.1:$port/v1/chat/completions" `
        -Method Post -Body $corpo -Headers $headers `
        -ContentType 'application/json; charset=utf-8' -TimeoutSec 7200
    $sw.Stop()

    $responsePath = Join-Path $run "$Tag.r1.response.json"
    $outputPath = Join-Path $run "$Tag.r1.output.txt"
    $response | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $responsePath -Encoding UTF8
    $content = [string] $response.choices[0].message.content
    $reasoning = [string] $response.choices[0].message.reasoning_content
    $toSave = $content
    if (-not $toSave) { $toSave = $reasoning }
    $toSave | Set-Content -LiteralPath $outputPath -Encoding UTF8

    New-Item -ItemType File -Path (Join-Path $run "$Tag.stop") -Force | Out-Null
    Start-Sleep -Milliseconds 750

    $logText = Get-Content -LiteralPath $serverLog -Raw
    function LastMatch([string]$pat) {
        $m = [regex]::Matches($logText, $pat)
        if ($m.Count -eq 0) { return $null }
        return $m[$m.Count - 1].Groups[1].Value
    }
    $result = [ordered]@{
        tag = $Tag
        probes_on = $ProbesOn
        max_tokens = $MaxTokens
        wall_ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 1)
        eval_tps = LastMatch '\|\s+eval time =.*?([0-9.]+) tokens per second'
        prompt_tps = LastMatch '\|\s+prompt eval time =.*?([0-9.]+) tokens per second'
        p1 = LastMatch 'draft acceptance = ([0-9.]+)'
        finish_reason = [string] $response.choices[0].finish_reason
        sha256_output = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash
        content_chars = $toSave.Length
        used_reasoning_fallback = (-not $content)
        prompt_tokens = $response.usage.prompt_tokens
        completion_tokens = $response.usage.completion_tokens
    }
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
    Write-Output ($result | ConvertTo-Json -Compress)
} finally {
    if ($hwProc -and -not $hwProc.HasExited) {
        Start-Sleep -Seconds 1
    }
    if ($proc) {
        $via = Stop-BatReplicaServer $proc
        Write-Output "shutdown=$via"
    }
}
