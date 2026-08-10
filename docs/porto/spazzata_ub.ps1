# SPAZZATA DI -ub SUL PREFILL: la leva, e non serve toccare una riga.
#
# Il prefill va a 22,6 t/s, il doppio del decode invece di cento volte tanto.
# Non e' un difetto: e' aritmetica del MoE. 64 token x 6 esperti = 384
# estrazioni che cadono su ~130-205 esperti DISTINTI per strato, quindi ogni
# lettura di pesi serve ~1,9 posizioni e non 64. L'ammortamento e'
# 6*ub/unione(ub): 1,9 a ub 64, ~12 a ub 512.
#
# I byte per ubatch hanno un TETTO per costruzione: 74.304 MiB, cioe' tutta la
# massa degli esperti una volta sola, qualunque sia il routing. Quindi alzare ub
# non puo' peggiorare il trasporto, puo' solo ammortizzarlo meglio.
#
# ATTESO (audit 38):  ub 256 -> 40-62 t/s   |   ub 512 -> 55-90 t/s
# CANCELLO CHE FALSIFICA: ub 256 sotto 35 t/s. ub 128 da solo non discrimina.
#
# RISCHIO da presidiare, mai esercitato: a ub >= 256 puo' capitare piu' di una
# chiusura HCA per ubatch. Guardo p1 e il testo: se la qualita' cade, e' li'.
# E il compute buffer cresce con ub: a ub 512 puo' non starci. Se un braccio
# muore in caricamento, e' quello -- non un difetto.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'

$passi = @(
  @{ T='ub064'; UB='64'  },   # il riferimento: 22,59 t/s misurati
  @{ T='ub256'; UB='256' },   # il punto che decide: sotto 35 t/s la tesi cade
  @{ T='ub512'; UB='512' },
  @{ T='ub128'; UB='128' }    # riempie la curva, da solo non discrimina
)

$msg  = [IO.File]::ReadAllText((Join-Path $run 'ctx_08k_prompt.txt'), [Text.Encoding]::UTF8)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 120; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

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

  $vram0 = try { (nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -replace '\s','' } catch { '?' }
  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (-ub $($p.UB))  VRAM libera prima: $vram0 MiB"

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
    if ($proc.HasExited) { "  *** MORTO IN CARICAMENTO: e' il compute buffer che non ci sta a ub $($p.UB), non un difetto ***"; break }
    try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su = $true; break } } catch {}
  }
  if ($su) {
    $vram1 = try { (nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -replace '\s','' } catch { '?' }
    try {
      $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 7200
      $risp = [string]$out.choices[0].message.content
      if (-not $risp) { $risp = [string]$out.choices[0].message.reasoning_content }
      $risp | Out-File (Join-Path $run "$tag.out.txt") -Encoding utf8
    } catch { "  *** RICHIESTA FALLITA: $($_.Exception.Message) ***"; $risp = '' }

    try { Stop-Process -Id $proc.Id -Force } catch {}
    Start-Sleep -Seconds 6
    $log = Join-Path $run "$tag.server.log"
    function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                               if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
    $pms = M 'prompt eval time =\s+([0-9.]+) ms'
    $pts = M 'prompt eval time =.*?([0-9.]+) tokens per second'
    $ntk = M 'prompt eval time =.*?ms /\s+([0-9]+) tokens'
    $p1  = M 'draft acceptance = ([0-9.]+)'
    $dts = M '\|        eval time =.*?([0-9.]+) tokens per second'
    "  PREFILL {0,7} token/s   ({1} ms su {2} token)   |  decode {3} t/s  p1 {4}  |  VRAM dopo il carico {5} MiB  |  risposta {6} car" -f $pts, $pms, $ntk, $dts, $p1, $vram1, $risp.Length
    if ($p.UB -eq '256') {
      "     CANCELLO: atteso 40-62 t/s, falsificato sotto 35  ->  $(if ([double]$pts -ge 40) { 'CONFERMATO' } elseif ([double]$pts -lt 35) { '*** TESI FALSIFICATA ***' } else { 'zona grigia 35-40' })"
    }
  } else { try { Stop-Process -Id $proc.Id -Force } catch {} ; Start-Sleep -Seconds 6 }
}
'SPAZZATA UB FINITA'
