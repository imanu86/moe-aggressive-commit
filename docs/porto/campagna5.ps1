# CAMPAGNA 5: AcceptMoE, per cancelli. E il costo del checkpoint.
#
# AcceptMoE inserisce due op fra il router e i MUL_MAT_ID: sulle sole righe
# speculative del batch di verifica, id e pesi vengono riscritti per RESIDENZA --
# cioe' le posizioni oltre la prima si verificano usando solo gli esperti gia'
# in VRAM. Attacca insieme il trasporto e il thrashing.
#
# SI MISURA PER CANCELLI, non a colpi di t/s:
#   C0  tutto spento          -> SHA CF2DEEA06E90 e 12,83-12,92. Se cade, il
#                                codice nuovo tocca il cammino normale.
#   C1b macchinario ARMATO ma ESATTE=99, cioe' nessuna riga mascherata
#                             -> SHA 23B14DCEB7CF (lo stesso di c4_n2bm3).
#                                Separa "il codice nuovo gira" da "il codice
#                                nuovo cambia il risultato". E' il cancello che
#                                vale di piu': se qui lo SHA cambia, il
#                                meccanismo ha un difetto e ogni numero dopo e'
#                                senza senso.
#   C2  ESATTE=1, maschera attiva sulle righe >= 1 -> QUI si misura.
#
# DUE TRAPPOLE segnalate da chi ha rifuso la patch:
#   - la riga di dump ESCE ANCHE A LEVE SPENTE (am_cont e' allocato sempre). Il
#     criterio di C0 non e' "nessuna riga nuova" ma "riga presente, contatori a
#     zero". Un cancello scritto male fallisce su un binario sano.
#   - LLAMA_OVERLAP_BATCH_MAX deve essere n-max+1, cioe' 3 sui bracci n-max 2.
#     E' l'errore che ha azzoppato la campagna 3.
#
# Piu' il CRONOMETRO DEL CHECKPOINT: si salva a ogni episodio con bozza, 599
# volte per 1.200 token, ~11,7 MiB verso l'host. Se costa ~8 ms/ciclo il tetto
# vero passa da 13,2 a 14,3 -- e diventa il bersaglio piu' grosso rimasto.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$NCORE = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors

$passi = @(
  @{ T='c5_c0';     N='1'; BM='2'; AM='0'; ES='1';  CONF='0';   CRONO='0'; ATT='CF2DEEA06E90' },
  @{ T='c5_crono';  N='1'; BM='2'; AM='0'; ES='1';  CONF='0';   CRONO='1'; ATT='CF2DEEA06E90' },
  @{ T='c5_c1b';    N='2'; BM='3'; AM='1'; ES='99'; CONF='0';   CRONO='0'; ATT='23B14DCEB7CF' },
  @{ T='c5_c2';     N='2'; BM='3'; AM='1'; ES='1';  CONF='0';   CRONO='0'; ATT='' },
  @{ T='c5_c2c08';  N='2'; BM='3'; AM='1'; ES='1';  CONF='0.8'; CRONO='0'; ATT='' },
  @{ T='c5_c2e2';   N='2'; BM='3'; AM='1'; ES='2';  CONF='0';   CRONO='0'; ATT='' },
  @{ T='c5_base';   N='1'; BM='2'; AM='0'; ES='1';  CONF='0';   CRONO='0'; ATT='CF2DEEA06E90' }
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
  $env:LLAMA_SPEC_CONF_ESENTA_POS0 = '0'
  $env:LLAMA_DSV4_HC_FUSO = '5'
  $env:GGML_CUDA_GRAPH_OPT = '0'
  $env:LLAMA_OVERLAP_ASYNC = '1'; $env:LLAMA_OVERLAP_K = '2'
  $env:LLAMA_OVERLAP_BATCH_MAX = $p.BM
  $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'; $env:LLAMA_OVERLAP_PIN = '1'
  $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
  $env:LLAMA_KV_RING = '1'; $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
  $env:LLAMA_ACCEPTMOE = $p.AM
  $env:LLAMA_ACCEPTMOE_ESATTE = $p.ES
  $env:LLAMA_CKPT_CRONO = $p.CRONO
  [Environment]::SetEnvironmentVariable('LLAMA_ACCEPTMOE_SOGLIA', $null)
  [Environment]::SetEnvironmentVariable('LLAMA_ACCEPTMOE_BATCH_MAX', $null)
  [Environment]::SetEnvironmentVariable('LLAMA_REAP', $null)

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (n-max=$($p.N), AM=$($p.AM), ESATTE=$($p.ES), conf=$($p.CONF), BATCH_MAX=$($p.BM), crono=$($p.CRONO))  base: VRAM $vram0, RAM $ram0 GiB"
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

  if ($p.ATT) {
    "     CANCELLO: SHA atteso $($p.ATT) -> $(if ($sha -eq $p.ATT) { 'PASSATO' } else { "*** DIVERSO ($sha): il codice nuovo cambia il risultato dove non doveva ***" })"
  }
  # il dump di AcceptMoE esce SEMPRE, e per DUE cache: bersaglio (339 slot) e
  # bozza (32 slot). La bozza stampa per ULTIMA ed e' sempre a zero (il suo
  # arch non inserisce le op): "-Last 1" leggeva LEI, ed e' cosi' che una leva
  # accesa e' stata dichiarata spenta (audit/36-acceptmoe-spenta.md). Il
  # cancello legge la riga del BERSAGLIO = quella col massimo di lanci.
  $am = Select-String -Path $log -Pattern 'acceptmoe' -EA SilentlyContinue |
        Sort-Object { [int64]([regex]::Match($_.Line, 'lanci=(\d+)').Groups[1].Value) } |
        Select-Object -Last 1
  if ($am) { "     acceptmoe> " + $am.Line.Trim() }
  $ck = Select-String -Path $log -Pattern 'checkpoint: .*' -EA SilentlyContinue | Select-Object -Last 1
  if ($ck) { "     " + $ck.Line.Trim() }

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
'CAMPAGNA 5 FINITA'
