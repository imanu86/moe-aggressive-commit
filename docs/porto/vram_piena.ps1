# RIEMPIRE LA VRAM, E SPINGERE GLI STRATI MAPPATI
#
# Osservazione dell'utente: restano sempre ~1,5 GB di VRAM non allocati che non
# si riempiono mai. E' vero, ed e' un difetto di GRANULARITA':
#
#   libero in VRAM            1.544 MiB
#   uno strato di esperti     1.728 MiB     <- 184 MiB troppo grande
#
# llama.cpp alloca per unita' intere: con -ngl 99 mette in VRAM tutto cio' che
# non e' esperto, poi si ferma perche' il pezzo successivo non ci sta. Quel
# margine resta li' per sempre.
#
# L'argomento dell'utente per riempirlo e' piu' forte del guadagno di calcolo:
# uno strato in VRAM SPARISCE DALLA RAM (1.728 MiB restituiti) e NON PUO' MAI
# FAULTARE. E' la stessa logica del pinned, sulla memoria migliore. Il calcolo
# in se' vale ~0,7%, sotto il rumore; il resto no.
#
# COME SI FA POSTO: -ub 32 invece di 64. Il compute buffer scende (a ctx 4096
# era 1.264 MiB con -ub 64) e lo strato entra. Costa sul PREFILL, che nel banco
# e' di 74 token e non conta.
#
# -ub 32 IN TUTTI I BRACCI, altrimenti il confronto avrebbe due variabili.
#
# TRE BRACCI:
#   Y0  17 mappati, VRAM come capita        <- riferimento dentro il run
#   Y1  17 mappati + 1 strato in VRAM       <- l'effetto del riempire
#   Y2  22 mappati + 1 strato in VRAM       <- l'effetto di mappare di piu'
#
# Y2 porta il pinned da 28,7 a 37,1 GiB: restano ~22 GiB per il sistema e per i
# 20 strati ancora su CPU (34,6 GiB). Se il pinned si mangia piu' di quanto
# renda, Y2 andra' PEGGIO di Y1 -- ed e' un risultato, non un fallimento.
#
# CANCELLO: dopo il caricamento si legge la memoria CONDIVISA. Se lo strato in
# VRAM non ci sta davvero, sborda li' -- ed e' il disastro che con -ub 512
# costava il 50%. Sopra 1 GiB il braccio va buttato.

$ErrorActionPreference = 'Continue'
$out  = 'D:\ds4_work\llama_run\vrampiena.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\vrampiena_paging.tsv'
"ora`tbraccio`tpage_reads`tpages_in`tram_disp_MB`tvram_MB`tcond_MB" | Out-File $camp -Encoding utf8

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$req     = 'D:\ds4_work\llama_run\neuraforge8k.req.json'

Add-Type -Namespace '' -Name CVP -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

$ESP = 'ffn_(gate|up|down)_exps\.weight'
$bracci = @(
    @{ n='Y0_17map';        porta=8271; ot = "blk\.([0-9]|1[0-6])\.$ESP=CUDA0_Mapped,$ESP=CPU" }
    @{ n='Y1_17map_1vram';  porta=8272; ot = "blk\.17\.$ESP=CUDA0,blk\.([0-9]|1[0-6])\.$ESP=CUDA0_Mapped,$ESP=CPU" }
    @{ n='Y2_22map_1vram';  porta=8273; ot = "blk\.22\.$ESP=CUDA0,blk\.([0-9]|1[0-9]|2[01])\.$ESP=CUDA0_Mapped,$ESP=CPU" }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_$($b.n).server.log"
    "-ot $($b.ot)   $(Get-Date -Format 'HH:mm:ss')" | Out-File $out -Append -Encoding utf8

    Remove-Item Env:LLAMA_ARG_CPU_MOE -EA SilentlyContinue
    $env:LLAMA_REAP             = '1'
    $env:LLAMA_REAP_PROF        = '1'
    $env:LLAMA_REAP_LOCK        = '1'
    $env:LLAMA_REAP_TOPK        = '1200'
    $env:LLAMA_REAP_PESO        = 'ripida'
    $env:LLAMA_REAP_DECADIMENTO = '1.0'
    Remove-Item Env:LLAMA_REAP_AMMISSIONE -EA SilentlyContinue
    Remove-Item Env:LLAMA_REAP_PREFETCH   -EA SilentlyContinue
    Remove-Item Env:LLAMA_REAP_PERIODO    -EA SilentlyContinue

    $argomenti = @('-m', $MODELLO, '-c','10000', '-ngl','99', '-ot', $b.ot,
                   '-ub','32', '-b','32', '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0')

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.PriorityClass -ne 'Normal') {
        "FERMO: priorita' $($srv.PriorityClass)" | Out-File $out -Append -Encoding utf8; continue
    }

    $pronto = $false
    for ($i = 0; $i -lt 300; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "IL SERVER NON E' PARTITO -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 25 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        continue
    }

    # CANCELLO: se lo strato in VRAM non ci sta, sborda in condivisa
    $d = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    $s = (Get-Counter -Counter '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    $dedMB  = [math]::Round($d.CookedValue/1MB)
    $condMB = [math]::Round($s.CookedValue/1MB)
    "VRAM dedicata $dedMB MiB   condivisa $condMB MiB" | Out-File $out -Append -Encoding utf8
    # la condivisa e' alta per costruzione nei bracci mappati (i 28-37 GiB
    # mappati ci compaiono dentro), quindi il cancello guarda la DEDICATA:
    # se ha sfondato, il driver ha gia' spostato roba fuori
    if ($dedMB -gt 12000) {
        "ATTENZIONE: dedicata a $dedMB MiB, al limite della scheda -- possibile travaso" |
            Out-File $out -Append -Encoding utf8
    }

    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','14400','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json',
            '--data-binary', "@$req", '-o', "D:\ds4_work\llama_run\vp_$($b.n).resp.json")

    while (-not $c.HasExited) {
        Start-Sleep -Seconds 15
        $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
        $v = (nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) 2>$null
        $sh = (Get-Counter -Counter '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue).CounterSamples |
              Sort-Object CookedValue -Descending | Select-Object -First 1
        "{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}" -f (Get-Date -Format 'HH:mm:ss'), $b.n,
            $m.PageReadsPerSec, $m.PagesInputPerSec, $m.AvailableMBytes, $v,
            [math]::Round($sh.CookedValue/1MB) | Out-File $camp -Append -Encoding utf8
    }

    if (-not $srv.HasExited) {
        [void][CVP]::FreeConsole()
        if ([CVP]::AttachConsole([uint32]$srv.Id)) {
            [void][CVP]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
            [void][CVP]::GenerateConsoleCtrlEvent(0, 0)
            Start-Sleep -Seconds 15
            [void][CVP]::FreeConsole(); [void][CVP]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
        }
        $srv.WaitForExit(120000) | Out-Null
    }

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|mappati host|model buffer size|compute buffer size|reap: politica' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue
'FINE' | Out-File $out -Append -Encoding utf8
