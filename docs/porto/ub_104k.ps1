# A 104k CI STA ub ALTO? E il meccanismo a fasi serve proprio qui.
#
# --no-host ha sbloccato il caricamento a 104k (il GiB di CUDA_Host esce dalla
# pinnata), ma restano 419 MiB liberi di VRAM e ub 512 ne vuole ~750. E' il caso
# esatto per cui il meccanismo a fasi e' stato costruito: cache evacuata durante
# il prefill, restituita al decode.
#
# PROMPT da 6.510 token DENTRO un contesto da 104.000: gli stessi token della
# spazzata a ctx 10.000, quindi i numeri sono confrontabili riga per riga --
# e rispondono gratis a una domanda che non abbiamo mai posto: il prefill
# rallenta per il contesto ALLOCATO o per quello USATO?
#
# Riferimenti a ctx 10.000:  ub 64 -> 22,58 t/s | 256 -> 46,27 | 512 -> 72,92
# Riferimento a ctx 104.000: ub 64 -> 22,61 (misurato adesso)
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'

$passi = @(
  @{ T='L_ub256';    UB='256'; SLOT='339'; FASI='0' },
  @{ T='L_ub512';    UB='512'; SLOT='339'; FASI='0' },   # probabile morte: 419 liberi contro 750 richiesti
  @{ T='L_ub512f2';  UB='512'; SLOT='339'; FASI='2' },   # LA PROVA: cache evacuata nel prefill
  @{ T='L_ub512s96'; UB='512'; SLOT='96';  FASI='0' },   # ripiego statico: cache piccola tutto il tempo
  @{ T='L_ub1024f2'; UB='1024';SLOT='339'; FASI='2' }
)

$msg  = [IO.File]::ReadAllText((Join-Path $run 'ctx_08k_prompt.txt'), [Text.Encoding]::UTF8)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 120; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

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
  $env:LLAMA_VRAM_A_FASI = $p.FASI

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (ctx 104k, -ub $($p.UB), $($p.SLOT) slot, FASI=$($p.FASI))"
  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf',
    '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16',
    '-otd', $OTD,
    '-c', '104000', '-ub', $p.UB, '-np', '1', '-ngl', '99',
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
  if ($morto) {
    "     *** MORTO: il buffer di calcolo a ub $($p.UB) non ci sta a 104k con $($p.SLOT) slot ***"
    Select-String -Path $log -Pattern 'fallita|out of memory|error loading' -EA SilentlyContinue | Select-Object -First 1 | ForEach-Object { "     " + ($_.Line -replace '^.*?E ','').Trim() }
    continue
  }
  if (-not $su) { "     *** timeout ***"; try { Stop-Process -Id $proc.Id -Force } catch {}; continue }
  $vram1 = try { (nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -replace '\s','' } catch { '?' }
  $risp = ''
  try {
    $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 7200
    $risp = [string]$out.choices[0].message.content
    if (-not $risp) { $risp = [string]$out.choices[0].message.reasoning_content }
  } catch { "     *** RICHIESTA FALLITA: $($_.Exception.Message) ***" }
  try { Stop-Process -Id $proc.Id -Force } catch {}
  Start-Sleep -Seconds 6
  function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                             if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
  $pf = M 'prompt eval time =.*?([0-9.]+) tokens per second'
  $pm = M 'prompt eval time =\s+([0-9.]+) ms'
  "     PREFILL $pf t/s  ($pm ms su 6.510 token)  |  decode $(M '\|        eval time =.*?([0-9.]+) tokens per second') t/s  |  p1 $(M 'draft acceptance = ([0-9.]+)')  |  VRAM libera $vram1 MiB  |  $($risp.Length) car"
  Select-String -Path $log -Pattern 'vram_a_fasi.*' -EA SilentlyContinue | Select-Object -Last 1 | ForEach-Object { "     > " + ($_.Line -replace '^.*?I ','').Trim() }
  "     (a ctx 10.000 lo stesso prompt dava: ub 64 -> 22,58 | 256 -> 46,27 | 512 -> 72,92)"
}
'UB A 104K FINITO'
