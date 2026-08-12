# MACCHINA FREDDA, 12 AGOSTO MATTINA — due domande in una finestra sola.
#
# La ripresa chiede due cose che vogliono entrambe la macchina fredda:
#   1. rimisurare la SOTA (alle 05:00 la deriva era 2,2%: niente sotto il 4%
#      era decidibile, quindi il 14,77 delle 19:29 va riconfermato)
#   2. decidere LLAMA_DSV4_HC_FUSO=7, lasciato in sospeso: +2,9% di ciclo,
#      -2,7% di p1, netto dentro il rumore
#
# ABBA (5, 7, 7, 5): la deriva lineare si cancella nella media dei bracci
# appaiati, e i due bracci FUSO=5 danno anche la misura DIRETTA della deriva.
# Se |m5a - m5b| supera il 2%, il confronto 5 vs 7 NON e' decidibile e va detto.
#
# CIO' CHE SI DICHIARA SEPARATO (regola comprata la notte scorsa): ciclo e p1.
# Il t/s li moltiplica e nasconde quale dei due si e' mosso.
#
# L'ambiente e' copiato dal MANIFESTO di qs512b.server.log (la corsa che ha
# fatto 14,77), non dalla nota: solo le voci marcate (E). Sonde spente --
# `sched-profilo` non compare nel log della SOTA, e una sonda puo' ribaltare
# il regime.
$ErrorActionPreference = 'Continue'
$bin  = 'D:\llama-overlap\build\bin\llama-server.exe'
$run  = 'D:\ds4_work\llama_run'
$MD   = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD  = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$REL  = Join-Path $run 'freddo_fuso.txt'
$msg  = [IO.File]::ReadAllText((Join-Path $run 'jprompt.txt'), [Text.Encoding]::UTF8)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 1200; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

function Nota([string]$t) { $t | Tee-Object -FilePath $REL -Append }

# --- IDENTITA' DEL BINARIO -------------------------------------------------
# Il ggml-cuda.dll e' stato ricostruito alle 02:35 del 12, cioe' DOPO la corsa
# delle 19:29 che ha fatto 14,77: quel numero NON e' di questo binario. Per
# questo la SOTA va rifatta, e per questo l'impronta va scritta accanto ai
# numeri -- e' l'identita' di ogni misura di oggi.
Nota ""
Nota ("=" * 78)
Nota ("FREDDO/FUSO  " + [DateTime]::Now.ToString('yyyy-MM-dd HH:mm'))
Nota ("=" * 78)
foreach ($d in @('ggml-cuda.dll','ggml-base.dll','llama.dll','llama-server-impl.dll','llama-common.dll')) {
  $p = "D:\llama-overlap\build\bin\$d"
  if (Test-Path $p) {
    $h = (Get-FileHash $p -Algorithm SHA256).Hash.Substring(0,12)
    Nota ("  {0,-24} {1}  {2}" -f $d, (Get-Item $p).LastWriteTime.ToString('MM-dd HH:mm'), $h)
  }
}
$os = Get-CimInstance Win32_OperatingSystem
Nota ("  uptime al via: {0} min   RAM libera {1} GB" -f [math]::Round(((Get-Date)-$os.LastBootUpTime).TotalMinutes,1), [math]::Round($os.FreePhysicalMemory/1MB,1))
Nota ""

function Attendi-Quiete([int]$sec) {
  while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }
  # la VRAM deve TORNARE, non basta che il processo sia sparito
  for ($i = 0; $i -lt 30; $i++) {
    $v = 0
    try { $v = [int]((& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) | Select-Object -First 1) } catch { break }
    if ($v -lt 1200) { break }
    Start-Sleep -Seconds 5
  }
  Start-Sleep -Seconds $sec
}

$esiti = @()
$bracci = @(@{T='m5a'; F='5'}, @{T='m7a'; F='7'}, @{T='m7b'; F='7'}, @{T='m5b'; F='5'})

foreach ($b in $bracci) {
  $tag = $b.T
  Attendi-Quiete 60

  # --- l'ambiente della SOTA, voce per voce dal manifesto di qs512b ---
  $env:LLAMA_CACHE_BOZZA_SLOT = '32'
  $env:LLAMA_CACHE_ESPERTI_BATCH = '8';   $env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
  $env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
  $env:LLAMA_CACHE_ESPERTI_CURA = '0';    $env:LLAMA_CACHE_ESPERTI_SCUDO = '0'
  $env:LLAMA_CACHE_ESPERTI_MASSA = '0';   $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'
  $env:LLAMA_CACHE_ESPERTI_LRU = '1';     $env:LLAMA_CACHE_ESPERTI_W = '0'
  $env:LLAMA_CACHE_ESPERTI_SLOT = '512'                     # <- SOTA
  $env:LLAMA_CACHE_ESPERTI_FORK = '2'                       # <- SOTA
  $env:LLAMA_CACHE_ESPERTI_FORK_BLOCCHI = '8'               # <- SOTA
  $env:LLAMA_ACCEPTMOE = '0';             $env:LLAMA_CKPT_CRONO = '0'
  $env:LLAMA_SPEC_CONF_ESENTA_POS0 = '0'; $env:LLAMA_SPEC_DRAFT_TOPK = '1'
  $env:LLAMA_MAPPED_IBRIDO = '1';         $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
  $env:LLAMA_OVERLAP_ASYNC = '1';         $env:LLAMA_OVERLAP_K = '2'
  $env:LLAMA_OVERLAP_BATCH_MAX = '2';     $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'
  $env:LLAMA_OVERLAP_PIN = '1';           $env:LLAMA_OVERLAP_JOIN_ASYNC = '0'
  $env:LLAMA_KV_RING = '1';               $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
  $env:LLAMA_KV_ROLLBACK_PARZIALE = '1';  $env:LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
  $env:LLAMA_VRAM_A_FASI = '0';           $env:LLAMA_DSV4_INDEXER_FUSO = '0'
  $env:GGML_CUDA_GRAPH_OPT = '0'
  [Environment]::SetEnvironmentVariable('LLAMA_VRAM_ZAVORRA', $null)
  [Environment]::SetEnvironmentVariable('GGML_SCHED_PROFILO', $null)   # sonda SPENTA
  [Environment]::SetEnvironmentVariable('LLAMA_CACHE_ORACOLO', $null)
  $env:LLAMA_DSV4_HC_FUSO = $b.F                            # <- l'unica che cambia

  $up = [math]::Round(((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes,1)
  Nota ("[{0}] {1}  FUSO={2}   (uptime {3} min)" -f [DateTime]::Now.ToString('HH:mm'), $tag, $b.F, $up)

  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf', '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16', '-otd', $OTD,
    '-c', '10000', '-ub', '64', '-np', '1', '-ngl', '99',
    '-ot', 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped', '-t', '7', '--no-mmap',
    '-lv', '4', '--host', '127.0.0.1', '--port', "$PORTA")
  $proc = Start-Process -FilePath $bin -ArgumentList $a -WindowStyle Hidden -PassThru `
    -RedirectStandardError (Join-Path $run "$tag.server.log") -RedirectStandardOutput (Join-Path $run "$tag.server.out")

  $su = $false
  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 10
    if ($proc.HasExited) { Nota "     *** MORTO ***"; break }
    try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su = $true; break } } catch {}
  }
  if (-not $su) { try { Stop-Process -Id $proc.Id -Force } catch {}; Start-Sleep -Seconds 6; continue }

  $risp = ''
  try {
    $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 7200
    $risp = [string]$out.choices[0].message.content
    if (-not $risp) { $risp = [string]$out.choices[0].message.reasoning_content }
    $risp | Out-File (Join-Path $run "$tag.output.html") -Encoding utf8
  } catch { Nota "     *** RICHIESTA FALLITA ***" }
  try { Stop-Process -Id $proc.Id -Force } catch {}
  Start-Sleep -Seconds 6

  $log = Join-Path $run "$tag.server.log"
  function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                             if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
  $ts  = M '\|        eval time =.*?([0-9.]+) tokens per second'
  $ml  = M 'mean len =\s+([0-9.]+)'
  $p1  = M 'draft acceptance = ([0-9.]+)'
  $pp  = M 'prompt eval time =.*?([0-9.]+) tokens per second'
  $sha = if (Test-Path (Join-Path $run "$tag.output.html")) { (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12) } else { '-' }
  $ciclo = if ($ts -ne '-' -and $ml -ne '-') { [math]::Round((1000/[double]$ts) * [double]$ml, 1) } else { '-' }
  Nota ("     t/s {0}   ciclo {1} ms   p1 {2}   len {3}   prefill {4} t/s   SHA {5}" -f $ts, $ciclo, $p1, $ml, $pp, $sha)
  $esiti += [pscustomobject]@{ tag=$tag; fuso=$b.F; ts=$ts; ciclo=$ciclo; p1=$p1; sha=$sha }
}

Nota ""
Nota ("-" * 78)
Nota "  braccio   FUSO    t/s     ciclo     p1        SHA"
foreach ($e in $esiti) { Nota ("  {0,-9} {1,-6} {2,-7} {3,-9} {4,-9} {5}" -f $e.tag, $e.fuso, $e.ts, $e.ciclo, $e.p1, $e.sha) }

# --- il verdetto, coi suoi cancelli ---------------------------------------
$q5 = $esiti | Where-Object { $_.fuso -eq '5' -and $_.ts -ne '-' }
$q7 = $esiti | Where-Object { $_.fuso -eq '7' -and $_.ts -ne '-' }
if ($q5.Count -eq 2 -and $q7.Count -eq 2) {
  $d5 = [math]::Abs([double]$q5[0].ts - [double]$q5[1].ts) / [double]$q5[0].ts * 100
  $m5 = ([double]$q5[0].ts + [double]$q5[1].ts) / 2
  $m7 = ([double]$q7[0].ts + [double]$q7[1].ts) / 2
  $c5 = ([double]$q5[0].ciclo + [double]$q5[1].ciclo) / 2
  $c7 = ([double]$q7[0].ciclo + [double]$q7[1].ciclo) / 2
  $r5 = ([double]$q5[0].p1 + [double]$q5[1].p1) / 2
  $r7 = ([double]$q7[0].p1 + [double]$q7[1].p1) / 2
  Nota ""
  Nota ("  DERIVA misurata (m5a vs m5b): {0}%" -f [math]::Round($d5,2))
  Nota ("  SOTA di oggi (FUSO=5): {0} t/s   ciclo {1} ms   p1 {2}" -f [math]::Round($m5,2), [math]::Round($c5,1), [math]::Round($r5,5))
  Nota ("  FUSO=7:                {0} t/s   ciclo {1} ms   p1 {2}" -f [math]::Round($m7,2), [math]::Round($c7,1), [math]::Round($r7,5))
  $delta = ($m7 - $m5) / $m5 * 100
  Nota ("  delta t/s {0}%   delta ciclo {1}%   delta p1 {2}%" -f [math]::Round($delta,2), [math]::Round(($c7-$c5)/$c5*100,2), [math]::Round(($r7-$r5)/$r5*100,2))
  if ($d5 -gt 2.0) {
    Nota ("  >>> NON DECIDIBILE: la deriva ({0}%) e' dello stesso ordine dell'effetto." -f [math]::Round($d5,2))
  } elseif ([math]::Abs($delta) -lt $d5) {
    Nota "  >>> DENTRO IL RUMORE: l'effetto e' piu' piccolo della deriva misurata."
  } else {
    Nota ("  >>> DECIDIBILE: FUSO=7 {0} il {1}%" -f $(if ($delta -gt 0) { 'VINCE' } else { 'PERDE' }), [math]::Round([math]::Abs($delta),2))
  }
}
Nota ""
Nota "FREDDO/FUSO FINITO"
