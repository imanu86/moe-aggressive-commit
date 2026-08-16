# LA CACHE DOVE SI LAVORA DAVVERO — ctx 102400, e una corsa lunga
#
# TUTTO quello che sappiamo sulla cache e' misurato a ctx 10000 con ub 64, dove
# entrano 380 slot e il guadagno e' +14% (9,16 contro 8,04). Ma il contesto vero
# e' 102400, dove i buffer di calcolo si mangiano 1.690 MiB e ne restano ~220.
#
# Tre domande in una corsa sola:
#   1. il +14% sopravvive con 220 slot invece di 380?
#   2. c'e' DERIVA su 1.200 token invece di 300? (la cache si riempie in un token
#      e mezzo, ma il working set si allarga quando il testo cambia argomento)
#   3. cosa c'e' dentro i 1.690 MiB di buffer? -> decide se l'anello scorrevole
#      puo' liberarli e raddoppiare gli slot
#
# ORDINE: il metro per PRIMO su macchina fredda, la cache dopo con la cache di
# sistema calda. L'ordine lavora contro la tesi.
#
# CANCELLO DI CONDIZIONE (la lezione della notte): si campiona la RAM libera
# all'avvio di ogni braccio. Sotto 10 GiB il braccio NON VALE -- e' quello che
# e' successo quando due processi da 74 GiB hanno girato insieme.
$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\cache100k.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$EXE = 'D:\llama-dspark\build\bin\llama-server.exe'
$MOD = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$req = 'D:\ds4_work\llama_run\neuraforge1200.req.json'
$b   = [char]92
$OT  = 'ffn_(gate|up|down)_exps' + $b + '.weight=CUDA0_Mapped'

# 220 slot = quel che entra a ctx 102400 con ub 128 (12.288 - 7.383 pesi
# - 1.690 buffer - margine). Il braccio a 380 verifica se sfora davvero.
$bracci = @(
    @{ n='K0_metro';      slot=0;   ub=128; d='metro senza cache, ctx pieno' },
    @{ n='K1_cache220';   slot=220; ub=128; d='cache quel che entra' },
    @{ n='K2_cache380';   slot=380; ub=128; d='cache come a ctx 10k -- entra o no?' },
    @{ n='K3_cache380u16';slot=380; ub=16;  d='ub 16 libera buffer: 380 slot ci stanno' }
)

$porta = 8461
foreach ($x in $bracci) {
    "=============== $($x.n) -- $($x.d) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\K_$($x.n).log"

    $m0 = Get-CimInstance Win32_OperatingSystem
    $ramLibera = $m0.FreePhysicalMemory/1MB
    "  [condizione] RAM libera all'avvio: {0:N1} GiB" -f $ramLibera | Out-File $out -Append -Encoding utf8
    if ($ramLibera -lt 10) {
        "  BRACCIO SCARTATO: sotto i 10 GiB liberi, la misura non varrebbe" | Out-File $out -Append -Encoding utf8
        continue
    }

    $env:LLAMA_MAPPED_IBRIDO = '1'
    $env:LLAMA_REAP = '0'
    $env:LLAMA_CACHE_ESPERTI_SLOT = "$($x.slot)"
    $env:LLAMA_CACHE_ESPERTI_W = '0'      # il predittore PERDE in tutte e tre le
                                          # implementazioni provate: resta spento

    $a = @('-m',$MOD,'-c','102400','-np','1','-ngl','99','-ot',$OT,
           '-ub',"$($x.ub)",'-b',"$($x.ub)",'-t','8','--port',"$porta",'--host','127.0.0.1',
           '--no-warmup','--no-mmap','--reasoning-budget','0')

    $srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -WindowStyle Minimized `
            -RedirectStandardError $log -RedirectStandardOutput ($log + '.out')

    $pronto = $false
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 10
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "  NON E' PARTITO:" | Out-File $out -Append -Encoding utf8
        Select-String -Path $log -Pattern 'failed|error|out of memory|cudaMalloc' | Select-Object -Last 3 |
            ForEach-Object { "    " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
        Start-Sleep -Seconds 45; $porta++; continue
    }

    $d = (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "  VRAM {0:N0} MiB, liberi {1:N0}" -f ($d.CookedValue/1MB), (12288 - $d.CookedValue/1MB) |
        Out-File $out -Append -Encoding utf8
    Select-String -Path $log -Pattern 'compute buffer size|cache-esperti: [0-9]+ slot' |
        ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8

    $risp = "D:\ds4_work\llama_run\k_$($x.n).json"
    & curl.exe -s --max-time 2400 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" -o $risp | Out-Null

    if (Test-Path $risp) {
        $j = Get-Content $risp -Raw | ConvertFrom-Json
        $t = $j.timings
        $c = $j.choices[0].message.content
        "  prefill {0,6:N2} t/s   decode {1,6:N2} t/s   {2:N2} ms/tok   ({3} tok)" -f `
            $t.prompt_per_second, $t.predicted_per_second, $t.predicted_per_token_ms, $t.predicted_n |
            Out-File $out -Append -Encoding utf8
        $c | Out-File "D:\ds4_work\llama_run\k_$($x.n).output.html" -Encoding utf8
        $h = (Get-FileHash "D:\ds4_work\llama_run\k_$($x.n).output.html" -Algorithm SHA256).Hash
        "  sha256 $($h.Substring(0,16))" | Out-File $out -Append -Encoding utf8
    }

    # LA DERIVA: su 1.200 token il working set si allarga. Le mediane per terzo
    # dicono se il vantaggio regge o si consuma.
    $tg = Select-String -Path $log -Pattern 'tg_3s = *([0-9.]+)' -AllMatches |
          ForEach-Object { $_.Matches } | ForEach-Object { [double]$_.Groups[1].Value }
    if ($tg.Count -ge 9) {
        $n = $tg.Count; $q = [int]($n/3)
        # BUG CORRETTO (16/8): [int]($v.Count/2) col banker's rounding cadeva un passo sopra il centro per Count dispari 3,7,11,... (con Count=3 era il MASSIMO); qui e' il caso pieno, i terzi possono avere 3 campioni; v. RUNBOOK par. 7.4
        $p = { param($v) ($v | Sort-Object)[[math]::Floor(($v.Count-1)/2)] }
        "  tg_3s {0} campioni -- mediane per terzo: {1:N2} / {2:N2} / {3:N2}" -f `
            $n, (& $p $tg[0..($q-1)]), (& $p $tg[$q..(2*$q-1)]), (& $p $tg[(2*$q)..($n-1)]) |
            Out-File $out -Append -Encoding utf8
    }
    Select-String -Path $log -Pattern 'cache-esperti: domanda' | Select-Object -Last 1 |
        ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8

    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep -Seconds 10
    Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
    Start-Sleep -Seconds 60
    "" | Out-File $out -Append -Encoding utf8
    $porta++
}
'FINE' | Out-File $out -Append -Encoding utf8

# ---------------------------------------------------------------------------
# BRACCIO K4, DA AGGIUNGERE: token_embd su CPU
#
# token_embd e' f16 e pesa 0,99 GiB della VRAM. Ma e' una TABELLA DI
# CONSULTAZIONE: per ogni token si legge una riga da 4096 float, 8 KiB.
# Spostarla in RAM costa una lettura irrisoria e NON richiede parallelismo fra
# dispositivi -- e' gia' serializzata per natura. E si fa con un flag.
#
#     -ot 'token_embd\.weight=CPU,ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped'
#
# Vale ~150 slot: a ctx 102400 si passerebbe da ~220 a ~370, cioe' da UN token
# di storia a QUATTRO, e i nuovi per token da ~150 a ~110.
#
# Da verificare nello stesso braccio: che il decode non peggiori (la riga di
# embedding passa dal PCIe una volta per token) e che lo SHA resti identico.
#
# NON FATTIBILE ORA, per confronto: gli esperti condivisi (ffn_*_shexp, q8_0,
# 1,08 GiB = 164 slot). Le due diramazioni SONO indipendenti nel grafo
# (moe_out + ffn_shexp prendono lo stesso ingresso e si sommano), ma lo
# scheduler di ggml esegue i pezzi di backend diversi in SEQUENZA: il calcolo
# sulla CPU si sommerebbe invece di affiancarsi. Serve lavoro sullo scheduler.
