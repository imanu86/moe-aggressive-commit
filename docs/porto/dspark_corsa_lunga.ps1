# DSPARK SULLA CORSA LUNGA: IL RUN CHE NON ABBIAMO MAI FATTO
#
# Buco trovato dall'utente il 3/8: TUTTI i run speculativi della campagna sono
# da 300 token o meno (S2, T2, T3, U1, W1, W2, e i 120 di Fable). E il verdetto
# "DSpark perde" e' stato dato su quelli -- violando la regola scritta la notte
# prima, che sta in curva_run.py e in memoria:
#
#   la media cumulativa di llama.cpp dipende dalla lunghezza della corsa.
#   Il controllo stesso fa 4,24 t/s a 300 token e 6,90 di REGIME a 1500.
#
# E c'e' una ragione specifica per cui il verdetto potrebbe ribaltarsi:
# L'ACCETTAZIONE CRESCE CON LA LUNGHEZZA DELLA CORSA.
#
#   120 token   accettazione 0,503   (misura di Fable)
#   300 token   accettazione 0,636
#   1500        ?
#
# Se sale ancora, salgono i token per ciclo, e il costo fisso del ciclo si
# spalma su piu' token. E' l'unica variabile che gioca a favore della
# speculazione e non l'abbiamo mai spinta.
#
# DUE BRACCI, stessa configurazione buona, unica differenza il draft.
# 1500 token, ctx 10000 -- gli stessi della misura di regime del binario.
#
#   L0  controllo:  -ngl 99 -ncmoe 42 -ub 64 -b 64
#   L1  DSpark:     idem + draft Q2Kfix, -ngld 99 -cmoed, n-max 5
#
# Il verdetto si legge col REGIME (mediana tg_3s in 500-800), non col numero
# finale:  python docs/porto/curva_run.py <log>
#
# NOTA sul banco: llama_confronto.ps1 NON e' utilizzabile sotto Utilita' di
# pianificazione -- stampa con Write-Host, che senza console fallisce con
# "Handle non valido" e uccide il braccio. Il run del regime del 3/8 ci ha
# perso il braccio di controllo. Qui si scrive solo con Out-File.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\dspark_lunga.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$DRAFT   = 'D:\ds4-models\DSpark-draft-Q2Kfix.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'

# stesso prompt di campagna di tutti gli altri run, 1500 token
$req = 'D:\ds4_work\llama_run\lunga1500.req.json'
@'
{"temperature":0,"stream":false,"messages":[{"content":"Create a complete single-file HTML landing page for a cyberpunk AI programming shop. Include CSS, navigation, hero, request form, and a JavaScript confirmation popup. Return only the HTML document.","role":"user"}],"model":"ds4","max_tokens":1500}
'@.Trim() | Out-File $req -Encoding ascii -NoNewline

Add-Type -Namespace '' -Name CL -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Spegni($p) {
    if ($null -eq $p -or $p.HasExited) { return }
    [void][CL]::FreeConsole()
    if ([CL]::AttachConsole([uint32]$p.Id)) {
        [void][CL]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CL]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][CL]::FreeConsole(); [void][CL]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $p.WaitForExit(60000) | Out-Null
}

$bracci = @(
    @{ n='L0_controllo'; porta=8141; extra=@() }
    @{ n='L1_dspark';    porta=8142
       extra=@('-md', $DRAFT, '--spec-type','draft-dspark','-ngld','99','-cmoed','--spec-draft-n-max','5') }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    # il nome del log e' quello che curva_run.py sa leggere
    $log = "D:\ds4_work\llama_run\LLAMA_ngl99_$($b.n)_lunga.server.log"
    $env:LLAMA_ARG_CPU_MOE = '1'

    $argomenti = @('-m', $MODELLO, '-c','10000', '-ngl','99', '-ncmoe','42',
                   '-ub','64', '-b','64',
                   '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0') + $b.extra

    "comando: $($argomenti -join ' ')" | Out-File $out -Append -Encoding utf8
    "log:     $log"                     | Out-File $out -Append -Encoding utf8

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.PriorityClass -ne 'Normal') {
        "FERMO: priorita' $($srv.PriorityClass), non Normal" | Out-File $out -Append -Encoding utf8
        Spegni $srv; continue
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
        Spegni $srv; continue
    }

    $d = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    $s = (Get-Counter -Counter '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "VRAM dedicata $([math]::Round($d.CookedValue/1MB)) condivisa $([math]::Round($s.CookedValue/1MB)) MiB" |
        Out-File $out -Append -Encoding utf8
    $m = Get-CimInstance Win32_OperatingSystem
    "RAM libera: $([math]::Round($m.FreePhysicalMemory/1024)) MiB" | Out-File $out -Append -Encoding utf8

    & curl.exe -sS --max-time 7200 -X POST "http://127.0.0.1:$($b.porta)/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" `
        -o "D:\ds4_work\llama_run\dspark_lunga_$($b.n).resp.json" | Out-Null

    Spegni $srv

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|graphs reused|acceptance|prompt eval time' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    # quiete lunga: il protocollo di igiene del 30/7 dice 300 s, 20 s danno
    # una tempesta di sfratti
    Start-Sleep -Seconds 300
}

'FINE' | Out-File $out -Append -Encoding utf8
