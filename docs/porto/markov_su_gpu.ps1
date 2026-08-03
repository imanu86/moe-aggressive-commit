# markov_w1 IN F16: TOGLIERE IL TENSORE CHE CADEVA SU CPU
#
# Il difetto, scritto in ogni log speculativo e mai letto:
#
#   done_getting_tensors: tensor 'markov_w1.weight' (q2_K) cannot be used with
#                         preferred buffer type CUDA0, using CPU instead
#
# ggml-cuda.cu:4691 -- GET_ROWS su CUDA accetta solo F16/F32/BF16/I32/Q1_0/
# Q4_0/Q4_1/Q5_0/Q5_1/Q8_0. Q2_K no. E markov_w1 viene usato proprio con
# ggml_get_rows, dentro il ciclo per posizione della testa di Markov
# (dflash.cpp:255-283), che e' SEQUENZIALE: prev = argmax(col) incatena la
# posizione i+1 alla i.
#
# L'ho introdotto io il 3/8 requantizzando il draft a Q2_K: il quantizzatore
# ha preso anche markov_w1, che non doveva toccare.
#
# LA PROVA CHE E' LUI, dai due punti gia' misurati:
#
#   S2  n_max 5   ciclo 1.354 ms   draft 919 ms
#   T3  n_max 1   ciclo   568 ms   draft 286 ms
#
#   draft(n) = A + B*n   ->   A = 128 ms fissi,  B = 158 ms PER POSIZIONE
#
# I tre strati del draft elaborano tutto il blocco in UNA decodifica batch,
# quindi non scalano col numero di posizioni. L'unica cosa che gira una volta
# per posizione e' il ciclo di Markov. 158 x 5 = 790 degli 919 ms.
#
# LA CURA: requantizzato da C:\ds4-models\DSV4-Flash-DSpark-draft-bf16.gguf con
#   --allow-requantize --tensor-type markov_w1=f16
# markov_w1 passa da q2_K a f16: 63,12 MiB, cioe' +54 MB di VRAM.
#
# TRE BRACCI, controllo appaiato ricalcolato nello stesso momento:
#   U0  senza draft                       (riferimento: S1 dava 231,33)
#   U1  draft riparato, n_max 5           (S2 dava 343,06)
#   U2  draft riparato, n_max 1           (T3 dava 282,12) -> rimisura A e B

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\markov_gpu.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$req     = 'D:\ds4_work\llama_run\spec_vero.req.json'
$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$DRAFT   = 'D:\ds4-models\DSpark-draft-Q2Kfix.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'

Add-Type -Namespace '' -Name CM -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Spegni($p) {
    if ($null -eq $p -or $p.HasExited) { return }
    [void][CM]::FreeConsole()
    if ([CM]::AttachConsole([uint32]$p.Id)) {
        [void][CM]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CM]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][CM]::FreeConsole(); [void][CM]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $p.WaitForExit(30000) | Out-Null
}

$SPEC = @('-md', $DRAFT, '--spec-type', 'draft-dspark', '-ngld', '99', '-cmoed')

$bracci = @(
    @{ n='U0_controllo';   porta=8111; extra=@() }
    @{ n='U1_markov_nmax5'; porta=8112; extra=$SPEC + @('--spec-draft-n-max','5') }
    @{ n='U2_markov_nmax1'; porta=8113; extra=$SPEC + @('--spec-draft-n-max','1') }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\mkv_$($b.n).log"
    $env:LLAMA_ARG_CPU_MOE = '1'

    $argomenti = @('-m', $MODELLO, '-c','4096', '-ngl','99', '-ncmoe','42',
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

    # il cancello: markov_w1 deve NON cadere piu' su CPU
    $caduta = Select-String -LiteralPath $log -Pattern "cannot be used with preferred buffer type" -EA SilentlyContinue
    if ($caduta) { "RICADUTA SU CPU ANCORA PRESENTE: $($caduta[0].Line)" | Out-File $out -Append -Encoding utf8 }
    else         { "nessuna ricaduta su CPU nel caricamento" | Out-File $out -Append -Encoding utf8 }

    $d = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    $s = (Get-Counter -Counter '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "VRAM dedicata $([math]::Round($d.CookedValue/1MB)) condivisa $([math]::Round($s.CookedValue/1MB)) MiB" |
        Out-File $out -Append -Encoding utf8

    & curl.exe -sS --max-time 3600 -X POST "http://127.0.0.1:$($b.porta)/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" `
        -o "D:\ds4_work\llama_run\mkv_$($b.n).resp.json" | Out-Null

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
