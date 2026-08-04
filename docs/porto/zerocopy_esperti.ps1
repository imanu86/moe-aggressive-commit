# ZERO-COPY: gli esperti calcolati dalla GPU leggendoli dalla RAM host
#
# Idea dell'utente. Il tetto della campagna e' ~6,5 t/s ed e' ORCHESTRAZIONE:
# quattro leve sulla memoria (spostare i pesi, eliminare il paging con Q1,
# anticiparlo col prefetch, negarlo con l'ammissione) non l'hanno mosso.
# Questa e' diversa: non riorganizza la memoria, TOGLIE LAVORO ALLA CPU.
#
# Oggi i 43 strati di esperti stanno in RAM e li calcola la CPU, mentre la GPU
# aspetta. Con CUDA0_Mapped (cudaHostAllocMapped + cudaHostGetDevicePointer, e
# is_host = false) i kernel CUDA leggono quei pesi dove sono, sul PCIe.
#
# ATTESA MISURATA su questa stessa 3060 (.microbench/zerocopy, era DwarfStar):
#   VRAM residente      0,079 ms/esperto  ->  14,9 ms/token
#   ZERO-COPY (questo)  0,274             ->  51,6
#   copia pinned->VRAM  0,403             ->  75,9
#
# VINCOLO FISICO: la memoria mappata e' PINNED, e 72,56 GiB di esperti non si
# bloccano su una macchina da 64. Si mappa un sottoinsieme di strati, e i
# rimanenti restano su CPU -- ma il pinned ruba spazio alla page cache che
# serve a quelli, quindi il compromesso e' reale e va misurato, non assunto.
#
# TRE BRACCI:
#   W0  controllo: tutti gli esperti su CPU (la configurazione attuale)
#   W1  17 strati mappati (28,7 GiB pinned, 39,5% del calcolo esperti su GPU)
#   W2   8 strati mappati (13,5 GiB pinned, 18,6%)
#
# La taglia non e' prudenziale ma presa dal ledger: sul 3060 la campagna ha
# gia' dimostrato 21,85 GB pinned (coffee@k83). Restare a 12 strati sarebbe
# stato timore, non misura.
#
# Il braccio a 8 serve da controprova: se il vantaggio scala col numero di
# strati e' il meccanismo; se non scala e' rumore.
#
# Il gate resta ACCESO in tutti e tre, perche' e' la configurazione buona e non
# e' la variabile in esame.

$ErrorActionPreference = 'Continue'
$out  = 'D:\ds4_work\llama_run\zerocopy.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\zerocopy_paging.tsv'
"ora`tbraccio`tpage_reads`tpages_in`tram_disp_MB`tvram_MB" | Out-File $camp -Encoding utf8

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$req     = 'D:\ds4_work\llama_run\neuraforge8k.req.json'

Add-Type -Namespace '' -Name CZC -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

$ESP = 'ffn_(gate|up|down)_exps\.weight'
# ORDINE: lo ZERO-COPY va PER PRIMO, di proposito.
# La macchina e' appena stata riavviata, quindi il primo braccio paga il
# caricamento completo degli 80 GB da disco e parte handicappato. Mettendoci
# la tesi da dimostrare, se vince lo fa NONOSTANTE lo svantaggio -- che e' la
# forma conservativa. Il contrario (controllo per primo) la favorirebbe.
$bracci = @(
    @{ n='W1_17strati';  porta=8262; ot = "blk\.([0-9]|1[0-6])\.$ESP=CUDA0_Mapped,$ESP=CPU" }
    @{ n='W0_controllo'; porta=8261; ot = "$ESP=CPU" }
    @{ n='W2_8strati';   porta=8263; ot = "blk\.[0-7]\.$ESP=CUDA0_Mapped,$ESP=CPU" }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_$($b.n).server.log"
    "-ot $($b.ot)   $(Get-Date -Format 'HH:mm:ss')" | Out-File $out -Append -Encoding utf8

    # niente LLAMA_ARG_CPU_MOE ne' -ncmoe: il piazzamento lo decide -ot, e due
    # meccanismi sullo stesso tensore sarebbero una variabile nascosta
    Remove-Item Env:LLAMA_ARG_CPU_MOE -EA SilentlyContinue
    $env:LLAMA_REAP             = '1'
    $env:LLAMA_REAP_PROF        = '1'
    $env:LLAMA_REAP_LOCK        = '1'
    $env:LLAMA_REAP_TOPK        = '1200'
    $env:LLAMA_REAP_PESO        = 'ripida'
    $env:LLAMA_REAP_DECADIMENTO = '1.0'
    Remove-Item Env:LLAMA_REAP_AMMISSIONE -EA SilentlyContinue
    Remove-Item Env:LLAMA_REAP_PREFETCH   -EA SilentlyContinue
    Remove-Item Env:LLAMA_REAP_PERIODO    -EA SilentlyContinue

    $argomenti = @('-m', $MODELLO, '-c','10000', '-ngl','99', '-ot', $b.ot,
                   '-ub','64', '-b','64', '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0')

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.PriorityClass -ne 'Normal') {
        "FERMO: priorita' $($srv.PriorityClass)" | Out-File $out -Append -Encoding utf8; continue
    }

    $pronto = $false
    for ($i = 0; $i -lt 300; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "IL SERVER NON E' PARTITO (la memoria pinned potrebbe non bastare) -- ultime righe:" |
            Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 25 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        continue
    }

    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','14400','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json',
            '--data-binary', "@$req", '-o', "D:\ds4_work\llama_run\zc_$($b.n).resp.json")

    while (-not $c.HasExited) {
        Start-Sleep -Seconds 15
        $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
        $v = (nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) 2>$null
        "{0}`t{1}`t{2}`t{3}`t{4}`t{5}" -f (Get-Date -Format 'HH:mm:ss'), $b.n,
            $m.PageReadsPerSec, $m.PagesInputPerSec, $m.AvailableMBytes, $v |
            Out-File $camp -Append -Encoding utf8
    }

    if (-not $srv.HasExited) {
        [void][CZC]::FreeConsole()
        if ([CZC]::AttachConsole([uint32]$srv.Id)) {
            [void][CZC]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
            [void][CZC]::GenerateConsoleCtrlEvent(0, 0)
            Start-Sleep -Seconds 15
            [void][CZC]::FreeConsole(); [void][CZC]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
        }
        $srv.WaitForExit(120000) | Out-Null
    }

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|mappati host|model buffer size|reap: politica' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue
'FINE' | Out-File $out -Append -Encoding utf8
