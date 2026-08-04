# Q1: TUTTO IN RAM, E QUINDI NIENTE DA PAGINARE
#
# L'idea e' dell'utente: se il modello ci sta INTERO in RAM, il problema non si
# ottimizza -- sparisce. Niente fault duri, niente sfratti, niente buchi.
#
#   DS4-0731-IQ2XXS            80,76 GiB   NON ci sta nei 63,9
#   IQ1_S-XL-merged            57,31 GiB   CI STA
#
# AVVERTENZA DICHIARATA: l'IQ1_S e' un checkpoint PIU' VECCHIO, non il 0731.
# Quindi questo run
#   PUO' dire   con tutto in RAM i fault duri vanno a zero? e quanto rende?
#               (architettura e taglia sono quelle, la fisica del paging pure)
#   NON PUO'    quanto costa Q1 in qualita' rispetto al nostro Q2: confonderebbe
#               checkpoint e quantizzazione in un numero solo
#
# DUE BRACCI, e il secondo e' una PREDIZIONE FALSIFICABILE:
#   I0  senza gate
#   I1  con gate
# Se tutto e' residente il gate non ha niente da proteggere, quindi deve
# risultare NEUTRO. Se invece desse ancora un guadagno, vorrebbe dire che ho
# capito male il suo meccanismo -- ed e' meglio saperlo.
#
# Prompt NeuraForge, 8000 token, ctx 10000: gli stessi del SOTA, cosi' i numeri
# sono confrontabili con la lunga serie gia' a ledger. L'HTML viene estratto a
# fine braccio, perche' l'utente lo vuole guardare.

$ErrorActionPreference = 'Continue'
$out  = 'D:\ds4_work\llama_run\q1ram.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\q1ram_paging.tsv'
"ora`tbraccio`tpage_reads`tpages_in`tram_disp_MB`tvram_MB" | Out-File $camp -Encoding utf8

$MODELLO = 'D:\ds4-models\DeepSeek-V4-Flash-IQ1_S-XL-merged.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$req     = 'D:\ds4_work\llama_run\neuraforge8k.req.json'

"modello: $MODELLO  ($([math]::Round((Get-Item $MODELLO).Length/1GB,2)) GB)" | Out-File $out -Append -Encoding utf8

Add-Type -Namespace '' -Name CQ1 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

$bracci = @(
    @{ n='I0_q1_senza_gate'; porta=8231; lock=$null }
    @{ n='I1_q1_con_gate';   porta=8232; lock='1'  }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log  = "D:\ds4_work\llama_run\LLAMA_$($b.n).server.log"
    $resp = "D:\ds4_work\llama_run\q1_$($b.n).resp.json"

    $env:LLAMA_ARG_CPU_MOE      = '1'
    $env:LLAMA_REAP             = '1'
    $env:LLAMA_REAP_PROF        = '1'
    $env:LLAMA_REAP_TOPK        = '1200'
    $env:LLAMA_REAP_PESO        = 'ripida'
    $env:LLAMA_REAP_DECADIMENTO = '1.0'
    Remove-Item Env:LLAMA_REAP_PREFETCH -EA SilentlyContinue
    Remove-Item Env:LLAMA_REAP_PERIODO  -EA SilentlyContinue
    if ($b.lock) { $env:LLAMA_REAP_LOCK = '1' } else { Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue }
    "GATE=$(if ($b.lock) { 'ACCESO' } else { 'spento' })   $(Get-Date -Format 'HH:mm:ss')" |
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
    for ($i = 0; $i -lt 240; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "IL SERVER NON E' PARTITO -- ultime righe del log:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 25 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        continue
    }

    $m0 = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
    "RAM disponibile dopo il caricamento: $($m0.AvailableMBytes) MB" | Out-File $out -Append -Encoding utf8

    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','14400','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json',
            '--data-binary', "@$req", '-o', $resp)

    while (-not $c.HasExited) {
        Start-Sleep -Seconds 15
        $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
        $v = (nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) 2>$null
        "{0}`t{1}`t{2}`t{3}`t{4}`t{5}" -f (Get-Date -Format 'HH:mm:ss'), $b.n,
            $m.PageReadsPerSec, $m.PagesInputPerSec, $m.AvailableMBytes, $v |
            Out-File $camp -Append -Encoding utf8
    }

    if (-not $srv.HasExited) {
        [void][CQ1]::FreeConsole()
        if ([CQ1]::AttachConsole([uint32]$srv.Id)) {
            [void][CQ1]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
            [void][CQ1]::GenerateConsoleCtrlEvent(0, 0)
            Start-Sleep -Seconds 15
            [void][CQ1]::FreeConsole(); [void][CQ1]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
        }
        $srv.WaitForExit(120000) | Out-Null
    }

    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|graphs reused|reap: politica|n_layer |n_expert ' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue
'FINE' | Out-File $out -Append -Encoding utf8
