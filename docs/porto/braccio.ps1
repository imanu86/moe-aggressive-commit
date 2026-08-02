# Un braccio del primo run del porto. Uso: .\braccio.ps1 -Arm A|B|C [-Tokens 150]
param(
    [Parameter(Mandatory)][ValidateSet('A','B','C','D','E','F','G')][string]$Arm,
    [int]$Tokens = 150,
    [int]$Ctx    = 8192,
    [int]$Port   = 8080,
    # C: e' l'NVMe (Lexar EQ790), D: e' il SATA (EMTEC X160): ~7000 contro ~550 MB/s.
    # Il riferimento gira da C:. Su un runtime che fa streaming dal disco, sbagliare
    # unita' significa misurare il disco invece del codice.
    #
    # PESI NUOVI dall'1/8: decisione utente, i vecchi (ds4-2bit.gguf) sono accantonati
    # insieme al binario del fork. Non tornarci senza che l'utente lo chieda.
    [string]$Model = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf',
    [string]$OutDir = 'D:\ds4_work\porto_run',
    # Prova a variabile singola: -Override @{ 'DS4_G73_OPEN' = '1' }
    # Applicato DOPO il preset, cosi' la sovrascrittura e' esplicita e finisce nel tag.
    [hashtable]$Override = @{},
    [switch]$NoStreaming,
    # ragionamento: SPENTO per default. -Think:$true per misurarlo di proposito.
    [bool]$Think = $false,
    # sblocca il braccio A, che dall'1/8 e' accantonato insieme ai pesi vecchi
    [switch]$Comunque
)
$ErrorActionPreference = 'Stop'
$R = 'C:\Users\imanu\source\repos\moe-aggressive-commit'
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$tag = "{0}_{1}" -f $Arm, (Get-Date -Format 'HHmmss')
if ($Think) { $tag = "$tag`_THINK" }
$srvLog = Join-Path $OutDir "$tag.server.log"

# --- igiene: nessuna DS4_* ereditata, mai ---
Get-ChildItem Env: | Where-Object Name -Like 'DS4_*' |
    ForEach-Object { Remove-Item -LiteralPath ("Env:{0}" -f $_.Name) -EA SilentlyContinue }

# token di spegnimento pulito, 64 hex
$tok = -join ((1..64) | ForEach-Object { '0123456789abcdef'[(Get-Random -Max 16)] })
$env:DS4_G130_U1_SHUTDOWN_TOKEN = $tok

# --- COMUNE A TUTTI E TRE I BRACCI, e non e' un nostro opt-in ---
# E' un parametro di regolazione del runtime come ctx, e il binario PORTATO legge
# la stessa variabile (ds4.c:12414) col medesimo default 2048 (ds4.c:12398).
# A 2048 i buffer di prefill tengono occupata la VRAM proprio quando la cache
# esperti viene dimensionata: capacity 135 invece di 306, e da li' 70877 sfratti
# del backbone in 64 token. Misurato l'1/8: 256 porta free_at_size da 1045 a 2199 MiB.
# Se i tre bracci non hanno lo STESSO valore, non stiamo confrontando il porto.
$env:DS4_METAL_PREFILL_CHUNK = '256'

switch ($Arm) {
  'A' {  # ACCANTONATO l'1/8 per decisione utente: il fork non e' piu' il banco.
         # Resta lanciabile solo con -Comunque, e il tag lo dichiara.
    if (-not $Comunque) {
        throw "braccio A ACCANTONATO (fork + pesi vecchi). Il banco e' il tronco: usa -Arm B o C. Per forzare: -Comunque"
    }
    $exe = "$R\ds4-p4a\build-native\ds4_server.exe"
    . "$R\docs\porto\preset_A.ps1"                   # la fonte, non un env trovato col grep
    $env:DS4_G130_U1_SHUTDOWN_TOKEN = $tok
    $tag = "$tag`_ACCANTONATO"
  }
  'B' {  # il TRONCO NUDO: tutti i nostri opt-in ASSENTI, non a zero
    $exe = "$R\ds4-port\build-verify\ds4-server.exe"
  }
  'C' {  # 0731 con la nostra politica accesa â€” RIFATTO col porto v2 (2/8)
    # Storia, perche' non si ripeta: fino al 2/8 questo braccio aveva TRE
    # variabili e girava di fatto come upstream nudo. Il motivo vero l'ha
    # trovato Codex: `DS4_CUDA_STREAMING_EXPERT_CACHE_N` non era letto da
    # NESSUN file di 0731, e la cache esperti si accendeva solo col vecchio
    # flag interno, che io avevo escluso. Risultato: arena orfana, zero righe
    # [iq2-expert-cache-size], e un 1,70 t/s attribuito alla "nostra politica".
    #
    # Col porto v2 la cache si accende per quattro vie indipendenti
    # (vram_expert_cache.cpp, enabled()): il flag interno, TIERING=enforce,
    # MOE_GPU_RESIDENT_ROUTES, o semplicemente chiedere N slot. Qui usiamo le
    # ultime due, che sono le nostre.
    $exe = "$R\ds4-port\build-verify\ds4-server.exe"

    # --- residenza host: l'arena ---
    $env:DS4_CUDA_DYNAMIC_ARENA_GB      = '30'
    $env:DS4_CUDA_PREFILL_MASS_OBSERVE  = '1'
    $env:DS4_CUDA_PREFILL_MASS_WRAP     = '1'   # senza questo non pubblica

    # --- cache esperti in VRAM: ora qualcuno la legge ---
    $env:DS4_CUDA_STREAMING_EXPERT_CACHE_N = '320'
    $env:DS4_CUDA_VRAM_INVERTED_PRIORITY   = '1'    # arma il sizing preventivo
    $env:DS4_CUDA_VRAM_BACKBONE_RESERVE_MB = '1536'
    $env:DS4_CUDA_VRAM_HYSTERESIS_MB       = '256'
    $env:DS4_CUDA_VRAM_MIN_EXPERT_SLOTS    = '32'   # pavimento se le riserve azzerano

    # --- tiering e ammissione ---
    $env:DS4_EXPERT_TIERING             = 'enforce'
    $env:DS4_EXPERT_TIER_POLICY         = 'mass-lfru'
    $env:DS4_EXPERT_TIER_CLOCK_CALLS    = '430'
    $env:DS4_EXPERT_TIER_MIN_FREQUENCY  = '3'
    $env:DS4_EXPERT_TIER_HYSTERESIS     = '1.25'
    $env:DS4_EXPERT_TIER_REPLACEMENT_BUDGET = '16'
    # ADMIT_KNOCKS_SSD non c'e': su 0731 il seed RAM e' ranking upstream, non
    # una transizione governata dalla policy. Dichiarato non portabile.

    # --- la coda di I/O: 229 IOPS a coda 2 su un NVMe, con file_qd=1 ---
    $env:DS4_CUDA_MOE_IO_QD             = '4'
    $env:DS4_CUDA_MOE_CACHE_POLICY      = 'lru'
    $env:DS4_CUDA_MOE_CACHE_STATS       = '1'
  }
  'D' {  # 0731 NUDO ma con la sola coda I/O: isola la leva che i numeri indicano
    $exe = "$R\ds4-port\build-verify\ds4-server.exe"
    $env:DS4_CUDA_MOE_IO_QD = '4'
  }
  'E' {  # 0731 SENZA arena, ma con cache esperti e coda. Nasce dal fallimento di C.
    # C con l'arena da 30 GiB ha dato free_at_size_mib=0.0 e capacity=0: la cache
    # non si e' potuta dimensionare perche' CUDA riportava ZERO VRAM libera, pur
    # con il backbone a 8393 MiB su 12287 totali. 3888 MiB non tracciati da noi.
    # Sul FORK, stesso ctx e stessa arena, free_at_size era 1977 MiB.
    # Ipotesi: su WDDM i 30 GiB host mapped-pinned costano VRAM in tabelle di
    # pagina e indirizzamento. Qui la tolgo e lascio che sia la cache VRAM a
    # tenere gli esperti â€” che e' anche il verso in cui 0731 e' progettato.
    $exe = "$R\ds4-port\build-verify\ds4-server.exe"
    $env:DS4_CUDA_STREAMING_EXPERT_CACHE_N = '320'
    $env:DS4_EXPERT_TIERING             = 'enforce'
    $env:DS4_EXPERT_TIER_POLICY         = 'mass-lfru'
    $env:DS4_EXPERT_TIER_CLOCK_CALLS    = '430'
    $env:DS4_EXPERT_TIER_MIN_FREQUENCY  = '3'
    $env:DS4_EXPERT_TIER_HYSTERESIS     = '1.25'
    $env:DS4_EXPERT_TIER_REPLACEMENT_BUDGET = '16'
    $env:DS4_CUDA_MOE_IO_QD             = '4'
    $env:DS4_CUDA_MOE_CACHE_POLICY      = 'lru'
    $env:DS4_CUDA_MOE_CACHE_STATS       = '1'
    # NIENTE arena, NIENTE INVERTED_PRIORITY: il sizing preventivo con 2304 MiB
    # di riserva su zero libero e' cio' che ha spento la cache nel braccio C.
  }
  'F' {  # L'INTUIZIONE DELL'UTENTE: il backbone non lascia spazio in VRAM perche'
         # sul fork una parte la tenevamo in RAM pinnata.
    # Sul fork DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB=2 mascherava 2 GiB di
    # pesi perche' arrivassero dalla RAM invece di occupare VRAM: la capacity
    # della cache esperti passo' da 135 a 253. E' l'unica leva che agisce sul
    # numeratore del problema di stanotte (backbone 8394 MiB su 12287, free=0).
    #
    # Arena a 24 GiB e non 30: quella da 30 azzerava free_at_size. Non e' provato
    # che la colpa fosse sua â€” il braccio E senza arena aveva free=0 lo stesso â€”
    # ma 24 lascia 6 GiB di margine in piu' sulla RAM.
    #
    # NIENTE INVERTED_PRIORITY: nel braccio C armava il sizing preventivo con
    # 2304 MiB di riserva su zero libero, ed e' cio' che ha dato capacity=0.
    $exe = "$R\ds4-port\build-verify\ds4-server.exe"
    $env:DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB = '2'
    $env:DS4_CUDA_DYNAMIC_ARENA_GB      = '24'
    $env:DS4_CUDA_PREFILL_MASS_OBSERVE  = '1'
    $env:DS4_CUDA_PREFILL_MASS_WRAP     = '1'
    $env:DS4_CUDA_STREAMING_EXPERT_CACHE_N = '320'
    $env:DS4_EXPERT_TIERING             = 'enforce'
    $env:DS4_EXPERT_TIER_POLICY         = 'mass-lfru'
    $env:DS4_CUDA_MOE_IO_QD             = '4'
    $env:DS4_CUDA_MOE_CACHE_POLICY      = 'lru'
  }
  'G' {  # E + la cache q8/f16 spenta. Il braccio che nasce dalla misura del 2/8.
    # Il run con DS4_CUDA_GRAPH_TENSOR_MANAGED=1 ha spostato 311 allocazioni di
    # tensori del grafo da cudaMalloc a cudaMallocManaged: 441 MiB, e capacity
    # e' rimasta 0. Quindi eb3c0b8 NON era la causa: valeva 441 MiB, non 2 GiB.
    # Il bilancio vero al decode-start di quel run:
    #     totale 12287   model_range_live 8394   q8/f16 1996   free 0
    # Il backbone e' legittimo, serve a ogni token. La q8/f16 no: e' un percorso
    # di accelerazione che dequantizza Q8->F16 per usare i tensor core invece del
    # kernel scalare DP4A. Su 2 bit la nostra memoria dice che non tocca la
    # qualita' (crepa di precisione = ramo q8/f16, NO_Q8_F16_CACHE = sicura).
    #
    # Perche' cresce a 1996 MiB con una riserva di 4096: si alloca in PREFILL,
    # quando il backbone non e' ancora tutto residente e free e' alto. Quando il
    # backbone arriva, la q8/f16 ha gia' preso il posto. Prima serva, prima servita.
    # cuda_q8_f16_cache_has_budget: `if (limit == 0) return 0` (ds4_cuda.cu:2970).
    #
    # Il baratto: 1996 MiB di q8/f16 contro ~270 slot esperti. Sul fork 274 slot
    # davano 474.937 vram_hits e 4,49 t/s. Se il baratto vale, si vede qui.
    $exe = "$R\ds4-port\build-verify\ds4-server.exe"
    $env:DS4_CUDA_Q8_F16_CACHE_MB       = '0'
    $env:DS4_CUDA_STREAMING_EXPERT_CACHE_N = '320'
    $env:DS4_EXPERT_TIERING             = 'enforce'
    $env:DS4_EXPERT_TIER_POLICY         = 'mass-lfru'
    $env:DS4_EXPERT_TIER_CLOCK_CALLS    = '430'
    $env:DS4_EXPERT_TIER_MIN_FREQUENCY  = '3'
    $env:DS4_EXPERT_TIER_HYSTERESIS     = '1.25'
    $env:DS4_EXPERT_TIER_REPLACEMENT_BUDGET = '16'
    $env:DS4_CUDA_MOE_IO_QD             = '4'
    $env:DS4_CUDA_MOE_CACHE_POLICY      = 'lru'
    $env:DS4_CUDA_MOE_CACHE_STATS       = '1'
  }
}
foreach ($k in $Override.Keys) {
    Set-Item -Path ("Env:{0}" -f $k) -Value $Override[$k]
    $tag = "$tag`_$k=$($Override[$k])"
}
if ($Override.Count) { $srvLog = Join-Path $OutDir "$tag.server.log" }
if (-not (Test-Path $exe)) { throw "binario assente: $exe" }

# Il FORK non ha --ssd-streaming: da noi lo streaming lo guida l'ambiente (l'arena).
# E' un flag di upstream, quindi va solo ai bracci B e C.
$args = @('-m', $Model, '--cuda', '-c', "$Ctx", '-n', "$Tokens",
          '--host','127.0.0.1','--port',"$Port")
# -NoStreaming: prova la doppia residenza. Il tronco con --ssd-streaming ha il
# meccanismo di streaming di UPSTREAM piu' la NOSTRA arena, e nessuno dei due sa
# dell'altro: processo a 47,4 GB contro i 32-33 del fork con la stessa arena.
if ($Arm -ne 'A' -and -not $NoStreaming) { $args += '--ssd-streaming' }

"=== BRACCIO $Arm  |  $Tokens token, ctx $Ctx ==="
"    binario  $exe"
"    modello  $Model"

# --- PREFLIGHT: le cose che se sbagliate falsano tutto, guardate PRIMA di lanciare.
#     L'1/8 ho misurato per mezz'ora un disco SATA credendo di misurare il porto.
$ml = (Split-Path $Model -Qualifier).TrimEnd(':')
$mp = Get-Partition -DriveLetter $ml -EA SilentlyContinue
if ($mp) {
    $md = Get-Disk -Number $mp.DiskNumber
    $pd = Get-PhysicalDisk | Where-Object DeviceId -eq $mp.DiskNumber
    $bus = $md.BusType
    "    DISCO    ${ml}: $($md.FriendlyName) [$bus $($pd.MediaType)]" + $(if ($bus -eq 'NVMe') { '  ok' } else { "  *** ATTENZIONE: non e' NVMe ***" })
}
$vram = (& nvidia-smi --query-gpu=memory.used --format=csv,noheader)
$freeRam = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB
$up = ((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes
$dirt = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -match 'codex' }).Count
"    VRAM     $vram all'avvio" + $(if ([int]($vram -replace '\D','') -gt 1500) { "  *** ATTENZIONE: non e' pulita ***" } else { "  ok" })
"    RAM      {0:N1} GB libera    uptime {1:N0} min    daemon codex {2}" -f $freeRam, $up, $dirt
if ($dirt -gt 0) { "    *** ATTENZIONE: daemon vivi, sfrattano le pagine del modello dalla page cache ***" }
$applied = @(Get-ChildItem Env: | Where-Object Name -Like 'DS4_*' | Sort-Object Name)
"    PRESET   $($applied.Count) variabili DS4_*"
foreach ($v in $applied) { if ($v.Name -notmatch 'SHUTDOWN_TOKEN') { "               $($v.Name)=$($v.Value)" } }
""
$t0 = Get-Date
$p = Start-Process -FilePath $exe -ArgumentList $args -PassThru -NoNewWindow `
        -RedirectStandardError $srvLog -RedirectStandardOutput "$srvLog.out"

# attesa del caricamento: 81 GB dal disco, puo' volerci
$ready = $false
for ($i = 0; $i -lt 900; $i++) {
    Start-Sleep -Seconds 2
    if ($p.HasExited) { throw "il server e' uscito da solo (exit $($p.ExitCode)) - vedi $srvLog" }
    try { Invoke-RestMethod "http://127.0.0.1:$Port/v1/models" -TimeoutSec 3 | Out-Null; $ready = $true; break } catch {}
}
if (-not $ready) { throw "server non pronto dopo 30 minuti" }
$load = ((Get-Date) - $t0).TotalSeconds
"    caricato in {0:N1}s" -f $load

# --- la richiesta, una sola, sempre la stessa ---
# IL PROMPT DELLA CAMPAGNA, non uno a caso. E' il carico su cui sono misurati TUTTI
# i riferimenti (X_CTL8K, X_P8K_comb): pagina intera, ~4900 token, quindi il 58%
# della generazione cade OLTRE il ginocchio dell'indexer a 2048.
# L'1/8 ho usato un prompt generico su una funzione Python: si e' esaurito a 909
# token, tutti PRIMA del ginocchio, e ho annunciato un SOTA che non era confrontabile.
# Lo script della campagna verifica lo SHA256 del prompt e abortisce se cambia:
# stesso presidio qui sotto.
$prompt = 'Create a complete single-file HTML landing page for a cyberpunk AI programming shop. Include CSS, navigation, hero, request form, and a JavaScript confirmation popup. Return only the HTML document.'
$promptSha = [BitConverter]::ToString(
    [System.Security.Cryptography.SHA256]::Create().ComputeHash(
        [Text.Encoding]::UTF8.GetBytes($prompt))).Replace('-','').ToLower()
"    PROMPT   pagina HTML della campagna   sha256 $($promptSha.Substring(0,16))..."
# RICHIESTA IN STREAMING, e non per gusto: con Invoke-RestMethod il testo resta in una
# variabile PowerShell finche' la risposta non e' completa, e se il processo muore prima
# (successo l'1/8 a gen=600) l'output e' perso per sempre. In streaming curl scrive i
# byte su disco mentre arrivano: un run interrotto lascia comunque il testo prodotto.
# think=false: SENZA questo il modello entra in fase di ragionamento e brucia
# centinaia di token prima di scrivere la pagina â€” sul tronco, l'1/8, non ne e'
# uscito nemmeno dopo 1340. Le pagine di riferimento della campagna sono HTML puro:
# misurare col ragionamento acceso significa misurare un altro carico.
# ds4_server.c:3292 legge "think" come booleano.
$body = @{ model='ds4'; max_tokens=$Tokens; temperature=0; stream=$true; think=$Think
           messages=@(@{role='user'; content=$prompt}) } | ConvertTo-Json -Depth 5
$reqPath    = Join-Path $OutDir "$tag.request.json"
$streamPath = Join-Path $OutDir "$tag.stream.ndjson"
[IO.File]::WriteAllText($reqPath, $body, [Text.UTF8Encoding]::new($false))
$t1 = Get-Date
& curl.exe -sS --no-buffer --max-time 7200 -X POST "http://127.0.0.1:$Port/v1/chat/completions" `
    -H 'Content-Type: application/json' --data-binary "@$reqPath" -o $streamPath
$gen = ((Get-Date) - $t1).TotalSeconds

# ricostruzione del testo dai delta
$content = ''
$out = 0
if (Test-Path $streamPath) {
    foreach ($line in [IO.File]::ReadLines($streamPath)) {
        if (-not $line.StartsWith('data: ')) { continue }
        $payload = $line.Substring(6)
        if ($payload -eq '[DONE]') { continue }
        try { $o = $payload | ConvertFrom-Json } catch { continue }
        $d = $o.choices[0].delta.content
        if ($d) { $content += [string]$d }
        if ($o.usage.completion_tokens) { $out = [int]$o.usage.completion_tokens }
    }
}
# ripiego: se lo streaming non ha prodotto delta, il server non lo supporta -> richiesta normale
if ($content.Length -eq 0) {
    "    streaming senza delta: ripiego su richiesta non-streaming"
    $body2 = @{ model='ds4'; max_tokens=$Tokens; temperature=0; think=$Think
                messages=@(@{role='user'; content=$prompt}) } | ConvertTo-Json -Depth 5
    $t1 = Get-Date
    $resp = Invoke-RestMethod "http://127.0.0.1:$Port/v1/chat/completions" -Method Post `
              -ContentType 'application/json' -Body $body2 -TimeoutSec 7200
    $gen = ((Get-Date) - $t1).TotalSeconds
    $content = [string]$resp.choices[0].message.content
    $out = $resp.usage.completion_tokens
}
# il conteggio autorevole e' quello del server nel log, se c'e'
$fromLog = (Select-String -LiteralPath $srvLog -Pattern 'gen=(\d+) .*chunk=' | Select-Object -Last 1)
if ($fromLog) { $out = [int]$fromLog.Matches[0].Groups[1].Value }
if (-not $out) { $out = $Tokens }
"    generati {0} token in {1:N1}s  ->  END2END {2:N3} t/s" -f $out, $gen, ($out/$gen)

# --- CATALOGAZIONE: l'output NON si perde mai. Regola utente 1/8. ---
# Ogni artefatto di un braccio porta lo STESSO identificativo, che e' $tag:
#     <tag>.server.log     il log del binario
#     <tag>.output.html    quello che il modello ha scritto   <-- mancava, e ho buttato 8 ore di testo
#     <tag>.meta.json      metriche + preset + sha, per ricostruire il run senza la chat
#     LEDGER_RUN.tsv       una riga per braccio, appesa, con lo stesso identificativo
# Il transcript delle chat non e' recuperabile: se non e' su disco non e' successo.
if (-not $content) { $content = '' }
$htmlPath = Join-Path $OutDir "$tag.output.html"
[IO.File]::WriteAllText($htmlPath, $content, [Text.UTF8Encoding]::new($false))
$contentSha = [BitConverter]::ToString(
    [Security.Cryptography.SHA256]::Create().ComputeHash(
        [Text.Encoding]::UTF8.GetBytes($content))).Replace('-','').ToLower()
"    output   {0:N0} caratteri  sha256 {1}  ->  {2}" -f $content.Length, $contentSha.Substring(0,16), (Split-Path $htmlPath -Leaf)
if ($content.Length -eq 0) { "    *** ATTENZIONE: output VUOTO, il braccio non ha prodotto testo ***" }

# il REGIME si legge dal log: mediana dei chunk oltre il token 300
$chunks = @(Select-String -LiteralPath $srvLog -Pattern 'gen=(\d+) decoding chunk=([0-9.]+)' -AllMatches |
    ForEach-Object { $_.Matches } |
    Where-Object { [int]$_.Groups[1].Value -gt 300 } |
    ForEach-Object { [double]$_.Groups[2].Value } | Sort-Object)
$regime = if ($chunks.Count) { $chunks[[int]($chunks.Count/2)] } else { $null }
$evict  = @(Select-String -LiteralPath $srvLog -Pattern 'evict_backbone=(\d+)' -AllMatches |
    ForEach-Object { $_.Matches } | ForEach-Object { [int]$_.Groups[1].Value } |
    Measure-Object -Maximum).Maximum
# Il braccio nudo NON stampa result=sized: senza guardia .Matches e' null e
# indicizzarlo fa esplodere l'harness DOPO aver gia' salvato l'output â€” cioe'
# nel punto peggiore, perche' il run e' riuscito ma sembra fallito.
$capMatch = Select-String -LiteralPath $srvLog -Pattern 'result=sized requested=\d+ capacity=(\d+)' |
    Select-Object -Last 1
$capacity = if ($capMatch) { $capMatch.Matches[0].Groups[1].Value } else { $null }

$meta = [ordered]@{
    id = $tag; arm = $Arm; timestamp = (Get-Date -Format 'o')
    exe = $exe; model = $Model; ctx = $Ctx; tokens_requested = $Tokens
    think = $Think
    prompt_sha256 = $promptSha; output_sha256 = $contentSha; output_chars = $content.Length
    tokens_generated = $out; seconds = [math]::Round($gen,1); load_seconds = [math]::Round($load,1)
    end2end_tps = [math]::Round($out/$gen,3); regime_tps = $regime; regime_n = $chunks.Count
    evict_backbone = $evict; expert_cache_capacity = $capacity
    no_expert_victim = @(Select-String -LiteralPath $srvLog -Pattern 'no-expert-victim').Count
    override = @($Override.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" })
    env = @($applied | Where-Object Name -notmatch 'SHUTDOWN_TOKEN' | ForEach-Object { "$($_.Name)=$($_.Value)" })
}
$metaPath = Join-Path $OutDir "$tag.meta.json"
$meta | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $metaPath -Encoding UTF8

$ledger = Join-Path $OutDir 'LEDGER_RUN.tsv'
if (-not (Test-Path $ledger)) {
    "id`tdata`tbraccio`tmodello`tctx`ttoken`tEND2END`tREGIME`tn`tcapacity`tevict_bb`tno_victim`toutput_sha256`toverride" |
        Set-Content -LiteralPath $ledger -Encoding UTF8
}
"{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6:N3}`t{7}`t{8}`t{9}`t{10}`t{11}`t{12}`t{13}" -f `
    $tag, (Get-Date -Format 'yyyy-MM-dd HH:mm'), $Arm, (Split-Path $Model -Leaf), $Ctx, $out,
    ($out/$gen), $regime, $chunks.Count, $capacity, $evict, $meta.no_expert_victim,
    $contentSha.Substring(0,16), (($Override.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ',') |
    Add-Content -LiteralPath $ledger -Encoding UTF8
"    ledger   riga appesa a $ledger"

# --- spegnimento PULITO: e' il punto, mai Stop-Process -Force ---
try {
    Invoke-RestMethod "http://127.0.0.1:$Port/__g130_u1_shutdown" -Method Post `
        -ContentType 'application/json' -Body ('{"token":"' + $tok + '"}') -TimeoutSec 20 | Out-Null
    "    spegnimento: endpoint accettato"
} catch { "    spegnimento: ENDPOINT FALLITO -> $($_.Exception.Message)" }
if (-not $p.WaitForExit(120000)) { "    ATTENZIONE: non e' uscito in 120s, resta vivo (NON lo forzo)" }
else { "    uscito pulito in {0:N1}s" -f ((Get-Date) - $t1).TotalSeconds }

Start-Sleep -Seconds 3
"    VRAM dopo: $((& nvidia-smi --query-gpu=memory.used --format=csv,noheader))"
"    log: $srvLog"

