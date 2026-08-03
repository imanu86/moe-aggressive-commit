# LA MAPPA DEL CALORE, ORA CON IL RANGO
#
# L'utente il 3/8 definisce la massa su cui tarare il gate SSD->RAM:
#     massa = peso di gating x frequenza di bussata
#
# I pesi veri non sono raggiungibili a costo zero: misurato con
# GGML_SCHED_DEBUG=2, ogni strato fa
#     SPLIT CUDA0   probs -> topk -> weights -> norm -> scale
#     SPLIT CPU     ingressi [ffn_norm] [ffn_moe_topk]   <- SOLO gli id scendono
#                   ffn_moe_gate / up / down
#     SPLIT CUDA0   ingresso [ffn_moe_down]              <- il risultato RISALE
#                   ffn_moe_weighted = esperti x pesi
# Lo scheduler fa risalire il risultato degli esperti (384 KB) invece di far
# scendere i pesi (0 KB). Prenderli costerebbe una lettura sincrona per strato:
# -18% sul prefill, gia' scartato.
#
# Ma l'ORDINE del top-k e' gia' sulla CPU dentro r.id[], e lo buttavamo. Il
# rango 0 e' l'esperto col peso di gating piu' alto, il 5 il piu' marginale.
# reap.cpp ora ne tiene l'istogramma GREZZO -- non una massa gia' pesata,
# perche' quale w(rango) usare e' la domanda a cui questa misura risponde.
#
# La modifica sta tutta nel CONSUMATORE (drena), non nella sezione critica:
# costo aggiunto zero. LLAMA_REAP_PROF=1 lo verifica.
#
# CONTROLLO DI VALIDITA' incorporato: ogni token sceglie esattamente un esperto
# per ciascuna posizione del top-k, quindi i totali per rango devono essere
# uguali fra loro. Il dump stampa `squilibrio_fra_ranghi`, atteso ~0. Se e'
# grande, l'assunzione "r.id[] e' ordinato per peso decrescente" e' falsa e
# l'istogramma non significa quello che crediamo.
#
# CANCELLO DI NEUTRALITA': il regime deve restare ~6,7-6,9 come le due misure
# del 3/8 sullo stesso binario e configurazione.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\mappa_rango.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$log     = 'D:\ds4_work\llama_run\LLAMA_ngl99_mappa_rango.server.log'
$mappa   = 'D:\ds4_work\llama_run\mappa_calore_rango.tsv'

$req = 'D:\ds4_work\llama_run\lunga1500.req.json'
if (-not (Test-Path $req)) {
    '{"temperature":0,"stream":false,"messages":[{"content":"Create a complete single-file HTML landing page for a cyberpunk AI programming shop. Include CSS, navigation, hero, request form, and a JavaScript confirmation popup. Return only the HTML document.","role":"user"}],"model":"ds4","max_tokens":1500}' |
        Out-File $req -Encoding ascii -NoNewline
}

$env:LLAMA_ARG_CPU_MOE = '1'
$env:LLAMA_REAP        = '1'
$env:LLAMA_REAP_PROF   = '1'
$env:LLAMA_REAP_DUMP   = $mappa

Add-Type -Namespace '' -Name CR2 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

$argomenti = @('-m', $MODELLO, '-c','10000', '-ngl','99', '-ncmoe','42',
               '-ub','64', '-b','64', '--port','8161', '--host','127.0.0.1',
               '--no-warmup', '--reasoning-budget','0')

"comando: $($argomenti -join ' ')" | Out-File $out -Append -Encoding utf8
"env: LLAMA_REAP=1 LLAMA_REAP_PROF=1 LLAMA_REAP_DUMP=$mappa" | Out-File $out -Append -Encoding utf8

$srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
        -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

Start-Sleep -Milliseconds 700
if ($srv.PriorityClass -ne 'Normal') {
    "FERMO: priorita' $($srv.PriorityClass)" | Out-File $out -Append -Encoding utf8
} else {
    $pronto = $false
    for ($i = 0; $i -lt 200; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri 'http://127.0.0.1:8161/health' -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if ($pronto) {
        & curl.exe -sS --max-time 7200 -X POST 'http://127.0.0.1:8161/v1/chat/completions' `
            -H 'Content-Type: application/json' --data-binary "@$req" `
            -o 'D:\ds4_work\llama_run\mappa_rango.resp.json' | Out-Null
    } else {
        "il server non e' partito -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 15 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
    }
}

# lo spegnimento grazioso E' quello che fa scattare reap_dump (sta nel clean_up
# del server): con Stop-Process la mappa non viene scritta.
if (-not $srv.HasExited) {
    [void][CR2]::FreeConsole()
    if ([CR2]::AttachConsole([uint32]$srv.Id)) {
        [void][CR2]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CR2]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 15
        [void][CR2]::FreeConsole(); [void][CR2]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $srv.WaitForExit(90000) | Out-Null
}

if (Test-Path $log) {
    Select-String -LiteralPath $log -Pattern 'eval time =|graphs reused|^reap:|reap:' |
        ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
        Out-File $out -Append -Encoding utf8
}
if (Test-Path $mappa) {
    "mappa scritta: $((Get-Item $mappa).Length) byte" | Out-File $out -Append -Encoding utf8
} else {
    "MAPPA NON SCRITTA -- lo spegnimento non ha fatto scattare reap_dump" | Out-File $out -Append -Encoding utf8
}

'FINE' | Out-File $out -Append -Encoding utf8
