# codex_reuse_test.ps1 -- verifica il riuso KV/prompt dall'endpoint /v1/chat/completions con
# un pattern da client agentico (Codex CLI): system lungo (~10-13k token) + storia che cresce
# di 2 turni brevi in piu'. Server sulla STESSA config bat-pulito (jinja+template, sonde spente).
# Addendum coordinatore 23/8.

param(
    [string] $Tag = 't24_codex_reuse_20260823'
)

$ErrorActionPreference = 'Stop'

$portoPath = $env:Path
[Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
[Environment]::SetEnvironmentVariable('Path', $portoPath, 'Process')

$bin   = 'D:\llama-subtract\build\bin\llama-server.exe'
$run   = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs'
$model = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$draft = 'D:\ds4-models\DSpark-draft-Q2K.gguf'
$tmpl  = 'D:\llama-subtract\models\templates\deepseek-ai-DeepSeek-V4-Flash-0731.jinja'
$port  = 8100
$apiKey = 'Stigrangazzi86!11235813'
$otd   = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$ot    = 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped'

New-Item -ItemType Directory -Force -Path $run | Out-Null
if (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) {
    throw 'Un processo llama-cli/llama-server e'' gia'' attivo.'
}

foreach ($v in @('PORTO_SPEC_NMAX','PORTO_SPEC_CONF_MIN','LLAMA_KV_PAD','LLAMA_KV_RING_BATTITO',
                 'LLAMA_DSV4_PREFILL_FATTN_Q_TILE','GGML_CUDA_DISABLE_GRAPHS',
                 'GGML_SCHED_PROFILO','GGML_CUDA_GRAPH_STATS')) {
    Remove-Item "Env:\$v" -ErrorAction SilentlyContinue
}

# --- stesso identico blocco ambientale di bat_replica_launcher.ps1 (bat-pulito, sonde OFF) ---
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
$env:GGML_SCHED_OFFLOAD_PACCHETTI = '0'
$env:LLAMA_CKPT_CRONO = '0'
$env:GGML_CUDA_GRAPH_OPT = '0'
# GGML_SCHED_PROFILO / GGML_CUDA_GRAPH_STATS / GGML_CUDA_DISABLE_GRAPHS restano ASSENTI

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

Add-Type -Namespace '' -Name PortoHotConsole4 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Stop-CodexReuseServer($Process) {
    if ($null -eq $Process -or $Process.HasExited) { return 'gia-uscito' }
    $via = 'ctrl-c'
    [void][PortoHotConsole4]::FreeConsole()
    if ([PortoHotConsole4]::AttachConsole([uint32]$Process.Id)) {
        [void][PortoHotConsole4]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][PortoHotConsole4]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][PortoHotConsole4]::FreeConsole()
        [void][PortoHotConsole4]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
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

# --- costruzione del "system" lungo: contenuto non significativo, SOLO la lunghezza conta ---
$sb = [System.Text.StringBuilder]::new()
for ($i = 1; $i -le 180; $i++) {
    [void]$sb.AppendLine("Riga $($i.ToString('0000')): contesto di prova per la simulazione del client agentico Codex, contenuto non significativo usato solo per riempire la finestra di contesto, indice $i, marcatore fittizio ALFA-$i-BETA.")
}
$bigSystem = $sb.ToString()

function Send-Turn([array]$Messages, [string]$Label, [ref]$LogCheckpoint) {
    $headers = @{ Authorization = "Bearer $apiKey" }
    $bodyObject = @{
        messages = $Messages
        max_tokens = 128
        temperature = 0
        cache_prompt = $true
        stream = $false
    }
    $corpo = [Text.Encoding]::UTF8.GetBytes(($bodyObject | ConvertTo-Json -Compress -Depth 10))
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $resp = Invoke-RestMethod "http://127.0.0.1:$port/v1/chat/completions" `
        -Method Post -Body $corpo -Headers $headers `
        -ContentType 'application/json; charset=utf-8' -TimeoutSec 7200
    $sw.Stop()
    Start-Sleep -Milliseconds 500
    $fullLog = Get-Content -LiteralPath $serverLog -Raw
    $prevLen = $LogCheckpoint.Value
    $delta = if ($fullLog.Length -gt $prevLen) { $fullLog.Substring($prevLen) } else { '' }
    $LogCheckpoint.Value = $fullLog.Length
    $promptEvalLine = ([regex]::Matches($delta, '.*\|\s+prompt eval time =.*') | Select-Object -Last 1).Value
    $evalLine = ([regex]::Matches($delta, '.*\|\s+eval time =.*') | Select-Object -Last 1).Value
    $draftLine = ([regex]::Matches($delta, '.*draft acceptance.*') | Select-Object -Last 1).Value
    $content = [string] $resp.choices[0].message.content
    $reasoning = [string] $resp.choices[0].message.reasoning_content
    $used = $content
    if (-not $used) { $used = $reasoning }
    [pscustomobject]@{
        label = $Label
        wall_ms = [math]::Round($sw.Elapsed.TotalMilliseconds,1)
        prompt_tokens_usage = $resp.usage.prompt_tokens
        completion_tokens_usage = $resp.usage.completion_tokens
        prompt_eval_log_line = $promptEvalLine
        eval_log_line = $evalLine
        draft_acceptance_line = $draftLine
        finish_reason = [string] $resp.choices[0].finish_reason
        reply_text = $used
    }
}

$proc = $null
try {
    Write-Output "[$Tag] avvio server (config bat-pulito)..."
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

    $hwProc = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-File',
        'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\sample_hw.ps1',
        '-Tag', $Tag, '-OutDir', $run, '-IntervalSeconds', '2'
    ) -WindowStyle Hidden -PassThru

    $checkpoint = 0L
    $u1 = 'In una frase, conferma di aver ricevuto il contesto sopra e indica approssimativamente quante righe numerate contiene.'
    $r1 = Send-Turn -Messages @(
        @{ role = 'system'; content = $bigSystem },
        @{ role = 'user'; content = $u1 }
    ) -Label 'r1_system_lungo' -LogCheckpoint ([ref]$checkpoint)
    Write-Output ($r1 | Select-Object label,wall_ms,prompt_tokens_usage,completion_tokens_usage,finish_reason | ConvertTo-Json -Compress)
    Write-Output "  r1 prompt_eval_log: $($r1.prompt_eval_log_line)"

    $u2 = 'Aggiungi un secondo dettaglio informativo, restando molto breve.'
    $r2 = Send-Turn -Messages @(
        @{ role = 'system'; content = $bigSystem },
        @{ role = 'user'; content = $u1 },
        @{ role = 'assistant'; content = $r1.reply_text },
        @{ role = 'user'; content = $u2 }
    ) -Label 'r2_turno2' -LogCheckpoint ([ref]$checkpoint)
    Write-Output ($r2 | Select-Object label,wall_ms,prompt_tokens_usage,completion_tokens_usage,finish_reason | ConvertTo-Json -Compress)
    Write-Output "  r2 prompt_eval_log: $($r2.prompt_eval_log_line)"

    $u3 = 'Chiudi con una terza e ultima osservazione, molto breve.'
    $r3 = Send-Turn -Messages @(
        @{ role = 'system'; content = $bigSystem },
        @{ role = 'user'; content = $u1 },
        @{ role = 'assistant'; content = $r1.reply_text },
        @{ role = 'user'; content = $u2 },
        @{ role = 'assistant'; content = $r2.reply_text },
        @{ role = 'user'; content = $u3 }
    ) -Label 'r3_turno3' -LogCheckpoint ([ref]$checkpoint)
    Write-Output ($r3 | Select-Object label,wall_ms,prompt_tokens_usage,completion_tokens_usage,finish_reason | ConvertTo-Json -Compress)
    Write-Output "  r3 prompt_eval_log: $($r3.prompt_eval_log_line)"

    New-Item -ItemType File -Path (Join-Path $run "$Tag.stop") -Force | Out-Null

    @{
        tag = $Tag
        system_chars = $bigSystem.Length
        r1 = $r1
        r2 = $r2
        r3 = $r3
    } | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
} finally {
    if ($proc) {
        $via = Stop-CodexReuseServer $proc
        Write-Output "shutdown=$via"
    }
}
