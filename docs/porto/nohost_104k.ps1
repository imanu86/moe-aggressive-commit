# --no-host a 104k: il GiB che non avevamo mai contato basta a farci entrare?
#
# Il bilancio della memoria BLOCCATA, dai log:
#   bersaglio  CUDA0_Mapped 74.304  +  CUDA_Host  1.010
#   bozza      CUDA0_Mapped  2.224
#   a 104k il compresso KV ne aggiunge ~689  ->  78.227 MiB = 76,4 GiB
# Il tetto misurato sta fra 74,7 e 76,9 GiB, e a 104k il caricamento MUORE:
# "cudaHostAlloc di 2224.00 MiB fallita: out of memory" sulla bozza.
#
# --no-host (arg.cpp:2203, "bypass host buffer allowing extra buffers to be
# used") toglie i 1.010 MiB di CUDA_Host e riporta a 75,4 GiB.
#
# TRE BRACCI:
#   A  104k senza --no-host   -> deve MORIRE (riproduce il guasto)
#   B  104k con  --no-host    -> deve CARICARE
#   C  10k  con  --no-host    -> il flag non deve costare niente a contesto corto
#      (riferimento 13,19-13,26, SHA 33D76723EB8D)
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'

$passi = @(
  @{ T='nh_A'; CTX='104000'; NOHOST=$false; PR='ctx_08k_prompt.txt'; TK='40' },
  @{ T='nh_B'; CTX='104000'; NOHOST=$true;  PR='ctx_08k_prompt.txt'; TK='40' },
  @{ T='nh_C'; CTX='10000';  NOHOST=$true;  PR='jprompt.txt';        TK='1200' }
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

  $ram0 = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1048576, 1)
  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (ctx $($p.CTX), --no-host $($p.NOHOST))  RAM libera $ram0 GiB"

  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf',
    '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16',
    '-otd', $OTD,
    '-c', $p.CTX, '-ub', '64', '-np', '1', '-ngl', '99',
    '-ot', 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped', '-t', '7', '--no-mmap',
    '-lv', '4', '--host', '127.0.0.1', '--port', "$PORTA")
  if ($p.NOHOST) { $a += '--no-host' }

  $proc = Start-Process -FilePath $bin -ArgumentList $a -WindowStyle Hidden -PassThru `
    -RedirectStandardError (Join-Path $run "$tag.server.log") -RedirectStandardOutput (Join-Path $run "$tag.server.out")
  $su = $false; $morto = $false
  for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 10
    if ($proc.HasExited) { $morto = $true; break }
    try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su = $true; break } } catch {}
  }
  $log = Join-Path $run "$tag.server.log"
  # il bilancio della pinnata, sempre
  Select-String -Path $log -Pattern 'model buffer size|KV buffer size' -EA SilentlyContinue | Select-Object -First 8 | ForEach-Object { "     " + ($_.Line -replace '^.*?I ','').Trim() }
  if ($morto) {
    "     *** MORTO IN CARICAMENTO ***"
    Select-String -Path $log -Pattern 'fallita|out of memory|error loading' -EA SilentlyContinue | Select-Object -First 2 | ForEach-Object { "     " + ($_.Line -replace '^.*?E ','').Trim() }
    if ($tag -eq 'nh_A') { "     ATTESO: questo braccio DEVE morire, riproduce il guasto" }
    if ($tag -eq 'nh_B') { "     *** --no-host NON BASTA: il contesto lungo resta chiuso ***" }
    continue
  }
  if (-not $su) { "     *** non si e' alzato e non e' morto: timeout ***"; try { Stop-Process -Id $proc.Id -Force } catch {}; continue }

  $vram1 = try { (nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -replace '\s','' } catch { '?' }
  if ($tag -eq 'nh_B') { "     >>> CARICATO A 104k: il contesto lungo e' SBLOCCATO. VRAM libera $vram1 MiB" }
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
  "     prefill $(M 'prompt eval time =.*?([0-9.]+) tokens per second') t/s | decode $(M '\|        eval time =.*?([0-9.]+) tokens per second') t/s | p1 $(M 'draft acceptance = ([0-9.]+)') | VRAM $vram1 MiB | $($risp.Length) car | SHA $sha"
  if ($tag -eq 'nh_C') {
    "     CANCELLO: --no-host a contesto corto non deve costare. SHA atteso 33D76723EB8D -> $(if ($sha -eq '33D76723EB8D') { 'IDENTICO' } else { "diverso ($sha)" })"
  }
}
'NO-HOST FINITO'
