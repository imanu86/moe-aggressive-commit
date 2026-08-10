# -cms: il veto che ci costa 288 secondi a ogni turno.
#
# I checkpoint di contesto NON sono spaziati: nascono nei punti di rottura del
# ciclo di riempimento, e -cms (--checkpoint-min-step) e' un VETO sul passo
# minimo. Col default 8192 quel veto rende impossibile creare un checkpoint di
# fine prompt per QUALUNQUE prompt sotto gli 8.192 token -- cioe' per tutti i
# nostri. Risultato: l'unico checkpoint che esiste sta a posizione 0, e il
# secondo turno ri-elabora tutto.
#
# PROVA MISURATA che il meccanismo funziona quando un checkpoint utile esiste:
# LLAMA_AGENTE, contesto 1.567 token, secondo turno -> 189 token elaborati su
# 1.681, 20,6 s invece di 186.
#
# ATTESO (audit 39, dai punti di rottura di kvd_A a 6.442 e 6.506):
#   -cms 8192  turno 2 -> 6.510 token, ~288 s     (il controllo: cio' che facciamo oggi)
#   -cms   32  turno 2 ->     4 token,   ~0,2 s
# CANCELLO: se col 32 il turno 2 resta sopra i 60 secondi, la tesi cade.
#
# Tre turni per braccio, PROMPT CHE CRESCE e sempre un solo messaggio utente
# (niente storia con ruolo assistant: e' quella che ha fatto 500 nel giro prima).
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'

$passi = @(
  @{ T='cms32';   CMS='32'   },   # il punto che decide
  @{ T='cms8192'; CMS='8192' }    # il controllo: il default di oggi
)

$base = [IO.File]::ReadAllText((Join-Path $run 'ctx_08k_prompt.txt'), [Text.Encoding]::UTF8)
$code = @(
  '',
  "`n`nDomanda breve: qual e il nome del file della cache per-esperto? Rispondi in una riga.",
  "`n`nAltra domanda breve: quanti slot ha la cache di default? Rispondi in una riga."
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

  "[$([DateTime]::Now.ToString('HH:mm'))] $tag  (-cms $($p.CMS))"
  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf',
    '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16',
    '-otd', $OTD,
    '-c', '10000', '-ub', '64', '-np', '1', '-ngl', '99',
    '-ot', 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped', '-t', '7', '--no-mmap',
    '-cms', $p.CMS, '-ctxcp', '32',
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

  $log = Join-Path $run "$tag.server.log"
  $visti = 0
  $testo = $base
  for ($t = 1; $t -le 3; $t++) {
    if ($t -gt 1) { $testo = $testo + $code[$t-1] }
    $body = @{ messages = @(@{ role='user'; content=$testo }); max_tokens = 80; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5
    $t0 = Get-Date
    try {
      $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 7200
      $risp = [string]$out.choices[0].message.content
      if (-not $risp) { $risp = [string]$out.choices[0].message.reasoning_content }
    } catch { "     TURNO $t FALLITO: $($_.Exception.Message)"; break }
    $muro = ((Get-Date)-$t0).TotalSeconds
    $tutti = @(Select-String -Path $log -Pattern 'prompt eval time =\s+([0-9.]+) ms /\s+([0-9]+) tokens' -EA SilentlyContinue)
    $nuovi = $tutti | Select-Object -Skip $visti
    $visti = $tutti.Count
    $riga = if ($nuovi) { $n = $nuovi[-1]; "{0,10:n0} ms su {1,6} token" -f [double]$n.Matches[0].Groups[1].Value, [int]$n.Matches[0].Groups[2].Value } else { "   nessun prompt eval: NIENTE da rielaborare" }
    "     turno $t  ->  $riga   |  muro {0,6:n1} s  |  risposta {1} car" -f $muro, $risp.Length
  }
  # cosa ha deciso il server
  Select-String -Path $log -Pattern 'created context checkpoint|restored context checkpoint|forcing full prompt' -EA SilentlyContinue | Select-Object -Last 5 | ForEach-Object { "       > " + ($_.Line -replace '^.*?\| ','').Trim() }
  try { Stop-Process -Id $proc.Id -Force } catch {}
  Start-Sleep -Seconds 6
}
'PROVA CMS FINITA'
