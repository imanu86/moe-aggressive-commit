# P2 - ciclo di ripetizione delle prove di corsa (T12-T15).
#
# Perche' esiste: T12, T13, T14 e T15 sono prove di CORSA, e una prova di corsa
# che passa una volta non ha detto niente (progetto §16, verifica n. 5). Vanno
# eseguite in ciclo, almeno cinquanta volte per numero di thread.
#
# Si ricicla l'INTERA batteria, non i soli T12-T15, per due ragioni:
#  - T15 prova la DISTRUZIONE con un job in volo, e la distruzione e' osservabile
#    solo se il processo termina davvero: un ciclo interno al processo proverebbe
#    qualcosa di diverso;
#  - la batteria intera costa poco piu' dei soli T12-T15 (il grosso del tempo e'
#    la quantizzazione iniziale dei banchi) e il ciclo diventa piu' severo, non
#    meno.
#
# Non lancia nessun server e non tocca la GPU: il test e' host-only.
#
# Uso:
#   .\cicla_corse.ps1                       # 50 giri a 4 e a 6 thread
#   .\cicla_corse.ps1 -Giri 100 -Thread 4,6
#   .\cicla_corse.ps1 -Giri 50 -Thread 4 -Full

param(
    [int]   $Giri   = 50,
    [int[]] $Thread = @(4, 6),
    [switch]$Full,
    [string]$Weights = "",
    [string]$LogDir  = ""
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
if ($LogDir -eq "") { $LogDir = Join-Path $here "log" }
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

if (-not (Test-Path (Join-Path $here "test_esecutore.exe"))) {
    throw "test_esecutore.exe non c'e': eseguire prima build_test.cmd"
}

$esitoGlobale = 0

foreach ($t in $Thread) {
    $argv = @("--threads", "$t")
    if ($Full)             { $argv += "--full" }
    if ($Weights -ne "")   { $argv += @("--weights", $Weights) }

    $etichetta = "t$t"
    if ($Full)           { $etichetta += "_full" }
    if ($Weights -ne "") { $etichetta += "_weights" }

    $logCiclo = Join-Path $LogDir "cicli_$etichetta.log"
    $logGuasti = Join-Path $LogDir "cicli_${etichetta}_guasti.log"
    Remove-Item -Path $logCiclo, $logGuasti -ErrorAction SilentlyContinue

    $passati = 0
    $falliti = 0
    $durate  = New-Object System.Collections.Generic.List[double]
    # Verifica n. 7 del progetto (§16): i ritardi iniettati non devono far
    # scattare per sbaglio le scadenze. Il modo di saperlo non e' l'esito
    # binario del giro ma il MARGINE, quindi si raccolgono i tre tempi a ogni
    # giro e si riporta il peggiore, non la media.
    $t12 = New-Object System.Collections.Generic.List[double]
    $t13 = New-Object System.Collections.Generic.List[double]
    $t15 = New-Object System.Collections.Generic.List[double]

    "ciclo T12-T15 (batteria intera): $Giri giri, argomenti: $($argv -join ' ')" |
        Tee-Object -FilePath $logCiclo -Append | Write-Host

    for ($i = 1; $i -le $Giri; $i++) {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $uscita = & (Join-Path $here "test_esecutore.exe") @argv 2>&1
        $codice = $LASTEXITCODE
        $sw.Stop()
        $durate.Add($sw.Elapsed.TotalSeconds)

        $riga = ($uscita | Select-String -Pattern "^ESITO" | Select-Object -First 1)
        $ok = ($codice -eq 0) -and ($riga -match "ESITO POSITIVO")

        if ($ok) {
            $passati++
        } else {
            $falliti++
            $esitoGlobale = 1
            "=== GIRO $i FALLITO (codice $codice) ===" | Add-Content -Path $logGuasti -Encoding utf8
            $uscita | Add-Content -Path $logGuasti -Encoding utf8
        }

        "giro $i/$Giri  esito=$(if ($ok) {'ok'} else {'FALLITO'})  codice=$codice  durata=$([math]::Round($sw.Elapsed.TotalSeconds,3))s" |
            Add-Content -Path $logCiclo -Encoding utf8

        # Anche i [ko] eventuali vanno conservati, non solo l'ESITO finale.
        $ko = $uscita | Select-String -Pattern "\[ko\]"
        if ($ko) { $ko | Add-Content -Path $logCiclo -Encoding utf8 }

        $testo = ($uscita | Out-String)
        if ($testo -match 'T12: .*-> wait ([0-9]+(?:[.,][0-9]+)?) ms')        { $t12.Add([double]($Matches[1] -replace ',','.')) }
        if ($testo -match 'T13: .*-> wait ([0-9]+(?:[.,][0-9]+)?) ms')        { $t13.Add([double]($Matches[1] -replace ',','.')) }
        if ($testo -match 'T15: distruzione con job in volo in ([0-9]+(?:[.,][0-9]+)?) ms') { $t15.Add([double]($Matches[1] -replace ',','.')) }
    }

    # Mediana vera (memoria del progetto: la «mediana» calcolata male era il
    # MASSIMO). Ordinare e prendere l'elemento centrale, o la media dei due
    # centrali se il numero di giri e' pari.
    $ord = @($durate | Sort-Object)
    if ($ord.Count -eq 0) { $mediana = 0 }
    elseif ($ord.Count % 2 -eq 1) { $mediana = $ord[[int](($ord.Count - 1) / 2)] }
    else { $mediana = ($ord[$ord.Count/2 - 1] + $ord[$ord.Count/2]) / 2 }

    $sommario = ("RIEPILOGO $etichetta : {0} eseguiti / {1} passati / {2} falliti " +
                 "| durata min {3}s mediana {4}s max {5}s | totale {6}s") -f `
        $Giri, $passati, $falliti,
        [math]::Round($ord[0],3), [math]::Round($mediana,3),
        [math]::Round($ord[$ord.Count-1],3),
        [math]::Round(($durate | Measure-Object -Sum).Sum, 1)

    $sommario | Tee-Object -FilePath $logCiclo -Append | Write-Host

    function Peggiore($lista) {
        if ($lista.Count -eq 0) { return "n/d" }
        $o = @($lista | Sort-Object)
        return ("min {0} / max {1} ms su {2} giri" -f
                [math]::Round($o[0],1), [math]::Round($o[$o.Count-1],1), $o.Count)
    }
    $margini = ("MARGINI $etichetta : T12 wait {0} (scadenze 5000/2000 ms) | " +
                "T13 wait {1} (limite del banco 200 ms) | T15 teardown {2} (limite 2000 ms)") -f `
        (Peggiore $t12), (Peggiore $t13), (Peggiore $t15)
    $margini | Tee-Object -FilePath $logCiclo -Append | Write-Host
}

if ($esitoGlobale -ne 0) { Write-Host "CICLO NEGATIVO: vedere i file *_guasti.log" }
else                     { Write-Host "CICLO POSITIVO" }
exit $esitoGlobale
