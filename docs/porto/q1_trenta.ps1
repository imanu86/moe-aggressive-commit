# Q1 CON 30 STRATI MAPPATI -- recupero dell'esperimento P1
#
# P1 (tutti e 43) e' fallito: cudaHostAlloc di 52.416 MiB out of memory, con
# 58,9 GB di RAM LIBERA. Non e' mancanza di memoria: cudaHostAlloc chiede un
# blocco UNICO pinnato e mappato nello spazio di indirizzi della GPU, e li' c'e'
# un tetto proprio.
#
# Quello che sappiamo funzionare:
#     17 strati IQ2   28,7 GiB   OK
#     22 strati IQ2   37,1 GiB   OK   (braccio Y2 del 4/8)
#     43 strati Q1    52,4 GiB   FALLITO
# Il muro sta fra 37 e 52 GiB, e vale anche con 128 GB di RAM installata.
#
# Su Q1 uno strato pesa 1,22 GiB invece di 1,69. Trenta strati sono 36,6 GiB,
# dentro il limite gia' dimostrato, e portano la copertura al 70% degli strati
# contro il 40% massimo mai provato sull'IQ2.
#
# Il metro e' P0 dello stesso run (esperti su CPU), che a sua volta deve
# riprodurre i 6,36 di I0 di stamattina.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\q1map.txt'
$camp = 'D:\ds4_work\llama_run\q1map_camp.tsv'
$MODELLO = 'D:\ds4-models\DeepSeek-V4-Flash-IQ1_S-XL-merged.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$req     = 'D:\ds4_work\llama_run\neuraforge8k.req.json'

Add-Type -Namespace '' -Name CVP2 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

$ESP = 'ffn_(gate|up|down)_exps\.weight'
$OT  = "blk\.([0-9]|1[0-9]|2[0-9])\.$ESP=CUDA0_Mapped,$ESP=CPU"
$n = 'P2_q1_30mappati'; $porta = 8303
$log = "D:\ds4_work\llama_run\LLAMA_$n.server.log"

"=============== $n ===============" | Out-File $out -Append -Encoding utf8
"-ot $OT   $(Get-Date -Format 'HH:mm:ss')" | Out-File $out -Append -Encoding utf8

$env:LLAMA_REAP = '1'; $env:LLAMA_REAP_PROF = '1'
Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue

$a = @('-m',$MODELLO,'-c','10000','-ngl','99','-ot',$OT,'-ub','64','-b','64',
       '--port',"$porta",'--host','127.0.0.1','--no-warmup','--reasoning-budget','0')
$srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

$pronto = $false
for ($i=0; $i -lt 480; $i++) {
    Start-Sleep -Seconds 5
    if ($srv.HasExited) { break }
    try { Invoke-RestMethod "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto=$true; break } catch {}
}
if (-not $pronto) {
    "NON E' PARTITO -- ultime righe:" | Out-File $out -Append -Encoding utf8
    if (Test-Path $log) { Get-Content $log -Tail 25 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
    'FINE' | Out-File $out -Append -Encoding utf8
    exit 1
}

$m0 = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
$d0 = (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples | Sort CookedValue -Desc | Select -First 1
"dopo il caricamento: RAM disponibile $($m0.AvailableMBytes) MB, VRAM dedicata $([math]::Round($d0.CookedValue/1MB)) MiB" | Out-File $out -Append -Encoding utf8

$c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
        '-sS','--max-time','14400','-X','POST',"http://127.0.0.1:$porta/v1/chat/completions",
        '-H','Content-Type: application/json','--data-binary',"@$req",'-o',"D:\ds4_work\llama_run\q1m_$n.resp.json")

while (-not $c.HasExited) {
    Start-Sleep -Seconds 15
    $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
    $g = (nvidia-smi --query-gpu=memory.used,utilization.gpu,power.draw --format=csv,noheader,nounits) 2>$null
    "{0}`t{1}`t{2}`t{3}`t{4}`t{5}" -f (Get-Date -Format 'HH:mm:ss'), $n, $m.PageReadsPerSec, $m.PagesInputPerSec, $m.AvailableMBytes, ($g -replace ',\s*',"`t") | Out-File $camp -Append -Encoding utf8
}

if (-not $srv.HasExited) {
    [void][CVP2]::FreeConsole()
    if ([CVP2]::AttachConsole([uint32]$srv.Id)) {
        [void][CVP2]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CVP2]::GenerateConsoleCtrlEvent(0,0)
        Start-Sleep -Seconds 15
        [void][CVP2]::FreeConsole(); [void][CVP2]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $srv.WaitForExit(120000) | Out-Null
}
if (Test-Path $log) {
    Select-String -LiteralPath $log -Pattern 'eval time =|model buffer size|mappati host' |
        ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } | Out-File $out -Append -Encoding utf8
}
'FINE-P2' | Out-File $out -Append -Encoding utf8
