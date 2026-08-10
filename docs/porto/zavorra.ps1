# LA SOGLIA DEI 400 MiB ESISTE DAVVERO?
#
# Da settimane trattiamo come una legge il fatto che "sotto ~400 MiB liberi la
# 3060 si strozza". Ma non e' MAI stato spiegato, e c'e' un confondimento in
# ogni misura che l'ha prodotta: la VRAM libera l'abbiamo sempre abbassata
# AGGIUNGENDO qualcosa -- slot di cache, o buffer piu' grande -- e quelle cose
# hanno costi propri che allora non conoscevamo:
#
#   - lo sfratto LRU e' O(n_slot) SEQUENZIALE in un kernel a un thread solo
#     (~39.000 iterazioni/token a 339 slot, e cresce con la capienza)
#   - il buffer di calcolo a contesto lungo era OTTO volte quello che credevamo
#   - un GiB di CUDA_Host non stava in nessun bilancio
#   - la ricattura del grafo costa ~50 ms a ogni cambio di taglia
#
# LA ZAVORRA SCIOGLIE IL CONFONDIMENTO: byte allocati e mai usati. Abbassa la
# VRAM libera senza toccare nient'altro -- nessuno slot in piu', nessun buffer
# piu' grande, nessuna ricerca piu' lunga.
#
#   il rallentamento c'e' lo stesso   ->  e' il driver: la soglia e' vera
#   non succede niente                ->  era il confondimento, e per settimane
#                                         abbiamo lasciato VRAM sul tavolo per
#                                         paura di un fantasma
#
# CONTROLLO INTERNO GRATIS: la zavorra non cambia niente di computazionale,
# quindi lo SHA deve restare 33D76723EB8D in TUTTI i bracci. Se si muove, la
# zavorra fa qualcosa che non dovrebbe e la misura non vale.
#
# Riferimento: 13,19-13,26 t/s, ms/ciclo 140,3-141,0, VRAM libera 1.217 MiB.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'

$passi = @(
  @{ T='z000'; Z='0'   },   # riferimento: ~1.217 liberi
  @{ T='z320'; Z='320' },   # ~897
  @{ T='z620'; Z='620' },   # ~597
  @{ T='z770'; Z='770' },   # ~447  <- appena sopra la presunta soglia
  @{ T='z870'; Z='870' },   # ~347  <- SOTTO la presunta soglia
  @{ T='z000b';Z='0'   }    # deriva
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
  $env:LLAMA_VRAM_A_FASI = '0'
  $env:LLAMA_DSV4_INDEXER_FUSO = '0'
  [Environment]::SetEnvironmentVariable('LLAMA_GRAPH_REUSE_DISABLE', $null)
  $env:LLAMA_VRAM_ZAVORRA = $p.Z

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (zavorra $($p.Z) MiB)"
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
    if ($proc.HasExited) { "     *** MORTO ***"; break }
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
  } catch { "     *** RICHIESTA FALLITA: $($_.Exception.Message) ***" }
  try { Stop-Process -Id $proc.Id -Force } catch {}
  Start-Sleep -Seconds 6
  $log = Join-Path $run "$tag.server.log"
  function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                             if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
  $ts = M '\|        eval time =.*?([0-9.]+) tokens per second'
  $ml = M 'mean len =\s+([0-9.]+)'
  $p1 = M 'draft acceptance = ([0-9.]+)'
  $best = $null; $bestN = -1
  Select-String -Path $log -Pattern 'cache-esperti: domanda ([0-9]+) \(colpi ([0-9]+) = ([0-9.]+)%, buchi ([0-9]+)' -EA SilentlyContinue | ForEach-Object {
    $n = [int]$_.Matches[0].Groups[1].Value; if ($n -gt $bestN) { $bestN = $n; $best = $_.Matches[0].Groups }
  }
  $sha = if (Test-Path (Join-Path $run "$tag.output.html")) { (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12) } else { '-' }
  $ciclo = if ($ts -ne '-' -and $ml -ne '-') { [math]::Round((1000/[double]$ts) * [double]$ml, 1) } else { '-' }
  "     decode $ts t/s   ms/ciclo $ciclo   p1 $p1   colpi $(if($best){$best[3].Value}else{'-'})%   |  VRAM libera $vram1 MiB  |  SHA $sha"
  if ($sha -ne '33D76723EB8D' -and $sha -ne '-') { "     *** SHA DIVERSO: la zavorra non e' inerte, la misura NON VALE ***" }
}
'ZAVORRA FINITO'
