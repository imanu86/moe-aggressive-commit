# CAMPAGNA NOTTURNA: il fronte del pavimento, che nessuno aveva mai toccato.
#
# Base: patch_sinkhorn.diff (il porto di #25585) + patch_strumenti.diff applicate.
# Entrambe con leva a difetto SPENTO, quindi il primo punto e' il cancello.
#
# COSA SAPPIAMO PRIMA DI COMINCIARE
#   il grafo del decode ha 34.329 nodi; ~10.000 sono macchineria hyper-connection
#   #25585 li porta a ~3 per blocco: grafo atteso 14-16k
#   la sonda distruttiva dava 9-28 ms/ciclo di risparmio (misurato in ms/CICLO,
#   perche' il t/s mente quando il p1 cambia -- errore mio di stasera)
#   stima dichiarata dall'agente: +0,8 / +5,4%
#
# IL CANCELLO, per primo e non saltabile:
#   FUSO=0 deve dare 10,2-10,8 t/s e SHA B396AB2137B2 (riprodotto SETTE volte
#   oggi, attraverso cinque ricompilazioni, un riavvio e un cambio di RAM).
#   Se non torna, la patch ha toccato il cammino a leva spenta e ci si ferma.
#
# LA MASCHERA: 1=comb (Sinkhorn+affine), 2=pre, 4=post (i 3 concat che copiano).
#   Provarli separati dice QUALE pezzo paga, con uscita valida in tutti i casi.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$NCORE = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors

$passi = @(
  @{ T='lungo_fu5'; FUSO='5'; K='2'; NMAX='1' },
  @{ T='lungo_fu0'; FUSO='0'; K='2'; NMAX='1' }
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

$msg = [string](Get-Content (Join-Path $run 'neuraforge_prompt.txt') -Raw)

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
  $env:LLAMA_DSV4_HC_FUSO = $p.FUSO
  $env:LLAMA_OVERLAP_ASYNC = '1'; $env:LLAMA_OVERLAP_K = $p.K
  $env:LLAMA_OVERLAP_BATCH_MAX = [string]([int]$p.NMAX + 1)
  $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'; $env:LLAMA_OVERLAP_PIN = '1'
  $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
  $env:LLAMA_KV_RING = '1'; $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
  [Environment]::SetEnvironmentVariable('LLAMA_REAP', $null)
  [Environment]::SetEnvironmentVariable('GGML_CUDA_GRAPH_OPT', $null)
  [Environment]::SetEnvironmentVariable('LLAMA_DSV4_SINKHORN_ITERS', $null)
  [Environment]::SetEnvironmentVariable('LLAMA_DFLASH_SINKHORN_ITERS', $null)

  $body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 8000; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (FUSO=$($p.FUSO), K=$($p.K), n-max=$($p.NMAX))  base: VRAM $vram0 MiB, RAM $ram0 GiB"
  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf',
    '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', $p.NMAX, '--spec-draft-ubatch-size', '16',
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
  # il dump con PIU' domande e' quello del bersaglio, non della bozza
  $best = $null; $bestN = -1
  Select-String -Path $log -Pattern 'cache-esperti: domanda ([0-9]+) \(colpi ([0-9]+) = ([0-9.]+)%, buchi ([0-9]+)' -EA SilentlyContinue | ForEach-Object {
    $n = [int]$_.Matches[0].Groups[1].Value
    if ($n -gt $bestN) { $bestN = $n; $best = $_.Matches[0].Groups }
  }
  $ts  = M 'eval time =.*?([0-9.]+) tokens per second'
  $p1  = M 'draft acceptance = ([0-9.]+)'
  $ml  = M 'mean len =\s+([0-9.]+)'
  $nod = M 'sched_reserve.*?([0-9]+) nodes'
  $gen = M 'per chiamata: gen ([0-9.]+) ms'
  $sha = '-'
  if (Test-Path $resp) {
    try {
      $j = Get-Content $resp -Raw | ConvertFrom-Json
      ([string]$j.choices[0].message.content) | Out-File (Join-Path $run "$tag.output.html") -Encoding utf8
      $sha = (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12)
        $fine_r = [string]$j.choices[0].finish_reason
        $txt = [string]$j.choices[0].message.content
        $chiusa = ($txt -match '</html>')
        $script:extra = "  completezza: caratteri=$($txt.Length) fine=$fine_r </html>=$(if($chiusa){'SI'}else{'NO'}) tag_chiusi=$(([regex]::Matches($txt,'</[a-z]+>')).Count)"
    } catch {}
  }
  # ms/CICLO: l'unita' indipendente dall'accettazione. Il t/s mente se p1 cambia.
  $ciclo = if ($ts -ne '-' -and $ml -ne '-') { [math]::Round((1000/[double]$ts) * [double]$ml, 1) } else { '-' }
  $col = if ($best) { $best[3].Value } else { '-' }
  $buc = if ($best) { $best[4].Value } else { '-' }
  $(if ($script:extra) { $script:extra }); "  t/s=$ts  ms/ciclo=$ciclo  p1=$p1  mean_len=$ml  colpi=$col%  buchi=$buc  gen=$gen  SHA=$sha"
  # NIENTE cancello SHA qui: il prompt e' un altro (neuraforge "molto dettagliato")
  # e i token sono 8.000 invece di 1.200. B396AB2137B2 vale solo per jprompt a 1.200.
  # Il cancello di QUESTO braccio e' la COMPLETEZZA, stampata sopra: la fusione deve
  # chiudere </html> come la non-fusa, altrimenti abbiamo comprato velocita' con la
  # qualita' senza accorgercene su 1.200 token.

  $pre = M 'prompt eval time =\s+([0-9.]+) ms'
  $csv = Join-Path $run "$tag.telemetria.csv"
  if ((Test-Path $csv) -and $t0 -and $pre -ne '-') {
    $s = Import-Csv $csv | Where-Object { $_.cpu_core_eq -ne '' }
    $fineP = $t0.AddMilliseconds([double]$pre)
    foreach ($fase in @('PREFILL','DECODE')) {
      $q = if ($fase -eq 'PREFILL') { $s | Where-Object { [DateTime]::Parse($_.ora) -le $fineP } }
           else                     { $s | Where-Object { [DateTime]::Parse($_.ora) -gt $fineP } }
      if (-not $q) { continue }
      function Med([string]$c) { $v = @($q | ForEach-Object { [double]$_.$c } | Sort-Object); if ($v.Count) { return $v[[int]($v.Count/2)] } else { return 0 } }
      $vmin = ($q | ForEach-Object { [int]$_.vram_libera } | Measure-Object -Minimum).Minimum
      $rmin = ($q | ForEach-Object { [int]$_.ram_libera_mib } | Measure-Object -Minimum).Minimum
      "    $fase> GPU $(Med 'gpu_util')%  $(Med 'clock_sm') MHz  $(Med 'watt') W | CPU $(Med 'cpu_core_eq') core/$NCORE | VRAM min $vmin MiB | RAM min $rmin MiB"
    }
  }
}
'VALIDAZIONE LUNGA FINITA'


