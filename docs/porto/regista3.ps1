# L'ANTICIPO: la sola strada verso il 95% di colpi che non passa ne' dalla lane
# CPU, ne' dalla zerocopy, ne' da una riquantizzazione.
#
# PERCHE'. Il 60% non e' un problema di capienza: in archivio c'e' che "con un
# token di anticipo 448 slot coprono il 100%". Il set di lavoro ci sta gia'.
# Manca sapere PRIMA cosa serve. E l'aritmetica torna: 6 esperti per strato x
# 6,75 MiB = 40,5 MiB, a 24 GiB/s sono 1,65 ms, contro ~3 ms di calcolo per
# strato (127 ms di ciclo su 43 strati). La copia entra dentro il calcolo dello
# strato precedente.
#
# IL FATTO CHE APRE QUESTA CAMPAGNA. Il prefetch fra strati richiede DUE
# interruttori insieme (cache-esperti.cu:1279):
#     runtime->dma_strato = runtime->dma_leva && prefetch_w > 0;
# cioe' LLAMA_CACHE_ESPERTI_DMA=1 E LLAMA_CACHE_ESPERTI_W>0. Non li abbiamo MAI
# accesi insieme. Il braccio q_dma di stamattina (-28%) aveva DMA=1 ma W=0:
# misurava il DMA a domanda, NON l'anticipo.
# E il codice dichiara, nel suo stesso commento (cache-esperti.cuh:36):
#     "Il predittore PREDICE (44 -> 78% di colpi, il 71% offline si conferma)"
#
# Le altre condizioni sono gia' soddisfatte: LRU pura (lru=1, massa=0) e il
# cancello sui colpi (53,4%), che a 448 slot passiamo con il 55,2% mentre i tre
# bracci che lo "falsificarono" giravano al 46,5% e non entravano mai.
#
# RIFERIMENTO: 448 slot = 14,71 t/s, colpi 55,2%, sync 2,380, p1 0,86604.
# COSA GUARDARE: i COLPI prima del t/s. Se non salgono, l'anticipo non e' entrato
# e il braccio non dice niente sulla velocita'.
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
    return [pscustomobject]@{
        tag=$tag; ts=$ts; ciclo=$ciclo; p1=(M 'draft acceptance = ([0-9.]+)')
        sync=(M 'di cui sync ([0-9.]+)\)')
        colpi=(M 'cache-esperti: domanda [0-9]+ \(colpi [0-9]+ = ([0-9.]+)%')
        # la prova che l'anticipo e' ENTRATO, non che e' stato chiesto
        ritardo=(M 'in ritardo [0-9]+ = ([0-9.]+)% dei prenotati')
        sha=$sha }
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
    # QUIETE: dopo un rilascio la macchina va lasciata assestare. Il 12/8 il
    # braccio wrif2, partito 60 s dopo la liberazione forzata di un server che
    # teneva 74,5 GB, ha fatto 10,25 invece di 14,4 -- e non era una leva.
    Start-Sleep -Seconds 45
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
            Nota ($tag + ": FATTO  t/s " + $e.ts + "  ciclo " + $e.ciclo + "  p1 " + $e.p1 + "  COLPI " + $e.colpi + "%  in-ritardo " + $e.ritardo + "%  sync " + $e.sync + "  SHA " + $e.sha)
            ("  {0,-8} {1,-7} {2,-8} {3,-9} {4,-8} {5,-8} {6,-7} {7}" -f $e.tag,$e.ts,$e.ciclo,$e.p1,($e.colpi+'%'),($e.ritardo+'%'),$e.sync,$e.sha) | Out-File -FilePath $tab -Append -Encoding utf8
            for ($j = 0; $j -lt 20; $j++) { if ($null -eq (Get-Process -Id $pid_b -EA SilentlyContinue)) { break }; Start-Sleep -Seconds 5 }
            return
        }
        if (-not $vivo) {
            $ko = Join-Path $run "$tag.server.log"
            $m = if (Test-Path $ko) { (Select-String -Path $ko -Pattern "error|out of memory|SPENTO|bloccato" -EA SilentlyContinue | Select-Object -Last 1).Line } else { '' }
            Nota ("*** " + $tag + ": morto. " + $m + " ***"); return
        }
    }
    Nota ("*** " + $tag + ": scaduto ***")
}

Nota "===== L'ANTICIPO: DMA + W, mai accesi insieme ====="
Nota "riferimento 448 slot: 14,71 t/s, colpi 55,2%, sync 2,380, p1 0,86604"
"  braccio  t/s     ciclo    p1        COLPI    ritardo  sync    SHA" | Out-File -FilePath $tab -Append -Encoding utf8

# W = quanti strati di anticipo. 1 = lo strato successivo, che e' quello che
# l'aritmetica dice sufficiente (1,65 ms di copia dentro 3 ms di calcolo).
# IL CONTROLLO PER PRIMO: il binario e' cambiato (cache-esperti.cu ricompilata,
# ggml-cuda.dll rilinkata), quindi i 14,71 di stamattina NON sono un riferimento
# valido. Serve sapere dove sta il banco adesso prima di leggere l'anticipo.
Braccio 'a_rif' @('a_rif', '448') 14
Braccio 'a_w1'  @('a_w1',  '448', '0', '"LLAMA_CACHE_ESPERTI_DMA=1;LLAMA_CACHE_ESPERTI_W=1"') 14
Braccio 'a_w2'  @('a_w2',  '448', '0', '"LLAMA_CACHE_ESPERTI_DMA=1;LLAMA_CACHE_ESPERTI_W=2"') 14
# e con lo SCUDO acceso: protegge i predetti in classe (c) della scansione
Braccio 'a_w1s' @('a_w1s', '448', '0', '"LLAMA_CACHE_ESPERTI_DMA=1;LLAMA_CACHE_ESPERTI_W=1;LLAMA_CACHE_ESPERTI_SCUDO=1"') 14
# se W entra ma il cancello sui colpi lo strozza, questo lo apre
Braccio 'a_w1g' @('a_w1g', '448', '0', '"LLAMA_CACHE_ESPERTI_DMA=1;LLAMA_CACHE_ESPERTI_W=1;LLAMA_CACHE_ESPERTI_DMA_HIT_PM=400"') 14
# e a 512, dove i colpi partono gia' cinque punti piu' in alto
Braccio 'a_w1_512' @('a_w1_512', '512', '0', '"LLAMA_CACHE_ESPERTI_DMA=1;LLAMA_CACHE_ESPERTI_W=1"') 14
Nota "===== FINITA ====="
