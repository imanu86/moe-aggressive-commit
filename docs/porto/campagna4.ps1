# CAMPAGNA 4: il fronte n-max 2, rifatto senza i due handicap.
#
# La campagna 3 aveva DUE difetti sui bracci a n-max 2, entrambi trovati dopo:
#   1. MIO: LLAMA_OVERLAP_BATCH_MAX=2 mentre il batch di verifica e' 3. La lane
#      CPU moriva -> 251 domande/token contro 190. Qui BM = n-max + 1.
#   2. DEL CODICE: la soglia di confidenza gatava anche la posizione 0, e a 0,8
#      il 38% dei cicli girava SENZA speculazione. Ora c'e' la leva
#      LLAMA_SPEC_CONF_ESENTA_POS0 (default 0 = comportamento upstream).
#
# LA BARRA, in aritmetica: perche' n-max 2 paghi serve ms/ciclo <= 202-233.
# Oggi e' 261. Se restiamo sopra dopo aver tolto entrambi gli handicap, il
# fronte si chiude con un conto e non con un'opinione.
#
# UNA IDEA NUOVA, braccio c4_n1_c05: a n-max 1 la soglia non tronca un blocco --
# decide SE speculare. Bozzare la posizione 0 aggiunge una posizione al batch di
# verifica, quindi paga finche' l'accettazione attesa supera il rapporto fra
# ciclo senza bozza (~96 ms) e ciclo con (~145), da noi circa 0,5. Sotto quella
# soglia saltare il giro dovrebbe essere piu' veloce che sbagliarlo.
#
# Base: FUSO=5 (12,87 t/s, confermato su DUE prompt), 339+32, blk.0 mappato,
# TOPK=1, K=2, ctx 10.000, ub 64, -t 7, 1200 token, temp 0.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$NCORE = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors

$passi = @(
  # IL CANCELLO, per primo: la barriera d'uscita di block_reduce non deve
  # cambiare NIENTE. SHA atteso CF2DEEA06E90, t/s atteso 12,83-12,92.
  @{ T='c4_gate';      N='1'; CONF='0';   BM='2'; E0='0'; FUSO='5' },

  # n-max 2 senza handicap: prima la lane sola, poi la soglia, poi l'esenzione
  @{ T='c4_n2bm3';     N='2'; CONF='0';   BM='3'; E0='0'; FUSO='5' },
  @{ T='c4_n2bm3c08';  N='2'; CONF='0.8'; BM='3'; E0='0'; FUSO='5' },
  @{ T='c4_n2bm3c08e'; N='2'; CONF='0.8'; BM='3'; E0='1'; FUSO='5' },
  @{ T='c4_n2bm3c05e'; N='2'; CONF='0.5'; BM='3'; E0='1'; FUSO='5' },
  @{ T='c4_n2bm3c09e'; N='2'; CONF='0.9'; BM='3'; E0='1'; FUSO='5' },
  # a n-max 2 il grafo pesa di piu': la fusione "pre" potrebbe tornare a pagare
  @{ T='c4_n2f7c08e';  N='2'; CONF='0.8'; BM='3'; E0='1'; FUSO='7' },

  # L'IDEA NUOVA: a n-max 1 la soglia decide SE speculare, non quanto
  @{ T='c4_n1c05';     N='1'; CONF='0.5'; BM='2'; E0='0'; FUSO='5' },
  @{ T='c4_n1c03';     N='1'; CONF='0.3'; BM='2'; E0='0'; FUSO='5' },

  @{ T='c4_base';      N='1'; CONF='0';   BM='2'; E0='0'; FUSO='5' }   # deriva
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

$msg  = [string](Get-Content (Join-Path $run 'jprompt.txt') -Raw)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 1200; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

foreach ($p in $passi) {
  $tag = $p.T
  $resp = Join-Path $run "$tag.resp.json"
  if (Test-Path $resp) { "salto $tag"; continue }
  while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }

  $vram0 = try { (nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -replace '\s','' } catch { '?' }
  $ram0  = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1048576, 1)

  $env:LLAMA_MAPPED_IBRIDO = '1'
  $env:LLAMA_CACHE_ESPERTI_SLOT = '339'
  $env:LLAMA_CACHE_ESPERTI_W = '0'; $env:LLAMA_CACHE_ESPERTI_CURA = '0'
  $env:LLAMA_CACHE_ESPERTI_SCUDO = '0'; $env:LLAMA_CACHE_ESPERTI_MASSA = '0'
  $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'; $env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
  $env:LLAMA_CACHE_ESPERTI_LRU = '1'
  $env:LLAMA_CACHE_ESPERTI_BATCH = '8'
  $env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
  $env:LLAMA_CACHE_ESPERTI_FORK = '0'
  $env:LLAMA_CACHE_BOZZA_SLOT = '32'
  $env:LLAMA_SPEC_DRAFT_TOPK = '1'
  $env:LLAMA_SPEC_CONF_ESENTA_POS0 = $p.E0
  $env:LLAMA_DSV4_HC_FUSO = $p.FUSO
  $env:GGML_CUDA_GRAPH_OPT = '0'
  $env:LLAMA_OVERLAP_ASYNC = '1'; $env:LLAMA_OVERLAP_K = '2'
  $env:LLAMA_OVERLAP_BATCH_MAX = $p.BM
  $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'; $env:LLAMA_OVERLAP_PIN = '1'
  $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
  $env:LLAMA_KV_RING = '1'; $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
  [Environment]::SetEnvironmentVariable('LLAMA_REAP', $null)

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (n-max=$($p.N), conf=$($p.CONF), BATCH_MAX=$($p.BM), esenta_pos0=$($p.E0), FUSO=$($p.FUSO))  base: VRAM $vram0, RAM $ram0 GiB"
  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf',
    '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', $p.N, '--spec-draft-ubatch-size', '16',
    '--spec-draft-conf-min', $p.CONF,
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
  "  t/s=$ts  ms/ciclo=$ciclo  mean_len=$ml  p1=$p1  colpi=$col%  buchi=$buc  gen=$gen  SHA=$sha"
  if ($tag -eq 'c4_gate') {
    "     CANCELLO BARRIERA: SHA atteso CF2DEEA06E90 -> $(if ($sha -eq 'CF2DEEA06E90') { 'PASSATO (la barriera non cambia il calcolo)' } else { '*** DIVERSO: la race MORDEVA, rileggere le misure della notte ***' })"
    "     e t/s atteso 12,83-12,92 -> misurato $ts"
  }
  if ($p.N -eq '2') { "     barra n-max 2: ms/ciclo <= 202-233 per pagare. Qui: $ciclo" }

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
'CAMPAGNA 4 FINITA'
