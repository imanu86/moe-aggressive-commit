# CAMPAGNA 2: rimisurare le leve sulla base NUOVA.
#
# La fusione delle hyper-connection ha tolto 24.000 nodi (34.329 -> 10.507) e
# portato il t/s da 10,86 a 12,66. **Tutte le leve misurate oggi lo sono state su
# un sistema che non esiste piu'.**
#
# In particolare il punto di equilibrio fra i due rami si e' spostato: la GPU ora
# finisce prima, quindi ASPETTA DI PIU' il ramo CPU. L'ottimo di K puo' essere
# sceso sotto 2 -- una zona mai esplorata perche' con K intero non si poteva.
#
# Base fissa di tutti i punti: FUSO=7, 339+32, blk.0 bozza mappato, TOPK=1,
# ctx 10.000, ub 64, -t 7, 1200 token, temp 0. Riferimento: 12,66 t/s (n=2).
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$NCORE = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors

# K: la GPU e' piu' veloce, quindi l'ottimo si sposta. Sotto il 2 non ci siamo mai andati.
# FORK: a K=2 valeva +0,4% con 34k nodi. Con 10k il quadro cambia.
# GRAPH_OPT: il codice dice no-op, ma su un grafo diverso vale la pena un punto.
# SLOT: la cache non l'abbiamo mai rimisurata sulla base nuova.
$passi = @(
  @{ T='c2_f3';    K='2';   FORK='0'; GO='0'; SLOT='339'; FUSO='3' },
  @{ T='c2_f5';    K='2';   FORK='0'; GO='0'; SLOT='339'; FUSO='5' },
  @{ T='c2_k15';    K='1.5'; FORK='0'; GO='0'; SLOT='339'; FUSO='7' },
  @{ T='c2_k25';    K='2.5'; FORK='0'; GO='0'; SLOT='339' ; FUSO='7' },
  @{ T='c2_k3';     K='3';   FORK='0'; GO='0'; SLOT='339' ; FUSO='7' },
  @{ T='c2_k2fork'; K='2';   FORK='1'; GO='0'; SLOT='339' ; FUSO='7' },
  @{ T='c2_k2go';   K='2';   FORK='0'; GO='1'; SLOT='339' ; FUSO='7' },
  @{ T='c2_s380';   K='2';   FORK='0'; GO='0'; SLOT='380' ; FUSO='7' },
  @{ T='c2_s300';   K='2';   FORK='0'; GO='0'; SLOT='300' ; FUSO='7' },
  @{ T='c2_base';   K='2';   FORK='0'; GO='0'; SLOT='339' ; FUSO='7' }   # il controllo IN CODA: cattura la deriva
)

$sampler = {
  param($procId, $csv)
  $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if (-not $p) { return }
  'ora,gpu_util,vram_usata,vram_libera,clock_sm,watt,cpu_core_eq,proc_ws_mib,ram_libera_mib' | Out-File $csv -Encoding utf8
  $prevCpu = $null; $prevT = $null
  while ($true) {
    try { $g = (nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.free,clocks.sm,power.draw --format=csv,noheader,nounits) -replace '\s','' } catch { $g = ',,,,' }
    $now = Get-Date
    try { $p.Refresh() } catch { break }
    $cpu = $p.TotalProcessorTime.TotalSeconds
    $coreEq = ''
    if ($null -ne $prevCpu) { $dt = ($now - $prevT).TotalSeconds; if ($dt -gt 0) { $coreEq = [math]::Round( ($cpu - $prevCpu) / $dt , 2) } }
    $prevCpu = $cpu; $prevT = $now
    $ws = [math]::Round($p.WorkingSet64 / 1MB)
    $ramFree = try { [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB) } catch { '' }
    "$($now.ToString('HH:mm:ss.fff')),$g,$coreEq,$ws,$ramFree" | Out-File $csv -Append -Encoding utf8
    Start-Sleep -Milliseconds 700
  }
}

$msg = [string](Get-Content (Join-Path $run 'jprompt.txt') -Raw)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 1200; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

foreach ($p in $passi) {
  $tag = $p.T
  $resp = Join-Path $run "$tag.resp.json"
  if (Test-Path $resp) { "salto $tag"; continue }
  while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }

  $vram0 = try { (nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -replace '\s','' } catch { '?' }
  $ram0  = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1048576, 1)

  $env:LLAMA_MAPPED_IBRIDO = '1'
  $env:LLAMA_CACHE_ESPERTI_SLOT = $p.SLOT
  $env:LLAMA_CACHE_ESPERTI_W = '0'; $env:LLAMA_CACHE_ESPERTI_CURA = '0'
  $env:LLAMA_CACHE_ESPERTI_SCUDO = '0'; $env:LLAMA_CACHE_ESPERTI_MASSA = '0'
  $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'; $env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
  $env:LLAMA_CACHE_ESPERTI_LRU = '1'
  $env:LLAMA_CACHE_ESPERTI_BATCH = '8'
  $env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
  $env:LLAMA_CACHE_ESPERTI_FORK = $p.FORK
  $env:LLAMA_CACHE_BOZZA_SLOT = '32'
  $env:LLAMA_SPEC_DRAFT_TOPK = '1'
  $env:LLAMA_DSV4_HC_FUSO = $p.FUSO
  $env:GGML_CUDA_GRAPH_OPT = $p.GO
  $env:LLAMA_OVERLAP_ASYNC = '1'; $env:LLAMA_OVERLAP_K = $p.K
  $env:LLAMA_OVERLAP_BATCH_MAX = '2'
  $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'; $env:LLAMA_OVERLAP_PIN = '1'
  $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
  $env:LLAMA_KV_RING = '1'; $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
  [Environment]::SetEnvironmentVariable('LLAMA_REAP', $null)

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (K=$($p.K), FORK=$($p.FORK), GRAPH_OPT=$($p.GO), slot=$($p.SLOT))  base: VRAM $vram0, RAM $ram0 GiB"
  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf',
    '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16',
    '-otd', $OTD,
    '-c', '10000', '-ub', '64', '-np', '1', '-ngl', '99',
    '-ot', 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped', '-t', '7', '--no-mmap',
    '-lv', '4', '--host', '127.0.0.1', '--port', "$PORTA")

  $proc = Start-Process -FilePath $bin -ArgumentList $a -WindowStyle Hidden -PassThru `
    -RedirectStandardError (Join-Path $run "$tag.server.log") -RedirectStandardOutput (Join-Path $run "$tag.server.out")
  $su = $false
  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 10
    if ($proc.HasExited) { "  *** MORTO IN CARICAMENTO ***"; break }
    try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su = $true; break } } catch {}
  }
  $t0 = $null
  if ($su) {
    $csv = Join-Path $run "$tag.telemetria.csv"
    $job = Start-Job -ScriptBlock $sampler -ArgumentList $proc.Id, $csv
    Start-Sleep -Seconds 2
    $t0 = Get-Date
    try {
      $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 3600
      $out | ConvertTo-Json -Depth 8 | Out-File $resp -Encoding utf8
    } catch { "  *** RICHIESTA FALLITA: $($_.Exception.Message) ***" }
    Stop-Job $job -EA SilentlyContinue; Remove-Job $job -Force -EA SilentlyContinue
  }
  try { Stop-Process -Id $proc.Id -Force } catch {}
  Start-Sleep -Seconds 8

  $log = Join-Path $run "$tag.server.log"
  function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                             if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
  $best = $null; $bestN = -1
  Select-String -Path $log -Pattern 'cache-esperti: domanda ([0-9]+) \(colpi ([0-9]+) = ([0-9.]+)%, buchi ([0-9]+)' -EA SilentlyContinue | ForEach-Object {
    $n = [int]$_.Matches[0].Groups[1].Value
    if ($n -gt $bestN) { $bestN = $n; $best = $_.Matches[0].Groups }
  }
  $ts = M 'eval time =.*?([0-9.]+) tokens per second'
  $p1 = M 'draft acceptance = ([0-9.]+)'
  $ml = M 'mean len =\s+([0-9.]+)'
  $gen = M 'per chiamata: gen ([0-9.]+) ms'
  $sha = '-'
  if (Test-Path $resp) {
    try {
      $j = Get-Content $resp -Raw | ConvertFrom-Json
      ([string]$j.choices[0].message.content) | Out-File (Join-Path $run "$tag.output.html") -Encoding utf8
      $sha = (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12)
    } catch {}
  }
  $ciclo = if ($ts -ne '-' -and $ml -ne '-') { [math]::Round((1000/[double]$ts) * [double]$ml, 1) } else { '-' }
  $col = if ($best) { $best[3].Value } else { '-' }
  $buc = if ($best) { $best[4].Value } else { '-' }
  "  t/s=$ts  ms/ciclo=$ciclo  p1=$p1  colpi=$col%  buchi=$buc  gen=$gen  SHA=$sha    (base fusa: 12,66)"

  $pre = M 'prompt eval time =\s+([0-9.]+) ms'
  $csv = Join-Path $run "$tag.telemetria.csv"
  if ((Test-Path $csv) -and $t0 -and $pre -ne '-') {
    $s = Import-Csv $csv | Where-Object { $_.cpu_core_eq -ne '' }
    $fineP = $t0.AddMilliseconds([double]$pre)
    $q = $s | Where-Object { [DateTime]::Parse($_.ora) -gt $fineP }
    if ($q) {
      function Med([string]$c) { $v = @($q | ForEach-Object { [double]$_.$c } | Sort-Object); if ($v.Count) { return $v[[int]($v.Count/2)] } else { return 0 } }
      $vmin = ($q | ForEach-Object { [int]$_.vram_libera } | Measure-Object -Minimum).Minimum
      "    DECODE> GPU $(Med 'gpu_util')%  $(Med 'watt') W | CPU $(Med 'cpu_core_eq') core/$NCORE | VRAM min $vmin MiB"
    }
  }
}
'CAMPAGNA 2 FINITA'
