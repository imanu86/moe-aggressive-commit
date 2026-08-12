# IL REGISTA: un processo staccato per braccio, risultato letto DAL LOG.
#
# TRE GUASTI IMPARATI IL 12/8, e questo file e' la cura di tutti e tre.
#  1. I processi lanciati dalla shell di Claude muoiono con la sessione.
#     Cura: Invoke-CimMethod Win32_Process Create -> processo NON figlio.
#  2. Un ciclo di bracci dentro un solo script si suicida al primo giro: la
#     chiusura pulita manda GenerateConsoleCtrlEvent(0,0) a TUTTO il gruppo
#     della console, quindi anche a chi lo manda.
#     Cura: ogni braccio e' un processo a se'.
#  3. Anche un braccio singolo puo' morire nella pulizia DOPO aver misurato.
#     Cura: (a) i bracci salvano prima e spengono dopo; (b) questo file non si
#     fida del marcatore, sonda ogni 15 s e legge il LOG DEL SERVER.
#
# E UN QUARTO, il piu' caro: un file vecchio con lo stesso tag e' un risultato
# FALSO. `k448.server.log` di un'altra giornata e' stato letto 15 s dopo l'avvio
# e ha prodotto un numero plausibile e sbagliato. Qui i file del tag si
# cancellano PRIMA di lanciare.
#
# LA CAMPAGNA. Adesso che SFRATTO_PAR=1 e' rimessa (il banco e' tornato a
# 14,40), tre leve non sono mai state misurate nel regime giusto:
#   - JOIN_ASYNC: da accesa fa 10,7 copie/grafo, ma in tutti gli script e' '0',
#     quindi il contatore "copie join-async" ha sempre stampato 0.0.
#   - Il DMA fra-strati: "non consegna un chunk su settemila" e' un numero che
#     misurava IL CANCELLO -- i bracci giravano al 46,5% di colpi e la soglia
#     ammette dal 53,4%.
#   - FUSO e' una MASCHERA (1=comb 2=pre 4=post): usiamo 5, abbiamo assaggiato
#     7, e non abbiamo mai provato 2, 4 e 6.
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
        sync=(M 'di cui sync ([0-9.]+)\)'); colpi=(M 'cache-esperti: domanda [0-9]+ \(colpi [0-9]+ = ([0-9.]+)%')
        # PRIMA occorrenza, non l'ultima: nel log ci sono DUE cache (bersaglio e
        # bozza) e l'ultima riga e' quella della bozza, che non usa la leva.
        # Con -Last stampava par=0 su corse che giravano a par=1.
        par=$(  $m = Select-String -Path $log -Pattern 'cache-esperti: \d+ slot da .*sfratto_par=(\d+)' -EA SilentlyContinue | Select-Object -First 1
                if ($m) { $m.Matches[0].Groups[1].Value } else { '-' } )
        ja=(M 'copie join-async ([0-9.]+)'); sha=$sha }
}

function Braccio([string]$tag, [string[]]$argomenti, [int]$minuti) {
    while (Get-Process -Name llama-server, llama-cli -EA SilentlyContinue) { Start-Sleep -Seconds 5 }
    for ($i = 0; $i -lt 30; $i++) {
        $v = 0; try { $v = [int]((& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) | Select-Object -First 1) } catch { break }
        if ($v -lt 1200) { break }
        Start-Sleep -Seconds 5
    }
    # QUARTO GUASTO: gli artefatti del tag si cancellano PRIMA
    foreach ($e in '.server.log', '.server.out', '.output.html', '.hw.csv') {
        Remove-Item (Join-Path $run ($tag + $e)) -Force -EA SilentlyContinue
    }
    Start-Sleep -Seconds 20
    $cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $doc 'dopo_il_riavvio.ps1') + '" ' + ($argomenti -join ' ')
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
            Nota ($tag + ": FATTO  t/s " + $e.ts + "  ciclo " + $e.ciclo + "  p1 " + $e.p1 + "  sync " + $e.sync + "  colpi " + $e.colpi + "%  par=" + $e.par + "  join-async " + $e.ja + "  SHA " + $e.sha)
            ("  {0,-10} {1,-7} {2,-8} {3,-9} {4,-7} {5,-7} {6,-5} {7,-8} {8}" -f $e.tag,$e.ts,$e.ciclo,$e.p1,$e.sync,($e.colpi+'%'),$e.par,$e.ja,$e.sha) | Out-File -FilePath $tab -Append -Encoding utf8
            for ($j = 0; $j -lt 20; $j++) { if ($null -eq (Get-Process -Id $pid_b -EA SilentlyContinue)) { break }; Start-Sleep -Seconds 5 }
            return
        }
        if (-not $vivo) { Nota ("*** " + $tag + ": morto SENZA risultato nel log ***"); return }
    }
    Nota ("*** " + $tag + ": scaduto dopo " + $minuti + " min ***")
}

Nota "==================== CAMPAGNA POST-SFRATTO_PAR ===================="
Nota "riferimento: s512 = 14,40 t/s, sync 2,266, p1 0,85449, SHA FE90AC77066D"
"  braccio    t/s     ciclo    p1        sync    colpi   par   join-as  SHA" | Out-File -FilePath $tab -Append -Encoding utf8

# ogni braccio cambia UNA leva sola rispetto a s512
Braccio 'q_join'  @('q_join',  '512', '0', '"LLAMA_OVERLAP_JOIN_ASYNC=1"')                                   12
Braccio 'q_dma'   @('q_dma',   '512', '0', '"LLAMA_CACHE_ESPERTI_DMA=1;LLAMA_CACHE_ESPERTI_DMA_HIT_PM=400"') 12
Braccio 'q_fu7'   @('q_fu7',   '512', '0', '"LLAMA_DSV4_HC_FUSO=7"')                                         12
Braccio 'q_fu6'   @('q_fu6',   '512', '0', '"LLAMA_DSV4_HC_FUSO=6"')                                         12
Braccio 'q_fu4'   @('q_fu4',   '512', '0', '"LLAMA_DSV4_HC_FUSO=4"')                                         12
Braccio 'q_rif'   @('q_rif',   '512')                                                                        12
Nota "==================== CAMPAGNA FINITA ===================="
