# CAMPAGNA "CERCA VELOCITA'", 12/8 pomeriggio.
#
# Il conto onesto fin qui: la giornata ha prodotto +1,9% (448 slot, 14,71
# contro un riferimento fra 14,39 e 14,47) e siamo sotto il record di ieri
# (14,78). Tutto il resto e' stato riparazione.
#
# Questa campagna cerca solo velocita', e parte da tre fatti nuovi:
#  - l'ottimo della capienza NON e' 512: 448 fa 14,71, 512 fa 14,39-14,47, e
#    intorno a 448 non abbiamo mai guardato;
#  - FUSO=7 e' NEUTRO (14,43 contro 14,39), quindi e' gratis e non e' mai
#    stato combinato con 448;
#  - K non e' mai stato rialzato nel regime con sfratto_par=1. La memoria dice
#    che a K=4 i colpi salgono al 76,8% e la CPU diventa il collo -- ma quella
#    misura e' del 9/8, in un regime dove la scansione delle vittime era
#    seriale e quindi il costo della cache era gonfiato.
#
# Ogni braccio cambia UNA leva rispetto a 448, e il controllo e' ripetuto.
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
    $par = $( $m = Select-String -Path $log -Pattern 'cache-esperti: \d+ slot da .*sfratto_par=(\d+)' -EA SilentlyContinue | Select-Object -First 1
              if ($m) { $m.Matches[0].Groups[1].Value } else { '-' } )
    return [pscustomobject]@{
        tag=$tag; ts=$ts; ciclo=$ciclo; p1=(M 'draft acceptance = ([0-9.]+)')
        sync=(M 'di cui sync ([0-9.]+)\)'); disp=(M 'dispatch ([0-9.]+) ms')
        ssync=(M 'sched-sync ([0-9.]+) ms'); colpi=(M 'cache-esperti: domanda [0-9]+ \(colpi [0-9]+ = ([0-9.]+)%')
        par=$par; sha=$sha }
}

function Braccio([string]$tag, [string[]]$argomenti, [int]$minuti) {
    while (Get-Process -Name llama-server, llama-cli -EA SilentlyContinue) { Start-Sleep -Seconds 5 }
    for ($i = 0; $i -lt 30; $i++) {
        $v = 0; try { $v = [int]((& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) | Select-Object -First 1) } catch { break }
        if ($v -lt 1200) { break }
        Start-Sleep -Seconds 5
    }
    foreach ($e in '.server.log', '.server.out', '.output.html', '.hw.csv') {
        Remove-Item (Join-Path $run ($tag + $e)) -Force -EA SilentlyContinue
    }
    Start-Sleep -Seconds 20
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
            Nota ($tag + ": FATTO  t/s " + $e.ts + "  ciclo " + $e.ciclo + "  p1 " + $e.p1 + "  sync " + $e.sync + "  colpi " + $e.colpi + "%  par=" + $e.par + "  SHA " + $e.sha)
            ("  {0,-8} {1,-7} {2,-8} {3,-9} {4,-7} {5,-7} {6,-7} {7,-7} {8,-4} {9}" -f $e.tag,$e.ts,$e.ciclo,$e.p1,$e.sync,$e.disp,$e.ssync,($e.colpi+'%'),$e.par,$e.sha) | Out-File -FilePath $tab -Append -Encoding utf8
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

Nota "============ CERCA VELOCITA': l'ottimo sta intorno a 448 ============"

# il ginocchio della capienza, mai sondato fra 448 e 512
Braccio 'v480'   @('v480',   '480') 12
Braccio 'v416'   @('v416',   '416') 12
# le due leve gratis, mai combinate con 448
Braccio 'v448f7' @('v448f7', '448', '0', '"LLAMA_DSV4_HC_FUSO=7"') 12
# controllo intercalato
Braccio 'v448'   @('v448',   '448') 12
# K non e' mai stato rialzato nel regime giusto
Braccio 'v448k3' @('v448k3', '448', '0', '"LLAMA_OVERLAP_K=3"') 12
Braccio 'v448k4' @('v448k4', '448', '0', '"LLAMA_OVERLAP_K=4"') 12
# la migliore combinazione plausibile, se le due sopra tengono
Braccio 'v480f7' @('v480f7', '480', '0', '"LLAMA_DSV4_HC_FUSO=7"') 12
# controllo finale
Braccio 'v448b'  @('v448b',  '448') 12
Nota "============ FINITA ============"
