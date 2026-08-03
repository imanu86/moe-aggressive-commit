# LA SONDA: LA TESTA DI MARKOV, ACCESA E SPENTA
#
# Stato: il costo del draft segue una retta misurata su due punti,
#
#   draft(n) = 128 ms fissi + 158 ms PER POSIZIONE del blocco
#
# ricavata da S2 (n_max 5, draft 919 ms) e T3 (n_max 1, draft 286 ms).
# I tre strati del draft elaborano tutto il blocco in UNA decodifica batch e
# non scalano col numero di posizioni, quindi quei 158 ms sono qualcosa che
# gira una volta per posizione. Due candidati, entrambi per-posizione:
#
#   il ciclo della testa di Markov   dflash.cpp:255-283
#       upstream (PR ggml-org/llama.cpp#25173) lo cita come overhead noto:
#       "il bias e' calcolato come un piccolo grafo ggml per-passo sullo
#       scheduler del contesto del draft"
#   il campionamento lato host       speculative.cpp:1211
#       5 letture di logit da 129.280 con sincronizzazione
#
# Non separabili da configurazione. Quindi: un cancello in dflash.cpp,
# DSPARK_NO_MARKOV=1, che salta la costruzione della testa. Spento per
# difetto: il binario resta quello di prima se la variabile non c'e'.
#
# ATTENZIONE ALLA LETTURA: senza la testa i draft non sono polarizzati
# (DFlash puro), quindi l'ACCETTAZIONE CALA e i t/s non sono confrontabili
# direttamente. Si confronta il COSTO DEL DRAFT PER CICLO:
#
#   ciclo    = eval_time / n_cicli        n_cicli = generati / lunghezza_media
#   verifica = P + 5T   con P+T dal controllo appaiato e la ripartizione 78/22
#   draft    = ciclo - verifica
#
# Se il draft crolla da ~919 a ~150: la testa di Markov E' la causa, e la
# riparazione indicata dall'upstream (costruire il grafo una volta per blocco)
# vale +51% in sequenza. Se non crolla: e' il campionamento, e serve la
# strada del backend sampling.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\markov_onoff.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$req     = 'D:\ds4_work\llama_run\spec_vero.req.json'
$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$DRAFT   = 'D:\ds4-models\DSpark-draft-Q2Kfix.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'

Add-Type -Namespace '' -Name CO -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Spegni($p) {
    if ($null -eq $p -or $p.HasExited) { return }
    [void][CO]::FreeConsole()
    if ([CO]::AttachConsole([uint32]$p.Id)) {
        [void][CO]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CO]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][CO]::FreeConsole(); [void][CO]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $p.WaitForExit(30000) | Out-Null
}

$SPEC = @('-md', $DRAFT, '--spec-type', 'draft-dspark', '-ngld', '99', '-cmoed', '--spec-draft-n-max', '5')

$bracci = @(
    @{ n='W0_controllo';    porta=8121; extra=@();    markov=$null }
    @{ n='W1_markov_ON';    porta=8122; extra=$SPEC;  markov=$null }
    @{ n='W2_markov_SPENTA'; porta=8123; extra=$SPEC; markov='1'  }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\mko_$($b.n).log"
    $env:LLAMA_ARG_CPU_MOE = '1'

    if ($b.markov) { $env:DSPARK_NO_MARKOV = $b.markov } else { Remove-Item Env:DSPARK_NO_MARKOV -EA SilentlyContinue }
    "DSPARK_NO_MARKOV = $(if ($b.markov) { $b.markov } else { '(non impostata)' })" | Out-File $out -Append -Encoding utf8

    $argomenti = @('-m', $MODELLO, '-c','4096', '-ngl','99', '-ncmoe','42',
                   '-ub','64', '-b','64',
                   '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0') + $b.extra

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
        if (Test-Path $log) { Get-Content $log -Tail 15 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        Spegni $srv; continue
    }

    # cancello: il braccio W2 DEVE dichiarare di aver saltato la testa
    $salto = Select-String -LiteralPath $log -Pattern 'testa di Markov SALTATA' -EA SilentlyContinue
    "cancello: $(if ($salto) { 'testa SALTATA (dichiarato dal binario)' } else { 'testa attiva' })" |
        Out-File $out -Append -Encoding utf8

    $d = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "VRAM dedicata $([math]::Round($d.CookedValue/1MB)) MiB" | Out-File $out -Append -Encoding utf8

    & curl.exe -sS --max-time 3600 -X POST "http://127.0.0.1:$($b.porta)/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" `
        -o "D:\ds4_work\llama_run\mko_$($b.n).resp.json" | Out-Null

    Spegni $srv

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|graphs reused|acceptance' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 45
}

Remove-Item Env:DSPARK_NO_MARKOV -EA SilentlyContinue
'FINE' | Out-File $out -Append -Encoding utf8
