param(
    [int] $Port = 8099,
    [ValidateSet(1024, 2048, 4096, 8192, 12288)]
    [int] $StartBatch = 12288,
    [ValidateSet(0, 1)]
    [int] $BlockSparse = 1,
    [ValidateSet(0, 5)]
    [int] $HcFused = 5,
    [string] $RunLabel = 'pin',
    [ValidateSet(0, 1)]
    [int] $BlockDenseCpu = 0,
    [int] $Packetizer = -1,
    [int] $PrefixChars = 0,
    [int] $Context = 150000,
    [int] $MaxTokens = 64,
    [int] $SpecNmax = 2,
    [string] $SpecConf = '0.8',
    [int] $Repliche = 1,
    [int] $CtxCheckpointMinStep = 32,
    [string] $ServerPath = 'D:\llama-overlap\build\bin\llama-server.exe',
    [int] $ReasoningBudgetTokens = -1,
    [string] $PortoCbForkDownTardi = '',
    [ValidateSet(0, 1)]
    [int] $GraphReusePerTaglia = 1,
    [string] $KvPad = '',
    [string] $KvRingBattito = '',
    [int] $NProbs = 0,
    [string] $KvRingVramLid = '',
    [string] $KvRingVramCsa = '',
    [int] $CacheEspertiSlot = 473
)

# [P2-RING-CONF, esecutore 28/8] DUE aggiunte dichiarate rispetto a p2_ring.ps1:
# 1) il parametro -SpecConf, passato a --spec-draft-conf-min al posto della costante '0.8'
#    cablata. A '0.8' (il default qui sotto) e' testualmente identico al comportamento
#    precedente di p2_ring.ps1. Serve per lanciare la Fase 2 con conf_min=0.70 (il campione
#    promosso in Fase 1b) invece del vecchio 0.80.
# 2) telemetria hw/cpu (RUNBOOK SS6.8): lancio di sample_hw.ps1 subito dopo /health OK,
#    stesso pattern gia' usato da cb_probe.ps1 -- p1_nudo.ps1/p2_ring.ps1 non la includevano
#    (lacuna dichiarata nella Fase 1 di questo turno, corretta qui).
# Tutto il resto (LID/CSA per-deposito, CacheEspertiSlot) e' invariato.

$ErrorActionPreference = 'Stop'

$serverBin = $ServerPath
$runDir = 'D:\ds4_work\llama_run'
$model = 'C:/ds4-models/DS4-0731-IQ2XXS.gguf'
$draft = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$promptPath = Join-Path $runDir 'jprompt102k.txt'
$otTarget = if ($BlockDenseCpu) {
    'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,blk\..*=CPU'
} else {
    'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped'
}
$otDraft = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$summaryFlavor = if ($BlockSparse) { 'bsparse' } else { 'densefa' }
$summary = Join-Path $runDir "sota100k_ctx150k_${summaryFlavor}_stage_hc${HcFused}_${RunLabel}.summary.txt"

function Note([string] $Text) {
    $Text | Tee-Object -FilePath $summary -Append
}

Add-Type -Namespace '' -Name Sota100kConsoleP2Conf -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Stop-Clean($Process) {
    if ($null -eq $Process -or $Process.HasExited) { return 'already-exited' }
    $how = 'ctrl-c'
    [void][Sota100kConsoleP2Conf]::FreeConsole()
    if ([Sota100kConsoleP2Conf]::AttachConsole([uint32] $Process.Id)) {
        [void][Sota100kConsoleP2Conf]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][Sota100kConsoleP2Conf]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][Sota100kConsoleP2Conf]::FreeConsole()
        [void][Sota100kConsoleP2Conf]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    } else {
        $how = 'AttachConsole-failed'
    }
    $Process.WaitForExit(60000) | Out-Null
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        $how += ' -> Stop-Process fallback'
    }
    return $how
}

function Set-SotaEnvironment {
    $env:LLAMA_MAPPED_IBRIDO = '1'
    $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
    $env:LLAMA_CACHE_ESPERTI_SLOT = '473'
    $env:LLAMA_CACHE_BOZZA_SLOT = '12'
    $env:LLAMA_CACHE_ESPERTI_BATCH = '8'
    $env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
    $env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
    $env:LLAMA_CACHE_ESPERTI_CURA = '0'
    $env:LLAMA_CACHE_ESPERTI_SCUDO = '0'
    $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'
    $env:LLAMA_CACHE_ESPERTI_LRU = '1'
    $env:LLAMA_CACHE_ESPERTI_W = '0'
    $env:LLAMA_CACHE_ESPERTI_SFRATTO_PAR = '1'
    $env:LLAMA_CACHE_ESPERTI_FORK = '2'
    $env:LLAMA_CACHE_ESPERTI_FORK_BLOCCHI = '8'
    $env:LLAMA_CACHE_ESPERTI_FORK_RIUSA_SLOT = '0'
    $env:LLAMA_CACHE_ESPERTI_FORK_SALTA_COPIA_PARITA = '0'
    $env:LLAMA_CACHE_ESPERTI_MASSA = '2'
    $env:LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE = '0'
    $env:LLAMA_CACHE_ESPERTI_MASSA_CORSIE = '0'
    $env:LLAMA_CACHE_ESPERTI_DMA = '0'

    $env:LLAMA_SPEC_DRAFT_TOPK = '1'
    $env:LLAMA_SPEC_CONF_ESENTA_POS0 = '1'
    $env:LLAMA_ACCEPTMOE = '1'
    $env:LLAMA_ACCEPTMOE_ESATTE = '1'
    $env:LLAMA_ACCEPTMOE_SOGLIA = '0.75'
    $env:LLAMA_ACCEPTMOE_COMPATTA = '1'
    $env:LLAMA_GRAPH_REUSE_PER_TAGLIA = "$GraphReusePerTaglia"

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
    if ($KvPad -ne '') { $env:LLAMA_KV_PAD = "$KvPad" } else { [Environment]::SetEnvironmentVariable('LLAMA_KV_PAD', $null) }
    if ($KvRingBattito -ne '') { $env:LLAMA_KV_RING_BATTITO = "$KvRingBattito" } else { [Environment]::SetEnvironmentVariable('LLAMA_KV_RING_BATTITO', $null) }
    # [P2-RING, esecutore 24/8] NOTE_IMPLEMENTAZIONE.md S17.3: knob per-deposito, atoi/strtoull
    # A VALORE, assente = fallback al condiviso LLAMA_KV_RING_VRAM_TOKEN (comportamento
    # invariato rispetto allo script canonico). '0' e' un valore legittimo (spegne il caldo,
    # fino al pavimento di 256 righe, S17.5) e va distinto da "non impostata".
    if ($KvRingVramLid -ne '') { $env:LLAMA_KV_RING_VRAM_LID = "$KvRingVramLid" } else { [Environment]::SetEnvironmentVariable('LLAMA_KV_RING_VRAM_LID', $null) }
    if ($KvRingVramCsa -ne '') { $env:LLAMA_KV_RING_VRAM_CSA = "$KvRingVramCsa" } else { [Environment]::SetEnvironmentVariable('LLAMA_KV_RING_VRAM_CSA', $null) }
    $env:LLAMA_VRAM_A_FASI = '2'
    $env:LLAMA_VRAM_A_FASI_UB = '64'
    $env:LLAMA_VRAM_A_FASI_CALDO = '0'
    $env:LLAMA_VRAM_A_FASI_MIN = '0'
    $env:LLAMA_VRAM_A_FASI_MARGINE = '0'

    $env:LLAMA_DSV4_INDEXER_FUSO = '1'
    $env:LLAMA_DSV4_HC_FUSO = "$HcFused"
    $env:LLAMA_DSV4_MASK_F16_INPUT = '0'
    $env:LLAMA_CUDA_FATTN_BLOCK_SPARSE = "$BlockSparse"
    $env:LLAMA_DSV4_PREFILL_LAYER_STAGING = '1'
    $env:LLAMA_DSV4_PREFILL_LAYER_EXECUTOR = '0'
    $env:LLAMA_DSV4_PREFILL_LAYER_SPLIT = '0'
    $env:LLAMA_DSV4_PREFILL_FFN_SUPEROP = '0'
    $packetizerActive = if ($Packetizer -ge 0) { $Packetizer } else { $BlockDenseCpu }
    $env:GGML_SCHED_OFFLOAD_PACCHETTI = "$packetizerActive"
    $env:GGML_CUDA_GRAPH_OPT = '0'
    $env:GGML_CUDA_GRAPH_STATS = '1'
    $env:GGML_SCHED_PROFILO = '1'
    $env:LLAMA_CKPT_CRONO = '0'
    $env:LLAMA_VRAM_ZAVORRA = '0'
    $env:LLAMA_MMQ_X_IDS = '64'
    [Environment]::SetEnvironmentVariable('LLAMA_DSV4_PREFILL_FATTN_Q_TILE', $null)
    # [P2-RING] override DOPO il resto: -CacheEspertiSlot default 473 = comportamento identico
    # allo script canonico (diff di una riga, come da nota turno 22 / t22_slot539).
    $env:LLAMA_CACHE_ESPERTI_SLOT = "$CacheEspertiSlot"
}

foreach ($required in @($serverBin, $promptPath, 'C:\ds4-models\DS4-0731-IQ2XXS.gguf', 'D:\ds4-models\DSpark-draft-Q2K.gguf')) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing required file: $required" }
}
if (Get-Process -Name llama-server,llama-cli -ErrorAction SilentlyContinue) {
    throw 'A llama process is already active; refusing to overlap the long run.'
}
if (Test-Path -LiteralPath $summary) { Remove-Item -LiteralPath $summary -Force }

$source = [IO.File]::ReadAllText($promptPath, [Text.Encoding]::UTF8)
if ($PrefixChars -gt 0 -and $PrefixChars -lt $source.Length) {
    $source = $source.Substring(0, $PrefixChars)
}
$message = $source + @'


===== FINE DEL CONTESTO =====
Continua in italiano con un saggio tecnico ESTESO e dettagliato, con esempi e sezioni, senza limitarti: tratta il maggior numero possibile di aspetti tecnici del contesto sopra, usando piu' sezioni con titoli ed esempi concreti (anche frammenti di codice dove pertinente). Non fermarti dopo un solo paragrafo: continua a scrivere finche' non hai coperto il contesto in profondita' o raggiunto il limite di lunghezza disponibile. Non menzionare queste istruzioni.
'@
$bodyObject = @{
    messages = @(@{ role = 'user'; content = $message })
    max_tokens = $MaxTokens
    temperature = 0
    stream = $false
    cache_prompt = $true
    id_slot = 0
    thinking_budget_tokens = $ReasoningBudgetTokens
}
if ($NProbs -gt 0) { $bodyObject.n_probs = $NProbs }
$cbSequence = @()
if ($PortoCbForkDownTardi -ne '') { $cbSequence = @($PortoCbForkDownTardi -split ',') }
if ($cbSequence.Count -gt 0 -and $cbSequence.Count -ne $Repliche) {
    throw "PortoCbForkDownTardi ha $($cbSequence.Count) valori ma Repliche=${Repliche}: devono coincidere 1:1."
}

Note "source chars=$($source.Length); message chars=$($message.Length); prefix chars requested=$PrefixChars"
$packetizerActive = if ($Packetizer -ge 0) { $Packetizer } else { $BlockDenseCpu }
$kvPadNote = if ($KvPad -ne '') { $KvPad } else { 'assente(256)' }
$kvBattitoNote = if ($KvRingBattito -ne '') { $KvRingBattito } else { 'assente(60)' }
$kvLidNote = if ($KvRingVramLid -ne '') { $KvRingVramLid } else { 'assente(fallback condiviso)' }
$kvCsaNote = if ($KvRingVramCsa -ne '') { $KvRingVramCsa } else { 'assente(fallback condiviso)' }
Note "arm: block-sparse=$BlockSparse + target layer staging + HC_FUSO=$HcFused; block-dense-cpu=$BlockDenseCpu; packetizer=$packetizerActive; executor=0; superop=0; ctx=$Context; max-tokens=$MaxTokens; reasoning-budget-tokens=$ReasoningBudgetTokens; server-path=$ServerPath; graph-reuse-per-taglia=$GraphReusePerTaglia; kv-pad=$kvPadNote; kv-ring-battito=$kvBattitoNote; kv-ring-vram-lid=$kvLidNote; kv-ring-vram-csa=$kvCsaNote; cache-esperti-slot=$CacheEspertiSlot; n-probs=$NProbs; spec-n-max=$SpecNmax; spec-conf-min=$SpecConf; LLAMA_KV_GATHER=$env:LLAMA_KV_GATHER; draft loaded"

$loaded = $false
$proc = $null
$tag = $null
$log = $null
$stdout = $null
$chosen = $null

$shapes = @(
    @{ Batch = 12288; UBatch = 12288 },
    @{ Batch = 8192; UBatch = 8192 },
    @{ Batch = 4096; UBatch = 4096 },
    @{ Batch = 2048; UBatch = 2048 },
    @{ Batch = 1024; UBatch = 1024 }
) | Where-Object { $_.Batch -le $StartBatch }

foreach ($shape in $shapes) {
    Set-SotaEnvironment
    $env:LLAMA_DSV4_PREFILL_MOE_UB = "$($shape.UBatch)"
    $sparseTag = if ($BlockSparse) { 'bsparse' } else { 'densefa' }
    $tag = "sota_ctx${Context}_${sparseTag}_stage_hc${HcFused}_${RunLabel}_f2_b$($shape.Batch)"
    $log = Join-Path $runDir "$tag.server.log"
    $stdout = Join-Path $runDir "$tag.server.out"
    foreach ($path in @($log, $stdout, (Join-Path $runDir "$tag.response.json"), (Join-Path $runDir "$tag.output.txt"))) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
    }
    Note "[$([DateTime]::Now.ToString('HH:mm:ss'))] loading $tag"
    $serverArgs = @(
        '-m', $model, '-md', $draft, '--spec-type', 'draft-dspark', '--fit', 'off',
        '-ngld', '99', '--spec-draft-n-max', "$SpecNmax", '--spec-draft-conf-min', "$SpecConf",
        '--spec-draft-ubatch-size', '16', '-otd', $otDraft,
        '-c', "$Context", '-b', "$($shape.Batch)", '-ub', "$($shape.UBatch)", '-np', '1',
        '-ngl', '99', '-ot', $otTarget,
        '-t', '7', '--no-mmap', '--no-host', '--cache-ram', '0',
        '-cms', "$CtxCheckpointMinStep",
        '-lv', '4', '--host', '127.0.0.1', '--port', "$Port"
    )
    $proc = Start-Process -FilePath $serverBin -ArgumentList $serverArgs -WindowStyle Hidden -PassThru `
        -RedirectStandardError $log -RedirectStandardOutput $stdout

    for ($i = 0; $i -lt 120; $i++) {
        Start-Sleep -Seconds 15
        if ($proc.HasExited) { break }
        try {
            if ((Invoke-WebRequest "http://127.0.0.1:$Port/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) {
                $loaded = $true
                break
            }
        } catch {}
    }
    if ($loaded) {
        $chosen = $shape
        $free = (nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -replace '\s',''
        Note "loaded $tag; free VRAM=$free MiB"
        $hwProc = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\sample_hw.ps1',
            '-Tag', $tag, '-OutDir', $runDir
        ) -WindowStyle Hidden -PassThru
        Note "telemetria avviata: sample_hw.ps1 pid=$($hwProc.Id) -> $runDir\$tag.hw.csv / .cpu.csv"
        break
    }

    Note "load failed for $tag"
    Select-String -LiteralPath $log -Pattern 'out of memory|CUDA error|error loading|failed' -ErrorAction SilentlyContinue |
        Select-Object -Last 4 | ForEach-Object { Note ('  ' + $_.Line) }
    if (-not $proc.HasExited) { Note ('shutdown: ' + (Stop-Clean $proc)) }
}

if (-not $loaded) {
    Note 'NO SHAPE LOADED; request not started.'
    exit 2
}

function Last-Match([string] $Pattern) {
    $m = Select-String -LiteralPath $log -Pattern $Pattern -ErrorAction SilentlyContinue | Select-Object -Last 1
    if ($m) { return $m.Matches[0].Groups[1].Value }
    return '-'
}

$cbNote = if ($cbSequence.Count -gt 0) { "porto_cb per replica = $($cbSequence -join '/')" } else { 'nessun porto_cb, mai (difetto)' }
Note "repliche richieste: $Repliche (ciclo nello stesso processo, stesso corpo base byte-per-byte tranne porto_cb; id_slot=0, cache_prompt=true; $cbNote)"
for ($r = 1; $r -le $Repliche; $r++) {
    $tagR = "${tag}_q$r"
    $responsePath = Join-Path $runDir "$tagR.response.json"
    $outputPath = Join-Path $runDir "$tagR.output.txt"
    $reqObject = $bodyObject.Clone()
    $cbToken = if ($cbSequence.Count -ge $r) { $cbSequence[$r-1].Trim() } else { '' }
    if ($cbToken -eq '0' -or $cbToken -eq '1') {
        $reqObject.porto_cb = @{ fork_down_tardi = [int]$cbToken }
    } elseif ($cbToken -ne '' -and $cbToken -ne '-') {
        throw "valore PortoCbForkDownTardi non valido alla posizione $r : '$cbToken' (ammessi '', '-', '0', '1')"
    }
    $cbDesc = if ($reqObject.ContainsKey('porto_cb')) { "fork_down_tardi=$($reqObject.porto_cb.fork_down_tardi)" } else { 'nessuno (leva invariata)' }
    $body = [Text.Encoding]::UTF8.GetBytes(($reqObject | ConvertTo-Json -Compress -Depth 5))
    $start = Get-Date
    Note "[$([DateTime]::Now.ToString('HH:mm:ss'))] r=$r/$Repliche request start; porto_cb=$cbDesc"
    try {
        $response = Invoke-RestMethod "http://127.0.0.1:$Port/v1/chat/completions" -Method Post `
            -Body $body -ContentType 'application/json; charset=utf-8' -TimeoutSec 21600
        $response | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $responsePath -Encoding UTF8
        $text = [string] $response.choices[0].message.content
        if (-not $text) { $text = [string] $response.choices[0].message.reasoning_content }
        $text | Set-Content -LiteralPath $outputPath -Encoding UTF8
        Note "r=$r request complete in $([math]::Round(((Get-Date)-$start).TotalMinutes,2)) min"
        Note "r=$r usage prompt=$($response.usage.prompt_tokens), completion=$($response.usage.completion_tokens), total=$($response.usage.total_tokens)"
        Note "r=$r timings prompt_n=$($response.timings.prompt_n), prefill=$($response.timings.prompt_per_second) t/s, decode=$($response.timings.predicted_per_second) t/s"
        Note "r=$r finish=$($response.choices[0].finish_reason); output chars=$($text.Length)"
        if (Test-Path -LiteralPath $outputPath) {
            Note "r=$r output sha256=$((Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash)"
        }
    } catch {
        Note "r=$r REQUEST FAILED: $($_.Exception.Message)"
    }
    Note "r=$r server prompt tokens=$(Last-Match 'task\.n_tokens = ([0-9]+)')"
    Note "r=$r server prefill=$(Last-Match 'prompt eval time =.*?([0-9.]+) tokens per second') t/s"
    Note "r=$r server decode=$(Last-Match '\|        eval time =.*?([0-9.]+) tokens per second') t/s"
    Note "r=$r p1=$(Last-Match 'draft acceptance = ([0-9.]+)')"
}
Note 'kv-ring profile tail:'
Select-String -LiteralPath $log -Pattern 'kv-ring-profile|kv-ring-vram|KV ring resident allocated' -ErrorAction SilentlyContinue |
    Select-Object -Last 10 | ForEach-Object { Note ('  ' + $_.Line) }
Note 'gather rows tail:'
Select-String -LiteralPath $log -Pattern 'bytes_h2d_per_token|rows_per_token' -ErrorAction SilentlyContinue |
    Select-Object -Last 10 | ForEach-Object { Note ('  ' + $_.Line) }
Note 'phase/fusion tail:'
Select-String -LiteralPath $log -Pattern 'vram[_-]a[_-]fasi|llama_context::vram_a_fasi|DSV4 HC|hc_fus' -ErrorAction SilentlyContinue |
    Select-Object -Last 20 | ForEach-Object { Note ('  ' + $_.Line) }
Note 'error scan:'
Select-String -LiteralPath $log -Pattern 'CUDA error|NaN|diverg|out of memory|failed' -ErrorAction SilentlyContinue |
    Select-Object -Last 20 | ForEach-Object { Note ('  ' + $_.Line) }

Note ('shutdown: ' + (Stop-Clean $proc))
Note "DONE tag=$tag batch=$($chosen.Batch) ubatch=$($chosen.UBatch)"
