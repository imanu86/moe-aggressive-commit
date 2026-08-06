# IL PEDAGGIO DEI CONFINI: da pavimento a valore
#
# DOVE SIAMO
# ----------
# La sonda sull'ibrido (F3) ha dato 86,9 split/grafo -- i 2x43+1 predetti -- e
# calc CPU 63,95 ms contro i 62-65 attesi dal costo del calcolo esperti. Da li'
# il pedaggio e' stato stimato per differenza:
#
#     65,55 (calc CPU marginale) - 62,4 (kernel puri dai FLOP) = 3,15 ms/token
#                                                              = ~72 us/confine
#
# Ma e' un PAVIMENTO, non un valore: un pedaggio nascosto dentro `ingressi` non
# era escluso, era solo non misurato. L'"incrocio" che sembrava sigillarlo era
# un'identita' algebrica (il residuo fuori-loop era definito COME residuo).
#
# COSA CAMBIA ADESSO
# ------------------
# Il timer di Fable (7d10c74) separa dentro `ingressi` il tempo di SYNC da
# quello di COPIA, escludendo i percorsi a eventi CUDA-CUDA che non sono il
# confine in esame. Sulla configurazione cache ha gia' parlato: ingressi 83,6
# di cui sync 82,0, cioe' il 98% e' attesa pura e le copie sono 1,6 ms.
#
# Ma quella e' la configurazione a 5 split, dove la CPU non calcola niente. La
# misura che serve al pricing e' l'IBRIDO: 87 confini, esperti su CPU.
#
#     se sync(marginale) ~ attesa-GPU e il resto sono copie
#         -> il pavimento 3,15 diventa valore chiuso
#     se sync eccede l'attesa-GPU plausibile
#         -> il pedaggio nascosto dentro ingressi ha finalmente un numero
#
# IL METODO: FINESTRA MARGINALE, non cumulato
# --------------------------------------------
# Le stampe sono cumulative e i primi grafi portano ~11 s di transitorio
# (spillover del prefill drenato dal primo sync, piu' primo tocco delle 74 GiB
# mappate). Il cumulato da 140,6 ms/grafo contro i 126,3 del token: impossibile.
# La finestra marginale fra due stampe lontane toglie il transitorio, e la sua
# somma DEVE stare sotto il tempo del token -- quello e' il vincolo vero.
#
# Servono due stampe ben distanziate: 600 token danno 12 stampe (una ogni 50
# grafi), quindi la finestra si puo' prendere in coda dove il regime e' pulito.
#
# I DUE BRACCI, appaiati nella stessa sessione (come vuole il discriminatore
# robusto: il rapporto fra gemelli, non le soglie assolute)
#   H1  ibrido, cache SPENTA   87 confini, esperti su CPU  <- QUELLO CHE SERVE
#   H2  cache ACCESA            5 confini, esperti su GPU  <- il gemello
$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\confini.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$EXE = 'D:\llama-dspark\build\bin\llama-server.exe'
$MOD = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$R   = 'D:\ds4_work\llama_run'
$b   = [char]92
$ESP = 'ffn_(gate|up|down)_exps' + $b + '.weight=CUDA0_Mapped'

$bracci = @(
    @{ n='H1_ibrido';  slot=0;   d='ibrido, cache SPENTA -- 87 confini, esperti su CPU' },
    @{ n='H2_cache';   slot=380; d='cache accesa -- 5 confini, il gemello' }
)
$porta = 8631
foreach ($x in $bracci) {
    "=============== $($x.n) -- $($x.d) ===============" | Out-File $out -Append -Encoding utf8
    $log = "$R\CNF_$($x.n).log"
    $ram = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB
    "  [condizione] RAM libera {0:N1} GiB" -f $ram | Out-File $out -Append -Encoding utf8
    if ($ram -lt 10) { "  SCARTATO" | Out-File $out -Append -Encoding utf8; continue }

    $env:LLAMA_MAPPED_IBRIDO         = '1'
    $env:LLAMA_REAP                  = '0'
    $env:LLAMA_CACHE_ESPERTI_SLOT    = "$($x.slot)"
    $env:LLAMA_CACHE_ESPERTI_W       = '0'
    $env:LLAMA_CACHE_ESPERTI_BATCH   = '8'
    $env:LLAMA_CACHE_ESPERTI_BATTITO = '5'
    $env:GGML_SCHED_PROFILO          = '1'

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

    # DUE richieste da 300: 600 grafi = 12 stampe della sonda, e la finestra
    # marginale si prende in coda dove il transitorio e' finito da un pezzo.
    foreach ($rip in 1,2) {
        $risp = "$R\cnf_$($x.n)_R$rip.json"
        & curl.exe -s --max-time 900 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
            -H 'Content-Type: application/json' --data-binary "@$R\par_p1.req.json" -o $risp | Out-Null
        if (-not (Test-Path $risp)) { "  ERRORE: nessuna risposta R$rip" | Out-File $out -Append -Encoding utf8; continue }
        $j = Get-Content $risp -Raw | ConvertFrom-Json
        if (-not $j.timings) { "  ERRORE: risposta senza timings" | Out-File $out -Append -Encoding utf8; continue }
        "  R{0}: decode {1,6:N2} t/s   {2:N2} ms/token" -f `
            $rip, $j.timings.predicted_per_second, $j.timings.predicted_per_token_ms |
            Out-File $out -Append -Encoding utf8
    }
    # TUTTE le stampe della sonda: la finestra marginale si calcola offline
    # scegliendo due punti lontani dal transitorio.
    "  --- stampe della sonda (per la finestra marginale) ---" | Out-File $out -Append -Encoding utf8
    Select-String -Path $log -Pattern 'sched-profilo' |
        ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8
    Select-String -Path $log -Pattern 'cache-esperti: domanda' | Select-Object -Last 1 |
        ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8

    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep 10
    Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
    Start-Sleep 60
    "" | Out-File $out -Append -Encoding utf8
    $porta++
}
'FINE' | Out-File $out -Append -Encoding utf8
