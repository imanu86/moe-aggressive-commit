# CAMPAGNA 3: la leva della CONFIDENZA, e due conferme.
#
# Scoperta stanotte nell'audit 31: --spec-draft-conf-min esiste, e' spenta di
# default, e ha gia' un consumatore nel NOSTRO speculative.cpp:1211-1216. Legge
# la testa di confidenza di DSpark (la conf_proj che l'audit 18 aveva marcato
# "mai usata") e tronca il blocco alla prima posizione sotto soglia.
#
# Perche' conta: la campagna 2 ha mostrato che il tempo di ciclo e' INCHIODATO a
# 145 ms su ogni leva provata. L'unica cosa che si muove e' p1. E n-max 2 era
# stato chiuso perche' il ciclo raddoppiava (145,7 -> 261,7) coi buchi per 2,7:
# il costo di bozzare SEMPRE due token, anche quando il secondo e' spazzatura.
# La soglia lo rende condizionale.
#
# ATTENZIONE alla scala: non sappiamo se quella confidenza sia una probabilita'
# in [0,1] o altro. La SPIA e' mean_len: se col troncamento resta identico al
# controllo c3_n2c0, la soglia non ha morso e il valore va cambiato, non
# interpretato.
#
# Base: FUSO=5 (non 7 -- la campagna 2 dice che la fusione "pre" costa p1 piu' di
# quanto renda in nodi: 12,83 contro 12,66). 339+32, blk.0 mappato, TOPK=1,
# ctx 10.000, ub 64, -t 7, 1200 token, temp 0.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$NCORE = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors

# I primi quattro aprono il fronte nuovo. Il quinto e il sesto confermano la
# campagna 2. Gli ultimi due chiedono se il vantaggio di FUSO=5 sia del CODICE o
# di QUESTO prompt -- domanda mai posta in 190 corse.
$passi = @(
  @{ T='c3_n2c0';   N='2'; CONF='0';    FUSO='5'; FORK='0'; SLOT='339'; PR='jprompt.txt' },
  @{ T='c3_n2c05';  N='2'; CONF='0.5';  FUSO='5'; FORK='0'; SLOT='339'; PR='jprompt.txt' },
  @{ T='c3_n2c08';  N='2'; CONF='0.8';  FUSO='5'; FORK='0'; SLOT='339'; PR='jprompt.txt' },
  @{ T='c3_n2c095'; N='2'; CONF='0.95'; FUSO='5'; FORK='0'; SLOT='339'; PR='jprompt.txt' },
  @{ T='c3_f5b';    N='1'; CONF='0';    FUSO='5'; FORK='0'; SLOT='339'; PR='jprompt.txt' },
  @{ T='c3_f5fork'; N='1'; CONF='0';    FUSO='5'; FORK='1'; SLOT='339'; PR='jprompt.txt' },
  @{ T='c3_f5s380'; N='1'; CONF='0';    FUSO='5'; FORK='0'; SLOT='380'; PR='jprompt.txt' },
  @{ T='c3_pr_f5';  N='1'; CONF='0';    FUSO='5'; FORK='0'; SLOT='339'; PR='prosa_prompt.txt' },
  @{ T='c3_pr_f7';  N='1'; CONF='0';    FUSO='7'; FORK='0'; SLOT='339'; PR='prosa_prompt.txt' },
  @{ T='c3_base';   N='1'; CONF='0';    FUSO='7'; FORK='0'; SLOT='339'; PR='jprompt.txt' }
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

foreach ($p in $passi) {
  $tag = $p.T
  $resp = Join-Path $run "$tag.resp.json"
  if (Test-Path $resp) { "salto $tag"; continue }
  while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }

  $msg  = [string](Get-Content (Join-Path $run $p.PR) -Raw)
  $body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 1200; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

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
  $env:GGML_CUDA_GRAPH_OPT = '0'
  $env:LLAMA_OVERLAP_ASYNC = '1'; $env:LLAMA_OVERLAP_K = '2'
  $env:LLAMA_OVERLAP_BATCH_MAX = '2'
  $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'; $env:LLAMA_OVERLAP_PIN = '1'
  $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
  $env:LLAMA_KV_RING = '1'; $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
  [Environment]::SetEnvironmentVariable('LLAMA_REAP', $null)

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (n-max=$($p.N), conf=$($p.CONF), FUSO=$($p.FUSO), FORK=$($p.FORK), slot=$($p.SLOT), prompt=$($p.PR))  base: VRAM $vram0, RAM $ram0 GiB"
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
  # il cancello della leva: se la riga non dice conf_min=<CONF>, il flag non e' passato
  $confvis = M 'conf_min=([0-9.]+)'
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
  "     [leva vista dal binario: conf_min=$confvis]"

  $pre = M 'prompt eval time =\s+([0-9.]+) ms'
  $csv = Join-Path $run "$tag.telemetria.csv"
  if ((Test-Path $csv) -and $t0 -and $pre -ne '-') {
    $s = Import-Csv $csv | Where-Object { $_.cpu_core_eq -ne '' }
    $fineP = $t0.AddMilliseconds([double]$pre)
    $q = $s | Where-Object { [DateTime]::Parse($_.ora) -gt $fineP }
    if ($q) {
      # BUG CORRETTO (16/8): $v[[int]($v.Count/2)] col banker's rounding cadeva un passo sopra il centro per Count dispari 3,7,11,... (con Count=3 era il MASSIMO); v. RUNBOOK par. 7.4
      function Med([string]$c) { $v = @($q | ForEach-Object { [double]$_.$c } | Sort-Object); if ($v.Count) { return $v[[math]::Floor(($v.Count-1)/2)] } else { return 0 } }
      $vmin = ($q | ForEach-Object { [int]$_.vram_libera } | Measure-Object -Minimum).Minimum
      "    DECODE> GPU $(Med 'gpu_util')%  $(Med 'watt') W | CPU $(Med 'cpu_core_eq') core/$NCORE | VRAM min $vmin MiB"
    }
  }
}
'CAMPAGNA 3 FINITA'
