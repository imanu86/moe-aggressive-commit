# LA SOGLIA E' UNA PROPRIETA' DEL MODELLO O DI QUESTO PROMPT?
#
# La prima mappa per rango (3/8 sera) dice che il 90% della massa sta in 2.381
# esperti su 11.008, cioe' 15,7 GB invece dei 25,8 che servirebbero contando le
# sole bussate. Ma e' la mappa di UNA landing page HTML.
#
# A ledger sta gia' il contro-esempio: al cambio di dominio gli sfratti passano
# da 0 a 141.000, un fattore 161 (cross-request-residency, 30/7). E la radice
# documentata del collasso wide e' il dominio-di-calibrazione della mask.
#
# Quindi prima di fissare qualunque soglia servono altre mappe. Due domini
# scelti il piu' lontano possibile dal primo E fra loro:
#
#   campagna   landing page HTML cyberpunk   (gia' misurata: 9.032 esperti)
#   prosa      saggio storico in italiano    (nessun codice, altra lingua)
#   codice     albero rosso-nero in C        (codice di sistema, niente markup)
#
# COSA DECIDE:
#   se i primi N per massa coincidono in larga parte fra i domini, la soglia e'
#     una proprieta' del MODELLO e il gate puo' avere una parte statica;
#   se differiscono, il gate dev'essere tutto dinamico -- che e' comunque il
#     disegno dell'utente ("appena diventano rilevanti si portano in ram") -- e
#     la misura dice quanto churn dovra' reggere, cioe' la costante di tempo
#     dell'ammissione.
#
# In nessuno dei due casi il disegno cade: cambia quanto lavoro deve fare.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\mappe_domini.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'

Add-Type -Namespace '' -Name CD3 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

$domini = @(
    @{ n='prosa';  porta=8171
       testo='Scrivi un saggio dettagliato sulle cause economiche e politiche della crisi del 1929, con particolare attenzione al ruolo del sistema bancario, alla speculazione azionaria e alle risposte politiche adottate nei diversi paesi. Argomenta in modo articolato.' }
    @{ n='codice'; porta=8172
       testo='Write a complete C implementation of a red-black tree supporting insertion, deletion and in-order traversal. Include the rotation helpers and comment every rebalancing case. Return only the C source.' }
)

foreach ($d in $domini) {
    "=============== $($d.n) ===============" | Out-File $out -Append -Encoding utf8

    $req   = "D:\ds4_work\llama_run\dom_$($d.n).req.json"
    $log   = "D:\ds4_work\llama_run\LLAMA_ngl99_dom_$($d.n).server.log"
    $mappa = "D:\ds4_work\llama_run\mappa_calore_rango_$($d.n)1500.tsv"

    # il JSON si costruisce con ConvertTo-Json: il testo contiene virgolette e
    # accenti, e concatenarlo a mano e' come si producono i prompt rotti che poi
    # invalidano il confronto senza dirlo
    $corpo = @{
        temperature = 0
        stream      = $false
        model       = 'ds4'
        max_tokens  = 1500
        messages    = @(@{ role = 'user'; content = $d.testo })
    } | ConvertTo-Json -Depth 5 -Compress
    [System.IO.File]::WriteAllText($req, $corpo, [System.Text.UTF8Encoding]::new($false))

    $sha = [BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash(
        [Text.Encoding]::UTF8.GetBytes($d.testo))).Replace('-','').ToLower().Substring(0,16)
    "prompt sha $sha" | Out-File $out -Append -Encoding utf8

    $env:LLAMA_ARG_CPU_MOE = '1'
    $env:LLAMA_REAP        = '1'
    $env:LLAMA_REAP_PROF   = '1'
    $env:LLAMA_REAP_DUMP   = $mappa

    $argomenti = @('-m', $MODELLO, '-c','10000', '-ngl','99', '-ncmoe','42',
                   '-ub','64', '-b','64', '--port', "$($d.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0')

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.PriorityClass -ne 'Normal') {
        "FERMO: priorita' $($srv.PriorityClass)" | Out-File $out -Append -Encoding utf8
        continue
    }

    $pronto = $false
    for ($i = 0; $i -lt 200; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($d.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "il server non e' partito -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 15 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
    } else {
        & curl.exe -sS --max-time 7200 -X POST "http://127.0.0.1:$($d.porta)/v1/chat/completions" `
            -H 'Content-Type: application/json' --data-binary "@$req" `
            -o "D:\ds4_work\llama_run\dom_$($d.n).resp.json" | Out-Null
    }

    # lo spegnimento grazioso E' quello che fa scattare reap_dump
    if (-not $srv.HasExited) {
        [void][CD3]::FreeConsole()
        if ([CD3]::AttachConsole([uint32]$srv.Id)) {
            [void][CD3]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
            [void][CD3]::GenerateConsoleCtrlEvent(0, 0)
            Start-Sleep -Seconds 15
            [void][CD3]::FreeConsole(); [void][CD3]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
        }
        $srv.WaitForExit(90000) | Out-Null
    }

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|graphs reused|reap:' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    if (Test-Path $mappa) {
        "mappa: $((Get-Item $mappa).Length) byte" | Out-File $out -Append -Encoding utf8
    } else {
        "MAPPA NON SCRITTA" | Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

'FINE' | Out-File $out -Append -Encoding utf8
