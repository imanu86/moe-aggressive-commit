# DA DOVE VIENE IL CROLLO DI B1: 8,91 -> 6,47 t/s?
#
# IL FATTO
# --------
# Stessa configurazione (np 1, ctx 10000, ub 64, cache 380 slot W=0), stesso
# prompt, stessa macchina, RAM e VRAM sane in entrambi i casi:
#
#     prima passata   decode 8,91 t/s   VRAM liberi 1.247
#     seconda passata decode 6,47       VRAM liberi 1.334   -27%
#
# E il tasso di colpi e' SALITO (44% di regime -> 64,7%): piu' colpi e piu'
# lento, che e' la firma di K4c ma senza la pressione di VRAM che la spiegava.
#
# LE TRE CAUSE POSSIBILI, e perche' non si separano guardando i numeri
# ---------------------------------------------------------------------
# Fra le due passate e' cambiato il BINARIO, e non solo per colpa mia:
#
#   (a) la mia patch     355c257  cache esperti senza il cancello a batch 1
#   (b) due commit altrui b2b432b  catch che nomina l'eccezione del lookahead
#                         afa62f0  sonda dei confini nel loop degli split
#   (c) lo stato della macchina
#
# Il braccio B1 della prima passata e' l'UNICO girato prima del build delle
# 14:19 dell'altra sessione: gli altri tre potrebbero aver preso il binario
# nuovo a meta' corsa. Quindi la prima passata non e' omogenea, e il confronto
# 8,91 contro 6,47 non e' a variabile singola.
#
# IL TAGLIO CHE DECIDE, in due bracci e dieci minuti
# ---------------------------------------------------
# Con la cache SPENTA il mio codice non viene mai eseguito: il percorso e'
# quello di sempre. Il metro senza cache e' noto e ripetuto, 8,04 t/s.
#
#     D1  cache spenta   -> se da' ~8,0  la regressione e' NEL PERCORSO CACHE (mia)
#                        -> se da' ~6,5  la regressione e' FUORI (loro, o macchina)
#     D2  cache accesa   -> il paragone appaiato, stesso binario e stessa ora
#
# D2 accende anche la sonda dei confini, che nella seconda passata non ha
# stampato niente pur essendo compilata nella dll (verificato: la stringa c'e').
# Qui si guarda ANCHE lo stdout, non solo lo stderr: se la sonda scrive di la',
# la cercavo nel posto sbagliato.
$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\diagnosi.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$EXE = 'D:\llama-dspark\build\bin\llama-server.exe'
$MOD = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$R   = 'D:\ds4_work\llama_run'
$b   = [char]92
$ESP = 'ffn_(gate|up|down)_exps' + $b + '.weight=CUDA0_Mapped'

$bracci = @(
    @{ n='D1_cache_spenta'; slot=0;   prof=$false; d='cache SPENTA -- il mio codice non gira. Metro noto: 8,04' },
    @{ n='D2_cache_accesa'; slot=380; prof=$true;  d='cache accesa + sonda -- il paragone appaiato' }
)
$porta = 8531
foreach ($x in $bracci) {
    "=============== $($x.n) -- $($x.d) ===============" | Out-File $out -Append -Encoding utf8
    $log = "$R\DIA_$($x.n).log"
    $ram = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB
    "  [condizione] RAM libera {0:N1} GiB" -f $ram | Out-File $out -Append -Encoding utf8
    if ($ram -lt 10) { "  SCARTATO" | Out-File $out -Append -Encoding utf8; continue }

    $env:LLAMA_MAPPED_IBRIDO      = '1'
    $env:LLAMA_REAP               = '0'
    $env:LLAMA_CACHE_ESPERTI_SLOT = "$($x.slot)"
    $env:LLAMA_CACHE_ESPERTI_W    = '0'
    if ($x.prof) { $env:GGML_SCHED_PROFILO = '1' }
    else         { Remove-Item Env:GGML_SCHED_PROFILO -EA SilentlyContinue }

    $a = @('-m',$MOD,'-c','10000','-np','1','-ngl','99','-ot',$ESP,
           '-ub','64','-b','64','-t','8','--port',"$porta",'--host','127.0.0.1',
           '--no-warmup','--no-mmap','--reasoning-budget','0')
    $srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -WindowStyle Minimized `
            -RedirectStandardError $log -RedirectStandardOutput ($log + '.out')
    $pronto = $false
    for ($i=0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 10
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto=$true; break } catch {}
    }
    if (-not $pronto) { "  NON PARTE" | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
        Start-Sleep 45; $porta++; continue }

    $d = (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "  VRAM {0:N0} MiB, liberi {1:N0}" -f ($d.CookedValue/1MB), (12288 - $d.CookedValue/1MB) |
        Out-File $out -Append -Encoding utf8

    $risp = "$R\dia_$($x.n).json"
    & curl.exe -s --max-time 900 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$R\par_p1.req.json" -o $risp | Out-Null
    if (Test-Path $risp) {
        $j = Get-Content $risp -Raw | ConvertFrom-Json
        "  prefill {0,6:N2}   decode {1,6:N2} t/s   {2:N2} ms/tok" -f `
            $j.timings.prompt_per_second, $j.timings.predicted_per_second, $j.timings.predicted_per_token_ms |
            Out-File $out -Append -Encoding utf8
        $j.choices[0].message.content | Out-File "$R\dia_$($x.n).output.html" -Encoding utf8
        "  sha256 " + (Get-FileHash "$R\dia_$($x.n).output.html" -Algorithm SHA256).Hash.Substring(0,16) |
            Out-File $out -Append -Encoding utf8
    }
    foreach ($f in @($log, ($log + '.out'))) {
        Select-String -Path $f -Pattern 'cache-esperti: domanda|sched-profilo' -EA SilentlyContinue |
            Select-Object -Last 2 |
            ForEach-Object { "  [$(Split-Path $f -Leaf)] " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } |
            Out-File $out -Append -Encoding utf8
    }
    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep 10
    Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
    Start-Sleep 60
    "" | Out-File $out -Append -Encoding utf8
    $porta++
}
'FINE' | Out-File $out -Append -Encoding utf8
