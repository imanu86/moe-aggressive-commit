# IL NUOVO SOTA, MISURATO PER DAVVERO: SEI CORSE DA 8K APPAIATE
#
# Finora ogni confronto e' n=1, e la varianza fra run IDENTICI e' misurata a
# +-7,6% (D10 ha fatto 6,50 dove M1, stessa identica configurazione, aveva
# fatto 6,04 tre ore prima). Con un effetto atteso del 7-9%, un confronto solo
# non basta a dichiarare niente.
#
# DISEGNO. Tre coppie, con l'ordine INVERTITO fra una coppia e l'altra:
#
#     1 controllo   2 GATE       <- il gate secondo
#     3 GATE        4 controllo  <- il gate primo
#     5 controllo   6 GATE       <- il gate secondo
#
# Cosi' la deriva lenta della macchina (cache, temperatura, frammentazione)
# entra in tutte e due le condizioni allo stesso modo invece di essere assunta
# assente. E si analizzano le DIFFERENZE DENTRO LE COPPIE, non le medie
# assolute: una coppia dura ~45 minuti, dentro i quali la macchina e' la
# stessa.
#
# CONDIZIONI, unica variabile il gate:
#   controllo   LLAMA_REAP=1, nessun blocco   (l'osservatore c'e' in entrambi,
#               cosi' il suo ~1% non entra nel confronto)
#   GATE        + LOCK, TOPK=1200, PESO=ripida, DECADIMENTO=1.0
#
# Il decadimento resta spento: falsificato il 4/8 (perde 12-17% e triplica la
# rotazione).
#
# COSA SI GUARDA:
#   la differenza dentro ogni coppia, tre volte -> se e' sempre dello stesso
#     segno e della stessa taglia, e' un effetto
#   la coda (min, p10, frazione sotto 2 t/s), dove l'effetto era gia' molto
#     oltre il rumore
#   l'identita' bit per bit di tutte e sei le uscite: se una differisce,
#     qualcosa non e' come credo
#
# Durata: ~2h15m. Le corse sono da 8000 token richiesti (~5.822 prodotti).

$ErrorActionPreference = 'Continue'
$out  = 'D:\ds4_work\llama_run\sota8k.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\sota8k_paging.tsv'
"ora`tbraccio`tpage_reads`tpages_in`tram_disp_MB`tvram_MB" | Out-File $camp -Encoding utf8

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'

$testo = 'Genera una pagina HTML completa single-file per una startup AI NeuraForge, stile cyberpunk neon: head con CSS interno, header con nav, hero, 3 feature card, tabella prezzi 3 tier, form contatti con validazione JS, footer. Codice completo e commentato, molto dettagliato.'
$req = 'D:\ds4_work\llama_run\neuraforge8k.req.json'
$corpo = @{
    temperature = 0; stream = $false; model = 'ds4'; max_tokens = 8000
    messages = @(@{ role = 'user'; content = $testo })
} | ConvertTo-Json -Depth 5 -Compress
[System.IO.File]::WriteAllText($req, $corpo, [System.Text.UTF8Encoding]::new($false))

Add-Type -Namespace '' -Name CST -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

# coppia 1: controllo poi gate | coppia 2: gate poi controllo | coppia 3: come la 1
$bracci = @(
    @{ n='C1_controllo'; porta=8221; lock=$null }
    @{ n='G1_gate';      porta=8222; lock='1'  }
    @{ n='G2_gate';      porta=8223; lock='1'  }
    @{ n='C2_controllo'; porta=8224; lock=$null }
    @{ n='C3_controllo'; porta=8225; lock=$null }
    @{ n='G3_gate';      porta=8226; lock='1'  }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_ngl99_$($b.n).server.log"

    $env:LLAMA_ARG_CPU_MOE      = '1'
    $env:LLAMA_REAP             = '1'
    $env:LLAMA_REAP_PROF        = '1'
    $env:LLAMA_REAP_TOPK        = '1200'
    $env:LLAMA_REAP_PESO        = 'ripida'
    $env:LLAMA_REAP_DECADIMENTO = '1.0'
    Remove-Item Env:LLAMA_REAP_PREFETCH -EA SilentlyContinue
    Remove-Item Env:LLAMA_REAP_PERIODO  -EA SilentlyContinue
    if ($b.lock) { $env:LLAMA_REAP_LOCK = '1' } else { Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue }
    "GATE=$(if ($b.lock) { 'ACCESO' } else { 'spento' })  TOPK=1200 PESO=ripida DECAD=1.0  $(Get-Date -Format 'HH:mm:ss')" |
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
            '-o', "D:\ds4_work\llama_run\sota_$($b.n).resp.json")

    while (-not $c.HasExited) {
        Start-Sleep -Seconds 15
        $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
        $v = (nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) 2>$null
        "{0}`t{1}`t{2}`t{3}`t{4}`t{5}" -f (Get-Date -Format 'HH:mm:ss'), $b.n,
            $m.PageReadsPerSec, $m.PagesInputPerSec, $m.AvailableMBytes, $v |
            Out-File $camp -Append -Encoding utf8
    }

    if (-not $srv.HasExited) {
        [void][CST]::FreeConsole()
        if ([CST]::AttachConsole([uint32]$srv.Id)) {
            [void][CST]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
            [void][CST]::GenerateConsoleCtrlEvent(0, 0)
            Start-Sleep -Seconds 15
            [void][CST]::FreeConsole(); [void][CST]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
        }
        $srv.WaitForExit(120000) | Out-Null
    }

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|graphs reused|reap: politica' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue
'FINE' | Out-File $out -Append -Encoding utf8
