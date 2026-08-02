# LA SCALA: quattro pioli che separano macchina, build e osservatore.
#
# Sostituisce reap_3bracci.ps1, che aveva un difetto di disegno: confrontava
# l'osservatore acceso contro spento, ma TUTTI i run lenti del 2/8 sera erano
# sulla build col reap dentro e TUTTI i veloci sulla b10227. Build e stato della
# macchina restavano confusi. Qui ogni piolo cambia UNA cosa sola rispetto al
# precedente:
#
#   1  b10227          <- il binario che ha prodotto il riferimento 7,88.
#                          CANCELLO: se non torna, la macchina non e' guarita e
#                          non ha senso misurare altro.
#   2  build reap, osservatore SPENTO   <- differenza col piolo 1 = la BUILD
#   3  build reap, osservatore ACCESO   <- differenza col piolo 2 = l'OSSERVATORE
#   4  b10227                           <- ritorno al piolo 1: quanto e' andata
#                                          alla deriva la macchina nel frattempo
#
# Il piolo 4 e' quello che ieri sera mancava. Senza, una deriva monotona (la
# cache che si scalda run dopo run) si legge come effetto della leva.
#
# Si legge con:  python docs/porto/curva_run.py <log>   -> riga REGIME
# NON il numero finale: e' una media cumulativa che dipende dalla lunghezza
# della corsa. Vedi curva_run.py per il perche'.

param(
    [int]$Tokens = 1500,
    [int]$Quiete = 120
)

$ErrorActionPreference = 'Continue'
$env:LLAMA_ARG_CPU_MOE = '1'

$banco   = Join-Path $PSScriptRoot 'llama_confronto.ps1'
$b10227  = 'D:\llama-b10227\llama-server.exe'
$reapexe = 'D:\llama-dspark\build\bin\llama-server.exe'
$comuni  = @{ Ngl = 99; Tokens = $Tokens; Ctx = 10000; Extra = @('-ncmoe','42') }

function Spegni-Reap {
    'LLAMA_REAP','LLAMA_REAP_PROF','LLAMA_REAP_DUMP' | ForEach-Object {
        if (Test-Path "Env:$_") { Remove-Item "Env:$_" }
    }
}

function Stato-Macchina($quando) {
    # La variabile che il 2/8 sera non era in nessun manifest, e che ha fatto
    # attribuire a un lookup su hash map un -32% che era della macchina.
    $m = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
    $standby = ($m.StandbyCacheNormalPriorityBytes + $m.StandbyCacheCoreBytes +
                $m.StandbyCacheReserveBytes) / 1GB
    $v = (nvidia-smi --query-gpu=memory.used --format=csv,noheader) 2>$null
    '  [{0}] {1:N1} GB disponibile, {2:N1} GB standby, VRAM {3}' -f `
        $quando, ($m.AvailableMBytes/1024), $standby, $v
}

function Piolo($n, $titolo, $exe, $etichetta, $reapOn) {
    Write-Host ""
    Write-Host "=============== PIOLO $n  $titolo ==============="
    Spegni-Reap
    if ($reapOn) {
        $env:LLAMA_REAP      = '1'
        $env:LLAMA_REAP_PROF = '1'
        $env:LLAMA_REAP_DUMP = "D:\ds4_work\llama_run\reap_calore_$etichetta.tsv"
    }
    Write-Host (Stato-Macchina 'prima')
    & $banco @comuni -Exe $exe -Etichetta $etichetta
    Write-Host (Stato-Macchina 'dopo ')
    if ($n -lt 4) {
        Write-Host "  --- quiete $Quiete s ---"
        Start-Sleep -Seconds $Quiete
    }
}

Piolo 1 'b10227, il binario del riferimento (CANCELLO)' $b10227  'scala1_b10227'   $false
Piolo 2 'build reap, osservatore SPENTO'                $reapexe 'scala2_reapoff'  $false
Piolo 3 'build reap, osservatore ACCESO + cronometro'   $reapexe 'scala3_reapon'   $true
Piolo 4 'b10227 di nuovo, per la deriva'                $b10227  'scala4_b10227'   $false

Spegni-Reap
Write-Host ""
Write-Host "=============== FINE, ora la lettura ==============="
Write-Host "  python docs/porto/curva_run.py D:/ds4_work/llama_run/*scala*.server.log"
