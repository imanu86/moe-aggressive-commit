# LA CACHE E' SENSIBILE AL DOMINIO? (e il -23% era un fantasma?)
#
# LA CACCIA, e dove ha svoltato
# ------------------------------
# Ho passato un'ora a cercare nel codice una regressione da -23%:
#
#     oggi   cache SPENTA  7,96 t/s      cache ACCESA  6,48   (-18%)
#     5/8    metro         8,04          cache         9,26   (+15%)
#
# Escluso tutto: la mia patch (BATCH=1 riproduce il cancello vecchio ed e'
# ancora 6,48), il termico (52 C, zero throttle reasons), la cornice (la
# relazione dice llama-server, come oggi). Restava la sonda dell'altra chat.
#
# Poi ho letto la relazione fino in fondo, e le due corse NON hanno lo stesso
# carico:
#
#     5/8   prompt 62 token, SAGGIO IN PROSA ITALIANA (navigazione fenicia)
#     oggi  prompt 70 token, GENERAZIONE DI CODICE HTML/CSS/JS (NeuraForge)
#
# E il registro dice gia' che il dominio governa il routing: al cambio dominio
# 141k sfratti contro 0 (cross-request-residency-domain-boundary). Se la cache
# rende in prosa e non in codice, non c'e' nessuna regressione: c'e' una
# proprieta' della cache che non avevamo mai misurato, e io stavo confrontando
# due carichi diversi chiamandoli lo stesso esperimento.
#
# IL DISEGNO, a variabile singola sul dominio
# --------------------------------------------
#     F1  cache ACCESA + prosa    <- se ~9,2, il -23% e' un fantasma
#     F2  cache ACCESA + codice   <- gia' misurato 3 volte a 6,48, qui ripetuto
#                                    nella stessa sessione per confrontabilita'
#     F3  cache SPENTA  + prosa   <- il metro in prosa: serve per sapere se e'
#                                    la CACHE a dipendere dal dominio o tutto
#
# F3 e' il braccio che distingue le due letture. Il metro in codice oggi e'
# 7,96 e quello storico in prosa era 8,04: se F3 li conferma entrambi, allora
# il dominio non tocca il decode di base e tocca SOLO la cache -- che e' il
# risultato interessante. Se F3 divergesse, si sposta tutto.
$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\dominio.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$EXE = 'D:\llama-dspark\build\bin\llama-server.exe'
$MOD = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$R   = 'D:\ds4_work\llama_run'
$b   = [char]92
$ESP = 'ffn_(gate|up|down)_exps' + $b + '.weight=CUDA0_Mapped'

$bracci = @(
    @{ n='F1_cache_prosa';  slot=380; req='par_prosa'; d='cache ACCESA + prosa -- il carico del 9,26' },
    @{ n='F2_cache_codice'; slot=380; req='par_p1';    d='cache ACCESA + codice -- il carico di oggi (atteso 6,48)' },
    @{ n='F3_metro_prosa';  slot=0;   req='par_prosa'; d='cache SPENTA + prosa -- il dominio tocca solo la cache?' }
)
$porta = 8571
foreach ($x in $bracci) {
    "=============== $($x.n) -- $($x.d) ===============" | Out-File $out -Append -Encoding utf8
    $log = "$R\DOM_$($x.n).log"
    $ram = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB
    "  [condizione] RAM libera {0:N1} GiB" -f $ram | Out-File $out -Append -Encoding utf8
    if ($ram -lt 10) { "  SCARTATO" | Out-File $out -Append -Encoding utf8; continue }

    $env:LLAMA_MAPPED_IBRIDO       = '1'
    $env:LLAMA_REAP                = '0'
    $env:LLAMA_CACHE_ESPERTI_SLOT  = "$($x.slot)"
    $env:LLAMA_CACHE_ESPERTI_W     = '0'
    $env:LLAMA_CACHE_ESPERTI_BATCH = '1'
    $env:GGML_SCHED_PROFILO        = '1'

    $a = @('-m',$MOD,'-c','10000','-np','1','-ngl','99','-ot',$ESP,
           '-ub','64','-b','64','-t','8','--port',"$porta",'--host','127.0.0.1',
           '--no-warmup','--no-mmap','--reasoning-budget','0')
    $srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -WindowStyle Minimized `
            -RedirectStandardError $log -RedirectStandardOutput ($log + '.out')
    $pronto = $false
    for ($i=0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 10
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto=$true; break } catch {}
    }
    if (-not $pronto) { "  NON PARTE" | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
        Start-Sleep 45; $porta++; continue }

    $d = (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "  VRAM {0:N0} MiB, liberi {1:N0}" -f ($d.CookedValue/1MB), (12288 - $d.CookedValue/1MB) |
        Out-File $out -Append -Encoding utf8

    # DUE richieste identiche, come la corsa storica: R1 a cache fredda, R2 calda.
    # Il 9,26 era R2, e io oggi ho sempre misurato solo R1: un'altra differenza
    # che avevo ignorato.
    #
    # NB: il contatore si chiama $rip e NON $r. In PowerShell i nomi di variabile
    # NON distinguono maiuscole da minuscole, quindi "foreach ($r in 1,2)"
    # SOVRASCRIVE $R, la directory -- e il primo giro ha costruito
    # "@1\par_prosa.req.json". curl con -s ha fallito in silenzio, il server e'
    # rimasto in ascolto senza ricevere niente, e lo script ha scritto zero righe
    # invece di un errore. Un'ora di macchina buttata da un maiuscolo.
    foreach ($rip in 1,2) {
        $risp = "$R\dom_$($x.n)_R$rip.json"
        $reqf = "$R\$($x.req).req.json"
        if (-not (Test-Path $reqf)) {
            "  ERRORE: richiesta assente: $reqf" | Out-File $out -Append -Encoding utf8; continue
        }
        & curl.exe -s --max-time 900 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
            -H 'Content-Type: application/json' --data-binary "@$reqf" -o $risp | Out-Null
        if (-not (Test-Path $risp)) {
            "  ERRORE: curl non ha prodotto risposta (uscita $LASTEXITCODE)" | Out-File $out -Append -Encoding utf8; continue
        }
        $j = Get-Content $risp -Raw | ConvertFrom-Json
        if (-not $j.timings) {
            "  ERRORE: risposta senza timings: " + (Get-Content $risp -Raw).Substring(0,200) |
                Out-File $out -Append -Encoding utf8; continue
        }
        "  R{0}: prefill {1,6:N2}   decode {2,6:N2} t/s   {3:N2} ms/tok   {4} tok" -f `
            $rip, $j.timings.prompt_per_second, $j.timings.predicted_per_second,
            $j.timings.predicted_per_token_ms, $j.usage.completion_tokens |
            Out-File $out -Append -Encoding utf8
    }
    Select-String -Path $log -Pattern 'cache-esperti: domanda|sched-profilo' | Select-Object -Last 2 |
        ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8

    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep 10
    Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
    Start-Sleep 60
    "" | Out-File $out -Append -Encoding utf8
    $porta++
}
'FINE' | Out-File $out -Append -Encoding utf8
