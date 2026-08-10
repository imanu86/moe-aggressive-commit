# IL PAVIMENTO DI ub NEL DECODE, e una separazione che possiamo gia' fare.
#
# A n-max 1 il batch di decode e' di DUE posizioni: bozza + bersaglio. Quindi
# ub 2 e' il pavimento vero. Sotto ub 16 non abbiamo mai girato: 8, 4 e 2 sono
# terra vergine e potrebbero rompersi su un kernel, non solo rallentare.
#
# MA IL BRACCIO CHE CONTA E' L'ULTIMO. Scendere da ub 64 a ub 2 libera ~104 MiB
# (misurato: ~1,67 MiB per unita' di ub). Se quei MiB li do alla CACHE -- da 339
# a 354 slot, 15 x 6,75 MiB = 101 MiB -- la VRAM libera torna quella del
# riferimento ma la cache e' piu' grande.
#
# E' LA SEPARAZIONE CHE IN 200 CORSE NON ABBIAMO MAI FATTO. Ogni volta che
# abbiamo aggiunto cache abbiamo tolto margine, e viceversa: capienza e margine
# si sono sempre mossi insieme, quindi non sappiamo quale delle due conti. Qui
# il margine sta fermo e la capienza cresce.
#
# La curva degli slot che credevamo di conoscere e' contaminata: 339 -> 12,93
# (p1 0,868), 380 -> 12,19 (p1 0,770), 448 -> 12,76 (p1 0,885). Non e' monotona
# ne' negli slot ne' nella VRAM libera, e il p1 oscilla abbastanza da spiegare
# tutto da solo.
#
# CANCELLO: il primo braccio deve dare SHA CF2DEEA06E90 e 12,83-12,92.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'

$passi = @(
  @{ T='fl_ub64';     UB='64'; SLOT='339' },   # riferimento e cancello SHA
  @{ T='fl_ub16';     UB='16'; SLOT='339' },
  @{ T='fl_ub8';      UB='8';  SLOT='339' },
  @{ T='fl_ub4';      UB='4';  SLOT='339' },
  @{ T='fl_ub2';      UB='2';  SLOT='339' },   # il pavimento, mai provato
  @{ T='fl_ub2s354';  UB='2';  SLOT='354' },   # LA SEPARAZIONE: stesso margine, piu' cache
  @{ T='fl_ub2s370';  UB='2';  SLOT='370' },   # e un passo oltre, per vedere la pendenza
  @{ T='fl_base';     UB='64'; SLOT='339' }    # deriva in coda
)

$msg  = [IO.File]::ReadAllText((Join-Path $run 'corto_prompt.txt'), [Text.Encoding]::UTF8)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 400; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

foreach ($p in $passi) {
  $tag = $p.T
  while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }

  $env:LLAMA_MAPPED_IBRIDO = '1'
  $env:LLAMA_CACHE_ESPERTI_SLOT = $p.SLOT
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

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (-ub $($p.UB), $($p.SLOT) slot)"
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
    if ($proc.HasExited) { "  *** MORTO IN CARICAMENTO a ub $($p.UB): e' un pavimento vero, non una lentezza ***"; break }
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
  $best = $null; $bestN = -1
  Select-String -Path $log -Pattern 'cache-esperti: domanda ([0-9]+) \(colpi ([0-9]+) = ([0-9.]+)%, buchi ([0-9]+)' -EA SilentlyContinue | ForEach-Object {
    $n = [int]$_.Matches[0].Groups[1].Value
    if ($n -gt $bestN) { $bestN = $n; $best = $_.Matches[0].Groups }
  }
  $col = if ($best) { $best[3].Value } else { '-' }
  $buc = if ($best) { $best[4].Value } else { '-' }
  $sha = if (Test-Path (Join-Path $run "$tag.output.html")) { (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12) } else { '-' }
  $ciclo = if ($ts -ne '-' -and $ml -ne '-') { [math]::Round((1000/[double]$ts) * [double]$ml, 1) } else { '-' }
  "  decode $ts t/s   ms/ciclo $ciclo   mean_len $ml   p1 $p1   colpi $col%   buchi $buc   |  VRAM libera $vram1 MiB  |  $($risp.Length) car  |  SHA $sha"
  if ($tag -eq 'fl_ub64') {
    $script:shaRif = $sha; "     (prompt corto: questo braccio E' il riferimento, SHA $sha)"
  }
  if ($sha -ne '-' -and $script:shaRif -and $tag -ne 'fl_ub64') { "     SHA contro il riferimento: $(if ($sha -eq $script:shaRif) { 'IDENTICO' } else { 'diverso (atteso: la residenza cambia chi calcola dove)' })" }
  if ($tag -eq 'fl_ub2s354') {
    "     >>> LA SEPARAZIONE: stessa VRAM libera del riferimento, 15 slot in piu'."
    "         Se qui il t/s sale, e' la CAPIENZA a pagare. Se non si muove, e' il MARGINE."
  }
}
'PAVIMENTO UB FINITO'
