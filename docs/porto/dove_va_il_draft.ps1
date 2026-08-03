# DENTRO IL DRAFT: 148 us PER NODO CONTRO 5,3 DEL BERSAGLIO
#
# Stato al 3/8 mattina. Il draft costa ~919 ms a ciclo e il costo NON dipende
# da dove stanno i pesi (936 su GPU / 919 esperti in RAM / 864 tutto in RAM).
# Normalizzato per nodo di grafo:
#
#   bersaglio   34.066 nodi in 180 ms  =   5,3 us/nodo   (costo di lancio)
#   draft        2.074 nodi in 306 ms  = 148,0 us/nodo   28 volte tanto
#
# E per STRATO i due grafi sono equivalenti (792 nodi contro 691), quindi non
# e' complessita' del grafo.
#
# QUESTA MISURA SERVE ALLA SOVRAPPOSIZIONE. Sovrapporre draft e verifica
# nasconde il termine piu' piccolo: oggi il draft e' 2,1 volte la verifica,
# quindi si nasconderebbero i 435 ms sbagliati e il guadagno sarebbe zero
# (233 ms/token contro i 231 del controllo). La sovrapposizione vale il 23%
# SOLO se prima il draft scende. Quindi: prima si capisce se scende.
#
# DUE DOMANDE, TRE BRACCI:
#
#   il costo del draft dipende dal CONTESTO?
#     il draft eredita n_ctx dal bersaglio (4096) e ha un lightning-indexer
#     con top_k=512 su 64 teste. Se il costo scala col contesto, il rimedio
#     e' dare al draft un contesto proprio -- oggi non c'e' bandiera, ma
#     sarebbe una riga in common_base_params_to_speculative.
#       T1  ctx 1024 senza draft   (controllo appaiato)
#       T2  ctx 1024 con draft
#
#   il costo del draft dipende dai TOKEN del blocco?
#     se abbozzare 1 token costa quanto abbozzarne 5, il costo e' tutto fisso
#     per passata: sincronizzazioni e lanci, non calcolo. Allora l'unica leva
#     e' ridurre le TRE passate per ciclo (llama_encode + 2 llama_decode).
#       T3  ctx 4096 con draft, --spec-draft-n-max 1
#
# Riferimenti gia' misurati, stesse condizioni salvo il ctx:
#   S1  ctx 4096 senza draft   231,33 ms/token
#   S2  ctx 4096 con draft     343,06 ms/token   (ciclo 1.354, draft ~919)

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\dove_va_draft.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$req     = 'D:\ds4_work\llama_run\spec_vero.req.json'
$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$DRAFT   = 'D:\ds4-models\DSpark-draft-Q2K.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'

Add-Type -Namespace '' -Name CV -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Spegni($p) {
    if ($null -eq $p -or $p.HasExited) { return }
    [void][CV]::FreeConsole()
    if ([CV]::AttachConsole([uint32]$p.Id)) {
        [void][CV]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CV]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][CV]::FreeConsole(); [void][CV]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $p.WaitForExit(30000) | Out-Null
}

$SPEC = @('-md', $DRAFT, '--spec-type', 'draft-dspark', '-ngld', '99', '-cmoed')

$bracci = @(
    @{ n='T1_ctx1024_controllo'; porta=8101; ctx='1024'; extra=@() }
    @{ n='T2_ctx1024_draft';     porta=8102; ctx='1024'; extra=$SPEC + @('--spec-draft-n-max','5') }
    @{ n='T3_nmax1';             porta=8103; ctx='4096'; extra=$SPEC + @('--spec-draft-n-max','1') }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\dvd_$($b.n).log"
    $env:LLAMA_ARG_CPU_MOE = '1'

    $argomenti = @('-m', $MODELLO, '-c', $b.ctx, '-ngl','99', '-ncmoe','42',
                   '-ub','64', '-b','64',
                   '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0') + $b.extra

    "comando: $($argomenti -join ' ')" | Out-File $out -Append -Encoding utf8

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.PriorityClass -ne 'Normal') {
        "FERMO: priorita' $($srv.PriorityClass), non Normal" | Out-File $out -Append -Encoding utf8
        Spegni $srv; continue
    }

    $pronto = $false
    for ($i = 0; $i -lt 180; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "il server non e' partito -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 12 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        Spegni $srv; continue
    }

    $d = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    $s = (Get-Counter -Counter '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "VRAM dedicata $([math]::Round($d.CookedValue/1MB)) condivisa $([math]::Round($s.CookedValue/1MB)) MiB" |
        Out-File $out -Append -Encoding utf8

    & curl.exe -sS --max-time 3600 -X POST "http://127.0.0.1:$($b.porta)/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" `
        -o "D:\ds4_work\llama_run\dvd_$($b.n).resp.json" | Out-Null

    Spegni $srv

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|graphs reused|acceptance' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 45
}

'FINE' | Out-File $out -Append -Encoding utf8
