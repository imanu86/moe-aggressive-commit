# SPECULAZIONE: IL CONFRONTO A VARIABILE SINGOLA
#
# Il 3/8 abbiamo misurato DSpark col draft quantizzato a 2,89 bpw:
#   -ngl 22, ctx 4096, 300 token, draft Q2_K su GPU
#   -> 376,56 ms/token, 2,66 t/s, accettazione 0,605, lunghezza media 3,97
#
# Ma l'ho confrontato con i 3,73 t/s della spazzata su -ngl, che erano a
# ctx 10000 e 900 token. Non e' un confronto: e' l'errore numero 3 di questa
# sessione, la lunghezza di corsa, fatto un'altra volta.
#
# Questo script fa i due bracci IDENTICI tranne la speculazione, nello stesso
# momento e sulla stessa macchina.
#
#   A  -ngl 22, ctx 4096, 300 token, SENZA speculazione
#   B  -ngl 22, ctx 4096, 300 token, CON draft Q2_K su GPU
#
# Il verdetto e' la differenza fra i due, e nient'altro.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\spec_ab.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$env:LLAMA_ARG_CPU_MOE = '1'
$req = 'D:\ds4_work\llama_run\spec_vero.req.json'

Add-Type -Namespace '' -Name CA -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Spegni($p) {
    if ($p.HasExited) { return }
    [void][CA]::FreeConsole()
    if ([CA]::AttachConsole([uint32]$p.Id)) {
        [void][CA]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CA]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][CA]::FreeConsole(); [void][CA]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $p.WaitForExit(30000) | Out-Null
}

$bracci = @(
    @{ n='A_senza_spec'; porta=8088; extra=@() }
    @{ n='B_con_spec';   porta=8087; extra=@('-md','D:\ds4-models\DSpark-draft-Q2K.gguf','--spec-type','draft-dspark','-ngld','99','--spec-draft-n-max','5') }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\spec_ab_$($b.n).log"
    $args = @('-m','C:\ds4-models\DS4-0731-IQ2XXS.gguf','-c','4096','-ngl','22',
              '-ub','64','-b','64','--port',"$($b.porta)",'--host','127.0.0.1',
              '--no-warmup','--reasoning-budget','0') + $b.extra
    $srv = Start-Process -FilePath 'D:\llama-dspark\build\bin\llama-server.exe' -ArgumentList $args `
            -PassThru -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 500
    if ($srv.PriorityClass -ne 'Normal') { "FERMO: priorita' $($srv.PriorityClass)" | Out-File $out -Append -Encoding utf8; Spegni $srv; continue }

    $ok = $false
    for ($i = 0; $i -lt 120; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $ok = $true; break } catch {}
    }
    if (-not $ok) { "non partito" | Out-File $out -Append -Encoding utf8; continue }

    $d = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "VRAM $([math]::Round($d.CookedValue/1MB)) MiB" | Out-File $out -Append -Encoding utf8

    & curl.exe -sS --max-time 3600 -X POST "http://127.0.0.1:$($b.porta)/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" `
        -o "D:\ds4_work\llama_run\spec_ab_$($b.n).resp.json" | Out-Null

    Spegni $srv

    Select-String -LiteralPath $log -Pattern '        eval time =|acceptance' |
        ForEach-Object { $_.Line -replace '^[0-9.]* *[A-Z] *','' } | Select-Object -Last 2 |
        Out-File $out -Append -Encoding utf8
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 45
}
'FINE' | Out-File $out -Append -Encoding utf8
