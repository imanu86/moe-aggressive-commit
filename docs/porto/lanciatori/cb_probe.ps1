param(
    [Parameter(Mandatory = $true)][string] $Tag,
    [Parameter(Mandatory = $true)][string] $PlanPath,
    [int] $Port = 8101,
    [string] $ServerPath = 'D:\llama-subtract\build\bin\llama-server.exe',
    [string] $OutDir = 'C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\4b4c0194-0c4f-4f6b-8e2c-cb939d8d7daa\scratchpad\cb_runs'
)

$ErrorActionPreference = 'Stop'

# Windows treats PATH and Path as the same environment variable, while
# Start-Process rejects the duplicated keys inherited by this task (stessa
# correzione di run_porto_hot.ps1).
$portoPath = $env:Path
[Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
[Environment]::SetEnvironmentVariable('Path', $portoPath, 'Process')

$plan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
if (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) {
    throw 'Un processo llama-cli/llama-server e'' gia'' attivo.'
}

$model = 'C:/ds4-models/DS4-0731-IQ2XXS.gguf'
$draft = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$promptPath = 'D:\ds4_work\llama_run\jprompt.txt'
$otd = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$ot = 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped'
$specNmax = if ($plan.spec_nmax) { $plan.spec_nmax } else { 3 }

# ---- ambiente di base = default di run_porto_hot.ps1, profilo forzato a 0 (config campione) ----
$base = [ordered]@{
    LLAMA_CACHE_BOZZA_SLOT = '12'; LLAMA_CACHE_ESPERTI_BATCH = '8'; LLAMA_CACHE_ESPERTI_BATTITO = '45'
    LLAMA_CACHE_ESPERTI_CODA_MAX = '0'; LLAMA_CACHE_ESPERTI_CURA = '0'; LLAMA_CACHE_ESPERTI_SCUDO = '0'
    LLAMA_CACHE_ESPERTI_MASSA = '2'; LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE = '0'; LLAMA_CACHE_ESPERTI_MASSA_CORSIE = '0'
    LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'; LLAMA_CACHE_ESPERTI_LRU = '1'; LLAMA_CACHE_ESPERTI_W = '0'
    LLAMA_CACHE_ESPERTI_SFRATTO_PAR = '1'; LLAMA_CACHE_ESPERTI_SLOT = '473'; LLAMA_CACHE_ESPERTI_FORK = '2'
    LLAMA_CACHE_ESPERTI_FORK_BLOCCHI = '8'; LLAMA_CACHE_ESPERTI_FORK_RIUSA_SLOT = '0'
    LLAMA_CACHE_ESPERTI_FORK_SALTA_COPIA_PARITA = '0'
    LLAMA_ACCEPTMOE = '1'; LLAMA_ACCEPTMOE_ESATTE = '1'; LLAMA_ACCEPTMOE_SOGLIA = '0.75'; LLAMA_ACCEPTMOE_COMPATTA = '1'
    LLAMA_CKPT_CRONO = '0'; LLAMA_SPEC_CONF_ESENTA_POS0 = '1'; LLAMA_SPEC_DRAFT_TOPK = '1'
    PORTO_SPEC_NMAX = "$specNmax"; PORTO_SPEC_CONF_MIN = '0.8'
    LLAMA_MAPPED_IBRIDO = '1'; LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
    LLAMA_OVERLAP_ASYNC = '1'; LLAMA_OVERLAP_K = '2'; LLAMA_OVERLAP_BATCH_MAX = '3'; LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'
    LLAMA_OVERLAP_PIN = '1'; LLAMA_OVERLAP_JOIN_ASYNC = '0'
    LLAMA_KV_RING = '1'; LLAMA_KV_RING_VRAM_TOKEN = '2048'; LLAMA_KV_ROLLBACK_PARZIALE = '1'; LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
    LLAMA_VRAM_A_FASI = '0'; LLAMA_DSV4_INDEXER_FUSO = '0'; LLAMA_DSV4_HC_FUSO = '5'; LLAMA_GRAPH_REUSE_PER_TAGLIA = '1'
    GGML_CUDA_GRAPH_OPT = '0'; GGML_SCHED_PROFILO = '0'; LLAMA_VRAM_ZAVORRA = '0'
}
foreach ($k in $base.Keys) { [Environment]::SetEnvironmentVariable($k, $base[$k]) }
if ($plan.unset_env) {
    foreach ($k in $plan.unset_env) { [Environment]::SetEnvironmentVariable($k, $null) }
}
if ($plan.env) {
    foreach ($p in $plan.env.PSObject.Properties) { [Environment]::SetEnvironmentVariable($p.Name, [string] $p.Value) }
}
# cancello SS10.4.14: mai impostata, nemmeno a 0 -- grafi accesi per costruzione
[Environment]::SetEnvironmentVariable('GGML_CUDA_DISABLE_GRAPHS', $null)

$serverLog = Join-Path $OutDir "$Tag.server.log"
$serverOut = Join-Path $OutDir "$Tag.server.out"
$summaryPath = Join-Path $OutDir "$Tag.summary.json"

$argsServer = @(
    '-m', $model, '-md', $draft, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', "$specNmax", '--spec-draft-ubatch-size', '16', '-otd', $otd,
    '-c', '10000', '-ub', '64', '-np', '1', '-ngl', '99', '-ot', $ot,
    '-t', '7', '--no-mmap', '-lv', '4', '--host', '127.0.0.1', '--port', "$Port",
    '--spec-draft-conf-min', '0.80', '--cache-ram', '8192', '--ctx-checkpoints', '32',
    '-cms', '8192'
)

Add-Type -Namespace '' -Name PortoCbConsole -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Stop-CbServer($Process) {
    if ($null -eq $Process -or $Process.HasExited) { return 'gia-uscito' }
    $via = 'ctrl-c'
    [void][PortoCbConsole]::FreeConsole()
    if ([PortoCbConsole]::AttachConsole([uint32] $Process.Id)) {
        [void][PortoCbConsole]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][PortoCbConsole]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][PortoCbConsole]::FreeConsole()
        [void][PortoCbConsole]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
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

$prompt = [IO.File]::ReadAllText($promptPath, [Text.Encoding]::UTF8)
$results = @()
$proc = $null
$hwProc = $null
$stopSentinel = Join-Path $OutDir "$Tag.stop"
if (Test-Path $stopSentinel) { Remove-Item $stopSentinel -Force -ErrorAction SilentlyContinue }

try {
    $proc = Start-Process -FilePath $ServerPath -ArgumentList $argsServer -WindowStyle Hidden -PassThru `
        -RedirectStandardError $serverLog -RedirectStandardOutput $serverOut

    $ready = $false
    for ($i = 0; $i -lt 150; $i++) {
        Start-Sleep -Seconds 5
        if ($proc.HasExited) {
            Write-Output "SERVER USCITO DURANTE IL CARICAMENTO, exitcode=$($proc.ExitCode)"
            break
        }
        try {
            $health = Invoke-WebRequest "http://127.0.0.1:$Port/health" -TimeoutSec 3 -UseBasicParsing
            if ($health.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
    }
    Write-Output "ready=$ready exited_after_load=$($proc.HasExited)"

    if ($ready) {
        $hwProc = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\sample_hw.ps1',
            '-Tag', $Tag, '-OutDir', $OutDir
        ) -WindowStyle Hidden -PassThru

        foreach ($req in $plan.requests) {
            if ($proc.HasExited) {
                Write-Output "SERVER GIA' USCITO (exitcode=$($proc.ExitCode)) -- salto richiesta $($req.label)"
                $results += [pscustomobject]@{ label = $req.label; skipped = $true; server_exit_code = $proc.ExitCode }
                continue
            }

            $bodyObj = [ordered]@{
                messages = @(@{ role = 'user'; content = $prompt })
                max_tokens = $req.n_predict
                temperature = 0
                cache_prompt = $true
                porto_hot_snapshot = [bool] $req.porto_hot_snapshot
                stream = $false
            }
            if ($req.porto_cb) {
                $cb = [ordered]@{}
                foreach ($p in $req.porto_cb.PSObject.Properties) { $cb[$p.Name] = $p.Value }
                $bodyObj.porto_cb = $cb
            }
            $bodyJson = $bodyObj | ConvertTo-Json -Compress -Depth 6
            $bodyBytes = [Text.Encoding]::UTF8.GetBytes($bodyJson)

            Write-Output "--> invio $($req.label) : $bodyJson"
            $sw = [Diagnostics.Stopwatch]::StartNew()
            $status = $null; $errBody = $null; $response = $null; $exMsg = $null
            try {
                $response = Invoke-RestMethod "http://127.0.0.1:$Port/v1/chat/completions" -Method Post `
                    -Body $bodyBytes -ContentType 'application/json; charset=utf-8' -TimeoutSec 900
                $status = 200
            } catch {
                $resp = $_.Exception.Response
                if ($resp) {
                    $status = [int] $resp.StatusCode
                    try {
                        $rs = $resp.GetResponseStream()
                        $rd = New-Object IO.StreamReader($rs)
                        $errBody = $rd.ReadToEnd()
                    } catch {}
                } else {
                    $status = -1
                    $exMsg = $_.Exception.Message
                }
            }
            $sw.Stop()

            $contentOut = $null; $sha = $null; $chars = $null; $finish = $null; $ptok = $null; $ctok = $null
            if ($status -eq 200 -and $response) {
                $contentOut = [string] $response.choices[0].message.content
                if (-not $contentOut) { $contentOut = [string] $response.choices[0].message.reasoning_content }
                $finish = [string] $response.choices[0].finish_reason
                $ptok = $response.usage.prompt_tokens
                $ctok = $response.usage.completion_tokens
                $outPath = Join-Path $OutDir "$Tag.$($req.label).output.txt"
                $contentOut | Set-Content -LiteralPath $outPath -Encoding UTF8 -NoNewline
                $sha = (Get-FileHash -LiteralPath $outPath -Algorithm SHA256).Hash
                $chars = $contentOut.Length
            }

            $rec = [ordered]@{
                label = $req.label
                porto_cb = $req.porto_cb
                n_predict = $req.n_predict
                porto_hot_snapshot = [bool] $req.porto_hot_snapshot
                http_status = $status
                wall_ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 1)
                err_body = $errBody
                exception = $exMsg
                sha256 = $sha
                content_chars = $chars
                finish_reason = $finish
                prompt_tokens = $ptok
                completion_tokens = $ctok
                server_exited_after = $proc.HasExited
                server_exit_code = if ($proc.HasExited) { $proc.ExitCode } else { $null }
            }
            $results += [pscustomobject] $rec
            Write-Output ($rec | ConvertTo-Json -Compress -Depth 5)
        }
    }
} finally {
    New-Item -ItemType File -Force -Path $stopSentinel | Out-Null
    if ($proc -and -not $proc.HasExited) {
        $via = Stop-CbServer $proc
        Write-Output "shutdown=$via"
    } elseif ($proc) {
        Write-Output "shutdown=gia-uscito-da-solo exitcode=$($proc.ExitCode)"
    }
    if ($hwProc -and -not $hwProc.HasExited) {
        Start-Sleep -Seconds 3
        if (-not $hwProc.HasExited) { Stop-Process -Id $hwProc.Id -Force -ErrorAction SilentlyContinue }
    }
    [pscustomobject]@{ tag = $Tag; plan = $PlanPath; results = $results } |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
}

Write-Output "DONE tag=$Tag serverLog=$serverLog summary=$summaryPath"
