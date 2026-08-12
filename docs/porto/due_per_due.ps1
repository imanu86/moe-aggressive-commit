# BOZZA x LANE: il 2x2, con i gemelli esatti di ieri.
#
# LA DOMANDA. Dopo il riavvio del 12/8 il banco rende il 13-15% in meno, e la
# perdita e' localizzata in `sync` (attesa host al confine CPU-GPU): 2,166 ->
# 6,5-7,1 ms per grafo, a calcolo CPU e GPU invariati. L'ipotesi e' che sia un
# costo PER OPERAZIONE HOST, non per byte.
#
# Se l'ipotesi tiene, il danno deve colpire in modo MOLTO diverso le quattro
# celle, perche' attraversano l'host un numero di volte molto diverso:
#   - la lane impone LLAMA_MAPPED_IBRIDO=1, cioe' `is_host`, che fa cadere lo
#     scheduler nel fallback che copia UN ESPERTO PER VOLTA: ~277
#     cudaMemcpyAsync per token, tutte sull'host;
#   - senza lane e senza IBRIDO quel fallback non si convoca.
#
# LA MAPPA STORICA (migliori sul disco, piattaforma BUONA):
#   A  bozza SI + lane ON  (IBRIDO=1)   14,78  b_f512    FORK=2/8, 512 slot
#   B  bozza SI + lane OFF (IBRIDO=0)   12,85  z_bozza   FORK=0,   512 slot
#   B' bozza SI + lane OFF (IBRIDO=1)   12,64  x512      FORK=0,   512 slot
#   D  bozza no + lane OFF (IBRIDO=0)   12,43  b8b       FORK=2/8, 512 slot
#
# Sulla piattaforma buona la lane valeva +15% (14,78 contro 12,85). Oggi con la
# lane accesa facciamo 12,30-12,45, gia' sotto il 12,85 che la cella SENZA lane
# faceva ieri.
#
# I QUATTRO BRACCI E COSA DECIDE CIASCUNO:
#   1 g_b8b    gemello esatto di b8b (12,43). Cammino GPU puro: niente lane,
#              niente bozza, niente IBRIDO. E' LA DIAGNOSI PIU' IMPORTANTE:
#              se resta a 12,43 il danno e' tutto nel cammino lane/IBRIDO;
#              se cala anche lei del 13%, e' universale e l'ipotesi cade.
#   2 g_zbozza gemello esatto di z_bozza (12,85). Aggiunge la bozza al cammino
#              GPU puro: misura quanto vale la speculazione oggi.
#   3 n_fork   LA CELLA MAI FATTA: bozza + lane spenta + IBRIDO=0 + FORK=2/8.
#              La ripresa la segna come non provata. Se batte i 12,45 di oggi
#              con la lane, la configurazione da usare cambia.
#   4 n_ibrido bozza + lane spenta ma IBRIDO=1 + FORK=2/8. Separa il contributo
#              di IBRIDO da quello della lane: e' l'unico modo di sapere se le
#              277 copie contano da sole.
#
# NIENTE CARATTERI NON-ASCII: PowerShell 5.1 legge il file in ANSI.
$ErrorActionPreference = 'Continue'
$bin  = 'D:\llama-overlap\build\bin\llama-server.exe'
$run  = 'D:\ds4_work\llama_run'
$MD   = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD  = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$REL  = Join-Path $run 'due_per_due.txt'
$msg  = [IO.File]::ReadAllText((Join-Path $run 'jprompt.txt'), [Text.Encoding]::UTF8)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 1200; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5
function Nota([string]$t) { $t | Tee-Object -FilePath $REL -Append }

Add-Type -Namespace '' -Name CL -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@
function Spegni($p) {
    if ($null -eq $p -or $p.HasExited) { return 'gia-uscito' }
    $via = 'ctrl-c'
    [void][CL]::FreeConsole()
    if ([CL]::AttachConsole([uint32]$p.Id)) {
        [void][CL]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CL]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][CL]::FreeConsole(); [void][CL]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    } else { $via = 'AttachConsole-fallita' }
    $p.WaitForExit(60000) | Out-Null
    if (-not $p.HasExited) { try { Stop-Process -Id $p.Id -Force } catch {}; $via = "$via -> RISERVA" }
    return $via
}

$bracci = @(
  @{ tag='g_b8b';    bozza=$false; ibrido='0'; async='0'; k='0'; fork='2'; blocchi='8';  rollback='0'; atteso='12,43 (b8b)' }
  @{ tag='g_zbozza'; bozza=$true;  ibrido='0'; async='0'; k='0'; fork='0'; blocchi='32'; rollback='1'; atteso='12,85 (z_bozza)' }
  @{ tag='n_fork';   bozza=$true;  ibrido='0'; async='0'; k='0'; fork='2'; blocchi='8';  rollback='1'; atteso='MAI FATTA' }
  @{ tag='n_ibrido'; bozza=$true;  ibrido='1'; async='0'; k='0'; fork='2'; blocchi='8';  rollback='1'; atteso='MAI FATTA (x512 a FORK=0 -> 12,64)' }
)
# UN BRACCIO PER PROCESSO. La chiusura pulita manda GenerateConsoleCtrlEvent(0,0)
# al gruppo della console, quindi anche a QUESTO script: in un ciclo si suicida
# dopo il primo giro (successo due volte il 12/8). Il regista chiama questo file
# una volta per braccio, passando il tag.
if ($args.Count -gt 0) { $bracci = @($bracci | Where-Object { $_.tag -eq $args[0] }) }
if ($bracci.Count -eq 0) { "nessun braccio con quel nome"; exit 1 }

Nota ""
Nota ("=" * 104)
Nota ("BOZZA x LANE  " + [DateTime]::Now.ToString('yyyy-MM-dd HH:mm'))
Nota ("oggi, cella A (bozza SI + lane ON + IBRIDO=1, FORK=2/8, 512): 12,30 / 12,45   -- ieri la stessa faceva 14,46-14,78")
Nota ("=" * 104)

$esiti = @()
foreach ($b in $bracci) {
  $tag = $b.tag
  while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }
  for ($i = 0; $i -lt 30; $i++) {
    $v = 0; try { $v = [int]((& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) | Select-Object -First 1) } catch { break }
    if ($v -lt 1200) { break }
    Start-Sleep -Seconds 5
  }
  Start-Sleep -Seconds 30

  # comuni a tutti i bracci
  $env:LLAMA_CACHE_ESPERTI_BATCH = '8';   $env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
  $env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
  $env:LLAMA_CACHE_ESPERTI_CURA = '0';    $env:LLAMA_CACHE_ESPERTI_SCUDO = '0'
  $env:LLAMA_CACHE_ESPERTI_MASSA = '0';   $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'
  $env:LLAMA_CACHE_ESPERTI_LRU = '1';     $env:LLAMA_CACHE_ESPERTI_W = '0'
  $env:LLAMA_CACHE_ESPERTI_SLOT = '512'
  $env:LLAMA_ACCEPTMOE = '0';             $env:LLAMA_CKPT_CRONO = '0'
  $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
  $env:LLAMA_OVERLAP_BATCH_MAX = '2';     $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'
  $env:LLAMA_OVERLAP_PIN = '1';           $env:LLAMA_OVERLAP_JOIN_ASYNC = '0'
  $env:LLAMA_KV_RING = '1';               $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
  $env:LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
  $env:LLAMA_VRAM_A_FASI = '0';           $env:LLAMA_DSV4_INDEXER_FUSO = '0'
  $env:LLAMA_DSV4_HC_FUSO = '5';          $env:GGML_CUDA_GRAPH_OPT = '0'
  $env:LLAMA_SPEC_CONF_ESENTA_POS0 = '0'
  [Environment]::SetEnvironmentVariable('LLAMA_VRAM_ZAVORRA', $null)
  [Environment]::SetEnvironmentVariable('LLAMA_CACHE_ORACOLO', $null)
  $env:GGML_SCHED_PROFILO = '1'

  # specifici del braccio
  $env:LLAMA_MAPPED_IBRIDO       = $b.ibrido
  $env:LLAMA_OVERLAP_ASYNC       = $b.async
  $env:LLAMA_OVERLAP_K           = $b.k
  $env:LLAMA_CACHE_ESPERTI_FORK  = $b.fork
  $env:LLAMA_CACHE_ESPERTI_FORK_BLOCCHI = $b.blocchi
  $env:LLAMA_KV_ROLLBACK_PARZIALE = $b.rollback
  if ($b.bozza) { $env:LLAMA_CACHE_BOZZA_SLOT = '32'; $env:LLAMA_SPEC_DRAFT_TOPK = '1' }
  else { [Environment]::SetEnvironmentVariable('LLAMA_CACHE_BOZZA_SLOT', $null)
         [Environment]::SetEnvironmentVariable('LLAMA_SPEC_DRAFT_TOPK', $null) }

  $up = [math]::Round(((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes,1)
  Nota ""
  Nota ("[" + [DateTime]::Now.ToString('HH:mm') + "] " + $tag + "   bozza=" + $(if($b.bozza){'SI'}else{'no'}) + " IBRIDO=" + $b.ibrido + " ASYNC=" + $b.async + " K=" + $b.k + " FORK=" + $b.fork + "/" + $b.blocchi + "   atteso: " + $b.atteso + "   (uptime " + $up + " min)")

  $a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf')
  if ($b.bozza) {
    $a += @('-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off', '-ngld', '99',
            '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16', '-otd', $OTD)
  }
  $a += @('-c', '10000', '-ub', '64', '-np', '1', '-ngl', '99',
          '-ot', 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped', '-t', '7', '--no-mmap',
          '-lv', '4', '--host', '127.0.0.1', '--port', "$PORTA")

  $proc = Start-Process -FilePath $bin -ArgumentList $a -PassThru -NoNewWindow `
    -RedirectStandardError (Join-Path $run "$tag.server.log") -RedirectStandardOutput (Join-Path $run "$tag.server.out")

  $camp = Join-Path $run "$tag.hw.csv"
  $sampler = Start-Job -ScriptBlock {
    param($out)
    "t,sm,mem,watt,util,gen,width,throttle,vram_usata,vram_libera,cpu_perf,server" | Out-File $out -Encoding utf8
    for ($i = 0; $i -lt 300; $i++) {
      $g = (& nvidia-smi --query-gpu=clocks.sm,clocks.mem,power.draw,utilization.gpu,pcie.link.gen.gpucurrent,pcie.link.width.current,clocks_throttle_reasons.active,memory.used,memory.free --format=csv,noheader,nounits) -join ','
      $c = try { [math]::Round(((Get-CimInstance Win32_PerfFormattedData_Counters_ProcessorInformation -EA Stop | Where-Object { $_.Name -eq '_Total' }).PercentProcessorPerformance),1) } catch { -1 }
      $n = @(Get-Process -Name llama-server, llama-cli -EA SilentlyContinue).Count
      "$($i*3),$g,$c,$n" | Out-File $out -Append -Encoding utf8
      Start-Sleep -Seconds 3
    }
  } -ArgumentList $camp

  $su = $false
  for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 10
    if ($proc.HasExited) { Nota "     *** MORTO ***"; break }
    try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su = $true; break } } catch {}
  }
  if ($su) {
    try {
      $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 7200
      $risp = [string]$out.choices[0].message.content
      if (-not $risp) { $risp = [string]$out.choices[0].message.reasoning_content }
      $risp | Out-File (Join-Path $run "$tag.output.html") -Encoding utf8
    } catch { Nota "     *** RICHIESTA FALLITA ***" }
  }
  # SI SALVA PRIMA, SI SPEGNE DOPO: `Spegni` puo' uccidere questo script.
  Stop-Job $sampler -EA SilentlyContinue; Remove-Job $sampler -Force -EA SilentlyContinue
  Start-Sleep -Seconds 2

  $log = Join-Path $run "$tag.server.log"
  function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                             if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
  $ts  = M '\|        eval time =.*?([0-9.]+) tokens per second'
  $ml  = M 'mean len =\s+([0-9.]+)'
  $p1  = M 'draft acceptance = ([0-9.]+)'
  $syn = M 'di cui sync ([0-9.]+)\)'
  $col = M 'cache-esperti: domanda [0-9]+ \(colpi [0-9]+ = ([0-9.]+)%'
  $sha = if (Test-Path (Join-Path $run "$tag.output.html")) { (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12) } else { '-' }
  # senza bozza mean len non esiste: il ciclo E' il tempo per token
  $ciclo = if ($ts -ne '-') { if ($ml -ne '-') { [math]::Round((1000/[double]$ts)*[double]$ml,1) } else { [math]::Round(1000/[double]$ts,1) } } else { '-' }
  $vram = '-'
  if (Test-Path $camp) {
    $h = @(Import-Csv $camp | Where-Object { $_.util -match '^[0-9]+$' -and [int]$_.util -gt 50 })
    if ($h.Count -gt 0) { $vu = @($h | ForEach-Object { [int]$_.vram_usata } | Sort-Object); $vram = $vu[[int]($vu.Count/2)] }
  }
  Nota ("     t/s " + $ts + "   ciclo " + $ciclo + "   p1 " + $p1 + "   sync " + $syn + "   colpi " + $col + "%   VRAM " + $vram + "   SHA " + $sha + "   chiusura " + $via)
  $esiti += [pscustomobject]@{ tag=$tag; ts=$ts; ciclo=$ciclo; p1=$p1; sync=$syn; colpi=$col; atteso=$b.atteso }
}

Nota ""
Nota ("-" * 104)
Nota "  braccio    t/s     ciclo    p1        sync    colpi    ieri"
foreach ($e in $esiti) {
  Nota ("  {0,-10} {1,-7} {2,-8} {3,-9} {4,-7} {5,-8} {6}" -f $e.tag, $e.ts, $e.ciclo, $e.p1, $e.sync, ($e.colpi + '%'), $e.atteso)
}
Nota ""
Nota "  ATTENZIONE al ciclo senza bozza: li' mean len non esiste e il ciclo E' il ms/token."
Nota "  Il confronto fra celle con e senza bozza si fa sul t/s, non sul ciclo."
Nota "DUE PER DUE FINITO"
