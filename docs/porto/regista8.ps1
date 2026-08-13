# LA CODA DEL PREFETCH: l'88% delle previsioni era scartato da una costante.
#
# LA CATENA, tutta misurata il 12/8:
#   1. la copia degli esperti dura 0,854 ms (cronometro nuovo) e muove 18,3 MiB
#      per strato = 20,9 GiB/s, cioe' l'86% del tetto del microbench: il canale
#      NON e' fermo, la copia e' gia' veloce quanto puo';
#   2. ma al join solo il 15,5% e' finito, perche' la finestra a domanda -- il
#      matmul dei residenti -- ne offre ~0,44: serve il DOPPIO del tempo;
#   3. l'anticipo di uno strato lo darebbe (uno strato dura 1,58 ms), e il
#      predittore di route esiste, e' implementato in deepseek4.cpp:1351 e
#      indovina il 71% a un strato;
#   4. ma il prefetch portava solo il 2,6% del traffico (17,55 GiB su 684),
#      perche' i contatori dicono: prenotati 2.661, saltati 9.094,
#      SCARTATI 11.105.
#   5. e gli scarti venivano da UNA COSTANTE:
#          const int limite_coda = c.dma_strato ? 1 : c.coda_max;
#      un solo batch di prefetch in volo. Con 43 strati che prevedono a ogni
#      token, tutto quello che arriva mentre ce n'e' uno in volo si butta.
#
# Adesso e' LLAMA_CACHE_ESPERTI_DMA_CODA, difetto 1 = comportamento storico.
#
# COSA GUARDARE, IN QUEST'ORDINE -- il t/s per ultimo:
#   scartati    deve crollare. Se non crolla, il collo non era questo.
#   GiB prefetch deve salire dal 2,6%. E' la definizione di "l'anticipo entra".
#   ritardo     quota dei prenotati arrivati tardi: se sale molto, la coda piu'
#               lunga sta solo accumulando lavoro che non fa in tempo.
#   COLPI       salgono solo se l'anticipo arriva PRIMA della domanda.
#   t/s         la conseguenza, non la misura.
$ErrorActionPreference = 'Continue'
$run = 'D:\ds4_work\llama_run'
$doc = 'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto'
$reg = Join-Path $run 'regista.txt'
$tab = Join-Path $run 'tabella.txt'
function Nota([string]$t) { ("[" + [DateTime]::Now.ToString('HH:mm:ss') + "] " + $t) | Out-File -FilePath $reg -Append -Encoding utf8 }

function Estrai([string]$tag) {
    $log = Join-Path $run "$tag.server.log"
    if (-not (Test-Path $log)) { return $null }
    function M([string]$pat) {
        $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
        if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
    $ts = M '\|        eval time =.*?([0-9.]+) tokens per second'
    if ($ts -eq '-') { return $null }
    $ml = M 'mean len =\s+([0-9.]+)'
    $out = Join-Path $run "$tag.output.html"
    $sha = if (Test-Path $out) { (Get-FileHash $out -Algorithm SHA256).Hash.Substring(0,12) } else { '-' }
    $ciclo = if ($ml -ne '-') { [math]::Round((1000/[double]$ts)*[double]$ml,1) } else { [math]::Round(1000/[double]$ts,1) }
    $dom = M 'byte a domanda \(stream calcolo\) ([0-9.]+) GiB'
    $pf  = M 'in prefetch \(stream DMA\) ([0-9.]+) GiB'
    $quota = '-'
    if ($dom -ne '-' -and $pf -ne '-' -and ([double]$dom + [double]$pf) -gt 0) {
        $quota = [math]::Round(100.0*[double]$pf/([double]$dom+[double]$pf),1)
    }
    return [pscustomobject]@{
        tag=$tag; ts=$ts; ciclo=$ciclo
        colpi=(M 'cache-esperti: domanda [0-9]+ \(colpi [0-9]+ = ([0-9.]+)%')
        ritardo=(M 'in ritardo [0-9]+ = ([0-9.]+)% dei prenotati')
        pren=(M 'prefetch prenotati ([0-9]+)'); scar=(M 'prenotati [0-9]+, saltati [0-9]+, scartati ([0-9]+)')
        pfq=$quota; copia=(M 'durata media della copia=([0-9.]+) ms')
        finita=(M "copia gia' finita=[0-9]+ \(([0-9.]+)%\)"); sha=$sha }
}

function Braccio([string]$tag, [string[]]$argomenti, [int]$minuti) {
    while (Get-Process -Name llama-server, llama-cli -EA SilentlyContinue) { Start-Sleep -Seconds 5 }
    for ($i = 0; $i -lt 40; $i++) {
        $v = 0; try { $v = [int]((& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) | Select-Object -First 1) } catch { break }
        if ($v -lt 1200) { break }
        Start-Sleep -Seconds 5
    }
    foreach ($e in '.server.log', '.server.out', '.output.html', '.hw.csv') {
        Remove-Item (Join-Path $run ($tag + $e)) -Force -EA SilentlyContinue
    }
    Start-Sleep -Seconds 40
    $cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $doc 'dopo_il_riavvio.ps1') + '" ' + ($argomenti -join ' ')
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd }
    if ($r.ReturnValue -ne 0) { Nota ("*** " + $tag + ": avvio fallito ***"); return }
    Nota ($tag + ": avviato, PID " + $r.ProcessId)
    $pid_b = $r.ProcessId
    for ($i = 0; $i -lt ($minuti * 4); $i++) {
        Start-Sleep -Seconds 15
        $vivo = $null -ne (Get-Process -Id $pid_b -EA SilentlyContinue)
        $e = Estrai $tag
        if (-not $e -and -not $vivo) { Start-Sleep -Seconds 5; $e = Estrai $tag }
        if ($e) {
            Nota ($tag + ": FATTO  t/s " + $e.ts + "  COLPI " + $e.colpi + "%  scartati " + $e.scar + "  prefetch " + $e.pfq + "%  ritardo " + $e.ritardo + "%  finita " + $e.finita + "%  copia " + $e.copia + " ms")
            ("  {0,-9} {1,-7} {2,-8} {3,-8} {4,-9} {5,-9} {6,-8} {7,-8} {8}" -f `
                $e.tag, $e.ts, $e.ciclo, ($e.colpi+'%'), $e.scar, ($e.pfq+'%'), ($e.ritardo+'%'), ($e.finita+'%'), $e.sha) |
                Out-File -FilePath $tab -Append -Encoding utf8
            for ($j = 0; $j -lt 20; $j++) { if ($null -eq (Get-Process -Id $pid_b -EA SilentlyContinue)) { break }; Start-Sleep -Seconds 5 }
            return
        }
        if (-not $vivo) {
            $ko = Join-Path $run "$tag.server.log"
            $m = if (Test-Path $ko) { (Select-String -Path $ko -Pattern "error|out of memory" -EA SilentlyContinue | Select-Object -Last 1).Line } else { '' }
            Nota ("*** " + $tag + ": morto. " + $m + " ***"); return
        }
    }
    Nota ("*** " + $tag + ": scaduto ***")
}

Nota "===== VERIFICA: l'abort di chiusura e il riferimento sulla DLL nuova ====="
Nota "atteso: t/s ~14,77 e NESSUN ggml-cuda.cu:108 alla chiusura"
"  braccio   t/s     ciclo    COLPI    scartati  prefetch  ritardo  finita   SHA" | Out-File -FilePath $tab -Append -Encoding utf8
Braccio 'h_rif'  @('h_rif',  '448') 14
Braccio 'h_rif2' @('h_rif2', '448') 14
Nota "===== FINITA ====="
