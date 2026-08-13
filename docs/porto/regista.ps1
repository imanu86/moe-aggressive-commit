# IL REGISTA: un processo staccato per braccio, risultato letto DAL LOG.
#
# QUATTRO GUASTI IMPARATI IL 12/8, e questo file e' la cura di tutti e quattro:
#  1. i processi lanciati dalla shell di Claude muoiono con la sessione
#     -> Invoke-CimMethod Win32_Process Create, processo NON figlio;
#  2. un ciclo di bracci dentro un solo script si suicida al primo giro, perche'
#     la chiusura pulita manda GenerateConsoleCtrlEvent(0,0) a tutto il gruppo
#     della console -> ogni braccio e' un processo a se';
#  3. anche un braccio singolo puo' morire nella pulizia DOPO aver misurato
#     -> i bracci salvano prima e spengono dopo, e qui si legge il LOG, non il
#        marcatore;
#  4. un file vecchio con lo stesso tag e' un risultato FALSO -> gli artefatti
#     del tag si cancellano prima di lanciare.
#
# CAMPAGNA DEL 12/8 POMERIGGIO, sul binario ricostruito alle 12:41.
# RIFERIMENTO: t512 = 14,47 t/s, sync 2,281, dispatch 0,178, sched-sync 0,119,
# p1 0,85449, SHA FE90AC77066D.
#
# Ogni braccio cambia UNA leva sola, e il riferimento e' ripetuto due volte
# dentro la campagna: senza controllo intercalato la deriva della finestra
# (misurata al 2,3% stamattina) rende indecidibile qualunque effetto sotto il 3%.
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
    # PRIMA riga della cache: la seconda e' quella della bozza, che non usa la leva
    $par = $( $m = Select-String -Path $log -Pattern 'cache-esperti: \d+ slot da .*sfratto_par=(\d+)' -EA SilentlyContinue | Select-Object -First 1
              if ($m) { $m.Matches[0].Groups[1].Value } else { '-' } )
    return [pscustomobject]@{
        tag=$tag; ts=$ts; ciclo=$ciclo; p1=(M 'draft acceptance = ([0-9.]+)')
        sync=(M 'di cui sync ([0-9.]+)\)'); disp=(M 'dispatch ([0-9.]+) ms')
        ssync=(M 'sched-sync ([0-9.]+) ms'); colpi=(M 'cache-esperti: domanda [0-9]+ \(colpi [0-9]+ = ([0-9.]+)%')
        par=$par; sha=$sha }
}

function Braccio([string]$tag, [string]$script, [string[]]$argomenti, [int]$minuti) {
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
    $cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $doc $script) + '" ' + ($argomenti -join ' ')
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd }
    if ($r.ReturnValue -ne 0) { Nota ("*** " + $tag + ": avvio fallito (" + $r.ReturnValue + ") ***"); return }
    Nota ($tag + ": avviato, PID " + $r.ProcessId)
    $pid_b = $r.ProcessId
    for ($i = 0; $i -lt ($minuti * 4); $i++) {
        Start-Sleep -Seconds 15
        $vivo = $null -ne (Get-Process -Id $pid_b -EA SilentlyContinue)
        $e = Estrai $tag
        if (-not $e -and -not $vivo) { Start-Sleep -Seconds 5; $e = Estrai $tag }
        if ($e) {
            Nota ($tag + ": FATTO  t/s " + $e.ts + "  ciclo " + $e.ciclo + "  p1 " + $e.p1 + "  sync " + $e.sync + "  disp " + $e.disp + "  ssync " + $e.ssync + "  colpi " + $e.colpi + "%  par=" + $e.par + "  SHA " + $e.sha)
            ("  {0,-8} {1,-7} {2,-8} {3,-9} {4,-7} {5,-7} {6,-7} {7,-7} {8,-4} {9}" -f $e.tag,$e.ts,$e.ciclo,$e.p1,$e.sync,$e.disp,$e.ssync,($e.colpi+'%'),$e.par,$e.sha) | Out-File -FilePath $tab -Append -Encoding utf8
            for ($j = 0; $j -lt 20; $j++) { if ($null -eq (Get-Process -Id $pid_b -EA SilentlyContinue)) { break }; Start-Sleep -Seconds 5 }
            return
        }
        if (-not $vivo) {
            $ko = Join-Path $run "$tag.server.log"
            $m = if (Test-Path $ko) { (Select-String -Path $ko -Pattern "error|out of memory" -EA SilentlyContinue | Select-Object -Last 1).Line } else { '' }
            Nota ("*** " + $tag + ": morto SENZA risultato. " + $m + " ***"); return
        }
    }
    Nota ("*** " + $tag + ": scaduto dopo " + $minuti + " min ***")
}

Nota "============ CAMPAGNA 12/8 POMERIGGIO, binario delle 12:41 ============"
Nota "riferimento t512 = 14,47 t/s, sync 2,281, disp 0,178, ssync 0,119, SHA FE90AC77066D"
"  braccio  t/s     ciclo    p1        sync    disp    ssync   colpi   par  SHA" | Out-File -FilePath $tab -Append -Encoding utf8

# --- la capienza, tutta da rifare a sfratto_par=1 -------------------------
Braccio 'w448'  'dopo_il_riavvio.ps1' @('w448',  '448') 12
Braccio 'w339'  'dopo_il_riavvio.ps1' @('w339',  '339') 12
# --- la maschera FUSO, indecidibile finora --------------------------------
Braccio 'wfu7'  'dopo_il_riavvio.ps1' @('wfu7',  '512', '0', '"LLAMA_DSV4_HC_FUSO=7"') 12
# --- controllo intercalato: senza, niente sotto il 3% e' decidibile -------
Braccio 'wrif'  'dopo_il_riavvio.ps1' @('wrif',  '512') 12
# --- IL 2x2: la casella mai provata, e quella che separa IBRIDO dalla lane -
Braccio 'wlane' 'dopo_il_riavvio.ps1' @('wlane', '512', '0', '"LLAMA_OVERLAP_ASYNC=0;LLAMA_OVERLAP_K=0;LLAMA_MAPPED_IBRIDO=0"') 12
Braccio 'wibr'  'dopo_il_riavvio.ps1' @('wibr',  '512', '0', '"LLAMA_OVERLAP_ASYNC=0;LLAMA_OVERLAP_K=0"') 12
# --- FUSO=4 e =6 a 339 slot: a 512 morivano per muro VRAM -----------------
Braccio 'wfu4'  'dopo_il_riavvio.ps1' @('wfu4',  '339', '0', '"LLAMA_DSV4_HC_FUSO=4"') 12
Braccio 'wfu6'  'dopo_il_riavvio.ps1' @('wfu6',  '339', '0', '"LLAMA_DSV4_HC_FUSO=6"') 12
# --- il cammino GPU puro, gemello esatto di b8b (12,43) -------------------
Braccio 'g_b8b' 'due_per_due.ps1'     @('g_b8b') 12
# --- controllo finale: la deriva sull'intera finestra ---------------------
Braccio 'wrif2' 'dopo_il_riavvio.ps1' @('wrif2', '512') 12
Nota "============ CAMPAGNA FINITA ============"
