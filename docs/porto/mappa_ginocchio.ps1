# DOVE SI FERMA LO ZERO-COPY: cercare il ginocchio
#
# Stato al 4/8 sera. Due confronti a variabile singola dai bracci Y:
#
#   Y0 -> Y1   aggiungere uno strato in VRAM reale     -12,0%
#   Y1 -> Y2   passare da 17 a 22 strati mappati       +10,0%
#
# Il secondo dice che mappare di piu' RENDE ANCORA a 22 strati. Il ginocchio
# non l'abbiamo trovato: 8 strati davano meta' di 17, 17 meno di 22.
#
# IL BUCO NEL DISEGNO PRECEDENTE: Y2 aveva DUE differenze da Y0 (cinque strati
# mappati in piu' E lo strato in VRAM). La configurazione piu' interessante --
# 22 mappati SENZA lo strato in VRAM -- non e' stata misurata da nessun
# braccio. L'aritmetica la darebbe a 6,15/0,88 = 6,99 t/s, ma un numero
# ottenuto per sottrazione e' proprio quello che il 4/8 mattina ha prodotto i
# 538 ms fantasma della testa di Markov (misurati poi a 2 ms). Si misura.
#
# TRE BRACCI, tutti SENZA strato in VRAM (Y1 lo ha falsificato):
#
#   M22   22 mappati   37,2 GiB pinned   21 strati su CPU (35,5 GiB)
#   M26   26 mappati   43,9 GiB pinned   17 strati su CPU (28,7 GiB)
#   M17   17 mappati   28,7 GiB pinned   26 strati su CPU (43,9 GiB)  <- metro
#
# Perche' M26 dovrebbe rompersi, ed e' il punto: 43,9 pinned + 28,7 di page
# cache per i restanti fanno 72,6 GiB su una macchina da 64. La memoria pinned
# NON e' sfrattabile, quindi a quel punto e' la coda su CPU a pagare, e i suoi
# 17 strati faultano. Se M26 va peggio di M22 abbiamo il ginocchio, e sarebbe
# la prima volta che questa leva ne mostra uno.
#
# ORDINE: le tesi per prime sulla macchina piu' fredda, il metro per ultimo con
# la cache piu' calda. M17 e' anche la TERZA ripetizione della stessa
# configurazione (6,37 il 4/8 mattina con -ub 64, 6,35 il pomeriggio con -ub
# 32): un controllo di riproducibilita' gratis.

$ErrorActionPreference = 'Continue'
$out  = 'D:\ds4_work\llama_run\ginocchio.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\ginocchio_camp.tsv'
"ora`tbraccio`tpage_reads`tram_disp_MB`tvram_MB`tgpu_pct`twatt" | Out-File $camp -Encoding utf8

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$req     = 'D:\ds4_work\llama_run\neuraforge8k.req.json'

Add-Type -Namespace '' -Name CVP -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

$ESP = 'ffn_(gate|up|down)_exps\.weight'
$bracci = @(
    @{ n='M22'; porta=8291; ot = "blk\.([0-9]|1[0-9]|2[01])\.$ESP=CUDA0_Mapped,$ESP=CPU" }
    @{ n='M26'; porta=8292; ot = "blk\.([0-9]|1[0-9]|2[0-5])\.$ESP=CUDA0_Mapped,$ESP=CPU" }
    @{ n='M17'; porta=8293; ot = "blk\.([0-9]|1[0-6])\.$ESP=CUDA0_Mapped,$ESP=CPU" }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_$($b.n).server.log"
    "-ot $($b.ot)   $(Get-Date -Format 'HH:mm:ss')" | Out-File $out -Append -Encoding utf8

    Remove-Item Env:LLAMA_ARG_CPU_MOE -EA SilentlyContinue
    $env:LLAMA_REAP             = '1'
    $env:LLAMA_REAP_PROF        = '1'
    $env:LLAMA_REAP_LOCK        = '1'
    $env:LLAMA_REAP_TOPK        = '1200'
    $env:LLAMA_REAP_PESO        = 'ripida'
    $env:LLAMA_REAP_DECADIMENTO = '1.0'
    Remove-Item Env:LLAMA_REAP_AMMISSIONE -EA SilentlyContinue
    Remove-Item Env:LLAMA_REAP_PREFETCH   -EA SilentlyContinue

    $argomenti = @('-m', $MODELLO, '-c','10000', '-ngl','99', '-ot', $b.ot,
                   '-ub','64', '-b','64', '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0')

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.HasExited) {
        "MORTO SUBITO -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 20 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        continue
    }

    # il caricamento di 44 GiB pinned puo' essere lento: 40 minuti di pazienza
    $pronto = $false
    for ($i = 0; $i -lt 480; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "NON E' PARTITO (pinned troppo? guarda qui sotto) -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 25 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        if (-not $srv.HasExited) { $srv.Kill(); $srv.WaitForExit(60000) | Out-Null }
        Start-Sleep -Seconds 120
        continue
    }

    # quanta RAM resta al sistema dopo aver pinnato: e' il numero che spiega
    # un eventuale crollo di M26
    $m0 = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
    "dopo il caricamento: RAM disponibile $($m0.AvailableMBytes) MB" | Out-File $out -Append -Encoding utf8

    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','14400','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json',
            '--data-binary', "@$req", '-o', "D:\ds4_work\llama_run\gn_$($b.n).resp.json")

    while (-not $c.HasExited) {
        Start-Sleep -Seconds 15
        $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
        $g = (nvidia-smi --query-gpu=memory.used,utilization.gpu,power.draw --format=csv,noheader,nounits) 2>$null
        "{0}`t{1}`t{2}`t{3}`t{4}" -f (Get-Date -Format 'HH:mm:ss'), $b.n,
            $m.PageReadsPerSec, $m.AvailableMBytes, ($g -replace ',\s*', "`t") | Out-File $camp -Append -Encoding utf8
    }

    if (-not $srv.HasExited) {
        [void][CVP]::FreeConsole()
        if ([CVP]::AttachConsole([uint32]$srv.Id)) {
            [void][CVP]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
            [void][CVP]::GenerateConsoleCtrlEvent(0, 0)
            Start-Sleep -Seconds 15
            [void][CVP]::FreeConsole(); [void][CVP]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
        }
        $srv.WaitForExit(120000) | Out-Null
    }

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|reap: politica|mappati host' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue
'FINE' | Out-File $out -Append -Encoding utf8
