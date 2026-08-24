# campione_plus_jinja_launcher.ps1 -- REPLICA ESATTA di run_porto_hot.ps1 (config campione,
# stessi env/CLI, stesso SpecNmax=2/SpecConf=0.80 usati per t24_base) con IN PIU' SOLO
# --jinja --chat-template-file <tmpl> --reasoning on --reasoning-preserve.
# Serve a isolare il costo NETTO della modalita' tool sopra il regime migliore (addendum
# coordinatore, 23/8): confronto t24_tool_campione vs t24_base, un solo asse di differenza.

param(
    [Parameter(Mandatory = $true)][string] $Tag,
    [int] $MaxTokens = 512
)

$ErrorActionPreference = 'Stop'

$portoPath = $env:Path
[Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
[Environment]::SetEnvironmentVariable('Path', $portoPath, 'Process')

$bin   = 'D:\llama-subtract\build\bin\llama-server.exe'
$run   = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs'
$model = 'C:/ds4-models/DS4-0731-IQ2XXS.gguf'
$draft = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$tmpl  = 'D:\llama-subtract\models\templates\deepseek-ai-DeepSeek-V4-Flash-0731.jinja'
$promptPath = 'D:\ds4_work\llama_run\jprompt.txt'
$port  = 8100
$otd   = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$ot    = 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped'
$SpecNmax = 2
$SpecConf = '0.80'
$CtxCheckpointMinStep = 8192

New-Item -ItemType Directory -Force -Path $run | Out-Null
if (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) {
    throw 'Un processo llama-cli/llama-server e'' gia'' attivo.'
}

foreach ($v in @('PORTO_SPEC_NMAX','PORTO_SPEC_CONF_MIN','GGML_CUDA_DISABLE_GRAPHS',
                 'GGML_SCHED_PROFILO','GGML_CUDA_GRAPH_STATS')) {
    Remove-Item "Env:\$v" -ErrorAction SilentlyContinue
}

# --- IDENTICO a run_porto_hot.ps1 righe 40-85 ---
$env:LLAMA_CACHE_BOZZA_SLOT = '12'
$env:LLAMA_CACHE_ESPERTI_BATCH = '8'
$env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
$env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
$env:LLAMA_CACHE_ESPERTI_CURA = '0'
$env:LLAMA_CACHE_ESPERTI_SCUDO = '0'
$env:LLAMA_CACHE_ESPERTI_MASSA = '2'
$env:LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE = '0'
$env:LLAMA_CACHE_ESPERTI_MASSA_CORSIE = '0'
$env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'
$env:LLAMA_CACHE_ESPERTI_LRU = '1'
$env:LLAMA_CACHE_ESPERTI_W = '0'
$env:LLAMA_CACHE_ESPERTI_SFRATTO_PAR = '1'
$env:LLAMA_CACHE_ESPERTI_SLOT = '473'
$env:LLAMA_CACHE_ESPERTI_FORK = '2'
$env:LLAMA_CACHE_ESPERTI_FORK_BLOCCHI = '8'
$env:LLAMA_CACHE_ESPERTI_FORK_RIUSA_SLOT = '0'
$env:LLAMA_CACHE_ESPERTI_FORK_SALTA_COPIA_PARITA = '0'
$env:LLAMA_ACCEPTMOE = '1'
$env:LLAMA_ACCEPTMOE_ESATTE = '1'
$env:LLAMA_ACCEPTMOE_SOGLIA = '0.75'
$env:LLAMA_ACCEPTMOE_COMPATTA = '1'
$env:LLAMA_CKPT_CRONO = '0'
$env:LLAMA_SPEC_CONF_ESENTA_POS0 = '1'
$env:LLAMA_SPEC_DRAFT_TOPK = '1'
$env:PORTO_SPEC_NMAX = "$SpecNmax"
$env:PORTO_SPEC_CONF_MIN = '0.8'
$env:LLAMA_MAPPED_IBRIDO = '1'
$env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
$env:LLAMA_OVERLAP_ASYNC = '1'
$env:LLAMA_OVERLAP_K = '2'
$env:LLAMA_OVERLAP_BATCH_MAX = '3'
$env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'
$env:LLAMA_OVERLAP_PIN = '1'
$env:LLAMA_OVERLAP_JOIN_ASYNC = '0'
$env:LLAMA_KV_RING = '1'
$env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
$env:LLAMA_KV_ROLLBACK_PARZIALE = '1'
$env:LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
$env:LLAMA_VRAM_A_FASI = '0'
$env:LLAMA_DSV4_INDEXER_FUSO = '0'
$env:LLAMA_DSV4_HC_FUSO = '5'
$env:LLAMA_GRAPH_REUSE_PER_TAGLIA = '1'
$env:GGML_CUDA_GRAPH_OPT = '0'
$env:GGML_SCHED_PROFILO = '0'   # parita' con t24_base (-Extra 'GGML_SCHED_PROFILO=0')
$env:LLAMA_VRAM_ZAVORRA = '0'
# GGML_CUDA_DISABLE_GRAPHS resta ASSENTE (grafi accesi)

$serverLog = Join-Path $run "$Tag.server.log"
$serverOut = Join-Path $run "$Tag.server.out"
$summaryPath = Join-Path $run "$Tag.summary.json"

# IDENTICO a run_porto_hot.ps1 righe 115-122, PIU' SOLO jinja/template/reasoning in coda
$argsServer = @(
    '-m', $model, '-md', $draft, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', "$SpecNmax", '--spec-draft-ubatch-size', '16', '-otd', $otd,
    '-c', '10000', '-ub', '64', '-np', '1', '-ngl', '99', '-ot', $ot,
    '-t', '7', '--no-mmap', '-lv', '4', '--host', '127.0.0.1', '--port', "$port",
    '--spec-draft-conf-min', $SpecConf, '--cache-ram', '8192', '--ctx-checkpoints', '32',
    '-cms', "$CtxCheckpointMinStep",
    '--jinja', '--chat-template-file', $tmpl, '--reasoning', 'on', '--reasoning-preserve'
)

Add-Type -Namespace '' -Name PortoHotConsole3 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Stop-CampioneJinjaServer($Process) {
    if ($null -eq $Process -or $Process.HasExited) { return 'gia-uscito' }
    $via = 'ctrl-c'
    [void][PortoHotConsole3]::FreeConsole()
    if ([PortoHotConsole3]::AttachConsole([uint32]$Process.Id)) {
        [void][PortoHotConsole3]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][PortoHotConsole3]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][PortoHotConsole3]::FreeConsole()
        [void][PortoHotConsole3]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
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
try {
    Write-Output "[$Tag] avvio server..."
    $proc = Start-Process -FilePath $bin -ArgumentList $argsServer -WindowStyle Hidden -PassThru `
        -RedirectStandardError $serverLog -RedirectStandardOutput $serverOut

    $ready = $false
    for ($i = 0; $i -lt 180; $i++) {
        Start-Sleep -Seconds 5
        if ($proc.HasExited) { break }
        try {
            $health = Invoke-WebRequest "http://127.0.0.1:$port/health" -TimeoutSec 3 -UseBasicParsing
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
        -Method Post -Body $corpo -ContentType 'application/json; charset=utf-8' -TimeoutSec 7200
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
    if ($proc) {
        $via = Stop-CampioneJinjaServer $proc
        Write-Output "shutdown=$via"
    }
}
