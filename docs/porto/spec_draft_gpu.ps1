# DSPARK CON IL DRAFT SU GPU — la configurazione che entra in 12 GB
#
# Il draft non e' caricabile da solo: manca 'dflash.attention.sliding_window_pattern'
# fra i suoi iperparametri, e' progettato per stare accanto al modello grande.
# Quindi il tempo di una sua passata non si isola.
#
# Ma c'e' una configurazione che entra nella scheda attuale e risponde lo stesso:
#
#   modello principale   -ngl 0     tutto CPU    ~750 MiB
#   draft                -ngld 99   tutto GPU    10,4 GB
#
# Il modello grande va lento (2,85 t/s misurati il 2/8) ma non e' quello che
# stiamo misurando. Le tre domande a cui risponde:
#
#   1. la plumbing -ngld/-devd con draft su GPU FUNZIONA? mai provata da nessuno
#   2. che accettazione si ottiene sul binario UFFICIALE? lo 0,907 e' del fork
#   3. il draft costa poco su GPU? se la speculativa guadagna anche con il
#      modello grande su CPU, il draft e' economico
#
# Riferimento senza speculazione, stessa configurazione: 2,85 t/s finale
# (LLAMA_ngl0_130457 del 2/8, 1500 token).

$ErrorActionPreference = 'Continue'
$porta = 8097
$out = 'D:\ds4_work\llama_run\spec_draft_gpu.txt'
$log = 'D:\ds4_work\llama_run\spec_draft_gpu.server.log'
if (Test-Path $out) { Remove-Item $out -Force }
if (Test-Path Env:LLAMA_ARG_CPU_MOE) { Remove-Item -LiteralPath Env:LLAMA_ARG_CPU_MOE }

$args = @('-m','C:\ds4-models\DS4-0731-IQ2XXS.gguf',
          '-md','C:\ds4-models\DSV4-Flash-DSpark-draft-bf16.gguf',
          '--spec-type','draft-dspark',
          '-c','4096','-ngl','0','-ngld','99',
          '--port',"$porta",'--host','127.0.0.1','--no-warmup','--reasoning-budget','0')
"comando: $($args -join ' ')" | Out-File $out -Append -Encoding utf8

$srv = Start-Process -FilePath 'D:\llama-b10227\llama-server.exe' -ArgumentList $args -PassThru `
        -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

$pronto = $false
for ($i = 0; $i -lt 180; $i++) {
    Start-Sleep -Seconds 5
    if ($srv.HasExited) { "il server e' USCITO (exit $($srv.ExitCode))" | Out-File $out -Append -Encoding utf8; break }
    try { Invoke-RestMethod -Uri "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
}

if ($pronto) {
    $d = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    $s = (Get-Counter -Counter '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "VRAM dedicata  $([math]::Round($d.CookedValue/1MB)) MiB  <- il draft ci sta?" | Out-File $out -Append -Encoding utf8
    "VRAM CONDIVISA $([math]::Round($s.CookedValue/1MB)) MiB" | Out-File $out -Append -Encoding utf8

    $body = @{ model='ds4'; max_tokens=300; temperature=0; stream=$false
               messages=@(@{role='user'; content='Create a complete single-file HTML landing page for a cyberpunk AI programming shop. Include CSS, navigation, hero, request form, and a JavaScript confirmation popup. Return only the HTML document.'}) } |
            ConvertTo-Json -Depth 5 -Compress
    $req = 'D:\ds4_work\llama_run\spec_draft_gpu.req.json'
    [IO.File]::WriteAllText($req, $body, [Text.UTF8Encoding]::new($false))
    & curl.exe -sS --max-time 3600 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" -o 'D:\ds4_work\llama_run\spec_draft_gpu.resp.json' | Out-Null
}

if (-not $srv.HasExited) {
    Add-Type -Namespace '' -Name C6 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@
    [void][C6]::FreeConsole()
    if ([C6]::AttachConsole([uint32]$srv.Id)) {
        [void][C6]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][C6]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][C6]::FreeConsole(); [void][C6]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $srv.WaitForExit(30000) | Out-Null
}

if (Test-Path $log) {
    Select-String -LiteralPath $log -Pattern 'eval time =|draft|accept|spec' |
        ForEach-Object { $_.Line -replace '.*\| ','' } | Select-Object -Last 20 |
        Out-File $out -Append -Encoding utf8
}
'FINE' | Out-File $out -Append -Encoding utf8
