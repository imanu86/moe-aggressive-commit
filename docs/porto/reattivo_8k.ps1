# L'ABLAZIONE, E LA CORSA LUNGA: NEURAFORGE A 8000 TOKEN
#
# Due lacune chiuse in un run solo, entrambe sollevate dall'utente.
#
# 1. TUTTE le misure del gate sono da 1500 token sul prompt di campagna, e la
#    corsa e' AUTO-SIMILE: i primi 100 token di una pagina HTML predicono
#    benissimo i 1400 successivi della stessa pagina. E' il caso piu' facile
#    che esista per una politica di residenza. A 8000 token l'insieme di lavoro
#    cresce e la mappa -- che oggi accumula da inizio corsa e non dimentica mai
#    -- invecchia.
#
# 2. E' dimostrato che BLOCCARE aiuta, NON che aiuti bloccare PER MASSA.
#    Se il blocco per sola frequenza rende quanto quello per massa, tutto il
#    lavoro sul rango e' decorazione. L'analisi dice che i primi mille dei due
#    criteri differiscono su 240 esperti; che quella differenza si traduca in
#    prestazione non e' mai stato misurato.
#
# TRE BRACCI, ordine scelto per non favorire nessuno: il controllo sta IN MEZZO,
# cosi' i due bracci col blocco vedono una cache rispettivamente fredda e calda.
#
#   M1  blocco per MASSA        LLAMA_REAP_PESO=ripida    (2^-rango)
#   M0  nessun blocco           controllo
#   M2  blocco per FREQUENZA    LLAMA_REAP_PESO=piatta    (= sola frequenza)
#
# COSA GUARDARE, in ordine:
#   la coda   -- min e frazione di campioni sotto 2 t/s. E' li' che il blocco
#                ha mostrato il suo effetto a 1500 token (mai sotto 2,87
#                contro crolli a 0,51)
#   M1 vs M2  -- se coincidono, la massa non serve e basta la frequenza
#   la deriva -- il regime nell'ultimo terzo contro il primo: se la mappa
#                invecchia, il vantaggio si consuma verso la fine
#
# E il cancello: le uscite dei tre bracci devono essere IDENTICHE bit per bit.
# Il blocco non nega esperti al router, impedisce solo lo sfratto delle pagine:
# se un'uscita differisce, qualcosa non e' come credo.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\reattivo8k.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\reattivo8k_paging.tsv'
"ora`tbraccio`tpage_reads`tpages_in`tram_disp_MB`tvram_MB" | Out-File $camp -Encoding utf8

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'

# il prompt NeuraForge, identico a llama_confronto.ps1: chiede sei schede
# invece di quattro, ed e' quello che ha prodotto la pagina migliore mai vista
$testo = 'Genera una pagina HTML completa single-file per una startup AI NeuraForge, stile cyberpunk neon: head con CSS interno, header con nav, hero, 3 feature card, tabella prezzi 3 tier, form contatti con validazione JS, footer. Codice completo e commentato, molto dettagliato.'
$req = 'D:\ds4_work\llama_run\neuraforge8k.req.json'
$corpo = @{
    temperature = 0; stream = $false; model = 'ds4'; max_tokens = 8000
    messages = @(@{ role = 'user'; content = $testo })
} | ConvertTo-Json -Depth 5 -Compress
[System.IO.File]::WriteAllText($req, $corpo, [System.Text.UTF8Encoding]::new($false))
$sha = [BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash(
    [Text.Encoding]::UTF8.GetBytes($testo))).Replace('-','').ToLower().Substring(0,16)
"prompt NeuraForge, sha $sha, max_tokens 8000, ctx 10000" | Out-File $out -Append -Encoding utf8

Add-Type -Namespace '' -Name CAB -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

# IL DECADIMENTO. Misurato il 4/8: col blocco per massa, a 1500 token il
# minimo era 2,87 t/s e ZERO campioni sotto i 2; a 8000 il minimo scende a 1,12
# e il 2,7% sta sotto i 2. La massa si accumula da inizio corsa e non dimentica
# mai, quindi a fine corsa lunga la mappa descrive una fase che non c'e' piu'.
#
# La media mobile esponenziale sull'incremento fra passate, con alfa:
#   1,0   nessun decadimento (identico a prima, e' il difetto)
#   0,9   emivita ~660 token
#   0,8   emivita ~300 token
#
# Il braccio senza decadimento e' lo STESSO M1 di prima, rifatto qui perche' un
# confronto fra momenti diversi e' l'errore che questa campagna ha gia' fatto
# nove volte.
# LO SWEEP REATTIVO. Osservazione dell'utente: dentro UNA pagina HTML il
# dominio cambia di colpo -- corpo, poi CSS, poi JS, poi di nuovo prosa nei
# commenti -- e con un'emivita da centinaia di token ci si ritrova nella
# configurazione sbagliata proprio al cambio di fase. Serve 50-100 token.
#
# VINCOLO: non si insegue piu' in fretta di quanto si campiona. La politica
# ricalcola ogni PERIODO record, e l'emivita non puo' scendere sotto quello.
#   emivita_token = periodo_token x ln(0,5)/ln(alfa)
# Con PERIODO a 100 token il minimo raggiungibile e' 100 (alfa 0,5). Per
# arrivare a 50 servono ENTRAMBE le manopole giu'.
#
# Qui PERIODO = 3.225 record = 25 token (43 strati x 3 nodi x 25):
#   alfa 0,707 -> emivita  50 token
#   alfa 0,841 -> emivita 100 token
# piu' il riferimento allo stesso periodo ma senza decadimento, per separare
# l'effetto del PERIODO da quello dell'ALFA.
#
# Rischio da guardare: ad alta reattivita' l'insieme sbatte, e ogni blocco e
# sblocco costa. A 8000 token con la politica lenta gia' comparivano 47-72
# fallimenti di VirtualLock; qui potrebbero moltiplicarsi.
$bracci = @(
    @{ n='E00_p25_nodecad'; porta=8211; lock='1'; peso='ripida'; dec='1.0';   per='3225' }
    @{ n='E50_emivita50';   porta=8212; lock='1'; peso='ripida'; dec='0.707'; per='3225' }
    @{ n='E100_emivita100'; porta=8213; lock='1'; peso='ripida'; dec='0.841'; per='3225' }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_ngl99_$($b.n).server.log"

    $env:LLAMA_ARG_CPU_MOE = '1'
    $env:LLAMA_REAP        = '1'
    $env:LLAMA_REAP_PROF   = '1'
    $env:LLAMA_REAP_TOPK   = '1200'
    $env:LLAMA_REAP_PESO   = $b.peso
    $env:LLAMA_REAP_DECADIMENTO = $b.dec
    $env:LLAMA_REAP_PERIODO     = $b.per
    Remove-Item Env:LLAMA_REAP_PREFETCH -EA SilentlyContinue
    if ($b.lock) { $env:LLAMA_REAP_LOCK = $b.lock } else { Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue }
    "LOCK=$(if ($b.lock) { '1' } else { 'spento' })  PESO=$($b.peso)  TOPK=1200  DECADIMENTO=$($b.dec)  PERIODO=$($b.per) record" |
        Out-File $out -Append -Encoding utf8

    $argomenti = @('-m', $MODELLO, '-c','10000', '-ngl','99', '-ncmoe','42',
                   '-ub','64', '-b','64', '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0')

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.PriorityClass -ne 'Normal') {
        "FERMO: priorita' $($srv.PriorityClass)" | Out-File $out -Append -Encoding utf8; continue
    }

    $pronto = $false
    for ($i = 0; $i -lt 200; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "il server non e' partito -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 15 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        continue
    }

    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','14400','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json',
            '--data-binary', "@$req",
            '-o', "D:\ds4_work\llama_run\abl_$($b.n).resp.json")

    while (-not $c.HasExited) {
        Start-Sleep -Seconds 15
        $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
        $v = (nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) 2>$null
        "{0}`t{1}`t{2}`t{3}`t{4}`t{5}" -f (Get-Date -Format 'HH:mm:ss'), $b.n,
            $m.PageReadsPerSec, $m.PagesInputPerSec, $m.AvailableMBytes, $v |
            Out-File $camp -Append -Encoding utf8
    }

    if (-not $srv.HasExited) {
        [void][CAB]::FreeConsole()
        if ([CAB]::AttachConsole([uint32]$srv.Id)) {
            [void][CAB]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
            [void][CAB]::GenerateConsoleCtrlEvent(0, 0)
            Start-Sleep -Seconds 15
            [void][CAB]::FreeConsole(); [void][CAB]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
        }
        $srv.WaitForExit(120000) | Out-Null
    }

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|graphs reused|reap:' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue
Remove-Item Env:LLAMA_REAP_PESO -EA SilentlyContinue
Remove-Item Env:LLAMA_REAP_DECADIMENTO -EA SilentlyContinue
Remove-Item Env:LLAMA_REAP_PERIODO -EA SilentlyContinue
'FINE' | Out-File $out -Append -Encoding utf8
