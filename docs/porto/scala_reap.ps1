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
    [int]$Quiete = 120,
    # Quali pioli fare. Serve a riprendere una scala interrotta senza rifare
    # quelli gia' a terra: -Pioli 2,3,4
    [int[]]$Pioli = @(1,2,3,4)
)

$ErrorActionPreference = 'Continue'
$env:LLAMA_ARG_CPU_MOE = '1'

$banco   = Join-Path $PSScriptRoot 'llama_confronto.ps1'
$b10227  = 'D:\llama-b10227\llama-server.exe'
# Era D:\llama-dspark\build\bin\llama-server.exe, cioe' il ramo dspark-dsv4 di
# YanissAmz: un fork, mentre il riferimento era il binario ufficiale. DSpark era
# gia' accantonato come funzione; la base era rimasta per inerzia, e valeva ~-21%.
# Ora e' un worktree su b10227 (f5919bf) con le sole patch del reap.
$reapexe = 'D:\llama-vanilla\build\bin\llama-server.exe'
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

# Campionatore di memoria: gira DURANTE il run e scrive una riga ogni 10 s.
#
# Serve a rispondere con una misura, non con un'opinione, alla domanda "il
# modello da 80,76 GiB su 64 GB di RAM sta strangolando il sistema?". Il numero
# che conta per l'esaurimento e' il COMMIT, non il working set: con mmap le
# pagine del modello sono file-backed e pulite, finiscono in standby e non
# consumano commit. Se il commit resta lontano dal limite, l'ipotesi cade.
function Avvia-Campionatore($percorso) {
    $codice = {
        param($out)
        "ora`tdisponibile_GB`tstandby_GB`tcommit_GB`tlimite_GB`tllama_WS_GB" |
            Out-File $out -Encoding utf8
        while ($true) {
            $m  = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
            $os = Get-CimInstance Win32_OperatingSystem
            $p  = Get-Process llama-server -ErrorAction SilentlyContinue |
                    Select-Object -First 1
            '{0}`t{1:N1}`t{2:N1}`t{3:N1}`t{4:N1}`t{5:N1}' -f (Get-Date -Format 'HH:mm:ss'),
                ($m.AvailableMBytes/1024),
                (($m.StandbyCacheNormalPriorityBytes+$m.StandbyCacheCoreBytes+
                  $m.StandbyCacheReserveBytes)/1GB),
                (($os.TotalVirtualMemorySize-$os.FreeVirtualMemory)/1MB),
                ($os.TotalVirtualMemorySize/1MB),
                $(if($p){$p.WorkingSet64/1GB}else{0}) | Out-File $out -Append -Encoding utf8
            Start-Sleep -Seconds 10
        }
    }
    Start-Job -ScriptBlock $codice -ArgumentList $percorso
}

function Piolo($n, $titolo, $exe, $etichetta, $reapOn) {
    if ($Pioli -notcontains $n) { return }
    Write-Host ""
    Write-Host "=============== PIOLO $n  $titolo ==============="
    Spegni-Reap
    if ($reapOn) {
        $env:LLAMA_REAP      = '1'
        $env:LLAMA_REAP_PROF = '1'
        $env:LLAMA_REAP_DUMP = "D:\ds4_work\llama_run\reap_calore_$etichetta.tsv"
    }
    Write-Host (Stato-Macchina 'prima')
    $campionatore = Avvia-Campionatore "D:\ds4_work\llama_run\memoria_$etichetta.tsv"
    try   { & $banco @comuni -Exe $exe -Etichetta $etichetta }
    finally {
        Stop-Job $campionatore -ErrorAction SilentlyContinue
        Remove-Job $campionatore -Force -ErrorAction SilentlyContinue
    }
    Write-Host (Stato-Macchina 'dopo ')
    if ($n -lt ($Pioli | Measure-Object -Maximum).Maximum) {
        Write-Host "  --- quiete $Quiete s ---"
        Start-Sleep -Seconds $Quiete
    }
}

Piolo 1 'b10227 ufficiale, il riferimento (CANCELLO)'   $b10227  'van1_b10227'  $false
Piolo 2 'vanilla nostro, osservatore SPENTO'            $reapexe 'van2_reapoff' $false
Piolo 3 'vanilla nostro, osservatore ACCESO + cronometro' $reapexe 'van3_reapon' $true
Piolo 4 'b10227 ufficiale di nuovo, per la deriva'      $b10227  'van4_b10227'  $false

Spegni-Reap
Write-Host ""
Write-Host "=============== FINE, ora la lettura ==============="
Write-Host "  python docs/porto/curva_run.py D:/ds4_work/llama_run/*scala*.server.log"
