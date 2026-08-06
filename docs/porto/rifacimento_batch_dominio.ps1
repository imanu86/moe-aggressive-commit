# RIFACIMENTO: la curva del batch E il test sul dominio, con la cache VIVA
#
# PERCHE' TUTTO DA CAPO
# ---------------------
# Un difetto mio (contiguita' pretesa su `ids`, che e' una vista con stride)
# scavalcava il percorso cache in OGNI braccio del 6/8 mattina e pomeriggio.
# Con la cache scavalcata gli esperti vanno sullo zero-copy da PCIe, che costa
# 6,35 t/s: tutte le misure erano confronti fra due zero-copy.
#
#     curva del batch (2 passate)   NULLA
#     test dominio F1/F2/F3         NULLA (F3 no: cache spenta, difetto assente)
#     bisezione C1/C8/C1b           NULLA (lo stesso difetto tre volte)
#
# Riparato (98a3dfa), il metro con cache e' tornato: 8,94 contro 7,77 = +15,1%.
#
# IL CANCELLO, PRIMA DI GUARDARE QUALUNQUE t/s
# --------------------------------------------
# Il contatore delle domande per token dice se la cache LAVORA:
#
#     ~257 domande/token   la cache serve ogni esperto di ogni strato
#      ~17 domande/token   la cache e' SCAVALCATA e il t/s non significa niente
#
# E' il sintomo che avevo in mano dalla mattina e che ho classificato come
# "semantica del contatore cambiata" invece di leggerlo. Qui viene stampato per
# ogni braccio e va guardato PRIMA della velocita'.
#
# SOSPETTO APERTO SU B2/B4: a ne[1] > 1 la contiguita' viene di nuovo pretesa,
# e ids resta una vista con stride. Quindi e' probabile che la cache sia
# scavalcata a batch>1 anche adesso. Se il contatore lo conferma, i bracci a
# batch>1 sono di nuovo nulli e la riparazione (passare lo stride al kernel)
# e' in revisione presso la sessione parallela.
#
# LE DUE DOMANDE, in un giro solo perche' condividono l'attrezzatura
# ------------------------------------------------------------------
#   G1  np1 codice    il metro con cache (atteso 8,94) e il riferimento
#   G2  np2 uguali    unione 258, entra nei 380 slot
#   G3  np2 diverse   unione ~446, sborda
#   G4  np4 diverse   unione ~751, sborda del doppio
#   G5  np1 prosa     appaiato a G1: il dominio conta, con la cache viva?
$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\rifacimento.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$EXE = 'D:\llama-dspark\build\bin\llama-server.exe'
$MOD = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$R   = 'D:\ds4_work\llama_run'
$b   = [char]92
$ESP = 'ffn_(gate|up|down)_exps' + $b + '.weight=CUDA0_Mapped'

$bracci = @(
    @{ n='G1_np1_codice'; np=1; req=@('par_p1');                            d='metro con cache -- il riferimento (atteso 8,94)' },
    @{ n='G2_np2_uguali'; np=2; req=@('par_p1','par_p1');                   d='due UGUALI: unione 258, entra nei 380 slot' },
    @{ n='G3_np2_divers'; np=2; req=@('par_p1','par_p3');                   d='due DIVERSE: unione ~446, sborda' },
    @{ n='G4_np4_divers'; np=4; req=@('par_p1','par_p2','par_p3','par_p4'); d='quattro diverse: unione ~751' },
    @{ n='G5_np1_prosa';  np=1; req=@('par_prosa');                         d='prosa, appaiato a G1 -- il dominio conta?' }
)
$porta = 8601
foreach ($x in $bracci) {
    "=============== $($x.n) -- $($x.d) ===============" | Out-File $out -Append -Encoding utf8
    $log = "$R\RIF_$($x.n).log"
    $ram = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB
    "  [condizione] RAM libera {0:N1} GiB" -f $ram | Out-File $out -Append -Encoding utf8
    if ($ram -lt 10) { "  SCARTATO: sotto 10 GiB" | Out-File $out -Append -Encoding utf8; continue }

    $env:LLAMA_MAPPED_IBRIDO       = '1'
    $env:LLAMA_REAP                = '0'
    $env:LLAMA_CACHE_ESPERTI_SLOT  = '380'
    $env:LLAMA_CACHE_ESPERTI_W     = '0'
    $env:LLAMA_CACHE_ESPERTI_BATCH = '8'
    $env:GGML_SCHED_PROFILO        = '1'

    $a = @('-m',$MOD,'-c','10000','-np',"$($x.np)",'-ngl','99','-ot',$ESP,
           '-ub','64','-b','64','-t','8','--port',"$porta",'--host','127.0.0.1',
           '--no-warmup','--no-mmap','--reasoning-budget','0')
    $srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -WindowStyle Minimized `
            -RedirectStandardError $log -RedirectStandardOutput ($log + '.out')
    $pronto = $false
    for ($i=0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 10
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto=$true; break } catch {}
    }
    if (-not $pronto) { "  NON PARTE" | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
        Start-Sleep 45; $porta++; continue }

    $d = (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "  VRAM {0:N0} MiB, liberi {1:N0}" -f ($d.CookedValue/1MB), (12288 - $d.CookedValue/1MB) |
        Out-File $out -Append -Encoding utf8

    # le richieste PARTONO INSIEME: e' l'unico modo perche' finiscano nello
    # stesso forward pass. Il contatore va letto PRIMA e DOPO, per avere le
    # domande di QUESTO gruppo e non il cumulato del processo.
    $c0 = 0
    $m = Select-String -Path $log -Pattern 'cache-esperti: domanda (\d+)' | Select-Object -Last 1
    if ($m) { $c0 = [int]$m.Matches[0].Groups[1].Value }

    $proc = @(); $t0 = Get-Date
    for ($k=0; $k -lt $x.req.Count; $k++) {
        $reqf = "$R\$($x.req[$k]).req.json"
        if (-not (Test-Path $reqf)) { "  ERRORE: manca $reqf" | Out-File $out -Append -Encoding utf8; continue }
        $args = @('-s','--max-time','1800','-X','POST',"http://127.0.0.1:$porta/v1/chat/completions",
                  '-H','Content-Type: application/json','--data-binary',"@$reqf",'-o',"$R\rif_$($x.n)_$k.json")
        $proc += Start-Process -FilePath 'curl.exe' -ArgumentList $args -PassThru -WindowStyle Hidden
    }
    if ($proc.Count -gt 0) { $proc | Wait-Process -Timeout 1900 }
    $muro = ((Get-Date) - $t0).TotalSeconds

    $tok = 0
    for ($k=0; $k -lt $x.req.Count; $k++) {
        $risp = "$R\rif_$($x.n)_$k.json"
        if (-not (Test-Path $risp)) { "  ERRORE: nessuna risposta per req $k" | Out-File $out -Append -Encoding utf8; continue }
        $j = Get-Content $risp -Raw | ConvertFrom-Json
        if (-not $j.timings) { "  ERRORE: risposta senza timings" | Out-File $out -Append -Encoding utf8; continue }
        $tok += $j.usage.completion_tokens
        "    req{0}: {1,4} tok  prefill {2,6:N2}  decode {3,6:N2} t/s" -f `
            $k, $j.usage.completion_tokens, $j.timings.prompt_per_second, $j.timings.predicted_per_second |
            Out-File $out -Append -Encoding utf8
        $j.choices[0].message.content | Out-File "$R\rif_$($x.n)_$k.output.html" -Encoding utf8
    }

    # IL CANCELLO: domande per token. ~257 = la cache lavora, ~17 = scavalcata.
    $c1 = 0
    $m = Select-String -Path $log -Pattern 'cache-esperti: domanda (\d+)' | Select-Object -Last 1
    if ($m) { $c1 = [int]$m.Matches[0].Groups[1].Value }
    $dpt = if ($tok -gt 0) { ($c1 - $c0) / $tok } else { 0 }
    "  --> {0} token in {1:N1} s = {2:N2} t/s AGGREGATO" -f $tok, $muro, ($tok/$muro) |
        Out-File $out -Append -Encoding utf8
    "  --> CANCELLO: {0:N0} domande su {1} token = {2:N1} per token   [{3}]" -f `
        ($c1-$c0), $tok, $dpt, $(if ($dpt -gt 150) { 'CACHE VIVA' } else { 'CACHE SCAVALCATA -- braccio NULLO' }) |
        Out-File $out -Append -Encoding utf8
    Select-String -Path $log -Pattern 'cache-esperti: domanda|sched-profilo' | Select-Object -Last 2 |
        ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8

    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep 10
    Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
    Start-Sleep 60
    "" | Out-File $out -Append -Encoding utf8
    $porta++
}
'FINE' | Out-File $out -Append -Encoding utf8
