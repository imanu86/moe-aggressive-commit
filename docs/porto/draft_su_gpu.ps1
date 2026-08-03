# QUANTO COSTA UNA PASSATA DEL DRAFT SU GPU — l'ultimo anello non misurato
#
# Il conto di DSpark rifatto sull'ammortamento misurato (3/8):
#
#   verifica di 5 token      108 + 5x30    =  258 ms
#   draft su GPU dedicata    5 passate     =   50-150 ms   <- QUESTO
#   per token accettato (4,65)                66-88 ms   contro i 138 attuali
#
# La forbice 1,6x - 2,1x dipende tutta da quanto costa una passata del draft.
# E si misura SENZA comprare la seconda scheda: il draft pesa 10.391 MiB e la
# 3060 ne ha 12.288, quindi ci sta da solo. Il modello grande non gira, ma non
# serve -- vogliamo solo il tempo del draft.
#
# ctx piccolo (2048) apposta: la KV del draft deve restare minima, il margine
# e' meno di 2 GB.
#
# ATTENZIONE: il draft e' a sua volta un MoE (256 esperti per blocco, 3
# blocchi). Se non entra tutto in VRAM, -ngl 99 fallisce o travasa, e lo
# vediamo dalla memoria condivisa.

$ErrorActionPreference = 'Continue'
$porta = 8098
$out = 'D:\ds4_work\llama_run\draft_gpu.txt'
$log = 'D:\ds4_work\llama_run\draft_gpu.server.log'
if (Test-Path $out) { Remove-Item $out -Force }

# NIENTE -cmoe qui: vogliamo il draft INTERO in VRAM
if (Test-Path Env:LLAMA_ARG_CPU_MOE) { Remove-Item -LiteralPath Env:LLAMA_ARG_CPU_MOE }

$args = @('-m','C:\ds4-models\DSV4-Flash-DSpark-draft-bf16.gguf',
          '-c','2048','-ngl','99','--port',"$porta",'--host','127.0.0.1',
          '--no-warmup','--reasoning-budget','0')
$srv = Start-Process -FilePath 'D:\llama-b10227\llama-server.exe' -ArgumentList $args -PassThru `
        -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

$pronto = $false
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 5
    if ($srv.HasExited) { "il server e' USCITO (exit $($srv.ExitCode)) -- il draft non entra?" | Out-File $out; break }
    try { Invoke-RestMethod -Uri "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
}

if ($pronto) {
    # VRAM e condivisa a modello caricato
    $d = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    $s = (Get-Counter -Counter '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "VRAM dedicata  $([math]::Round($d.CookedValue/1MB)) MiB" | Out-File $out -Append -Encoding utf8
    "VRAM CONDIVISA $([math]::Round($s.CookedValue/1MB)) MiB  (>0 = non ci sta tutto)" | Out-File $out -Append -Encoding utf8

    $body = @{ model='draft'; max_tokens=200; temperature=0; stream=$false
               messages=@(@{role='user'; content='Write a short paragraph about neural networks.'}) } |
            ConvertTo-Json -Depth 5 -Compress
    $req = 'D:\ds4_work\llama_run\draft_gpu.req.json'
    [IO.File]::WriteAllText($req, $body, [Text.UTF8Encoding]::new($false))
    & curl.exe -sS --max-time 900 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" -o 'D:\ds4_work\llama_run\draft_gpu.resp.json' | Out-Null
}

if (-not $srv.HasExited) {
    Add-Type -Namespace '' -Name C5 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@
    [void][C5]::FreeConsole()
    if ([C5]::AttachConsole([uint32]$srv.Id)) {
        [void][C5]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][C5]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][C5]::FreeConsole(); [void][C5]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $srv.WaitForExit(30000) | Out-Null
}

if (Test-Path $log) {
    Select-String -LiteralPath $log -Pattern 'prompt eval time =|        eval time =' |
        ForEach-Object { $_.Line -replace '.*\| ','' } | Out-File $out -Append -Encoding utf8
}
'FINE' | Out-File $out -Append -Encoding utf8
