# IL REGISTA: un processo staccato per braccio, e il risultato letto DAL LOG.
#
# TRE GUASTI IMPARATI IL 12/8, e questo file e' la cura di tutti e tre.
#
# 1. I processi lanciati dalla shell di Claude muoiono con la sessione.
#    Cura: Invoke-CimMethod Win32_Process Create -> processo NON figlio.
#
# 2. UN CICLO DI BRACCI DENTRO UN SOLO SCRIPT SI SUICIDA AL PRIMO GIRO.
#    La chiusura pulita fa AttachConsole sulla console del server e manda
#    GenerateConsoleCtrlEvent(0,0): quell'evento va a TUTTO il gruppo, quindi
#    anche allo script che l'ha mandato.
#    Cura: ogni braccio e' un processo a se'.
#
# 3. E ANCHE UN BRACCIO SINGOLO PUO' MORIRE NELLA PULIZIA, dopo aver misurato.
#    Alle 08:06 k339 e' girato per intero e il suo numero e' andato perso
#    perche' lo script spegneva PRIMA di leggere il log. Poi il regista ha
#    aspettato 15 minuti un marcatore che non poteva arrivare, senza mai
#    guardare lo stato.
#    Cura doppia: (a) i bracci salvano prima e spengono dopo; (b) QUESTO file
#    non si fida del marcatore: sonda ogni 15 s, e quando il processo del
#    braccio muore va a leggere il LOG DEL SERVER e ne estrae il risultato da
#    solo. Il log e' la verita' a terra; il marcatore e' una cortesia.
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
    $vram = '-'
    $camp = Join-Path $run "$tag.hw.csv"
    if (Test-Path $camp) {
        $h = @(Import-Csv $camp | Where-Object { $_.util -match '^[0-9]+$' -and [int]$_.util -gt 50 })
        if ($h.Count -gt 0) { $v = @($h | ForEach-Object { [int]$_.vram_usata } | Sort-Object); $vram = $v[[int]($v.Count/2)] }
    }
    return [pscustomobject]@{
        tag=$tag; ts=$ts; ciclo=$ciclo; p1=(M 'draft acceptance = ([0-9.]+)')
        sync=(M 'di cui sync ([0-9.]+)\)'); calc=(M 'calcolo ([0-9.]+) ms, attesa-lavoro')
        colpi=(M 'cache-esperti: domanda [0-9]+ \(colpi [0-9]+ = ([0-9.]+)%'); vram=$vram; sha=$sha }
}

function Braccio([string]$script, [string[]]$argomenti, [string]$tag, [int]$minuti) {
    while (Get-Process -Name llama-server, llama-cli -EA SilentlyContinue) { Start-Sleep -Seconds 5 }
    for ($i = 0; $i -lt 30; $i++) {
        $v = 0; try { $v = [int]((& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) | Select-Object -First 1) } catch { break }
        if ($v -lt 1200) { break }
        Start-Sleep -Seconds 5
    }
    Start-Sleep -Seconds 20
    $cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $doc $script) + '" ' + ($argomenti -join ' ')
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd }
    if ($r.ReturnValue -ne 0) { Nota ("*** " + $tag + ": avvio fallito (" + $r.ReturnValue + ") ***"); return }
    Nota ($tag + ": avviato, PID " + $r.ProcessId)
    $pid_b = $r.ProcessId
    $ultimo = ''
    for ($i = 0; $i -lt ($minuti * 4); $i++) {
        Start-Sleep -Seconds 15
        $vivo = $null -ne (Get-Process -Id $pid_b -EA SilentlyContinue)
        # BATTITO: cosa sta facendo davvero, non "sto aspettando"
        $log = Join-Path $run "$tag.server.log"
        if (Test-Path $log) {
            $d = Select-String -Path $log -Pattern 'n_decoded = *[0-9]+, tg = *[0-9.]+' -EA SilentlyContinue | Select-Object -Last 1
            $stato = if ($d) { ($d.Line -replace '^.*n_decoded','n_decoded') } else { 'in caricamento' }
            if ($stato -ne $ultimo -and ($i % 8) -eq 0) { Nota ("  " + $tag + " | " + $stato.Substring(0,[Math]::Min(70,$stato.Length))); $ultimo = $stato }
        }
        $e = Estrai $tag
        if ($e) { Nota ($tag + ": FATTO  t/s " + $e.ts + "  ciclo " + $e.ciclo + "  p1 " + $e.p1 + "  sync " + $e.sync + "  colpi " + $e.colpi + "%  VRAM " + $e.vram + "  SHA " + $e.sha)
                  ("  {0,-10} {1,-7} {2,-8} {3,-9} {4,-7} {5,-8} {6,-7} {7}" -f $e.tag,$e.ts,$e.ciclo,$e.p1,$e.sync,($e.colpi+'%'),$e.vram,$e.sha) | Out-File -FilePath $tab -Append -Encoding utf8
                  # il processo puo' essere ancora vivo a spegnere il server: lo si lascia finire
                  for ($j = 0; $j -lt 20; $j++) { if ($null -eq (Get-Process -Id $pid_b -EA SilentlyContinue)) { break }; Start-Sleep -Seconds 5 }
                  return }
        if (-not $vivo) {
            Start-Sleep -Seconds 5
            $e = Estrai $tag
            if ($e) { Nota ($tag + ": FATTO (processo gia' uscito)  t/s " + $e.ts + "  ciclo " + $e.ciclo + "  sync " + $e.sync)
                      ("  {0,-10} {1,-7} {2,-8} {3,-9} {4,-7} {5,-8} {6,-7} {7}" -f $e.tag,$e.ts,$e.ciclo,$e.p1,$e.sync,($e.colpi+'%'),$e.vram,$e.sha) | Out-File -FilePath $tab -Append -Encoding utf8 }
            else { Nota ("*** " + $tag + ": processo morto SENZA risultato nel log ***") }
            return
        }
    }
    Nota ("*** " + $tag + ": scaduto dopo " + $minuti + " min ***")
}

Nota "==================== REGISTA AVVIATO ===================="
"  braccio    t/s     ciclo    p1        sync    colpi    VRAM    SHA" | Out-File -FilePath $tab -Append -Encoding utf8

foreach ($s in @('339','256','448','512')) { Braccio 'dopo_il_riavvio.ps1' @("k$s", $s) "k$s" 12 }
Nota "---------- curva finita, passo al 2x2 ----------"
foreach ($b in @('g_b8b','n_fork','g_zbozza','n_ibrido')) { Braccio 'due_per_due.ps1' @($b) $b 12 }
Nota "==================== REGISTA FINITO ===================="
