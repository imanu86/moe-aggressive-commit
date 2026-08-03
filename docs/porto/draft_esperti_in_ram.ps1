# IL DRAFT NON DEVE STARE IN VRAM: NE TOCCA IL 3%
#
# La sonda -lv 10 del 3/8 ha dato i numeri che mancavano:
#
#   bersaglio (22 strati) su CUDA0    3.905 MiB    grafo 34.066 nodi
#   compute buffer del bersaglio      1.276 MiB
#   DRAFT su CUDA0                    6.831 MiB    grafo  2.074 nodi
#   compute buffer del draft             33 MiB
#   VRAM: dedicata 11.935  CONDIVISA 1.233 MiB    <- traboccava
#
# E l'architettura del draft:
#
#   n_layer = 3      n_expert = 256   n_expert_used = 6 (+1 condiviso)
#   expert_ffn = 2048   n_embd = 4096   6,68 GiB a 2,89 bpw
#
# Attivi per passata: 3 x 7 x (3 x 4096 x 2048) = ~529 M di esperti, piu'
# l'attenzione: ~650 M parametri = ~235 MB letti. Il draft occupa 6,8 GB per
# IMMAGAZZINARE 256 esperti e ne tocca il 3% a passata.
#
# Quei 6,8 GB in VRAM erano il vero costo della speculazione: per fargli posto
# si tolgono venti strati di backbone (2,57 invece di 7,21) E per giunta si
# traboccava di 1,2 GB in memoria condivisa.
#
# LA CURA: -cmoed mette in RAM SOLO gli esperti del draft. Attenzione, testa e
# grafo restano sulla GPU (costano ~150 MiB). Il backbone riprende tutti i suoi
# strati.
#
# ARITMETICA DELLA SOGLIA (dal modello di costo misurato il 3/8):
#   passata 108 ms, token 30 ms  ->  verifica di 5+1 = 288 ms per ciclo
#   token per ciclo 4,76 (300 token / 63 cicli, misurati)
#   pareggio col controllo (138,7 ms/token) se il draft costa < 372 ms
#   a 41,6 ms/GB, 235 MB costano ~10 ms
#
# TRE BRACCI, un solo cambio per volta rispetto al riferimento ufficiale:
#
#   S1  controllo: -ngl 99 -ncmoe 42 -ub 64, SENZA draft
#   S2  cura:      idem + draft con -cmoed (esperti del draft in RAM)
#   S3  estremo:   idem + draft tutto in RAM (-ngld 0), se S2 non entra

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\draft_in_ram.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$req     = 'D:\ds4_work\llama_run\spec_vero.req.json'
$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$DRAFT   = 'D:\ds4-models\DSpark-draft-Q2K.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'

Add-Type -Namespace '' -Name CR -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

function Spegni($p) {
    if ($null -eq $p -or $p.HasExited) { return }
    [void][CR]::FreeConsole()
    if ([CR]::AttachConsole([uint32]$p.Id)) {
        [void][CR]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CR]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][CR]::FreeConsole(); [void][CR]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
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

$SPEC = @('-md', $DRAFT, '--spec-type', 'draft-dspark', '--spec-draft-n-max', '5')

$bracci = @(
    @{ n='S1_controllo';      porta=8091; extra=@() }
    @{ n='S2_esperti_in_ram'; porta=8092; extra=$SPEC + @('-ngld','99','-cmoed') }
    @{ n='S3_draft_in_ram';   porta=8093; extra=$SPEC + @('-ngld','0') }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\dram_$($b.n).log"

    $env:LLAMA_ARG_CPU_MOE = '1'

    $argomenti = @('-m', $MODELLO, '-c','4096', '-ngl','99', '-ncmoe','42',
                   '-ub','64', '-b','64',
                   '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0') + $b.extra

    "comando: $($argomenti -join ' ')" | Out-File $out -Append -Encoding utf8

    # memoria di sistema PRIMA: il draft in RAM compete col page cache degli esperti
    $m0 = Get-CimInstance Win32_OperatingSystem
    "RAM libera prima: $([math]::Round($m0.FreePhysicalMemory/1024)) MiB" | Out-File $out -Append -Encoding utf8

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.PriorityClass -ne 'Normal') {
        "FERMO: priorita' $($srv.PriorityClass), non Normal" | Out-File $out -Append -Encoding utf8
        Spegni $srv; continue
    }

    $pronto = $false
    for ($i = 0; $i -lt 180; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "il server non e' partito -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 12 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        Spegni $srv; continue
    }

    $v1 = Vram
    $m1 = Get-CimInstance Win32_OperatingSystem
    "VRAM caricato   dedicata $($v1.ded) condivisa $($v1.cond) MiB" | Out-File $out -Append -Encoding utf8
    "RAM libera dopo: $([math]::Round($m1.FreePhysicalMemory/1024)) MiB" | Out-File $out -Append -Encoding utf8

    $resp = "D:\ds4_work\llama_run\dram_$($b.n).resp.json"
    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','3600','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json',
            '--data-binary', "@$req", '-o', $resp)

    $picco_d = 0; $picco_c = 0
    while (-not $c.HasExited) {
        Start-Sleep -Seconds 6
        $v = Vram
        if ($v.ded  -gt $picco_d) { $picco_d = $v.ded }
        if ($v.cond -gt $picco_c) { $picco_c = $v.cond }
    }
    "VRAM in corsa   dedicata $picco_d condivisa $picco_c MiB (picco)" | Out-File $out -Append -Encoding utf8

    Spegni $srv

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|graphs reused|acceptance' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 45
}

'FINE' | Out-File $out -Append -Encoding utf8
