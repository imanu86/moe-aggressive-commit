# VRAM A FASI: i cancelli del valore, in ordine.
#
# 1  IDENTITA'     leva spenta, ub 64   -> SHA 33D76723EB8D e 13,19-13,23
#                  (tre riproduzioni). Se lo SHA si muove qui, si ferma tutto.
# 2  IL VALORE     leva 1, ub 512       -> atteso 13,15-13,25 contro R512 = 12,99
#                  MISURATO. Sotto 13,05 il meccanismo non consegna il margine.
# 2b ripetizione   la banda e' larga 0,10 e il rumore 0,8%: serve n>=2.
# 4  RICARICA      leva 1 + CALDO=1     -> CANCELLO DURO: incoerenze dove/chi = 0.
#                  Qualunque altro valore = residenza non fidata, si spegne.
#                  Sul t/s totale l'effetto atteso e' +0,1-0,2%: il valore e'
#                  la latenza dei primi token, non il totale.
# 1b deriva in coda.
#
# Il prefill al tetto (leva 2, ub 1024/2048/2700) e la separazione
# capienza/margine sono campagne separate: qui si misura se il meccanismo
# restituisce i 654 MiB dello strozzamento.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'

$passi = @(
  @{ T='g1';   UB='64';  FASI='0'; CALDO='0'; ATT='33D76723EB8D' },
  @{ T='g2';   UB='512'; FASI='1'; CALDO='0'; ATT='' },
  @{ T='g2b';  UB='512'; FASI='1'; CALDO='0'; ATT='' },
  @{ T='g4';   UB='512'; FASI='1'; CALDO='1'; ATT='' },
  @{ T='g1b';  UB='64';  FASI='0'; CALDO='0'; ATT='33D76723EB8D' }
)

$msg  = [IO.File]::ReadAllText((Join-Path $run 'jprompt.txt'), [Text.Encoding]::UTF8)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 1200; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

foreach ($p in $passi) {
  $tag = $p.T
  while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }

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
  $env:LLAMA_OVERLAP_BATCH_MAX = '2'
  $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'; $env:LLAMA_OVERLAP_PIN = '1'
  $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
  $env:LLAMA_KV_RING = '1'; $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
  $env:LLAMA_ACCEPTMOE = '0'; $env:LLAMA_CKPT_CRONO = '0'
  $env:LLAMA_KV_ROLLBACK_PARZIALE = '1'; $env:LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
  $env:LLAMA_VRAM_A_FASI = $p.FASI
  $env:LLAMA_VRAM_A_FASI_CALDO = $p.CALDO
  [Environment]::SetEnvironmentVariable('LLAMA_VRAM_A_FASI_UB', $null)
  [Environment]::SetEnvironmentVariable('LLAMA_VRAM_A_FASI_SLOT', $null)
  [Environment]::SetEnvironmentVariable('LLAMA_VRAM_A_FASI_MARGINE', $null)
  [Environment]::SetEnvironmentVariable('LLAMA_VRAM_ZAVORRA', $null)

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (-ub $($p.UB), FASI=$($p.FASI), CALDO=$($p.CALDO))"
  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf',
    '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16',
    '-otd', $OTD,
    '-c', '10000', '-ub', $p.UB, '-np', '1', '-ngl', '99',
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
  if (-not $su) { try { Stop-Process -Id $proc.Id -Force } catch {}; Start-Sleep -Seconds 6; continue }
  $vram1 = try { (nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -replace '\s','' } catch { '?' }
  $risp = ''
  try {
    $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 7200
    $risp = [string]$out.choices[0].message.content
    if (-not $risp) { $risp = [string]$out.choices[0].message.reasoning_content }
    $risp | Out-File (Join-Path $run "$tag.output.html") -Encoding utf8
  } catch { "  *** RICHIESTA FALLITA: $($_.Exception.Message) ***" }
  try { Stop-Process -Id $proc.Id -Force } catch {}
  Start-Sleep -Seconds 6

  $log = Join-Path $run "$tag.server.log"
  function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                             if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
  $ts = M '\|        eval time =.*?([0-9.]+) tokens per second'
  $p1 = M 'draft acceptance = ([0-9.]+)'
  $ml = M 'mean len =\s+([0-9.]+)'
  $sha = if (Test-Path (Join-Path $run "$tag.output.html")) { (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12) } else { '-' }
  $ciclo = if ($ts -ne '-' -and $ml -ne '-') { [math]::Round((1000/[double]$ts) * [double]$ml, 1) } else { '-' }
  "  decode $ts t/s   ms/ciclo $ciclo   mean_len $ml   p1 $p1   |  VRAM libera $vram1 MiB  |  $($risp.Length) car  |  SHA $sha"

  # cosa dice il meccanismo di se stesso
  Select-String -Path $log -Pattern 'vram_a_fasi.*|ricarica CALDA.*|incoerenze.*' -EA SilentlyContinue | Select-Object -Last 4 | ForEach-Object { "     > " + ($_.Line -replace '^.*?I ','').Trim() }

  if ($p.ATT) {
    "     CANCELLO 1: SHA atteso $($p.ATT) -> $(if ($sha -eq $p.ATT) { 'PASSATO' } else { "*** DIVERSO ($sha): si ferma tutto ***" })"
  }
  if ($tag -eq 'g2' -or $tag -eq 'g2b') {
    $v = if ($ts -ne '-') { [double]$ts } else { 0 }
    "     CANCELLO 2: R512 = 12,99 misurato, atteso 13,15-13,25 -> $(if ($v -ge 13.15 -and $v -le 13.25) { 'CENTRATO' } elseif ($v -lt 13.05) { '*** il meccanismo NON consegna il margine ***' } elseif ($v -gt 13.25) { 'sopra la banda: rumore, o R512 era sfortunata' } else { 'zona grigia 13,05-13,15' })"
  }
}
'CANCELLI FASI FINITO'
