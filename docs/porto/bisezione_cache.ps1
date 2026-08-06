# DI CHI E' LA REGRESSIONE, E QUANTO COSTA UN CONFINE
#
# IL FATTO DA SPIEGARE
# --------------------
# Stesso binario, stessa ora, stessa macchina (diagnosi.txt del 6/8):
#
#     cache SPENTA   7,96 t/s     <- il metro, esatto
#     cache ACCESA   6,49         -18%, e i colpi al 64,7% contro il 44% storico
#
# La campagna misurava 8,04 -> 9,26, cioe' +15%. Uno scarto di 33 punti, con
# piu' colpi e meno velocita'. Fra le due misure e' cambiato il binario, e il
# ramo jacobi aggiunge a dspark-dsv4 tre file: lookahead.cpp (che non entra in
# nessuna DLL), la sonda dei confini in ggml-backend.cpp, e la mia rimozione del
# cancello a batch 1 in ggml-cuda.cu.
#
# LA BISEZIONE, SENZA UNA SECONDA COMPILAZIONE
# ---------------------------------------------
# LLAMA_CACHE_ESPERTI_BATCH mette un tetto su ids->ne[1]. A 1 il comportamento e'
# IDENTICO a prima della mia patch, sullo stesso identico binario:
#
#     C1  BATCH=1   ~9,2 -> la colpa e' la mia patch
#                   ~6,5 -> la colpa e' fuori dal mio diff (sonda, o altro)
#     C8  BATCH=8   il braccio utile: cache viva a batch stretto, fuori dal prefill
#     C1b BATCH=1   ripetizione, per sapere quanto vale il rumore prima di
#                   attribuire qualunque differenza
#
# E LA SONDA, che adesso scrive con fprintf diretto (605b5dc: il callback del
# server filtrava gli INFO di origine ggml, per questo era muta). Accesa su
# TUTTI i bracci: costa un branch per split e il giro precedente l'ha misurata
# sotto il rumore (5,59 contro 5,56). Da' la coppia che serve:
#
#     split per grafo   -> conteggio ~86 o diverso?
#     ingressi ms       -> il TOTALE del costo dei confini per grafo
#
# e con quella si legge il prezzo della sovrapposizione CPU||GPU:
#     conteggio ~86, totale ~11 ms -> i 255 us erano rumore, vale il tetto 128
#     conteggio >86, totale ~11 ms -> unitario piu' basso, PRICING INVARIATO
#     conteggio ~86, totale >>11   -> la sottrazione ibrido-cache era sbagliata
$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\bisezione.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$EXE = 'D:\llama-dspark\build\bin\llama-server.exe'
$MOD = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$R   = 'D:\ds4_work\llama_run'
$b   = [char]92
$ESP = 'ffn_(gate|up|down)_exps' + $b + '.weight=CUDA0_Mapped'

$bracci = @(
    @{ n='C1';  batch=1; slot=380; d='BATCH=1 -- identico a prima della patch. Storico: 9,2' },
    @{ n='C8';  batch=8; slot=380; d='BATCH=8 -- il braccio utile, cache a batch stretto' },
    @{ n='C1b'; batch=1; slot=380; d='BATCH=1 ripetuto -- il rumore, prima di attribuire' }
)
$porta = 8551
foreach ($x in $bracci) {
    "=============== $($x.n) -- $($x.d) ===============" | Out-File $out -Append -Encoding utf8
    $log = "$R\BIS_$($x.n).log"
    $ram = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB
    "  [condizione] RAM libera {0:N1} GiB" -f $ram | Out-File $out -Append -Encoding utf8
    if ($ram -lt 10) { "  SCARTATO" | Out-File $out -Append -Encoding utf8; continue }

    $env:LLAMA_MAPPED_IBRIDO       = '1'
    $env:LLAMA_REAP                = '0'
    $env:LLAMA_CACHE_ESPERTI_SLOT  = "$($x.slot)"
    $env:LLAMA_CACHE_ESPERTI_W     = '0'
    $env:LLAMA_CACHE_ESPERTI_BATCH = "$($x.batch)"
    $env:GGML_SCHED_PROFILO        = '1'

    $a = @('-m',$MOD,'-c','10000','-np','1','-ngl','99','-ot',$ESP,
           '-ub','64','-b','64','-t','8','--port',"$porta",'--host','127.0.0.1',
           '--no-warmup','--no-mmap','--reasoning-budget','0')
    $srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -WindowStyle Minimized `
            -RedirectStandardError $log -RedirectStandardOutput ($log + '.out')
    $pronto = $false
    for ($i=0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 10
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto=$true; break } catch {}
    }
    if (-not $pronto) { "  NON PARTE" | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
        Start-Sleep 45; $porta++; continue }

    $d = (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "  VRAM {0:N0} MiB, liberi {1:N0}" -f ($d.CookedValue/1MB), (12288 - $d.CookedValue/1MB) |
        Out-File $out -Append -Encoding utf8

    $risp = "$R\bis_$($x.n).json"
    & curl.exe -s --max-time 900 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$R\par_p1.req.json" -o $risp | Out-Null
    if (Test-Path $risp) {
        $j = Get-Content $risp -Raw | ConvertFrom-Json
        "  prefill {0,6:N2}   decode {1,6:N2} t/s   {2:N2} ms/tok" -f `
            $j.timings.prompt_per_second, $j.timings.predicted_per_second, $j.timings.predicted_per_token_ms |
            Out-File $out -Append -Encoding utf8
        $j.choices[0].message.content | Out-File "$R\bis_$($x.n).output.html" -Encoding utf8
        "  sha256 " + (Get-FileHash "$R\bis_$($x.n).output.html" -Algorithm SHA256).Hash.Substring(0,16) |
            Out-File $out -Append -Encoding utf8
    }
    foreach ($f in @($log, ($log + '.out'))) {
        Select-String -Path $f -Pattern 'cache-esperti: domanda|sched-profilo' -EA SilentlyContinue |
            Select-Object -Last 2 |
            ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8
    }
    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep 10
    Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
    Start-Sleep 60
    "" | Out-File $out -Append -Encoding utf8
    $porta++
}
'FINE' | Out-File $out -Append -Encoding utf8
