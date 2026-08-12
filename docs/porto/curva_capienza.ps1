# LA CURVA DELLA CAPIENZA SULLA PIATTAFORMA DI OGGI, quattro bracci in catena.
#
# PERCHE'. Dopo il riavvio del 12/8 alle 06:07 il banco rende il 13-15% in meno a
# parita' di tutto (stesso binario, stesso manifesto, stessa uscita bit per bit),
# e la perdita e' localizzata in `sync`, l'attesa dell'host al confine CPU-GPU:
# 2,166 -> 6,5-7,1 ms per grafo. In questo regime l'ottimo della capienza si e'
# spostato: 512 slot, che era la SOTA, adesso perde contro 448 e 339 SUL CICLO.
#
#   slot   t/s      ciclo    p1         sync     (misure del 12/8 mattina)
#   512   12,30    150,7    0,85449    6,488
#   512   12,45    148,9    0,85449    7,084     <- ripetizione: deriva 1,2% sul
#   448   12,91    144,6    0,86604    6,332        t/s ma 9,2% su sync
#   339   12,63    139,2    0,75806    5,017
#
# COSA MANCA E PERCHE' QUESTA CATENA. (a) la VRAM in decode misurata come
# MEDIANA per 448/339/256 -- finora ne avevo letture secche prese in istanti
# diversi, e su quelle avevo costruito (e ritirato) una conclusione sbagliata;
# (b) un punto piu' in basso, 256, per vedere se il ciclo continua a scendere o
# inverte; (c) un terzo 512 in coda, che misura la deriva sull'intera finestra.
#
# COME SI GIUDICA. Il CICLO, non il t/s: il p1 e' una lotteria di traiettoria
# (a 339 esce 0,75806, riprodotto identico dalla notte scorsa) e il t/s li
# moltiplica nascondendo quale dei due si e' mosso.
#
# NIENTE CARATTERI NON-ASCII: PowerShell 5.1 legge il file in ANSI.
$ErrorActionPreference = 'Continue'
$bin  = 'D:\llama-overlap\build\bin\llama-server.exe'
$run  = 'D:\ds4_work\llama_run'
$MD   = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD  = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$REL  = Join-Path $run 'curva_capienza.txt'
$msg  = [IO.File]::ReadAllText((Join-Path $run 'jprompt.txt'), [Text.Encoding]::UTF8)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 1200; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5
function Nota([string]$t) { $t | Tee-Object -FilePath $REL -Append }

Add-Type -Namespace '' -Name CL -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@
function Spegni($p) {
    if ($null -eq $p -or $p.HasExited) { return 'gia-uscito' }
    $via = 'ctrl-c'
    [void][CL]::FreeConsole()
    if ([CL]::AttachConsole([uint32]$p.Id)) {
        [void][CL]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CL]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][CL]::FreeConsole(); [void][CL]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    } else { $via = 'AttachConsole-fallita' }
    $p.WaitForExit(60000) | Out-Null
    if (-not $p.HasExited) { try { Stop-Process -Id $p.Id -Force } catch {}; $via = "$via -> RISERVA" }
    return $via
}

Nota ""
Nota ("=" * 96)
Nota ("CURVA DELLA CAPIENZA  " + [DateTime]::Now.ToString('yyyy-MM-dd HH:mm') + "   (uptime " + [math]::Round(((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes,1) + " min)")
Nota ("riferimento piattaforma BUONA: j_rif 05:10 -> 14,46 t/s, ciclo 128,2, sync 2,166")
Nota ("=" * 96)

$esiti = @()
foreach ($SLOT in @('448','339','256','512')) {
  $tag = "cc$SLOT"
  while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }
  for ($i = 0; $i -lt 30; $i++) {
    $v = 0; try { $v = [int]((& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) | Select-Object -First 1) } catch { break }
    if ($v -lt 1200) { break }
    Start-Sleep -Seconds 5
  }
  Start-Sleep -Seconds 30

  $env:LLAMA_CACHE_BOZZA_SLOT = '32'
  $env:LLAMA_CACHE_ESPERTI_BATCH = '8';   $env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
  $env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
  $env:LLAMA_CACHE_ESPERTI_CURA = '0';    $env:LLAMA_CACHE_ESPERTI_SCUDO = '0'
  $env:LLAMA_CACHE_ESPERTI_MASSA = '0';   $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'
  $env:LLAMA_CACHE_ESPERTI_LRU = '1';     $env:LLAMA_CACHE_ESPERTI_W = '0'
  $env:LLAMA_CACHE_ESPERTI_SLOT = $SLOT
  $env:LLAMA_CACHE_ESPERTI_FORK = '2';    $env:LLAMA_CACHE_ESPERTI_FORK_BLOCCHI = '8'
  $env:LLAMA_ACCEPTMOE = '0';             $env:LLAMA_CKPT_CRONO = '0'
  $env:LLAMA_SPEC_CONF_ESENTA_POS0 = '0'; $env:LLAMA_SPEC_DRAFT_TOPK = '1'
  $env:LLAMA_MAPPED_IBRIDO = '1';         $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
  $env:LLAMA_OVERLAP_ASYNC = '1';         $env:LLAMA_OVERLAP_K = '2'
  $env:LLAMA_OVERLAP_BATCH_MAX = '2';     $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'
  $env:LLAMA_OVERLAP_PIN = '1';           $env:LLAMA_OVERLAP_JOIN_ASYNC = '0'
  $env:LLAMA_KV_RING = '1';               $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
  $env:LLAMA_KV_ROLLBACK_PARZIALE = '1';  $env:LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
  $env:LLAMA_VRAM_A_FASI = '0';           $env:LLAMA_DSV4_INDEXER_FUSO = '0'
  $env:LLAMA_DSV4_HC_FUSO = '5';          $env:GGML_CUDA_GRAPH_OPT = '0'
  [Environment]::SetEnvironmentVariable('LLAMA_VRAM_ZAVORRA', $null)
  [Environment]::SetEnvironmentVariable('LLAMA_CACHE_ORACOLO', $null)
  $env:GGML_SCHED_PROFILO = '1'   # accesa: costa ~1,5% ma e' l'unico modo di vedere `sync`

  $up = [math]::Round(((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes,1)
  Nota ""
  Nota ("[" + [DateTime]::Now.ToString('HH:mm') + "] " + $tag + "   SLOT=" + $SLOT + "   (uptime " + $up + " min)")

  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf', '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16', '-otd', $OTD,
    '-c', '10000', '-ub', '64', '-np', '1', '-ngl', '99',
    '-ot', 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped', '-t', '7', '--no-mmap',
    '-lv', '4', '--host', '127.0.0.1', '--port', "$PORTA")
  $t0 = Get-Date
  $proc = Start-Process -FilePath $bin -ArgumentList $a -PassThru -NoNewWindow `
    -RedirectStandardError (Join-Path $run "$tag.server.log") -RedirectStandardOutput (Join-Path $run "$tag.server.out")

  $camp = Join-Path $run "$tag.hw.csv"
  $sampler = Start-Job -ScriptBlock {
    param($out)
    "t,sm,mem,watt,util,gen,width,throttle,vram_usata,vram_libera,cpu_perf,cpu_carico,server,ram_gb" | Out-File $out -Encoding utf8
    for ($i = 0; $i -lt 300; $i++) {
      $g = (& nvidia-smi --query-gpu=clocks.sm,clocks.mem,power.draw,utilization.gpu,pcie.link.gen.gpucurrent,pcie.link.width.current,clocks_throttle_reasons.active,memory.used,memory.free --format=csv,noheader,nounits) -join ','
      $c = try { [math]::Round(((Get-CimInstance Win32_PerfFormattedData_Counters_ProcessorInformation -EA Stop | Where-Object { $_.Name -eq '_Total' }).PercentProcessorPerformance),1) } catch { -1 }
      $k = try { (Get-CimInstance Win32_Processor -EA Stop).LoadPercentage } catch { -1 }
      $n = @(Get-Process -Name llama-server, llama-cli -EA SilentlyContinue).Count
      $r = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)
      "$($i*3),$g,$c,$k,$n,$r" | Out-File $out -Append -Encoding utf8
      Start-Sleep -Seconds 3
    }
  } -ArgumentList $camp

  $su = $false
  for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 10
    if ($proc.HasExited) { Nota "     *** MORTO ***"; break }
    try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su = $true; break } } catch {}
  }
  $tcar = [math]::Round(((Get-Date)-$t0).TotalSeconds,1)
  if ($su) {
    try {
      $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 7200
      $risp = [string]$out.choices[0].message.content
      if (-not $risp) { $risp = [string]$out.choices[0].message.reasoning_content }
      $risp | Out-File (Join-Path $run "$tag.output.html") -Encoding utf8
    } catch { Nota "     *** RICHIESTA FALLITA ***" }
  }
  $via = Spegni $proc
  Stop-Job $sampler -EA SilentlyContinue; Remove-Job $sampler -Force -EA SilentlyContinue
  Start-Sleep -Seconds 5

  $log = Join-Path $run "$tag.server.log"
  function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                             if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
  $ts  = M '\|        eval time =.*?([0-9.]+) tokens per second'
  $ml  = M 'mean len =\s+([0-9.]+)'
  $p1  = M 'draft acceptance = ([0-9.]+)'
  $syn = M 'di cui sync ([0-9.]+)\)'
  $ing = M 'per grafo: ingressi ([0-9.]+) ms'
  $cal = M 'calcolo ([0-9.]+) ms, attesa-lavoro'
  $col = M 'cache-esperti: domanda [0-9]+ \(colpi [0-9]+ = ([0-9.]+)%'
  $sha = if (Test-Path (Join-Path $run "$tag.output.html")) { (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12) } else { '-' }
  $ciclo = if ($ts -ne '-' -and $ml -ne '-') { [math]::Round((1000/[double]$ts) * [double]$ml, 1) } else { '-' }
  $vram = '-'; $vlib = '-'; $cpu = '-'; $srvmax = '-'
  if (Test-Path $camp) {
    $h = @(Import-Csv $camp | Where-Object { $_.util -match '^[0-9]+$' -and [int]$_.util -gt 50 })
    if ($h.Count -gt 0) {
      $vu = @($h | ForEach-Object { [int]$_.vram_usata } | Sort-Object); $vram = $vu[[int]($vu.Count/2)]
      $vl = @($h | ForEach-Object { [int]$_.vram_libera } | Sort-Object); $vlib = $vl[[int]($vl.Count/2)]
      $cp = @($h | ForEach-Object { [double]$_.cpu_perf } | Sort-Object); $cpu = $cp[[int]($cp.Count/2)]
      $srvmax = (@($h | ForEach-Object { [int]$_.server }) | Measure-Object -Maximum).Maximum
    }
  }
  Nota ("     t/s " + $ts + "   ciclo " + $ciclo + "   p1 " + $p1 + "   sync " + $syn + "   colpi " + $col + "%   SHA " + $sha)
  Nota ("     VRAM " + $vram + "/" + $vlib + " MiB   CPU " + $cpu + "   carico " + $tcar + " s   server max " + $srvmax + "   chiusura " + $via)
  $esiti += [pscustomobject]@{ slot=$SLOT; ts=$ts; ciclo=$ciclo; p1=$p1; sync=$syn; ingressi=$ing; calcolo=$cal; colpi=$col; vram=$vram; vlib=$vlib; carico=$tcar; sha=$sha }
}

Nota ""
Nota ("-" * 96)
Nota "  slot   t/s     ciclo    p1        sync    ingressi  worker    colpi   VRAM/libera    carico   SHA"
foreach ($e in $esiti) {
  Nota ("  {0,-6} {1,-7} {2,-8} {3,-9} {4,-7} {5,-9} {6,-9} {7,-7} {8,-14} {9,-8} {10}" -f `
    $e.slot, $e.ts, $e.ciclo, $e.p1, $e.sync, $e.ingressi, $e.calcolo, ($e.colpi + '%'), ($e.vram + '/' + $e.vlib), ($e.carico + 's'), $e.sha)
}
Nota ""
Nota "  riferimento BUONO (j_rif 05:10, 512 slot):  14,46 t/s   ciclo 128,2   p1 0,85449   sync 2,166   colpi 63,6%"
Nota "CURVA FINITA"
