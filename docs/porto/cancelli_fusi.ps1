# DOPO LA FUSIONE DI fix/morti E fix/default: due cancelli, uno dei quali e' il
# punto di tutto il lavoro sui default.
#
#  1  AMBIENTE ESPLICITO (come fanno tutti gli script di oggi: W=0, LRU=1, TOPK=1
#     passati a mano) -> deve dare SHA 33D76723EB8D e 13,19-13,26, cioe' esattamente
#     quello di prima. Verifica che togliere ring-esperti e reap non abbia mosso
#     niente: a rigore era codice che non girava, e se lo SHA si muove girava.
#
#  2  NIENTE AMBIENTE, solo i default nuovi -> deve dare LO STESSO SHA.
#     OGGI NON LO DAREBBE: col vecchio default W=2 e LRU=0 il binario faceva un
#     calcolo diverso e piu' lento (-25,6% secondo il sorgente stesso). E' il
#     motivo per cui questo lavoro esiste: la SOTA viveva solo in una riga di
#     PowerShell, e una riga dimenticata la faceva regredire in silenzio.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$msg  = [IO.File]::ReadAllText((Join-Path $run 'jprompt.txt'), [Text.Encoding]::UTF8)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 1200; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

foreach ($p in @(@{T='f_env'; ESPL=$true}, @{T='f_def'; ESPL=$false})) {
  $tag = $p.T
  while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }
  # le leve che restano comunque: non sono in discussione qui
  $env:LLAMA_MAPPED_IBRIDO = '1'
  $env:LLAMA_CACHE_ESPERTI_SLOT = '339'
  $env:LLAMA_CACHE_ESPERTI_CURA = '0'; $env:LLAMA_CACHE_ESPERTI_SCUDO = '0'
  $env:LLAMA_CACHE_ESPERTI_MASSA = '0'; $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'
  $env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
  $env:LLAMA_CACHE_ESPERTI_BATCH = '8'; $env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
  $env:LLAMA_CACHE_ESPERTI_FORK = '0'
  $env:LLAMA_CACHE_BOZZA_SLOT = '32'
  $env:LLAMA_SPEC_CONF_ESENTA_POS0 = '0'
  $env:LLAMA_DSV4_HC_FUSO = '5'
  $env:GGML_CUDA_GRAPH_OPT = '0'
  $env:LLAMA_OVERLAP_ASYNC = '1'; $env:LLAMA_OVERLAP_K = '2'; $env:LLAMA_OVERLAP_BATCH_MAX = '2'
  $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'; $env:LLAMA_OVERLAP_PIN = '1'
  $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
  $env:LLAMA_KV_RING = '1'; $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
  $env:LLAMA_ACCEPTMOE = '0'; $env:LLAMA_CKPT_CRONO = '0'
  $env:LLAMA_KV_ROLLBACK_PARZIALE = '1'; $env:LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
  $env:LLAMA_VRAM_A_FASI = '0'; $env:LLAMA_DSV4_INDEXER_FUSO = '0'
  [Environment]::SetEnvironmentVariable('LLAMA_VRAM_ZAVORRA', $null)

  # LE TRE IN DISCUSSIONE
  if ($p.ESPL) {
    $env:LLAMA_CACHE_ESPERTI_W = '0'; $env:LLAMA_CACHE_ESPERTI_LRU = '1'; $env:LLAMA_SPEC_DRAFT_TOPK = '1'
  } else {
    [Environment]::SetEnvironmentVariable('LLAMA_CACHE_ESPERTI_W', $null)
    [Environment]::SetEnvironmentVariable('LLAMA_CACHE_ESPERTI_LRU', $null)
    [Environment]::SetEnvironmentVariable('LLAMA_SPEC_DRAFT_TOPK', $null)
  }

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (W/LRU/TOPK $(if($p.ESPL){'dall AMBIENTE'}else{'dai DEFAULT nuovi'}))"
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
  # il manifesto, che e' il pezzo che vale piu' dei tre numeri
  Select-String -Path $log -Pattern 'manifesto|MANIFESTO' -EA SilentlyContinue | Select-Object -First 12 | ForEach-Object { "     | " + ($_.Line -replace '^.*?I ','').Trim() }
  $ts = M '\|        eval time =.*?([0-9.]+) tokens per second'
  $ml = M 'mean len =\s+([0-9.]+)'
  $sha = if (Test-Path (Join-Path $run "$tag.output.html")) { (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12) } else { '-' }
  $ciclo = if ($ts -ne '-' -and $ml -ne '-') { [math]::Round((1000/[double]$ts) * [double]$ml, 1) } else { '-' }
  "     decode $ts t/s   ms/ciclo $ciclo   p1 $(M 'draft acceptance = ([0-9.]+)')   |  $($risp.Length) car  |  SHA $sha"
  "     CANCELLO: atteso 33D76723EB8D -> $(if ($sha -eq '33D76723EB8D') { 'PASSATO' } else { "*** DIVERSO ($sha) ***" })"
}
'CANCELLI FUSI FINITO'
