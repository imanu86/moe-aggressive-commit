# JOIN ASINCRONO: la previsione piu' ambiziosa della campagna, e ora e' falsificabile.
#
# Codex ha scritto il numero PRIMA del codice, come richiesto:
#   ms/ciclo 140,3 -> 111,35     decode 13,26 -> 16,65-16,74 t/s
#
# La tesi (audit 44): i 45 ms per ciclo che il ledger attribuiva alla DIPENDENZA
# dei dati sono quattro pedaggi indipendenti da K per ogni strato -- attesa host
# del worker, drenaggio completo dello stream, H2D sincrona, rilancio WDDM.
# 43 strati per ~1 ms l'uno. La patch accoda la copia di ritorno sullo stream di
# calcolo invece di drenare.
#
# CANCELLI:
#  1  leva spenta   -> SHA 33D76723EB8D, 13,19-13,26   (identita')
#  2  leva accesa   -> LO STESSO SHA. Cambia QUANDO avviene una copia, non cosa
#                      si calcola: se il risultato cambia, la copia asincrona
#                      legge prima che la scrittura sia finita, ed e' un difetto
#                      di correttezza travestito da guadagno.
#  3  il numero     -> ms/ciclo, atteso 111,35. La storia della campagna dice di
#                      diffidare (le stime in ms sono state gonfiate quasi
#                      sempre, fattore 0,08-0,43), ma stavolta era scritta prima.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$msg  = [IO.File]::ReadAllText((Join-Path $run 'jprompt.txt'), [Text.Encoding]::UTF8)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 1200; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

foreach ($p in @(@{T='j0'; J='0'}, @{T='j1'; J='1'}, @{T='j1b'; J='1'}, @{T='j0b'; J='0'})) {
  $tag = $p.T
  while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }
  $env:LLAMA_MAPPED_IBRIDO = '1'
  $env:LLAMA_CACHE_ESPERTI_SLOT = '339'
  $env:LLAMA_CACHE_ESPERTI_CURA = '0'; $env:LLAMA_CACHE_ESPERTI_SCUDO = '0'
  $env:LLAMA_CACHE_ESPERTI_MASSA = '0'; $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'
  $env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
  $env:LLAMA_CACHE_ESPERTI_BATCH = '8'; $env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
  $env:LLAMA_CACHE_ESPERTI_FORK = '0'; $env:LLAMA_CACHE_BOZZA_SLOT = '32'
  $env:LLAMA_SPEC_CONF_ESENTA_POS0 = '0'
  $env:LLAMA_DSV4_HC_FUSO = '5'; $env:GGML_CUDA_GRAPH_OPT = '0'
  $env:LLAMA_OVERLAP_ASYNC = '1'; $env:LLAMA_OVERLAP_K = '2'; $env:LLAMA_OVERLAP_BATCH_MAX = '2'
  $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'; $env:LLAMA_OVERLAP_PIN = '1'
  $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
  $env:LLAMA_KV_RING = '1'; $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
  $env:LLAMA_ACCEPTMOE = '0'; $env:LLAMA_CKPT_CRONO = '0'
  $env:LLAMA_KV_ROLLBACK_PARZIALE = '1'; $env:LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
  $env:LLAMA_VRAM_A_FASI = '0'; $env:LLAMA_DSV4_INDEXER_FUSO = '0'
  [Environment]::SetEnvironmentVariable('LLAMA_VRAM_ZAVORRA', $null)
  $env:LLAMA_OVERLAP_JOIN_ASYNC = $p.J

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (JOIN_ASYNC=$($p.J))"
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
    if ($proc.HasExited) { "     *** MORTO ***"; break }
    try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su = $true; break } } catch {}
  }
  if (-not $su) { try { Stop-Process -Id $proc.Id -Force } catch {}; Start-Sleep -Seconds 6; continue }
  $risp = ''
  try {
    $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 7200
    $risp = [string]$out.choices[0].message.content
    if (-not $risp) { $risp = [string]$out.choices[0].message.reasoning_content }
    $risp | Out-File (Join-Path $run "$tag.output.html") -Encoding utf8
  } catch { "     *** RICHIESTA FALLITA ***" }
  try { Stop-Process -Id $proc.Id -Force } catch {}
  Start-Sleep -Seconds 6
  $log = Join-Path $run "$tag.server.log"
  function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                             if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
  $ts = M '\|        eval time =.*?([0-9.]+) tokens per second'
  $ml = M 'mean len =\s+([0-9.]+)'
  $sha = if (Test-Path (Join-Path $run "$tag.output.html")) { (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12) } else { '-' }
  $ciclo = if ($ts -ne '-' -and $ml -ne '-') { [math]::Round((1000/[double]$ts) * [double]$ml, 1) } else { '-' }
  # i contatori del join
  Select-String -Path $log -Pattern 'us_sync|join-async|us_join' -EA SilentlyContinue | Select-Object -Last 2 | ForEach-Object { "     > " + ($_.Line -replace '^.*?I ','').Trim() }
  "     decode $ts t/s   ms/ciclo $ciclo   p1 $(M 'draft acceptance = ([0-9.]+)')   |  $($risp.Length) car  |  SHA $sha"
  "     SHA: $(if ($sha -eq '33D76723EB8D') { 'INVARIATO (come deve)' } else { "*** DIVERSO ($sha): la copia asincrona legge prima della scrittura ***" })"
  if ($p.J -eq '1' -and $ciclo -ne '-') {
    "     PREVISIONE 111,35 ms -> misurato $ciclo   $(if ([double]$ciclo -le 115) { 'CENTRATA' } elseif ([double]$ciclo -ge 138) { '*** nessun effetto ***' } else { 'parziale' })"
  }
}
'CANCELLI JOIN FINITO'
