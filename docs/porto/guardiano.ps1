# IL GUARDIANO: un poll che NON muore con la sessione.
#
# PERCHE'. Due volte il 12/8 la campagna e' rimasta senza sorveglianza: la prima
# perche' il processo era figlio della sessione e la sessione e' morta, la
# seconda perche' l'orchestratore aspettava un marcatore che nessuno scriveva e
# non c'era modo di sapere se stesse lavorando o fosse appeso. Questo script non
# lancia niente e non decide niente: guarda, e scrive una riga sola in un posto
# fisso. Chiunque -- io, l'utente, un'altra sessione -- legge stato.txt e sa.
#
# VA LANCIATO STACCATO, come i bracci:
#   Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
#       CommandLine = 'powershell -NoProfile -ExecutionPolicy Bypass -File ...guardiano.ps1' }
#
# COSA SCRIVE, in stato.txt (sovrascritto, non accodato: si legge l'ULTIMO
# stato, non la storia -- la storia sta gia' in regista.txt):
#   l'ora, se la campagna e' viva, il braccio in corso e da quanto,
#   i contatori che contano ADESSO (prenotati/scartati: la diagnosi del
#   12/8 dice che e' li' che si vede se l'anello e' inceppato), la VRAM,
#   e la tabella dei bracci gia' chiusi.
#
# E RILEVA L'INCAGLIO. Un braccio che non produce da piu' di SOGLIA_FERMO
# minuti viene marcato ***FERMO***: e' il caso che il 12/8 e' costato 25 minuti
# di campagna con un server orfano che teneva 74,5 GB.
$ErrorActionPreference = 'Continue'
$run = 'D:\ds4_work\llama_run'
$reg = Join-Path $run 'regista.txt'
$tab = Join-Path $run 'tabella.txt'
$sta = Join-Path $run 'stato.txt'
$SOGLIA_FERMO = 20      # minuti senza nuove righe nel regista

function Ultimo([string]$f, [int]$n) {
    if (Test-Path $f) { return @(Get-Content $f -EA SilentlyContinue | Select-Object -Last $n) }
    return @()
}

for ($giro = 0; $giro -lt 2000; $giro++) {
    $ora = [DateTime]::Now
    $righe = @()
    $righe += "STATO alle " + $ora.ToString('yyyy-MM-dd HH:mm:ss') + "   (giro " + $giro + ")"
    $righe += ""

    # 1. chi e' vivo
    $srv = @(Get-Process -Name llama-server -EA SilentlyContinue)
    $ps  = @(Get-Process -Name powershell -EA SilentlyContinue)
    $vram = '-'
    try { $vram = ((& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) | Select-Object -First 1) } catch { }
    $righe += ("  llama-server: " + $srv.Count + " vivi   powershell: " + $ps.Count + "   VRAM: " + $vram + " MiB")

    # 2. a che punto e' la campagna
    $ultime = Ultimo $reg 3
    $finita = $false
    # IL BANNER, non la parola. Select-String e' case-insensitive di difetto e la
    # riga di ogni braccio contiene "finita 15.5%" (la quota di copie gia'
    # concluse al join): cercare 'FINITA' faceva uscire il guardiano al PRIMO
    # braccio chiuso, cioe' proprio quando serviva.
    if (Test-Path $reg) { $finita = @(Select-String -Path $reg -Pattern '===== FINITA' -EA SilentlyContinue).Count -gt 0 }
    $eta = '-'
    if (Test-Path $reg) {
        $m = (Get-Item $reg).LastWriteTime
        $eta = [math]::Round(($ora - $m).TotalMinutes, 1)
    }
    $righe += ("  regista: ultima riga " + $eta + " min fa" + $(if ($finita) { "   ===== CAMPAGNA FINITA =====" } else { "" }))
    if (-not $finita -and $eta -ne '-' -and [double]$eta -gt $SOGLIA_FERMO) {
        $righe += ("  *** FERMO da " + $eta + " min: nessuna riga nuova. Braccio incagliato o orchestratore morto. ***")
    }
    $righe += ""
    foreach ($r in $ultime) { $righe += ("  | " + $r) }

    # 3. i contatori che contano ADESSO, dal log del braccio in corso
    $righe += ""
    $log = @(Get-ChildItem $run -Filter '*.server.log' -EA SilentlyContinue |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1)
    if ($log.Count -gt 0) {
        $L = $log[0]
        $righe += ("  log corrente: " + $L.Name + "  (scritto " + [math]::Round(($ora - $L.LastWriteTime).TotalSeconds) + " s fa)")
        function M([string]$pat) {
            $x = Select-String -Path $L.FullName -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
            if ($x) { return $x.Matches[0].Groups[1].Value } else { return '-' } }
        $righe += ("     prenotati " + (M 'prefetch prenotati ([0-9]+)') +
                   "   scartati " + (M 'prenotati [0-9]+, saltati [0-9]+, scartati ([0-9]+)') +
                   "   colpi " + (M 'cache-esperti: domanda [0-9]+ \(colpi [0-9]+ = ([0-9.]+)%') + "%")
        $righe += ("     prefetch DEVICE: batch " + (M 'prefetch DEVICE -> batch serviti=([0-9]+)') +
                   "   esperti " + (M 'batch serviti=[0-9]+, esperti in anticipo=([0-9]+)'))
        $righe += ("     t/s " + (M '\|        eval time =.*?([0-9.]+) tokens per second'))
        $err = Select-String -Path $L.FullName -Pattern 'CUDA error|out of memory' -EA SilentlyContinue | Select-Object -Last 1
        if ($err) { $righe += ("     *** " + $err.Line.Trim() + " ***") }
    }

    # 4. i bracci gia' chiusi
    $t = Ultimo $tab 12
    if ($t.Count -gt 0) {
        $righe += ""
        $righe += "  TABELLA:"
        foreach ($r in $t) { $righe += ("  " + $r) }
    }

    $righe | Out-File -FilePath $sta -Encoding utf8
    if ($finita) {
        ("[" + $ora.ToString('HH:mm:ss') + "] guardiano: campagna finita, esco") | Out-File -FilePath $sta -Append -Encoding utf8
        break
    }
    Start-Sleep -Seconds 60
}
