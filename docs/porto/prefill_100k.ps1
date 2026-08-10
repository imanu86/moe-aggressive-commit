# PREFILL A 100k, PAGATO UNA VOLTA SOLA.
#
# Il prefill gira a ~20 token/s: 96.000 token fanno ~80 minuti prima del primo
# token. E finora li abbiamo ripagati A OGNI RIAVVIO del server -- e' il motivo
# per cui non abbiamo mai fatto una campagna seria a contesto lungo.
#
# LA MOSSA: max_tokens=1, cosi' si paga il prefill e si genera un token solo;
# poi SALVA SUBITO lo slot su disco. La parte costosa e' al sicuro prima di
# qualunque generazione. Da li' in poi ogni braccio a 100k riparte con un
# ripristino da secondi.
#
# Poi, sullo stesso server ancora caldo, una generazione vera da 300 token per
# misurare il DECODE a 96k di contesto -- che non abbiamo mai visto.
#
# Configurazione: SOTA (FUSO=5, K=2, 339+32, n-max 1, rollback parziale) ma
# ub 16 invece di 64, perche' a 100k il buffer di calcolo a ub 64 non ci sta
# (ledger 6/8). L'anello KV tiene in VRAM solo 2048 token, il resto compresso.
$bin = 'D:\llama-overlap\build\bin\llama-server.exe'
$run = 'D:\ds4_work\llama_run'
$KV  = 'D:\ds4_work\kv_store'
$MD  = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
# A 104k il KV mangia la host memory che serve al pin: cudaHostAlloc dei 2.224 MiB
# del blk.0 della bozza fallisce in CARICAMENTO (tetto del pin ~76,5 GiB, il
# bersaglio da solo ne usa 74,3). Il blk.0 della bozza va su CPU come gli altri.
$OTD = 'ffn_(gate|up|down)_exps\.weight=CPU'
$tag = 'p100k'
New-Item -ItemType Directory -Force $KV | Out-Null

$sampler = {
  param($procId, $csv)
  $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if (-not $p) { return }
  'ora,gpu_util,vram_usata,vram_libera,clock_sm,watt,cpu_core_eq,proc_ws_mib,ram_libera_mib' | Out-File $csv -Encoding utf8
  $prevCpu = $null; $prevT = $null
  while ($true) {
    try { $g = (nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.free,clocks.sm,power.draw --format=csv,noheader,nounits) -replace '\s','' } catch { $g = ',,,,' }
    $now = Get-Date
    try { $p.Refresh() } catch { break }
    $cpu = $p.TotalProcessorTime.TotalSeconds
    $coreEq = ''
    if ($null -ne $prevCpu) { $dt = ($now - $prevT).TotalSeconds; if ($dt -gt 0) { $coreEq = [math]::Round( ($cpu - $prevCpu) / $dt , 2) } }
    $prevCpu = $cpu; $prevT = $now
    $ws = [math]::Round($p.WorkingSet64 / 1MB)
    $ramFree = try { [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB) } catch { '' }
    "$($now.ToString('HH:mm:ss.fff')),$g,$coreEq,$ws,$ramFree" | Out-File $csv -Append -Encoding utf8
    Start-Sleep -Milliseconds 2000
  }
}

while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }
# NON Get-Content -Raw: su PowerShell 5.1 legge in ANSI e sbriciola l'UTF-8.
$msg = [IO.File]::ReadAllText((Join-Path $run 'jprompt105k.txt'), [Text.Encoding]::UTF8)
"[$([DateTime]::Now.ToString('HH:mm'))] prefill 100k -- $($msg.Length) caratteri, ~$([math]::Round($msg.Length/3.5)) token stimati"

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
$env:LLAMA_ACCEPTMOE = '0'
$env:LLAMA_CKPT_CRONO = '0'
$env:LLAMA_KV_ROLLBACK_PARZIALE = '1'
$env:LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
[Environment]::SetEnvironmentVariable('LLAMA_REAP', $null)

$a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf',
  '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
  '-ngld', '99', '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16',
  '-otd', $OTD,
  '-c', '104000', '-ub', '16', '-np', '1', '-ngl', '99',
  '-ot', 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped', '-t', '7', '--no-mmap',
  '--slot-save-path', $KV,
  '-lv', '4', '--host', '127.0.0.1', '--port', "$PORTA")

$proc = Start-Process -FilePath $bin -ArgumentList $a -WindowStyle Hidden -PassThru `
  -RedirectStandardError (Join-Path $run "$tag.server.log") -RedirectStandardOutput (Join-Path $run "$tag.server.out")
$su = $false
for ($i = 0; $i -lt 120; $i++) {
  Start-Sleep -Seconds 10
  if ($proc.HasExited) { "  *** MORTO IN CARICAMENTO -- guardare $tag.server.log ***"; return }
  try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su = $true; break } } catch {}
}
if (-not $su) { "  *** NON SI E' ALZATO ***"; try { Stop-Process -Id $proc.Id -Force } catch {}; return }
"  server su. VRAM libera: $((nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -replace '\s','') MiB"

$job = Start-Job -ScriptBlock $sampler -ArgumentList $proc.Id, (Join-Path $run "$tag.telemetria.csv")

# --- PASSO 1: prefill puro, UN token, poi SALVA ---
"[$([DateTime]::Now.ToString('HH:mm'))] passo 1: prefill + 1 token. Attesi ~80 minuti."
$b1 = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 1; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5
$t0 = Get-Date
try {
  $o1 = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $b1 -ContentType 'application/json' -TimeoutSec 21600
  "  prefill finito in {0:n1} minuti" -f ((Get-Date)-$t0).TotalMinutes
} catch { "  *** PREFILL FALLITO: $($_.Exception.Message) ***" }

"[$([DateTime]::Now.ToString('HH:mm'))] SALVO subito lo slot, prima di qualunque generazione"
$ts = Get-Date
try {
  $sv = Invoke-RestMethod "http://127.0.0.1:$PORTA/slots/0?action=save" -Method Post -Body (@{ filename = 'ctx100k.bin' } | ConvertTo-Json -Compress) -ContentType 'application/json' -TimeoutSec 3600
  "  SALVATO in {0:n1} s: {1}" -f ((Get-Date)-$ts).TotalSeconds, ($sv | ConvertTo-Json -Compress -Depth 4)
  $f = Join-Path $KV 'ctx100k.bin'
  if (Test-Path $f) { "  file su disco: {0:n1} MiB   <-- gli 80 minuti sono al sicuro" -f ((Get-Item $f).Length/1MB) }
} catch { "  *** SALVATAGGIO FALLITO: $($_.Exception.Message) -- gli 80 minuti NON sono recuperabili ***" }

# --- PASSO 2: decode vero a 96k di contesto, mai misurato ---
"[$([DateTime]::Now.ToString('HH:mm'))] passo 2: 300 token di decode a 96k di contesto"
$b2 = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 300; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5
$t2 = Get-Date
try {
  $o2 = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $b2 -ContentType 'application/json' -TimeoutSec 7200
  $txt = [string]$o2.choices[0].message.content
  $txt | Out-File (Join-Path $run "$tag.output.txt") -Encoding utf8
  "  decode finito in {0:n1} s, {1} caratteri" -f ((Get-Date)-$t2).TotalSeconds, $txt.Length
} catch { "  *** DECODE FALLITO: $($_.Exception.Message) ***" }

Stop-Job $job -EA SilentlyContinue; Remove-Job $job -Force -EA SilentlyContinue
try { Stop-Process -Id $proc.Id -Force } catch {}
Start-Sleep -Seconds 10

# --- PASSO 3: LA PROVA. Server NUOVO, ripristino da disco, stesso prompt. ---
# Qui il prefill NON deve costare 80 minuti. Se li costa, la leva non e' attiva
# e tutto il giro non serve a niente.
"[$([DateTime]::Now.ToString('HH:mm'))] passo 3: server NUOVO, ripristino da disco. QUI si decide."
$proc2 = Start-Process -FilePath $bin -ArgumentList $a -WindowStyle Hidden -PassThru `
  -RedirectStandardError (Join-Path $run "${tag}_rest.server.log") -RedirectStandardOutput (Join-Path $run "${tag}_rest.server.out")
$su2 = $false
for ($i = 0; $i -lt 120; $i++) {
  Start-Sleep -Seconds 10
  if ($proc2.HasExited) { "  *** MORTO IN CARICAMENTO ***"; break }
  try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su2 = $true; break } } catch {}
}
if ($su2) {
  $tr = Get-Date
  try {
    $rs = Invoke-RestMethod "http://127.0.0.1:$PORTA/slots/0?action=restore" -Method Post -Body (@{ filename = 'ctx100k.bin' } | ConvertTo-Json -Compress) -ContentType 'application/json' -TimeoutSec 3600
    "  RIPRISTINATO in {0:n1} s: {1}" -f ((Get-Date)-$tr).TotalSeconds, ($rs | ConvertTo-Json -Compress -Depth 4)
  } catch { "  *** RIPRISTINO FALLITO: $($_.Exception.Message) ***" }
  $t3 = Get-Date
  try {
    $o3 = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $b2 -ContentType 'application/json' -TimeoutSec 7200
    ([string]$o3.choices[0].message.content) | Out-File (Join-Path $run "${tag}_rest.output.txt") -Encoding utf8
    "  richiesta completa in {0:n1} minuti" -f ((Get-Date)-$t3).TotalMinutes
  } catch { "  *** RICHIESTA FALLITA: $($_.Exception.Message) ***" }
  $lr = Join-Path $run "${tag}_rest.server.log"
  $m3 = Select-String -Path $lr -Pattern 'prompt eval time =\s+([0-9.]+) ms' -EA SilentlyContinue | Select-Object -Last 1
  if ($m3) {
    $ms3 = [double]$m3.Matches[0].Groups[1].Value
    "  prompt eval DOPO IL RIPRISTINO: {0:n0} ms = {1:n1} minuti" -f $ms3, ($ms3/60000)
    "  -> $(if ($ms3 -lt 300000) { 'LA LEVA FUNZIONA: il prefill e sparito' } else { '*** 80 minuti anche col ripristino: LA LEVA NON E ATTIVA ***' })"
  } else { "  nessun prompt eval nel log: o non ha ri-prefillato affatto (ottimo) o non ha risposto" }
}
try { Stop-Process -Id $proc2.Id -Force } catch {}
Start-Sleep -Seconds 8

$log = Join-Path $run "$tag.server.log"
function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                           if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
""
"=== PREFILL 100k ==="
"  prompt eval:  $(M 'prompt eval time =\s+([0-9.]+) ms') ms  ->  $(M 'prompt eval time =.*?([0-9.]+) tokens per second') token/s"
"  token del prompt: $(M 'prompt eval time =.*?/\s+([0-9]+) tokens')"
"  decode:       $(M 'eval time =.*?([0-9.]+) tokens per second') token/s"
"  p1:           $(M 'draft acceptance = ([0-9.]+)')"
$csv = Join-Path $run "$tag.telemetria.csv"
if (Test-Path $csv) {
  $s = Import-Csv $csv | Where-Object { $_.cpu_core_eq -ne '' }
  if ($s) {
    function Med([string]$c) { $v = @($s | ForEach-Object { [double]$_.$c } | Sort-Object); if ($v.Count) { return $v[[int]($v.Count/2)] } else { return 0 } }
    "  TELEMETRIA (mediana su tutta la corsa): GPU $(Med 'gpu_util')%  $(Med 'clock_sm') MHz  $(Med 'watt') W | CPU $(Med 'cpu_core_eq') core"
    "  VRAM libera minima: $(($s | ForEach-Object { [int]$_.vram_libera } | Measure-Object -Minimum).Minimum) MiB   |   RAM libera minima: $(($s | ForEach-Object { [int]$_.ram_libera_mib } | Measure-Object -Minimum).Minimum) MiB"
  }
}
'PREFILL 100k FINITO'
