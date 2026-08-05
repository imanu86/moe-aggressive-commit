# DOVE SI FERMA LO ZERO-COPY -- sull'IQ2, con il controllo di degenerazione
#
# Perche' questo run, e perche' NON su Q1
# ---------------------------------------
# Il 4/8 sera il braccio P2 (Q1, 30 strati mappati) ha dato 7,63 t/s contro i
# 6,24 del suo metro: +22,3%, distribuzioni quasi disgiunte. Sembrava il
# risultato piu' grande della campagna.
#
# ERA DEGENERAZIONE. Zero sezioni HTML su sei, una riga di ragionamento
# ripetuta 51 volte, 8.000 token bruciati in un ciclo. E il testo ripetuto
# attiva sempre gli stessi esperti -- localita' massima, letture distinte
# minime -- quindi va piu' veloce. Stessa trappola del "record 7,22 t/s" della
# mattina.
#
# Il numero e' stato buttato. Quello che resta di quel run e' solo il metro
# (P0 a 6,24 contro i 6,36 di I0: riproducibile) e il tetto strutturale.
#
# Qui si torna sull'IQ2, il modello vero, dove 17 strati mappati hanno prodotto
# output sani tutto il giorno (25-34 KB, rubrica passata) e la degenerazione
# non si e' mai vista.
#
# IL TETTO CHE LIMITA LA SALITA
# -----------------------------
# La memoria mappata vive nella "memoria GPU condivisa" di Windows, che vale il
# 75% della RAM installata:
#
#     limite condiviso     47,9 GiB   (misurato: Task Manager, 47,9 su 63,9)
#     strato IQ2            1,69 GiB
#     -> massimo mappabile    28 strati
#
# Confermato dal fallimento di P1: cudaHostAlloc di 51,2 GiB rifiutata con 58,9
# GB di RAM libera. Non e' mancanza di memoria, e' il tetto.
#
# I BRACCI
# --------
#   M22   22 strati mappati   37,2 GiB   (gia' dimostrato funzionante in Y2)
#   M26   26 strati           43,9 GiB
#   M17   17 strati           28,7 GiB   <- il metro, e terza ripetizione
#
# M26 potrebbe rompersi, ed e' il punto: 43,9 pinnati piu' 28,7 di page cache
# per i 17 strati rimasti fanno 72,6 GiB su 63,9. La memoria pinnata NON e'
# sfrattabile, quindi a pagare e' la coda su CPU.
#
# ORDINE: le tesi per prime sulla macchina piu' fredda, il metro per ultimo con
# la cache piu' calda. L'ordine lavora CONTRO cio' che si vuole dimostrare.
#
# CANCELLO DI DEGENERAZIONE: alla fine di ogni braccio si contano le sezioni
# HTML e la ripetizione massima di riga. Un braccio degenerato va DICHIARATO,
# non confrontato -- il suo t/s misura la localita' del testo ripetuto, non la
# configurazione.

$ErrorActionPreference = 'Continue'
$out  = 'D:\ds4_work\llama_run\ginocchio.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\ginocchio_camp.tsv'
"ora`tbraccio`tpage_reads`tpages_in`tram_disp_MB`tvram_MB`tgpu_pct`twatt" | Out-File $camp -Encoding utf8

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
    $env:LLAMA_REAP_PERIODO     = '12900'
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
        if (Test-Path $log) { Get-Content $log -Tail 25 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        continue
    }

    $pronto = $false
    for ($i = 0; $i -lt 480; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "NON E' PARTITO (oltre il tetto della condivisa?) -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 25 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        if (-not $srv.HasExited) { $srv.Kill(); $srv.WaitForExit(60000) | Out-Null }
        Start-Sleep -Seconds 120
        continue
    }

    $m0 = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
    $d0 = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
          Sort-Object CookedValue -Descending | Select-Object -First 1
    $s0 = (Get-Counter -Counter '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue).CounterSamples |
          Sort-Object CookedValue -Descending | Select-Object -First 1
    "dopo il caricamento: RAM disp $($m0.AvailableMBytes) MB, VRAM ded $([math]::Round($d0.CookedValue/1MB)) MiB, condivisa $([math]::Round($s0.CookedValue/1MB)) MiB" |
        Out-File $out -Append -Encoding utf8

    $risp = "D:\ds4_work\llama_run\gn_$($b.n).resp.json"
    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','14400','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json',
            '--data-binary', "@$req", '-o', $risp)

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
        $srv.WaitForExit(180000) | Out-Null
    }

    # IL BRACCIO PRECEDENTE DEV'ESSERE DAVVERO MORTO, non "probabilmente".
    # Il 4/8 sera il server di M22 ha ignorato il CTRL+C, WaitForExit e' scaduto,
    # il copione ha proseguito e quel processo e' rimasto vivo per SETTE ORE
    # tenendosi 38 GiB di memoria mappata. Risultato: M26 ha fallito
    # l'allocazione (e l'ho letto come un tetto hardware che non esiste) e M17
    # ha girato in contesa dando 5,32 invece di 6,37. Due verdetti su tre
    # inventati da un processo zombie.
    $resti = Get-Process llama-server -EA SilentlyContinue
    if ($resti) {
        "ATTENZIONE: la chiusura graziosa non ha funzionato, uccido $($resti.Id -join ', ')" |
            Out-File $out -Append -Encoding utf8
        $resti | ForEach-Object { $_.Kill() }
        Start-Sleep -Seconds 20
    }
    $resti = Get-Process llama-server -EA SilentlyContinue
    if ($resti) {
        "FERMO IL RUN: non riesco a liberare la macchina, i bracci seguenti sarebbero falsati" |
            Out-File $out -Append -Encoding utf8
        break
    }
    $mLib = (Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory).AvailableMBytes
    "macchina liberata: RAM disponibile $mLib MB" | Out-File $out -Append -Encoding utf8
    if ($mLib -lt 40000) {
        "ATTENZIONE: solo $mLib MB liberi dopo la chiusura -- qualcosa non ha rilasciato" |
            Out-File $out -Append -Encoding utf8
    }

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|reap: politica' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }

    # CANCELLO DI DEGENERAZIONE -- prima del t/s, non dopo
    if (Test-Path $risp) {
        $py = @"
import json
d=json.load(open(r'$risp',encoding='utf-8'))
t=d['choices'][0]['message']['content']
open(r'$risp'.replace('.resp.json','.output.html'),'w',encoding='utf-8').write(t)
c=sum(1 for k in ('<html','<style','<nav','<form','<script','<footer') if k in t.lower())
r=[x.strip() for x in t.split(chr(10)) if len(x.strip())>20]
rip=max((r.count(x) for x in set(r)), default=0)
print('CANCELLO: %d caratteri, sezioni %d/6, ripetizione max %d -- %s' % (len(t),c,rip,'SANO' if c>=5 and rip<8 else 'DEGENERATO, IL t/s NON VALE'))
"@
        $py | Out-File "$env:TEMP\gate.py" -Encoding utf8
        (python "$env:TEMP\gate.py") | Out-File $out -Append -Encoding utf8
    }

    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue
'FINE' | Out-File $out -Append -Encoding utf8
