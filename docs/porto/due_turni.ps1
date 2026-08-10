# DUE TURNI: il cammino che in 200+ corse di ledger non abbiamo MAI esercitato.
#
# Tutto il banco manda UN prompt e riavvia il server. Nell'uso vero il secondo
# messaggio riprende il contesto del primo, e il prefisso non andrebbe
# ri-elaborato. Secondo la lettura del codice quel riuso funziona gia' -- ma e'
# DEDOTTO, non misurato, perche' nessuna corsa ha mai avuto due richieste.
#
# Tre turni sullo STESSO server, prompt che cresce:
#   T1  prompt da ~6.500 token                  -> prefill pieno, atteso ~288 s
#   T2  stesso prompt + una domanda in coda     -> se il riuso c'e', prefill ~0
#   T3  T2 + un'altra domanda                   -> conferma
#
# Il numero che conta e' "prompt eval time" del turno 2 e 3: se sono secondi
# invece di minuti, il riuso fra turni funziona e non lo sapevamo.
# Secondo cancello: il testo deve esserci (si contano i CARATTERI, non lo SHA --
# E3B0C44298FC e' lo SHA della stringa vuota e ha gia' fatto passare due
# cancelli su corse che non avevano prodotto niente).
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$tag = 'turni'

while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }
$base = [IO.File]::ReadAllText((Join-Path $run 'ctx_08k_prompt.txt'), [Text.Encoding]::UTF8)

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
  '-lv', '4', '--host', '127.0.0.1', '--port', "$PORTA")

"[$([DateTime]::Now.ToString('HH:mm'))] avvio (un server solo, tre turni)"
$proc = Start-Process -FilePath $bin -ArgumentList $a -WindowStyle Hidden -PassThru `
  -RedirectStandardError (Join-Path $run "$tag.server.log") -RedirectStandardOutput (Join-Path $run "$tag.server.out")
$su = $false
for ($i = 0; $i -lt 90; $i++) {
  Start-Sleep -Seconds 10
  if ($proc.HasExited) { "  *** MORTO IN CARICAMENTO ***"; return }
  try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su = $true; break } } catch {}
}
if (-not $su) { "  *** NON SI E' ALZATO ***"; try { Stop-Process -Id $proc.Id -Force } catch {}; return }

$log = Join-Path $run "$tag.server.log"
function PrefillFinora { $m = Select-String -Path $log -Pattern 'prompt eval time =\s+([0-9.]+) ms /\s+([0-9]+) tokens' -EA SilentlyContinue | Select-Object -Last 1
                         if ($m) { return @([double]$m.Matches[0].Groups[1].Value, [int]$m.Matches[0].Groups[2].Value) } else { return @(-1,-1) } }

# la conversazione cresce: ogni turno riusa TUTTO il precedente come prefisso
$storia = @( @{ role='user'; content=$base } )
$domande = @(
  'Ora, in due righe: qual e il nome del file che contiene la cache per-esperto?',
  'E in due righe: quante posizioni indietro legge la chiusura CSA?'
)

for ($t = 1; $t -le 3; $t++) {
  $body = @{ messages = $storia; max_tokens = 120; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 6
  $t0 = Get-Date
  try {
    $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 7200
  } catch { "  *** TURNO $t FALLITO: $($_.Exception.Message) ***"; break }
  $muro = ((Get-Date)-$t0).TotalSeconds
  $risp = [string]$out.choices[0].message.content
  if (-not $risp) { $risp = [string]$out.choices[0].message.reasoning_content }
  $pf = PrefillFinora
  "[$([DateTime]::Now.ToString('HH:mm'))] TURNO $t  ->  prompt eval {0:n0} ms su {1} token   |   muro {2:n1} s   |   risposta {3} caratteri" -f $pf[0], $pf[1], $muro, $risp.Length
  if ($t -eq 1) { "     (questo e' il prefill pieno: e' il riferimento)" }
  else { "     (se questi ms sono secondi invece di minuti, IL RIUSO FRA TURNI FUNZIONA)" }
  $risp | Out-File (Join-Path $run "$tag.t$t.txt") -Encoding utf8
  if ($t -le 2) {
    $storia += @{ role='assistant'; content=$risp }
    $storia += @{ role='user';      content=$domande[$t-1] }
  }
}

try { Stop-Process -Id $proc.Id -Force } catch {}
Start-Sleep -Seconds 6
""
"=== TUTTI I prompt eval DELLA SESSIONE ==="
Select-String -Path $log -Pattern 'prompt eval time =\s+([0-9.]+) ms /\s+([0-9]+) tokens' -EA SilentlyContinue | ForEach-Object {
  "  {0,12:n0} ms  su {1,6} token" -f [double]$_.Matches[0].Groups[1].Value, [int]$_.Matches[0].Groups[2].Value
}
"=== e cosa dice il server del riuso ==="
Select-String -Path $log -Pattern 'forcing full prompt|new prompt|cache_n|n_past =|re-processing|reusing' -EA SilentlyContinue | Select-Object -Last 12 | ForEach-Object { "  " + $_.Line.Trim() }
'DUE TURNI FINITO'
