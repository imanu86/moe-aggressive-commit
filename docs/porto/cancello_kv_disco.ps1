# CANCELLO: il KV su disco funziona davvero?
#
# --slot-save-path esiste da sempre in llama.cpp e non l'abbiamo MAI usato. Se
# funziona, il prefill si paga UNA volta e poi si ripristina in secondi -- il che
# cambia tutto a 100k token, dove costa 82 minuti.
#
# PRIMA di spendere 82 minuti, sei di cancello a 7k token:
#   A. server fresco, prompt intero  -> prefill_ms(A), SHA(A), poi SALVA lo slot
#   B. server fresco, RIPRISTINA lo slot, stesso prompt -> prefill_ms(B), SHA(B)
#
# PASSA se: SHA(B) == SHA(A)  E  prefill_ms(B) << prefill_ms(A).
# Se lo SHA cambia, lo stato ripristinato NON e' quello salvato e la funzione e'
# inutilizzabile per noi, per quanto veloce sia.
# Se il prefill non cala, il ripristino c'e' ma il server ri-prefilla comunque.
#
# Configurazione SOTA: FUSO=5, K=2, 339+32, n-max 1, rollback parziale acceso.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$KV  = 'D:\ds4_work\kv_store'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
New-Item -ItemType Directory -Force $KV | Out-Null

# NON Get-Content -Raw: su PowerShell 5.1 legge con la codepage ANSI di sistema e
# sbriciola ogni carattere multi-byte. Non ci aveva mai morso perche' tutti i
# prompt del banco erano ASCII puro; questo comincia con un trattino lungo.
$msg  = [IO.File]::ReadAllText((Join-Path $run 'ctx_08k_prompt.txt'), [Text.Encoding]::UTF8)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 200; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5

function Avvia {
  # le leve di produzione: il cancello va fatto nella configurazione che useremo,
  # non ai default -- altrimenti prova un sistema diverso da quello che ci serve
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
  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf',
    '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
    '-ngld', '99', '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16',
    '-otd', $OTD,
    '-c', '10000', '-ub', '64', '-np', '1', '-ngl', '99',
    '-ot', 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped', '-t', '7', '--no-mmap',
    '--slot-save-path', $KV,
    '-lv', '4', '--host', '127.0.0.1', '--port', "$PORTA")
  $script:proc = Start-Process -FilePath $bin -ArgumentList $a -WindowStyle Hidden -PassThru `
    -RedirectStandardError (Join-Path $run "$script:tag.server.log") -RedirectStandardOutput (Join-Path $run "$script:tag.server.out")
  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 10
    if ($script:proc.HasExited) { return $false }
    try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { return $true } } catch {}
  }
  return $false
}
function Ferma { try { Stop-Process -Id $script:proc.Id -Force } catch {}; Start-Sleep -Seconds 8 }
function Misura([string]$tag) {
  $log = Join-Path $run "$tag.server.log"
  $m = Select-String -Path $log -Pattern 'prompt eval time =\s+([0-9.]+) ms' -EA SilentlyContinue | Select-Object -Last 1
  if ($m) { return [double]$m.Matches[0].Groups[1].Value } else { return -1 }
}

# ---------- A: server fresco, prefill intero, poi salva ----------
$script:tag = 'kvd_A'
while (Get-Process -Name llama-server -EA SilentlyContinue) { Start-Sleep -Seconds 5 }
"[$([DateTime]::Now.ToString('HH:mm'))] A -- server fresco, prompt da 7k token"
if (-not (Avvia)) { "  *** MORTO IN CARICAMENTO ***"; return }
$t0 = Get-Date
$outA = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 3600
$shaA = (Get-FileHash -InputStream ([IO.MemoryStream]::new([Text.Encoding]::UTF8.GetBytes([string]$outA.choices[0].message.content))) -Algorithm SHA256).Hash.Substring(0,12)
$preA = Misura 'kvd_A'
"  prefill = $preA ms   SHA = $shaA   (muro: $([math]::Round(((Get-Date)-$t0).TotalSeconds,1)) s)"

"  salvo lo slot 0..."
try {
  $sv = Invoke-RestMethod "http://127.0.0.1:$PORTA/slots/0?action=save" -Method Post -Body (@{ filename = 'gate7k.bin' } | ConvertTo-Json -Compress) -ContentType 'application/json' -TimeoutSec 600
  "  SALVATO: " + ($sv | ConvertTo-Json -Compress -Depth 4)
} catch { "  *** SALVATAGGIO FALLITO: $($_.Exception.Message) ***" }
Ferma
$f = Join-Path $KV 'gate7k.bin'
if (Test-Path $f) { "  file su disco: {0:n1} MiB" -f ((Get-Item $f).Length/1MB) } else { "  *** NESSUN FILE SU DISCO ***" }

# ---------- B: server fresco, RIPRISTINA, stesso prompt ----------
$script:tag = 'kvd_B'
"[$([DateTime]::Now.ToString('HH:mm'))] B -- server fresco, ripristino lo slot, stesso prompt"
if (-not (Avvia)) { "  *** MORTO IN CARICAMENTO ***"; return }
$tr = Get-Date
try {
  $rs = Invoke-RestMethod "http://127.0.0.1:$PORTA/slots/0?action=restore" -Method Post -Body (@{ filename = 'gate7k.bin' } | ConvertTo-Json -Compress) -ContentType 'application/json' -TimeoutSec 600
  "  RIPRISTINATO in {0:n1} s: {1}" -f ((Get-Date)-$tr).TotalSeconds, ($rs | ConvertTo-Json -Compress -Depth 4)
} catch { "  *** RIPRISTINO FALLITO: $($_.Exception.Message) ***" }
$t0 = Get-Date
$outB = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 3600
$shaB = (Get-FileHash -InputStream ([IO.MemoryStream]::new([Text.Encoding]::UTF8.GetBytes([string]$outB.choices[0].message.content))) -Algorithm SHA256).Hash.Substring(0,12)
$preB = Misura 'kvd_B'
"  prefill = $preB ms   SHA = $shaB   (muro: $([math]::Round(((Get-Date)-$t0).TotalSeconds,1)) s)"
Ferma

# ---------- il verdetto ----------
""
"=== CANCELLO KV SU DISCO ==="
# DUE VOLTE questo cancello ha stampato "UGUALI" sul niente. Prima su due SHA
# nulli (guardia aggiunta), poi su due SHA di STRINGA VUOTA -- che non sono
# nulli: E3B0C44298FC e' lo SHA-256 di "". Il criterio giusto non e' "lo SHA
# esiste" ma "c'e' del testo": si contano i caratteri, non gli hash.
if ($lenA -lt 1 -or $lenB -lt 1) {
  "  TESTO:    A=$lenA car  B=$lenB car  ->  *** UNA DELLE DUE CORSE NON HA PRODOTTO TESTO: cancello NON valutabile ***"
} elseif (-not $shaA -or -not $shaB) {
  "  SHA:      A='$shaA'  B='$shaB'  ->  *** UNA DELLE DUE CORSE NON HA PRODOTTO NIENTE: cancello NON valutabile ***"
} elseif ($shaA -eq $shaB) {
  "  SHA:      A=$shaA  B=$shaB  ->  UGUALI: lo stato ripristinato e' quello salvato"
} else {
  "  SHA:      A=$shaA  B=$shaB  ->  *** DIVERSI: il ripristino NON riproduce lo stato, funzione inutilizzabile ***"
}
if ($preA -gt 0 -and $preB -ge 0) {
  $g = [math]::Round(100 * (1 - $preB/$preA), 1)
  "  prefill:  A=$preA ms  B=$preB ms  ->  risparmio $g%  $(if ($g -gt 80) { 'PASSA' } else { '*** il ripristino non salta il prefill ***' })"
}
"  a 100k token il prefill costa ~82 minuti: questo risparmio, se regge, lo paga UNA volta sola."
