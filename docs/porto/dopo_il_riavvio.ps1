# QUALE COMPONENTE E' CRESCIUTA -- il braccio j_rif rifatto dopo il riavvio.
#
# Fatto acquisito stamattina: stesso binario, stessa configurazione, stesso
# SHA d'uscita e stessi contatori della cache, e il decode fa 12,84 contro
# 14,48 di f5b (05:06). In mezzo c'e' SOLO il riavvio delle 06:07, che ha
# applicato KB5123304 + KB5121003 + KB5120708.
#
# Il proponente non e' rallentato (8,45 -> 8,31 ms per chiamata, stesse 650
# chiamate) e il microbench del letto mappato da' 24,47 GiB/s contro i 24,4
# dell'11: la GPU e la banda stanno bene. Cresce solo il cammino del bersaglio,
# e cresce di un fattore costante fin dal primo campione.
#
# j_rif (05:10) aveva la sonda del join ACCESA e ha fatto 14,46, quindi la
# sonda non paga. La sua scomposizione, da confrontare riga per riga:
#
#   per grafo:  ingressi 2.834 ms (di cui sync 2.161)
#               calc CPU 0.848 ms
#               calc altri 3.050 ms
#   worker:     attesa-evento 9.271 ms
#               calcolo      15.445 ms      <- il fronte aperto della ripresa
#               attesa-lavoro 8.302 ms
#               join (sched) 24.698 ms
#
# Se cresce `calcolo`, e' la CPU. Se crescono `ingressi`/`sync`, e' l'host o il
# driver. Se cresce `calc altri`, e' la GPU -- ma il proponente dice di no.
#
# NIENTE CARATTERI NON-ASCII IN QUESTO FILE: PowerShell 5.1 lo legge in ANSI e
# spezza le stringhe. E' il motivo per cui tutti gli script qui scrivono "e'".
$ErrorActionPreference = 'Continue'
$bin  = 'D:\llama-overlap\build\bin\llama-server.exe'
$run  = 'D:\ds4_work\llama_run'
$MD   = 'D:/ds4-models/DSpark-draft-Q2K.gguf'
$PORTA = 8099
$OTD  = 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
$REL  = Join-Path $run 'dopo_il_riavvio.txt'
$msg  = [IO.File]::ReadAllText((Join-Path $run 'jprompt.txt'), [Text.Encoding]::UTF8)
$body = @{ messages = @(@{ role='user'; content=$msg }); max_tokens = 1200; temperature = 0; stream = $false } | ConvertTo-Json -Compress -Depth 5
function Nota([string]$t) { $t | Tee-Object -FilePath $REL -Append }

# CHIUSURA PULITA -- l'idioma e' in casa da sempre, in 31 script di questa
# cartella, e io avevo copiato spin.ps1 che e' fra i 40 che ammazzano.
# `Stop-Process -Force` e' una TerminateProcess: il contesto CUDA non viene
# distrutto e 74 GiB di pinnata li rilascia il sistema per conto suo, quando
# gli pare. Il server ha un gestore di segnale (tools/server/server.cpp:518),
# quindi la via pulita e' un Ctrl+C vero.
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
    # riserva, e va REGISTRATA come anomalia: se finiamo qui la pinnata non e'
    # stata rilasciata in modo ordinato e il braccio dopo ne paga il conto.
    if (-not $p.HasExited) { try { Stop-Process -Id $p.Id -Force } catch {}; $via = "$via -> RISERVA Stop-Process" }
    return $via
}

$tag  = if ($args.Count -gt 0) { $args[0] } else { 'p_rif' }
# A 512 slot siamo AL MURO (11,8 su 12,3 GiB). Quando la VRAM e' satura il
# gestore video di Windows sposta allocazioni a ogni sottomissione, e quel
# costo non si vede nel calcolo ne' nella banda: si vede nell'ATTESA
# dell'host, cioe' esattamente dove lo stiamo misurando. 448 slot liberano
# 432 MiB e falsificano o confermano in una corsa sola.
$SLOT = if ($args.Count -gt 1) { [string]$args[1] } else { '512' }
# Terzo parametro: ZAVORRA in MiB, inerte, per separare LA CAPIENZA dal MARGINE.
# Osservazione dell'utente: che il pool si "riprenda" la VRAM liberata e' solo
# una delle due letture; l'altra e' che a 512 il pool sia STROZZATO sotto la
# taglia che vorrebbe -- e un allocatore compresso ricicla di piu', e riciclare
# costa lavoro PER SOTTOMISSIONE, cioe' dove misuriamo il danno.
# Con 339 slot + ~645 MiB di zavorra si riporta il margine a quello di 512
# tenendo fermi slot, colpi e lavoro di cache: se `sync` risale, e' il margine.
# NB: la soglia dei 400 MiB fu falsificata l'11/8 con 870 MiB di zavorra (costo
# 0,6%), ma su una piattaforma dove sync valeva 2,17 invece di 6,5: quella
# falsificazione non si trasferisce a questo regime.
$ZAV = if ($args.Count -gt 2) { [string]$args[2] } else { $null }
while (Get-Process -Name llama-cli, llama-server -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 5 }
Start-Sleep -Seconds 30

$env:LLAMA_CACHE_BOZZA_SLOT = '32'
$env:LLAMA_CACHE_ESPERTI_BATCH = '8';   $env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
$env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
$env:LLAMA_CACHE_ESPERTI_CURA = '0';    $env:LLAMA_CACHE_ESPERTI_SCUDO = '0'
$env:LLAMA_CACHE_ESPERTI_MASSA = '0';   $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'
$env:LLAMA_CACHE_ESPERTI_LRU = '1';     $env:LLAMA_CACHE_ESPERTI_W = '0'
# LA VARIABILE CHE IL MANIFESTO NON STAMPA, ed e' costata una giornata.
# Con SFRATTO_PAR=0 la scelta della vittima e' la scansione SEQUENZIALE
# O(n_slot) su UN SOLO thread GPU (`decidi_fili` -> 1, cache-esperti.cu:2893);
# con =1 e' una riduzione cooperativa a 256 thread. E' lavoro DEVICE accodato
# sullo stream di calcolo, quindi il suo tempo cade dentro `us_sync` e lascia
# intatti calc CPU e calc altri -- ed e' proporzionale a sfratti x n_slot.
# Tutte le corse veloci (14,46-14,77) hanno sfratto_par=1; tutte le mie di
# oggi (12,79-12,88) hanno sfratto_par=0, perche' ho costruito l'ambiente DAL
# MANIFESTO e questa voce li' dentro non c'e'.
# Si verifica nel log, non qui: `grep -o "sfratto_par=[0-9]" <tag>.server.log`.
$env:LLAMA_CACHE_ESPERTI_SFRATTO_PAR = '1'
$env:LLAMA_CACHE_ESPERTI_SLOT = $SLOT
$env:LLAMA_CACHE_ESPERTI_FORK = '2';    $env:LLAMA_CACHE_ESPERTI_FORK_BLOCCHI = '8'
$env:LLAMA_ACCEPTMOE = '0';             $env:LLAMA_CKPT_CRONO = '0'
$env:LLAMA_SPEC_CONF_ESENTA_POS0 = '0'; $env:LLAMA_SPEC_DRAFT_TOPK = '1'
$env:LLAMA_MAPPED_IBRIDO = '1';         $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
$env:LLAMA_OVERLAP_ASYNC = '1';         $env:LLAMA_OVERLAP_K = '2'
$env:LLAMA_OVERLAP_BATCH_MAX = '2';     $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'
$env:LLAMA_OVERLAP_PIN = '1';           $env:LLAMA_OVERLAP_JOIN_ASYNC = '0'
$env:LLAMA_KV_RING = '1';               $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
$env:LLAMA_KV_ROLLBACK_PARZIALE = '1';  $env:LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
$env:LLAMA_VRAM_A_FASI = '0';           $env:LLAMA_DSV4_INDEXER_FUSO = '0'
$env:LLAMA_DSV4_HC_FUSO = '5';          $env:GGML_CUDA_GRAPH_OPT = '0'
if ($ZAV) { $env:LLAMA_VRAM_ZAVORRA = $ZAV } else { [Environment]::SetEnvironmentVariable('LLAMA_VRAM_ZAVORRA', $null) }
[Environment]::SetEnvironmentVariable('LLAMA_CACHE_ORACOLO', $null)
$env:GGML_SCHED_PROFILO = '1'          # <- come j_rif

$up = [math]::Round(((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes,1)
Nota ""
Nota ("=== " + $tag + "  " + [DateTime]::Now.ToString('HH:mm') + "   (uptime " + $up + " min)  SLOT=" + $SLOT + "  -- confronto con j_rif delle 05:10 ===")

$a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf', '-md', $MD, '--spec-type', 'draft-dspark', '--fit', 'off',
  '-ngld', '99', '--spec-draft-n-max', '1', '--spec-draft-ubatch-size', '16', '-otd', $OTD,
  '-c', '10000', '-ub', '64', '-np', '1', '-ngl', '99',
  '-ot', 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped', '-t', '7', '--no-mmap',
  '-lv', '4', '--host', '127.0.0.1', '--port', "$PORTA")
$proc = Start-Process -FilePath $bin -ArgumentList $a -WindowStyle Hidden -PassThru `
  -RedirectStandardError (Join-Path $run "$tag.server.log") -RedirectStandardOutput (Join-Path $run "$tag.server.out")

# Campionamento dello stato hardware DURANTE la corsa: e' l'unica cosa che non
# abbiamo mai osservato, e il riavvio e' il sospettato.
$camp = Join-Path $run "$tag.hw.csv"
$sampler = Start-Job -ScriptBlock {
  param($out)
  "t,sm_mhz,mem_mhz,power_w,util,pcie_gen,pcie_width,throttle,vram_usata,vram_libera,cpu_perf,server_vivi,ram_libera_gb" | Out-File $out -Encoding utf8
  for ($i = 0; $i -lt 200; $i++) {
    # vram.used/free servono a giudicare il MURO in decode: togliere slot non
    # libera VRAM, perche' il pool temporaneo dei matmul se la riprende (512 ->
    # 448 ha lasciato l'occupazione a 11801 MiB su 12288).
    $g = (& nvidia-smi --query-gpu=clocks.sm,clocks.mem,power.draw,utilization.gpu,pcie.link.gen.gpucurrent,pcie.link.width.current,clocks_throttle_reasons.active,memory.used,memory.free --format=csv,noheader,nounits) -join ','
    # il contatore in inglese NON esiste su Windows italiano e rendeva -1:
    # la via CIM e' neutrale alla lingua
    $c = try { [math]::Round(((Get-CimInstance Win32_PerfFormattedData_Counters_ProcessorInformation -EA Stop | Where-Object { $_.Name -eq '_Total' }).PercentProcessorPerformance),1) } catch { -1 }
    # LA CONTESA SI MISURA, NON SI DEDUCE: v_sota (06:45) e' partita a 12,51 ed e'
    # collassata a 9,3 dentro la stessa corsa. Una corsa che parte giusta e degrada
    # ha qualcuno accanto. Da qui in poi ogni corsa porta il suo testimone.
    $n = @(Get-Process -Name llama-server, llama-cli -EA SilentlyContinue).Count
    $r = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)
    "$($i*3),$g,$c,$n,$r" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 3
  }
} -ArgumentList $camp

$su = $false
for ($i = 0; $i -lt 90; $i++) {
  Start-Sleep -Seconds 10
  if ($proc.HasExited) { Nota "*** MORTO ***"; break }
  try { if ((Invoke-WebRequest "http://127.0.0.1:$PORTA/health" -TimeoutSec 5 -UseBasicParsing).StatusCode -eq 200) { $su = $true; break } } catch {}
}
if ($su) {
  try {
    $out = Invoke-RestMethod "http://127.0.0.1:$PORTA/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 7200
    $risp = [string]$out.choices[0].message.content
    if (-not $risp) { $risp = [string]$out.choices[0].message.reasoning_content }
    $risp | Out-File (Join-Path $run "$tag.output.html") -Encoding utf8
  } catch { Nota "*** RICHIESTA FALLITA ***" }
}
# SI SALVA PRIMA, SI SPEGNE DOPO. `Spegni` manda GenerateConsoleCtrlEvent al
# gruppo della console e puo' uccidere QUESTO script: l'8/12 alle 08:06 il
# braccio k339 e' girato per intero e il suo numero e' andato perso nella
# pulizia, perche' spegnevo prima di leggere il log. Tutte le metriche vengono
# dal log del server, che e' gia' completo quando la risposta HTTP e' tornata:
# non c'e' nessun motivo di chiudere prima di leggerlo.
Stop-Job $sampler -EA SilentlyContinue; Remove-Job $sampler -Force -EA SilentlyContinue
Start-Sleep -Seconds 2

$log = Join-Path $run "$tag.server.log"
function M([string]$pat) { $m = Select-String -Path $log -Pattern $pat -EA SilentlyContinue | Select-Object -Last 1
                           if ($m) { return $m.Matches[0].Groups[1].Value } else { return '-' } }
$ts = M '\|        eval time =.*?([0-9.]+) tokens per second'
$p1 = M 'draft acceptance = ([0-9.]+)'
$sha = if (Test-Path (Join-Path $run "$tag.output.html")) { (Get-FileHash (Join-Path $run "$tag.output.html") -Algorithm SHA256).Hash.Substring(0,12) } else { '-' }
Nota ("  t/s " + $ts + "   p1 " + $p1 + "   SHA " + $sha + "        (j_rif delle 05:10 -> 14,46)")
Nota ""
Nota "  --- la scomposizione, contro quella delle 05:10 ---"
Select-String -Path $log -Pattern 'sched-profilo' -EA SilentlyContinue | Select-Object -Last 2 | ForEach-Object { Nota ("  ADESSO  " + ($_.Line -replace '^.*?sched-profilo: ','')) }
Nota "  05:10   2600 grafi, 35.2 split/grafo, per grafo: ingressi 2.839 ms (di cui sync 2.166), calc CPU 0.848 ms, calc altri 3.015 ms"
Nota "  05:10   worker 10 lavori/grafo, per grafo: attesa-evento 9.271 ms, calcolo 15.445 ms, attesa-lavoro 8.302 ms | join (sched) 24.698 ms"
Nota ""
if (Test-Path $camp) {
  $h = @(Import-Csv $camp | Where-Object { $_.util -match '^[0-9]+$' -and [int]$_.util -gt 50 })
  if ($h.Count -gt 0) {
    $sm  = @($h | ForEach-Object { [int]$_.sm_mhz } | Sort-Object)
    $mem = @($h | ForEach-Object { [int]$_.mem_mhz } | Sort-Object)
    $cpu = @($h | ForEach-Object { [double]$_.cpu_perf } | Sort-Object)
    $pw  = ($h | ForEach-Object { [double]$_.power_w } | Measure-Object -Average).Average
    Nota ("  hardware sotto carico (" + $h.Count + " campioni con util>50):")
    Nota ("    SM mediano " + $sm[[int]($sm.Count/2)] + " MHz  (min " + $sm[0] + ", max " + $sm[-1] + ")   mem " + $mem[[int]($mem.Count/2)] + " MHz   potenza " + [math]::Round($pw,1) + " W")
    Nota ("    PCIe gen " + ($h[-1].pcie_gen) + " x" + ($h[-1].pcie_width) + "   throttle " + ($h[-1].throttle))
    $vu = @($h | ForEach-Object { [int]$_.vram_usata } | Sort-Object)
    $vl = @($h | ForEach-Object { [int]$_.vram_libera } | Sort-Object)
    Nota ("    VRAM in decode: usata " + $vu[[int]($vu.Count/2)] + " MiB, libera " + $vl[[int]($vl.Count/2)] + " MiB   (512 slot -> 11801 usata / 315 libera)")
    Nota ("    CPU prestazioni mediana " + $cpu[[int]($cpu.Count/2)] + " per cento  (100 = base 3,8 GHz, 120 = circa 4,55 GHz)")
    $srv = @($h | ForEach-Object { [int]$_.server_vivi })
    $ram = @($h | ForEach-Object { [double]$_.ram_libera_gb } | Sort-Object)
    $max = ($srv | Measure-Object -Maximum).Maximum
    Nota ("    server vivi: max " + $max + "   RAM libera minima " + $ram[0] + " GB")
    if ($max -gt 1) { Nota "    *** CONTESA: piu' di un server durante la corsa, la misura NON vale ***" }
  }
}
Nota "DOPO_IL_RIAVVIO FINITO"

# Adesso, e SOLO adesso, si spegne: il risultato e' gia' su disco. Se il Ctrl+C
# ammazza anche questo script, non si perde niente e il regista puo' proseguire.
$via = Spegni $proc
Nota ("  chiusura: " + $via)
