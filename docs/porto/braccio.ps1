# Un braccio del primo run del porto. Uso: .\braccio.ps1 -Arm A|B|C [-Tokens 150]
param(
    [Parameter(Mandatory)][ValidateSet('A','B','C')][string]$Arm,
    [int]$Tokens = 150,
    [int]$Ctx    = 8192,
    [int]$Port   = 8080,
    # C: e' l'NVMe (Lexar EQ790), D: e' il SATA (EMTEC X160): ~7000 contro ~550 MB/s.
    # Il riferimento gira da C:. Su un runtime che fa streaming dal disco, sbagliare
    # unita' significa misurare il disco invece del codice.
    [string]$Model = 'C:\ds4-models\ds4-2bit.gguf',
    [string]$OutDir = 'D:\ds4_work\porto_run',
    # Prova a variabile singola: -Override @{ 'DS4_G73_OPEN' = '1' }
    # Applicato DOPO il preset, cosi' la sovrascrittura e' esplicita e finisce nel tag.
    [hashtable]$Override = @{},
    [switch]$NoStreaming
)
$ErrorActionPreference = 'Stop'
$R = 'C:\Users\imanu\source\repos\moe-aggressive-commit'
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$tag = "{0}_{1}" -f $Arm, (Get-Date -Format 'HHmmss')
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
  'A' {  # il FORK, binario bin_codex4 = ds4_server.exe (il .pre_codex4 e' quello PRIMA)
    $exe = "$R\ds4-p4a\build-native\ds4_server.exe"
    . "$R\docs\porto\preset_A.ps1"                   # la fonte, non un env trovato col grep
    $env:DS4_G130_U1_SHUTDOWN_TOKEN = $tok
  }
  'B' {  # il TRONCO NUDO: tutti i nostri opt-in ASSENTI, non a zero
    $exe = "$R\ds4-port\build-verify\ds4-server.exe"
  }
  'C' {  # il TRONCO con la nostra politica accesa
    # CORRETTO l'1/8 dopo la lettura del codice. Il primo tentativo aveva tre
    # variabili di cui una sabotava l'altra, e girava come upstream nudo:
    #   ds4_cuda.cu:26520  con VRAM_EXPERT_CACHE=1 il budget entra nel ramo VRAM
    #                      e NON raggiunge mai dynamic_arena::enabled()
    #   ds4_cuda.cu:26521  quel ramo torna ZERO senza requested_slots/expert_bytes
    #   ds4.c:53898        fuori da --ssd-streaming il core non li valorizza mai
    #   prefill_observer.cu:376  OBSERVE arma solo l'osservatore: per pubblicare
    #                      nell'arena serve _WRAP, che mancava
    $exe = "$R\ds4-port\build-verify\ds4-server.exe"
    $env:DS4_CUDA_DYNAMIC_ARENA_GB     = '30'
    $env:DS4_CUDA_PREFILL_MASS_OBSERVE = '1'
    $env:DS4_CUDA_PREFILL_MASS_WRAP    = '1'   # mancava: senza, non pubblica
    # DS4_CUDA_VRAM_EXPERT_CACHE NON va acceso insieme all'arena: si escludono.
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
$body = @{ model='ds4'; max_tokens=$Tokens; temperature=0
           messages=@(@{role='user'; content=$prompt}) } | ConvertTo-Json -Depth 5
$t1 = Get-Date
$resp = Invoke-RestMethod "http://127.0.0.1:$Port/v1/chat/completions" -Method Post `
          -ContentType 'application/json' -Body $body -TimeoutSec 7200
$gen = ((Get-Date) - $t1).TotalSeconds
$out = $resp.usage.completion_tokens
if (-not $out) { $out = $Tokens }
"    generati {0} token in {1:N1}s  ->  END2END {2:N3} t/s" -f $out, $gen, ($out/$gen)

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
