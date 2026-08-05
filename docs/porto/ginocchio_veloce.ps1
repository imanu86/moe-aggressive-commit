# IL GINOCCHIO DELLA MAPPATURA -- cinque punti, corse corte
#
# Il disegno precedente era sbagliato, e la correzione e' dell'utente: 8.000
# token per braccio costano 22 minuti di generazione per un numero che si
# stabilizza molto prima. Dai dati del 4/8 il regime arriva intorno al token
# 600-700 e poi non si muove piu':
#
#     token   100    380    684   1144   1298
#     tg_3s  4,21   6,05   6,32   6,25   6,49
#
# Quindi 1.200 token bastano: 600 di riscaldamento, 600 di finestra utile. E
# con quel budget si misurano CINQUE punti invece di tre, che e' quello che
# serve per trovare un ginocchio invece di dedurlo da due.
#
# COSA SAPPIAMO GIA' (bracci primi, macchina pulita, output sano)
#      0 strati   5,68
#      8          6,11
#     17          6,37  e  6,35
#     22          6,11
# Sembra un massimo intorno a 17, ma fra 8 e 22 ci sono solo tre punti e due
# coincidono. Qui si infittisce: 14, 17, 20, 22, 25.
#
# IL MECCANISMO DA VERIFICARE: a 22 strati restavano 270 MB di RAM libera. La
# memoria mappata e' pinnata e non sfrattabile, quindi ogni strato mappato
# toglie lavoro alla CPU E toglie page cache ai 43-N strati che restano su di
# essa. L'ottimo e' dove i due effetti si pareggiano. Per questo il campionatore
# registra la RAM disponibile: se il massimo cade dove la RAM libera si azzera,
# il meccanismo e' la fame e i banchi in piu' lo curerebbero.
#
# TETTO DI WINDOWS (documentato, non congetturato): cudaHostAlloc e' limitata a
# circa il 50% della RAM di sistema, gestito da Windows e non dal driver NVIDIA.
# Sui nostri dati: 38,1 GiB (60%) riuscito, 51,2 (80%) fallito. Il braccio a 25
# strati chiede 42,2 GiB = 66%: potrebbe non entrare, ed e' un dato anche
# quello -- ma ora su macchina PULITA, non con uno zombie che tiene 38 GiB.
#
# MISURA: mediana di tg_3s nella finestra 600-1200 token. NON il cumulativo,
# che a corsa corta e' dominato dall'avvio freddo.
#
# CANCELLO DI DEGENERAZIONE: a 1.200 token l'HTML non e' finito, quindi il
# conteggio delle sezioni non vale. Resta la ripetizione di riga, che e' il
# segnale che ha smascherato P2 ieri sera.

$ErrorActionPreference = 'Continue'
$out  = 'D:\ds4_work\llama_run\ginocchio5.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\ginocchio5_camp.tsv'
"ora`tbraccio`tpage_reads`tram_disp_MB`tvram_MB`tgpu_pct" | Out-File $camp -Encoding utf8

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$req     = 'D:\ds4_work\llama_run\neuraforge1200.req.json'

Add-Type -Namespace '' -Name CVP -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

$ESP = 'ffn_(gate|up|down)_exps\.weight'
# ordine: i punti alti per primi (macchina piu' fredda), 17 per ultimo che e'
# il campione in carica e va sfidato con la cache piu' calda
# TRE bracci che stringono attorno al picco. G14 e G20 stanno ai due lati dei
# 17 strati che sono il campione in carica (6,37 e 6,35, misurati due volte);
# G17 chiude e serve a validare LO STRUMENTO -- il protocollo a corsa corta e'
# nuovo, e se non riproduce i 6,37 allora e' la misura a essere rotta, non la
# configurazione, e gli altri due numeri non vanno creduti.
$bracci = @(
    @{ n='G20'; porta=8313; ot = "blk\.([0-9]|1[0-9])\.$ESP=CUDA0_Mapped,$ESP=CPU" }
    @{ n='G14'; porta=8314; ot = "blk\.([0-9]|1[0-3])\.$ESP=CUDA0_Mapped,$ESP=CPU" }
    @{ n='G17'; porta=8315; ot = "blk\.([0-9]|1[0-6])\.$ESP=CUDA0_Mapped,$ESP=CPU" }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_$($b.n).server.log"
    "$(Get-Date -Format 'HH:mm:ss')" | Out-File $out -Append -Encoding utf8

    Remove-Item Env:LLAMA_ARG_CPU_MOE -EA SilentlyContinue
    $env:LLAMA_REAP             = '1'
    $env:LLAMA_REAP_PROF        = '1'
    $env:LLAMA_REAP_LOCK        = '1'
    $env:LLAMA_REAP_TOPK        = '1200'
    $env:LLAMA_REAP_PESO        = 'ripida'
    $env:LLAMA_REAP_DECADIMENTO = '1.0'
    $env:LLAMA_REAP_PERIODO     = '12900'

    $argomenti = @('-m', $MODELLO, '-c','10000', '-ngl','99', '-ot', $b.ot,
                   '-ub','64', '-b','64', '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0')

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    $pronto = $false
    for ($i = 0; $i -lt 300; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        $err = (Select-String -LiteralPath $log -Pattern 'cudaHostAlloc|out of memory|failed to allocate' |
                Select-Object -Last 2 | ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' }) -join ' | '
        "NON E' PARTITO: $err" | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Start-Sleep -Seconds 60
        Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
        Start-Sleep -Seconds 30
        continue
    }

    $m0 = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
    $s0 = (Get-Counter -Counter '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue).CounterSamples |
          Sort-Object CookedValue -Descending | Select-Object -First 1
    "caricato: RAM disp $($m0.AvailableMBytes) MB, mappati $([math]::Round($s0.CookedValue/1MB)) MiB" |
        Out-File $out -Append -Encoding utf8

    $risp = "D:\ds4_work\llama_run\g5_$($b.n).resp.json"
    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','3600','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json','--data-binary', "@$req", '-o', $risp)

    while (-not $c.HasExited) {
        Start-Sleep -Seconds 10
        $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
        $g = (nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits) 2>$null
        "{0}`t{1}`t{2}`t{3}`t{4}" -f (Get-Date -Format 'HH:mm:ss'), $b.n,
            $m.PageReadsPerSec, $m.AvailableMBytes, ($g -replace ',\s*', "`t") | Out-File $camp -Append -Encoding utf8
    }

    if (-not $srv.HasExited) {
        [void][CVP]::FreeConsole()
        if ([CVP]::AttachConsole([uint32]$srv.Id)) {
            [void][CVP]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
            [void][CVP]::GenerateConsoleCtrlEvent(0, 0)
            Start-Sleep -Seconds 12
            [void][CVP]::FreeConsole(); [void][CVP]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
        }
        $srv.WaitForExit(150000) | Out-Null
    }
    # il 4/8 un server ha ignorato il CTRL+C ed e' rimasto vivo SETTE ORE
    # tenendosi 38 GiB, falsificando i due bracci successivi
    $resti = Get-Process llama-server -EA SilentlyContinue
    if ($resti) {
        "la chiusura graziosa non ha funzionato, uccido" | Out-File $out -Append -Encoding utf8
        $resti | ForEach-Object { $_.Kill() }; Start-Sleep -Seconds 20
    }
    if (Get-Process llama-server -EA SilentlyContinue) {
        "FERMO IL RUN: macchina non liberabile" | Out-File $out -Append -Encoding utf8; break
    }

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } | Out-File $out -Append -Encoding utf8
    }
    if (Test-Path $risp) {
        $py = @"
import json
d=json.load(open(r'$risp',encoding='utf-8'))
t=d['choices'][0]['message']['content']
r=[x.strip() for x in t.split(chr(10)) if len(x.strip())>20]
rip=max((r.count(x) for x in set(r)), default=0)
print('  degenerazione: %d caratteri, ripetizione max %d -- %s' % (len(t),rip,'SANO' if rip<8 else 'DEGENERATO, IL t/s NON VALE'))
"@
        $py | Out-File "$env:TEMP\g5.py" -Encoding utf8
        (python "$env:TEMP\g5.py") | Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 180
}

Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue
'FINE' | Out-File $out -Append -Encoding utf8
