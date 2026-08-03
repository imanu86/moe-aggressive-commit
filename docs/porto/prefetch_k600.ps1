# FASE 2: IL PREFETCH PER MASSA, ACCESO CONTRO SPENTO
#
# La politica: ogni ~100 token si prendono i primi K esperti per massa
# (peso 2^-rango, la scelta misurata in MASSA_PER_RANGO.md) e si chiede al
# gestore di memoria di renderli residenti con PrefetchVirtualMemory.
#
# PERCHE' UN PREFETCH E NON UNO SFRATTO. Su Windows non si sostituisce la
# politica del page cache, che e' LRU -- e l'LRU qui e' la peggiore possibile
# (11% di colpi contro il 28% di un insieme caldo statico e il 48% di Belady).
# Ma la si puo' SFRUTTARE: toccare periodicamente cio' che la massa dice
# contare lo rende "usato di recente", e il gestore sfratta il resto. Il
# prefetch diventa il controllo di sfratto, per via indiretta.
#
# COSA MISURA QUESTO RUN, in ordine di importanza:
#   1. i fault duri scendono?      (PageReadsPerSec, campionato in entrambi)
#   2. i crolli della GPU si diradano?  (tg_3s sotto soglia)
#   3. il regime sale?             (mediana tg_3s in 500-800)
#
# Il terzo e' il verdetto ma e' anche il piu' rumoroso: due run identici della
# stessa configurazione hanno dato 6,73 e 6,90 (2,5%). I primi due sono piu'
# sensibili e dicono se il meccanismo FA quello che deve, anche se il guadagno
# finale fosse dentro il rumore.
#
# LIMITE DICHIARATO: questo run e' SENZA drafter. Con il drafter caricato
# l'osservatore non e' affidabile, perche' chiave per numero di strato ricavato
# dal nome e i tre strati del draft (0,1,2) collidono con quelli del bersaglio.
# Va corretto prima di misurare il caso che interessa davvero all'utente.
#
# E se il braccio di controllo NON pagina, il test non e' valido: senza fault
# duri il prefetch non ha niente da togliere. Per questo si campiona anche il
# controllo, invece di darlo per scontato.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\prefetch_k600.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\prefetch_k600_paging.tsv'
"ora`tbraccio`tpage_reads`tpages_in`tram_disp_MB`tvram_MB" | Out-File $camp -Encoding utf8

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$req     = 'D:\ds4_work\llama_run\lunga1500.req.json'

Add-Type -Namespace '' -Name CPF -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

# secondo giro: K piccolo. Il primo (K=2400 = 16,2 GB a passata) ha PEGGIORATO
# i fault duri del 25%. Se anche con 600 esperti (4 GB) non migliora, il
# meccanismo non puo' vincere: un punto solo non e' una curva, due bastano a
# dire la direzione.
$bracci = @(
    @{ n='Q0_controllo'; porta=8183; pf=$null; k='2400' }
    @{ n='Q1_k600';      porta=8184; pf='1';   k='600'  }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log   = "D:\ds4_work\llama_run\LLAMA_ngl99_$($b.n).server.log"
    $mappa = "D:\ds4_work\llama_run\mappa_$($b.n).tsv"

    $env:LLAMA_ARG_CPU_MOE = '1'
    $env:LLAMA_REAP        = '1'
    $env:LLAMA_REAP_PROF   = '1'
    $env:LLAMA_REAP_DUMP   = $mappa
    $env:LLAMA_REAP_TOPK   = $b.k
    if ($b.pf) { $env:LLAMA_REAP_PREFETCH = $b.pf }
    else       { Remove-Item Env:LLAMA_REAP_PREFETCH -EA SilentlyContinue }
    "LLAMA_REAP_PREFETCH = $(if ($b.pf) { $b.pf } else { '(spento)' })  TOPK=$($b.k)" |
        Out-File $out -Append -Encoding utf8

    $argomenti = @('-m', $MODELLO, '-c','10000', '-ngl','99', '-ncmoe','42',
                   '-ub','64', '-b','64', '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0')

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.PriorityClass -ne 'Normal') {
        "FERMO: priorita' $($srv.PriorityClass)" | Out-File $out -Append -Encoding utf8
        continue
    }

    $pronto = $false
    for ($i = 0; $i -lt 200; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "il server non e' partito -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 15 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        continue
    }

    # richiesta staccata, cosi' si campiona il paging MENTRE genera
    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','7200','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json',
            '--data-binary', "@$req",
            '-o', "D:\ds4_work\llama_run\prefetch_$($b.n).resp.json")

    while (-not $c.HasExited) {
        Start-Sleep -Seconds 10
        # classi CIM: nomi inglesi fissi anche su Windows italiano, a differenza
        # dei percorsi Get-Counter che danno -1
        $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
        $v = (nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) 2>$null
        "{0}`t{1}`t{2}`t{3}`t{4}`t{5}" -f (Get-Date -Format 'HH:mm:ss'), $b.n,
            $m.PageReadsPerSec, $m.PagesInputPerSec, $m.AvailableMBytes, $v |
            Out-File $camp -Append -Encoding utf8
    }

    if (-not $srv.HasExited) {
        [void][CPF]::FreeConsole()
        if ([CPF]::AttachConsole([uint32]$srv.Id)) {
            [void][CPF]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
            [void][CPF]::GenerateConsoleCtrlEvent(0, 0)
            Start-Sleep -Seconds 15
            [void][CPF]::FreeConsole(); [void][CPF]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
        }
        $srv.WaitForExit(90000) | Out-Null
    }

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|graphs reused|reap:' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

Remove-Item Env:LLAMA_REAP_PREFETCH -EA SilentlyContinue
'FINE' | Out-File $out -Append -Encoding utf8
