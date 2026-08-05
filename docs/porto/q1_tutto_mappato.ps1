# Q1 CON TUTTI I 43 STRATI MAPPATI -- la domanda che blocca due acquisti
#
# L'osservazione e' dell'utente: "ma scusa il Q1 non stava tutto in RAM?".
# Ha ragione, e rende inutile il modello potato che stavo per proporre.
#
# COSA MISURAVA IL TEST Q1 DI STAMATTINA, E COSA NO
# --------------------------------------------------
# I0_q1_senza_gate: 6,36 t/s, IQ1_S-XL-merged (57,3 GiB) INTERAMENTE in RAM,
# fault duri a zero. Da li' e' venuto il verdetto "il tetto e' orchestrazione:
# togliere tutta la memoria non lo sposta".
#
# Ma quel run aveva TUTTI GLI ESPERTI SULLA CPU. Lo zero-copy non esisteva
# ancora: l'ho costruito nel pomeriggio. Quindi misurava la RESIDENZA, non la
# mappatura.
#
# QUELLO CHE NON E' MAI STATO PROVATO
# -----------------------------------
# L'unica leva che ha scalato in tutta la campagna e' mappare gli strati di
# esperti in CUDA0_Mapped, cosi' li calcola la GPU leggendoli sul PCIe:
#
#     8 strati   6,11 t/s
#    17 strati   6,37
#    22 strati   +10,0% su Y1 (a variabile singola)
#
# Sempre in salita, e il ginocchio non l'abbiamo trovato. Non possiamo salire
# sull'IQ2 perche' 43 strati sono 72,7 GiB di memoria pinnata su 63,9 di RAM.
#
# MA SU Q1 CI STANNO. 57,3 GiB totali meno ~7 di backbone che va in VRAM fanno
# ~50 GiB di esperti: entrano, e restano ~14 GB al sistema.
#
# PERCHE' DECIDE DUE SPESE
# ------------------------
# Se mappare scala fino a 43 strati, allora liberare RAM vale, e i 128 GB
# (400 EUR) comprano qualcosa di reale sull'IQ2. Se la curva si e' gia' spenta,
# non si compra niente -- ne' RAM ne' seconda GPU -- perche' lo spazio liberato
# non avrebbe cosa farci.
#
# DUE BRACCI, VARIABILE SINGOLA
# -----------------------------
#   P1  tutti i 43 strati in CUDA0_Mapped     <- la tesi
#   P0  tutti gli esperti su CPU              <- il metro, riproduce I0 (6,36)
#
# Ordine P1-P0: la TESI PER PRIMA sulla macchina piu' fredda, il metro per
# ultimo con la cache piu' calda. L'ordine lavora CONTRO cio' che voglio
# dimostrare.
#
# Niente gate in nessuno dei due: I0 senza gate faceva 6,36 e I1 con gate 6,20,
# quindi il metro giusto e' senza. E con tutto mappato il gate sarebbe comunque
# senza oggetto -- e' gia' tutto pinnato.
#
# ATTENZIONE AL CONFRONTO: questi numeri NON sono paragonabili ai 6,37
# dell'IQ2. E' un'altra quantizzazione e sono pesi vecchi (non il checkpoint
# 0731). Vale solo il confronto P1 contro P0, dentro Q1.

$ErrorActionPreference = 'Continue'
$out  = 'D:\ds4_work\llama_run\q1map.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\q1map_camp.tsv'
"ora`tbraccio`tpage_reads`tpages_in`tram_disp_MB`tvram_MB`tgpu_pct`twatt" | Out-File $camp -Encoding utf8

$MODELLO = 'D:\ds4-models\DeepSeek-V4-Flash-IQ1_S-XL-merged.gguf'
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
    @{ n='P1_q1_tutto_mappato'; porta=8301; ot = "$ESP=CUDA0_Mapped" }
    @{ n='P0_q1_cpu';           porta=8302; ot = "$ESP=CPU" }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_$($b.n).server.log"
    "-ot $($b.ot)   $(Get-Date -Format 'HH:mm:ss')" | Out-File $out -Append -Encoding utf8

    Remove-Item Env:LLAMA_ARG_CPU_MOE -EA SilentlyContinue
    $env:LLAMA_REAP      = '1'
    $env:LLAMA_REAP_PROF = '1'
    Remove-Item Env:LLAMA_REAP_LOCK        -EA SilentlyContinue
    Remove-Item Env:LLAMA_REAP_AMMISSIONE  -EA SilentlyContinue
    Remove-Item Env:LLAMA_REAP_PREFETCH    -EA SilentlyContinue

    $argomenti = @('-m', $MODELLO, '-c','10000', '-ngl','99', '-ot', $b.ot,
                   '-ub','64', '-b','64', '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0')

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.HasExited) {
        "MORTO SUBITO -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 25 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        continue
    }

    # 50 GiB di pinned possono essere lenti da allocare: 40 minuti di pazienza
    $pronto = $false
    for ($i = 0; $i -lt 480; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "NON E' PARTITO (50 GiB pinned non entrano?) -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 30 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        if (-not $srv.HasExited) { $srv.Kill(); $srv.WaitForExit(60000) | Out-Null }
        Start-Sleep -Seconds 120
        continue
    }

    # quanta RAM resta dopo aver pinnato: e' il numero che dice se il braccio
    # sta misurando quel che credo o sta gia' annegando
    $m0 = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
    $d0 = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
          Sort-Object CookedValue -Descending | Select-Object -First 1
    "dopo il caricamento: RAM disponibile $($m0.AvailableMBytes) MB, VRAM dedicata $([math]::Round($d0.CookedValue/1MB)) MiB" |
        Out-File $out -Append -Encoding utf8

    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','14400','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json',
            '--data-binary', "@$req", '-o', "D:\ds4_work\llama_run\q1m_$($b.n).resp.json")

    while (-not $c.HasExited) {
        Start-Sleep -Seconds 15
        $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
        $g = (nvidia-smi --query-gpu=memory.used,utilization.gpu,power.draw --format=csv,noheader,nounits) 2>$null
        "{0}`t{1}`t{2}`t{3}`t{4}`t{5}" -f (Get-Date -Format 'HH:mm:ss'), $b.n,
            $m.PageReadsPerSec, $m.PagesInputPerSec, $m.AvailableMBytes, ($g -replace ',\s*', "`t") |
            Out-File $camp -Append -Encoding utf8
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
        Select-String -LiteralPath $log -Pattern 'eval time =|model buffer size|compute buffer size|mappati host' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

'FINE' | Out-File $out -Append -Encoding utf8
