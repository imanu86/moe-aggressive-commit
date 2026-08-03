# PERCHE' IL DRAFT COSTA UN SECONDO A CICLO
#
# Dal confronto A/B del 3/8 si ricava che il ciclo di draft costa ~1.000 ms
# sulla 3060. Un modello da 6,8 GB su quella scheda non puo' costare tanto:
# a 360 GB/s lo leggerebbe intero in 19 ms. Quindi il tempo NON e' calcolo.
#
# Il log del braccio B dice gia' due cose:
#
#   graphs reused =    8      (contro 294 del braccio A)
#   [spec] failed to measure draft model memory
#
# Il fork costruisce grafi da 34.054 nodi (misurato il 3/8 su -lv 10). Se in
# speculazione il grafo si ricostruisce a ogni passata, quel lavoro e' CPU pura
# con la GPU ferma -- che e' esattamente cio' che l'utente vede sul monitor.
#
# TRE IPOTESI, TRE BRACCI A VARIABILE SINGOLA:
#
#   R0  sonda -lv 10 sulla configurazione B, 8 token
#       -> dove finiscono i byte: bersaglio, draft, KV, compute, condivisa
#
#   R1  come il braccio A (senza draft) ma con LLAMA_GRAPH_REUSE_DISABLE=1
#       -> costo di ricostruire il grafo, ISOLATO dalla speculazione.
#          Confronto: A faceva 388,69 ms/token riusando 294 grafi su 300.
#
#   R2  come il braccio B (draft caricato) ma con --spec-draft-n-max 0
#       -> il draft occupa la VRAM ma non abbozza: separa il COSTO DI PRESENZA
#          (travaso, pressione) dal COSTO DI CALCOLO del draft.
#
# Aritmetica finale:
#   costo ricostruzione grafo = R1 - A
#   costo presenza del draft  = R2 - A
#   costo calcolo del draft   = B - R2   (a parita' di token prodotti)

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\draft_perche.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$req   = 'D:\ds4_work\llama_run\spec_vero.req.json'
$sonda = 'D:\ds4_work\llama_run\sonda8.req.json'
(Get-Content $req -Raw -Encoding UTF8) -replace '"max_tokens":300', '"max_tokens":8' |
    Out-File $sonda -Encoding ascii -NoNewline

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$DRAFT   = 'D:\ds4-models\DSpark-draft-Q2K.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'

Add-Type -Namespace '' -Name CD -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Spegni($p) {
    if ($null -eq $p -or $p.HasExited) { return }
    [void][CD]::FreeConsole()
    if ([CD]::AttachConsole([uint32]$p.Id)) {
        [void][CD]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CD]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][CD]::FreeConsole(); [void][CD]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $p.WaitForExit(30000) | Out-Null
}

function Vram {
    $d = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    $s = (Get-Counter -Counter '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    return @{ ded = [math]::Round($d.CookedValue/1MB); cond = [math]::Round($s.CookedValue/1MB) }
}

$SPEC = @('-md', $DRAFT, '--spec-type', 'draft-dspark', '-ngld', '99')

$bracci = @(
    @{ n='R0_sonda_lv10'; porta=8081; tok=$sonda; lv='10'
       extra = $SPEC + @('--spec-draft-n-max','5'); env=@{} }

    @{ n='R1_grafo_no_riuso'; porta=8082; tok=$req; lv='3'
       extra = @(); env=@{ LLAMA_GRAPH_REUSE_DISABLE='1' } }

    @{ n='R2_draft_fermo'; porta=8083; tok=$req; lv='3'
       extra = $SPEC + @('--spec-draft-n-max','0'); env=@{} }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\dperche_$($b.n).log"

    foreach ($k in $b.env.Keys) { Set-Item -Path "Env:$k" -Value $b.env[$k] }
    $env:LLAMA_ARG_CPU_MOE = '1'

    $argomenti = @('-m', $MODELLO, '-c','4096', '-ngl','22', '-ub','64', '-b','64',
                   '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0', '-lv', $b.lv) + $b.extra

    "comando: $($argomenti -join ' ')" | Out-File $out -Append -Encoding utf8
    foreach ($k in $b.env.Keys) { "env: $k=$($b.env[$k])" | Out-File $out -Append -Encoding utf8 }

    $v0 = Vram
    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.PriorityClass -ne 'Normal') {
        "FERMO: priorita' $($srv.PriorityClass), non Normal" | Out-File $out -Append -Encoding utf8
        Spegni $srv
        foreach ($k in $b.env.Keys) { Remove-Item -Path "Env:$k" -EA SilentlyContinue }
        continue
    }

    $pronto = $false
    for ($i = 0; $i -lt 150; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "il server non e' partito" | Out-File $out -Append -Encoding utf8
        Spegni $srv
        foreach ($k in $b.env.Keys) { Remove-Item -Path "Env:$k" -EA SilentlyContinue }
        continue
    }

    $v1 = Vram
    "VRAM a riposo   dedicata $($v0.ded) condivisa $($v0.cond) MiB" | Out-File $out -Append -Encoding utf8
    "VRAM caricato   dedicata $($v1.ded) condivisa $($v1.cond) MiB" | Out-File $out -Append -Encoding utf8

    # la richiesta parte staccata, cosi' posso campionare la VRAM mentre genera
    $resp = "D:\ds4_work\llama_run\dperche_$($b.n).resp.json"
    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','3600','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json',
            '--data-binary', "@$($b.tok)", '-o', $resp)

    $picco_d = 0; $picco_c = 0
    while (-not $c.HasExited) {
        Start-Sleep -Seconds 6
        $v = Vram
        if ($v.ded  -gt $picco_d) { $picco_d = $v.ded }
        if ($v.cond -gt $picco_c) { $picco_c = $v.cond }
    }
    "VRAM in corsa   dedicata $picco_d condivisa $picco_c MiB (picco)" | Out-File $out -Append -Encoding utf8

    Spegni $srv
    foreach ($k in $b.env.Keys) { Remove-Item -Path "Env:$k" -EA SilentlyContinue }

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|graphs reused|acceptance|graph reuse disabled' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8

        # solo per la sonda: la ripartizione dei buffer
        if ($b.lv -eq '10') {
            "--- allocazioni ---" | Out-File $out -Append -Encoding utf8
            Select-String -LiteralPath $log -Pattern 'buffer size|KV self|kv cache|compute buffer|model buffer|offloaded|graph nodes|nodes =|reserving|free memory target|reduce device memory' |
                ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } | Select-Object -First 60 |
                Out-File $out -Append -Encoding utf8
        }
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 45
}

'FINE' | Out-File $out -Append -Encoding utf8
