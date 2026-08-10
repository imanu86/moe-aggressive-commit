# INDEXER FUSO: i cancelli guardano il BUFFER, non il t/s.
#
# Avvertenza dell'agente che l'ha portato: a contesto corto questo porto vale
# +0,14%, dentro il rumore. Chi lo misura col t/s a contesto corto ottiene un
# numero che non vuol dire niente. Il cancello e' la TAGLIA DEL BUFFER.
#
#  1  identita'      leva spenta, ub 64   -> SHA 33D76723EB8D, 13,19-13,26
#  2  il numero      leva accesa, ctx 10.000, ub 512
#                    buffer 859,68 -> ~220 MiB   (costa un minuto, decide tutto)
#  3  a 104k         leva accesa, ctx 104.000, ub 512
#                    buffer 6.960,93 -> ~430 MiB (banda 330-435), e DEVE CARICARE
#                    ~3.700 => sparita una sola delle due copie
#                    invariato => la leva non e' scattata
#  4  a 104k, ub 64  il riferimento di prefill (22,61) con la leva accesa
#
# LLAMA_GRAPH_REUSE_DISABLE=1 ovunque: l'op deriva la griglia da n_kv ed e' la
# classe dell'audit 11 (stesso uid, stessi nodi, ne diverso -> griglia stantia
# SENZA crash). Prima di fidarsi serve escludere quel cammino.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'

$passi = @(
  @{ T='ix1'; CTX='10000';  UB='64';  FUSO='0'; PR='jprompt.txt';        TK='1200'; ATT=859.68 },
  @{ T='ix2'; CTX='10000';  UB='512'; FUSO='1'; PR='jprompt.txt';        TK='400';  ATT=220 },
  @{ T='ix2b';CTX='10000';  UB='512'; FUSO='0'; PR='jprompt.txt';        TK='400';  ATT=859.68 },
  @{ T='ix3'; CTX='104000'; UB='512'; FUSO='1'; PR='ctx_08k_prompt.txt'; TK='120';  ATT=430 },
  @{ T='ix4'; CTX='104000'; UB='64';  FUSO='1'; PR='ctx_08k_prompt.txt'; TK='120';  ATT=0 }
)

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
  $env:LLAMA_VRAM_A_FASI = '0'
  $env:LLAMA_DSV4_INDEXER_FUSO = $p.FUSO
  $env:LLAMA_GRAPH_REUSE_DISABLE = '1'

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (ctx $($p.CTX), ub $($p.UB), FUSO=$($p.FUSO))"
  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf',
    '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16',
    '-otd', $OTD,
    '-c', $p.CTX, '-ub', $p.UB, '-np', '1', '-ngl', '99',
    '-ot', 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped', '-t', '7', '--no-mmap',
    '--no-host',
    '-lv', '4', '--host', '127.0.0.1', '--port', "$PORTA")
  $proc = Start-Process -FilePath $bin -ArgumentList $a -WindowStyle Hidden -PassThru `
    -RedirectStandardError (Join-Path $run "$tag.server.log") -RedirectStandardOutput (Join-Path $run "$tag.server.out")
  $su = $false; $morto = $false
  for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 10
    if ($proc.HasExited) { $morto = $true; break }
    try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su = $true; break } } catch {}
  }
  $log = Join-Path $run "$tag.server.log"
  # IL NUMERO CHE CONTA: il buffer di calcolo
  $cb = Select-String -Path $log -Pattern 'compute buffer size\s*=\s*([0-9.]+) MiB|buffer di calcolo ([0-9.]+)' -EA SilentlyContinue | Select-Object -First 3
  if ($cb) { $cb | ForEach-Object { "     BUFFER> " + ($_.Line -replace '^.*?I ','').Trim() } }
  $nodi = Select-String -Path $log -Pattern 'sched_reserve.*?([0-9]+) nodes' -EA SilentlyContinue | Select-Object -First 1
  if ($nodi) { "     nodi> " + ($nodi.Line -replace '^.*?I ','').Trim() }
  $li = Select-String -Path $log -Pattern 'Lightning Indexer.*' -EA SilentlyContinue | Select-Object -First 1
  if ($li) { "     > " + ($li.Line -replace '^.*?I ','').Trim() } elseif ($p.FUSO -eq '1') { "     *** nessuna riga 'Lightning Indexer': la leva NON e' scattata ***" }
  if ($morto) {
    "     *** MORTO IN CARICAMENTO ***"
    Select-String -Path $log -Pattern 'fallita|out of memory|error loading' -EA SilentlyContinue | Select-Object -First 1 | ForEach-Object { "     " + ($_.Line -replace '^.*?E ','').Trim() }
    if ($tag -eq 'ix3') { "     *** il porto NON sblocca 104k a ub 512 ***" }
    continue
  }
  if (-not $su) { "     *** timeout ***"; try { Stop-Process -Id $proc.Id -Force } catch {}; continue }
  $vram1 = try { (nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -replace '\s','' } catch { '?' }
  if ($tag -eq 'ix3') { "     >>> CARICATO a 104k con ub 512. VRAM libera $vram1 MiB" }
  $msg  = [IO.File]::ReadAllText((Join-Path $run $p.PR), [Text.Encoding]::UTF8)
  $body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = [int]$p.TK; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5
  $risp = ''
  try {
    $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 7200
    $risp = [string]$out.choices[0].message.content
    if (-not $risp) { $risp = [string]$out.choices[0].message.reasoning_content }
    $risp | Out-File (Join-Path $run "$tag.output.html") -Encoding utf8
  } catch { "     *** RICHIESTA FALLITA: $($_.Exception.Message) ***" }
  try { Stop-Process -Id $proc.Id -Force } catch {}
  Start-Sleep -Seconds 6
  function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                             if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
  $sha = if (Test-Path (Join-Path $run "$tag.output.html")) { (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12) } else { '-' }
  "     prefill $(M 'prompt eval time =.*?([0-9.]+) tokens per second') t/s | decode $(M '\|        eval time =.*?([0-9.]+) tokens per second') t/s | p1 $(M 'draft acceptance = ([0-9.]+)') | VRAM $vram1 | $($risp.Length) car | SHA $sha"
  if ($tag -eq 'ix1') {
    "     CANCELLO 1: SHA atteso 33D76723EB8D -> $(if ($sha -eq '33D76723EB8D') { 'PASSATO' } else { "*** DIVERSO ($sha): si ferma tutto ***" })"
  }
}
'CANCELLI INDEXER FINITO'
