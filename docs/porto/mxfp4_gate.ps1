# IL MODELLO CHE NON ENTRA, E IL PRIMO COLLAUDO VERO DEL GATE
#
# Riscritto il 5/8 dopo aver letto per intero reap-loop/docs/INTUITION_REGISTER.md
# e BOOT_PROBE_DESIGN.md. Tre correzioni alla versione precedente, tutte dai
# documenti dell'utente. Il ragionamento sta in PIANO_GATE_MODELLO_CHE_NON_ENTRA.md.
#
# IL MODELLO
# ----------
# DeepSeek-V4-Flash-0731-IQ2_XS-IQ3_XXS-GateUp-MXFP4-Down-Q8_0, 112,1 GiB:
#   gate/up   IQ2_XS (strati 0-17) e IQ3_XXS (18-42)   -- codebook
#   down      MXFP4 NATIVO                             -- a blocchi
#   non-esperte  Q8_0
#
# DUE DOMANDE IN UNA CORSA
#   1. un terzo degli esperti si spacchetta con uno shift invece che con una
#      tabella: il decode va piu' veloce pur leggendo PIU' byte?
#   2. il gate sa scegliere chi sta nei 96 GB quando il modello ne vuole 112?
#
# L'ARITMETICA (corretta -- prima avevo scritto "quasi il doppio del margine")
#   modello               112,1 GiB      RAM   95,9      fuori  ~16,2 = 14,5%
#   riserva sistema/KV     ~12   GiB
#   esperti che entrano   ~78%
#   esperti mai toccati    25,2%   ->   domanda  74,8%
# 78 contro 74,8. Il margine c'e' ma e' stretto: il gate deve essere BUONO.
#
# CORREZIONE 1 -- mmap ACCESO, non --no-mmap
# ------------------------------------------
# Su un modello che NON entra, --no-mmap rende anonimi i 16 GiB di troppo: li
# sostiene il pagefile, quindi ogni sfratto e' una SCRITTURA e poi una lettura.
# Con mmap le pagine degli esperti sono pulite (file-backed): lo sfratto e'
# gratis e il page-in legge dal GGUF. Dimezza l'I/O per costruzione.
# VirtualLock funziona lo stesso su una vista mappata -- e' quello che fa --mlock.
# (--no-mmap resta obbligatorio nel regime PRECEDENTE, modello che entra +
# pinning, dove serve a evitare la doppia residenza. E' regime-dipendente.)
#
# CORREZIONE 2 -- il braccio che mancava: TOPK grande
# ---------------------------------------------------
# TOPK 1200 blocca ~11 GiB su 112 e lascia il 90% del problema a Windows: e' un
# mezzo esperimento. Il braccio-tesi blocca quanto ci sta (~7.500 esperti,
# ~72 GiB) e chiede al gate di fare l'unica cosa per cui esiste -- decidere CHI
# sta in RAM.
#
# CORREZIONE 3 -- il WRAP, e il contatore di copertura
# ----------------------------------------------------
# VirtualLock e' un page-in sincrono: seriale e' una coda profonda UNO, misurata
# 0,314 GiB/s contro 2,10 a 4 vie (BOOT_PROBE_DESIGN §3). Bloccare 72 GiB in
# serie sono 3,8 minuti dentro il thread della politica; a 8 thread ~35 s.
# LLAMA_REAP_THREADS=8.
# E il gate ora riporta un ESITO e non un'INTENZIONE: COPERTURA = delle
# selezioni vere del router, quante hanno trovato l'esperto gia' bloccato.
# Senza quel numero questo A/B direbbe solo "t/s su o giu'".
#
# ORDINE: la tesi (M3) per PRIMA sulla macchina piu' fredda, il controllo senza
# gate DOPO con la cache piu' calda. L'ordine lavora contro cio' che mi aspetto.
#
# CONFRONTO VALIDO SOLO SUL DECODE: M4 gira in ibrido (prefill su GPU), i bracci
# del misto no -- 106 GiB di esperti non stanno in cudaHostAlloc. Il prefill dei
# due modelli non e' confrontabile, il decode si' (in entrambi e' su CPU).

$ErrorActionPreference = 'Continue'
$out  = 'D:\ds4_work\llama_run\mxfp4.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\mxfp4_camp.tsv'
"ora`tbraccio`tpage_reads`tpages_in`tram_disp_MB" | Out-File $camp -Encoding utf8

$NUOVO   = 'C:\ds4-models\DS4-0731-GateUp-MXFP4Down.gguf'
$VECCHIO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$req     = 'D:\ds4_work\llama_run\neuraforge1200.req.json'
$esp     = 'ffn_(gate|up|down)_exps' + [char]92 + '.weight'

# IL METRO ERA ROTTO (corretto dall'utente, 5/8). La prima versione confrontava
# i bracci del misto (mmap + -ot=CPU) con un braccio del vecchio in IBRIDO e
# --no-mmap: DUE variabili in piu' oltre al formato dei pesi. Se il misto avesse
# vinto non si sarebbe saputo perche'.
#
# Ora ci sono DUE metri:
#   M0  il vecchio nella configurazione IDENTICA ai nuovi -> l'unica cosa che
#       cambia fra M0 e M1 e' il formato dei pesi. E' il confronto che vale.
#   M4  il vecchio in ibrido --no-mmap -> l'aggancio al 7,45 t/s storico, per
#       sapere quanto costa la configurazione stessa.
$bracci = @(
    @{ n='M3_topk7500';   m=$NUOVO;   gate=$true;  topk=7500; mmap=$true;  ib=$false; ot=($esp + '=CPU') }
    @{ n='M2_topk1200';   m=$NUOVO;   gate=$true;  topk=1200; mmap=$true;  ib=$false; ot=($esp + '=CPU') }
    @{ n='M1_senzagate';  m=$NUOVO;   gate=$false; topk=0;    mmap=$true;  ib=$false; ot=($esp + '=CPU') }
    @{ n='M0_metro_stessaconf'; m=$VECCHIO; gate=$false; topk=0; mmap=$true; ib=$false; ot=($esp + '=CPU') }
    @{ n='M4_metro_ibrido'; m=$VECCHIO; gate=$false; topk=0;  mmap=$false; ib=$true;  ot=($esp + '=CUDA0_Mapped') }
)

$porta = 8341
foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_$($b.n).server.log"

    # l'ibrido SOLO dove c'e' qualcosa da mappare. Sui bracci -ot=CPU il flag e'
    # inerte (non esistono buffer CUDA0_Mapped su cui agire) ma lasciarlo acceso
    # rende il manifesto bugiardo, e un manifesto bugiardo e' come si perdono le
    # attribuzioni.
    $env:LLAMA_MAPPED_IBRIDO = $(if ($b.ib) { '1' } else { '0' })
    if ($b.gate) {
        $env:LLAMA_REAP      = '1'
        $env:LLAMA_REAP_PROF = '1'
        $env:LLAMA_REAP_LOCK = '1'
        $env:LLAMA_REAP_TOPK = "$($b.topk)"
        $env:LLAMA_REAP_PESO = 'ripida'
        $env:LLAMA_REAP_DECADIMENTO = '1.0'
        $env:LLAMA_REAP_THREADS = '8'
        # una passata ogni 64 token (43 record per token), non ogni 300: su una
        # corsa da 1200 il difetto lasciava il gate spento per un quarto del run
        $env:LLAMA_REAP_PERIODO = '2752'
    } else {
        # il gate spento MA l'osservatore acceso: senza, il braccio di controllo
        # non produce la mappa del calore e non si puo' dire quanto ERA
        # copribile. Costa ~40 ns a chiamata (misurato).
        $env:LLAMA_REAP      = '1'
        $env:LLAMA_REAP_LOCK = '0'
        $env:LLAMA_REAP_PROF = '1'
        Remove-Item Env:\LLAMA_REAP_TOPK -EA SilentlyContinue
        Remove-Item Env:\LLAMA_REAP_PERIODO -EA SilentlyContinue
    }

    $a = @('-m',$b.m,'-c','10000','-ngl','99','-ot',$b.ot,'-ub','64','-b','64',
           '-t','8','--port',"$porta",'--host','127.0.0.1',
           '--no-warmup','--reasoning-budget','0')
    if (-not $b.mmap) { $a += '--no-mmap' }

    $srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -WindowStyle Minimized `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out"

    # con mmap il caricamento non legge il file: dovrebbe essere veloce. Con
    # --no-mmap (solo M4) sono 80 GiB da leggere. 25 minuti di pazienza per
    # entrambi.
    $pronto = $false
    for ($i = 0; $i -lt 150; $i++) {
        Start-Sleep -Seconds 10
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "NON E' PARTITO:" | Out-File $out -Append -Encoding utf8
        Select-String -Path $log -Pattern 'failed|error|cudaHostAlloc' | Select-Object -Last 3 |
            ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Start-Sleep -Seconds 60
        $porta++
        continue
    }

    $m0 = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
    "  caricato: RAM disp {0:N1} GiB   pages input/s {1}" -f ($m0.AvailableMBytes/1024), $m0.PagesInputPerSec |
        Out-File $out -Append -Encoding utf8

    $risp = "D:\ds4_work\llama_run\mx_$($b.n).resp.json"
    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','2400','-X','POST',"http://127.0.0.1:$porta/v1/chat/completions",
            '-H','Content-Type: application/json','--data-binary',"@$req",'-o',$risp)
    while (-not $c.HasExited) {
        Start-Sleep -Seconds 15
        $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
        "{0}`t{1}`t{2}`t{3}`t{4}" -f (Get-Date -Format 'HH:mm:ss'), $b.n,
            $m.PageReadsPerSec, $m.PagesInputPerSec, $m.AvailableMBytes | Out-File $camp -Append -Encoding utf8
    }

    if (Test-Path $risp) {
        $j = Get-Content $risp -Raw | ConvertFrom-Json
        $t = $j.timings
        $cc = $j.choices[0].message.content
        $r = ($cc -split "`n") | Where-Object { $_.Trim().Length -gt 20 } | ForEach-Object { $_.Trim() }
        $rip = if ($r.Count) { ($r | Group-Object | Sort-Object Count -Desc | Select-Object -First 1).Count } else { 0 }
        "  prefill {0,7:N2} ms/tok  {1,6:N2} t/s" -f $t.prompt_per_token_ms, $t.prompt_per_second | Out-File $out -Append -Encoding utf8
        "  decode  {0,7:N2} ms/tok  {1,6:N2} t/s  ({2} tok)" -f $t.predicted_per_token_ms, $t.predicted_per_second, $t.predicted_n | Out-File $out -Append -Encoding utf8
        "  {0} car, ripetizione {1} -- {2}" -f $cc.Length, $rip, $(if ($rip -lt 8) {'SANO'} else {'DEGENERATO, IL t/s NON VALE'}) | Out-File $out -Append -Encoding utf8
        # l'uscita va SALVATA: senza testo il cancello di neutralita' non e'
        # verificabile (regola 1/8)
        $cc | Out-File "D:\ds4_work\llama_run\mx_$($b.n).output.html" -Encoding utf8
    }

    # llama-server e' un processo CONSOLE: CloseMainWindow non lo chiude (provato
    # nel collaudo del 5/8, il dump non girava mai). Quindi la copertura si
    # stampa a ogni passata e qui si puo' uccidere senza perdere niente.
    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep -Seconds 10

    # L'ESITO DEL GATE, non l'intenzione
    "  --- il gate ---" | Out-File $out -Append -Encoding utf8
    # la PRIMA passata (il costo del page-in a freddo, dove si vede il WRAP) e le
    # ULTIME tre (dove la copertura e' a regime)
    $pass = Select-String -Path $log -Pattern 'reap: passata'
    if ($pass) {
        ($pass | Select-Object -First 1) + ($pass | Select-Object -Last 3) |
            ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } |
            Out-File $out -Append -Encoding utf8
        "  ({0} passate in totale)" -f $pass.Count | Out-File $out -Append -Encoding utf8
    }
    Select-String -Path $log -Pattern 'quota|VirtualLock|esperti distinti|COPERTURA non' |
        Select-Object -Last 4 | ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } |
        Out-File $out -Append -Encoding utf8

    Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
    Start-Sleep -Seconds 90     # QUIETE: la cache si assesta fra i bracci
    "" | Out-File $out -Append -Encoding utf8
    $porta++
}

'FINE' | Out-File $out -Append -Encoding utf8
