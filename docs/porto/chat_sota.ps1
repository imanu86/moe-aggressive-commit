# CHAT INTERATTIVA sulla miglior SOTA, con decadimento a emivita 100 token
#
# Perche' questo run esiste
# -------------------------
# Ogni misura del 4/8 -- gate, decadimento, ammissione, zero-copy, VRAM -- usa
# LO STESSO prompt NeuraForge: un dominio solo, HTML. Non abbiamo nessun banco
# multidominio, e il decadimento e' stato falsificato (D08/D09/D10, -12 e -17%)
# proprio dentro quel dominio, dove dimenticare puo' solo far danno perche' non
# c'e' niente a cui adattarsi.
#
# Il caso indicato dall'utente -- HTML, poi CSS, poi prosa, nella stessa
# sessione -- non e' mai stato provato. E l'unico dato che abbiamo su quel
# confine (30/7: 141.000 sfratti contro 0 al cambio di dominio, a variabile
# singola) dice che e' li' che la politica attuale si rompe.
#
# L'aritmetica del decadimento
# ----------------------------
# LLAMA_REAP_PERIODO e' in TICK DELL'OSSERVATORE, non in token, e l'osservatore
# vede solo gli strati rimasti sul percorso CPU:
#
#   43 strati - 17 mappati su GPU = 26 osservati
#   26 strati x 3 mul_mat_id      = 78 tick per token
#   periodo di difetto 12900 tick = 165,4 token per passata
#
# Verificato sul run Y0: 38 passate su 6.374 token = 167,7. Torna.
#
# Per l'emivita di 100 token chiesta dall'utente:
#   PERIODO 3900 tick = 50 token per passata
#   emivita 100 token = 2 passate -> alfa = 0,5^(1/2) = 0,707
#
# Nota: il periodo scende di 3,3 volte rispetto al difetto, quindi le passate
# sono 3,3 volte piu' frequenti. Il churn e' il modo noto in cui il decadimento
# fallisce (nei bracci D08/D09 triplicava): qui se ne aggiunge dell'altro. E'
# voluto -- l'utente vuole la reattivita' -- ma va guardato nel profilo.
#
# La configurazione di base e' la SOTA MISURATA, non quella dedotta
# ----------------------------------------------------------------
# 17 strati mappati, -ub 64, gate acceso: 6,37 t/s il 4/8 mattina e 6,35 il
# pomeriggio a -ub 32, cioe' 0,3% di scarto. NON 22 strati: il confronto
# Y1->Y2 suggerisce che sarebbero meglio, ma 22 SENZA lo strato in VRAM non e'
# misurato da nessun braccio e non si mette una config dedotta sotto una
# sessione interattiva.
#
# NIENTE strato di esperti in VRAM: Y1 lo ha falsificato oggi, -12%, e la
# perdita era tutta nel pavimento (9% del tempo sotto 2 t/s contro 0,0%).
#
# ctx 50000 su richiesta dell'utente. E' 5 volte il banco: il KV di DSV4 e'
# compresso e a dimensione fissa, ma lo spazio di lavoro dell'attenzione no.
# Il cancello sotto legge la VRAM dedicata dopo il caricamento: se sborda in
# condivisa la sessione e' inutilizzabile (costa il 50%) e va abbassato a -ub 32.

$ErrorActionPreference = 'Continue'
$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$PORTA   = 8080
$log     = 'D:\ds4_work\llama_run\LLAMA_CHAT_sota.server.log'

$ESP = 'ffn_(gate|up|down)_exps\.weight'
$OT  = "blk\.([0-9]|1[0-6])\.$ESP=CUDA0_Mapped,$ESP=CPU"

$env:LLAMA_REAP             = '1'
$env:LLAMA_REAP_PROF        = '1'
$env:LLAMA_REAP_LOCK        = '1'
$env:LLAMA_REAP_TOPK        = '1200'
$env:LLAMA_REAP_PESO        = 'ripida'
$env:LLAMA_REAP_DECADIMENTO = '0.707'   # emivita 100 token, con PERIODO 3900
$env:LLAMA_REAP_PERIODO     = '3900'    # 50 token per passata
Remove-Item Env:LLAMA_REAP_AMMISSIONE -EA SilentlyContinue
Remove-Item Env:LLAMA_REAP_PREFETCH   -EA SilentlyContinue
Remove-Item Env:LLAMA_ARG_CPU_MOE     -EA SilentlyContinue

$argomenti = @('-m', $MODELLO, '-c','50000', '-ngl','99', '-ot', $OT,
               '-ub','64', '-b','64', '--port', "$PORTA", '--host','127.0.0.1',
               '--no-warmup', '--ui')

Write-Output "avvio: $(Get-Date -Format 'HH:mm:ss')  --  17 strati mappati, ctx 50000, emivita 100 token"
$srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
        -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow
Write-Output "pid $($srv.Id)"

$pronto = $false
for ($i = 0; $i -lt 360; $i++) {
    Start-Sleep -Seconds 5
    if ($srv.HasExited) { break }
    try { Invoke-RestMethod -Uri "http://127.0.0.1:$PORTA/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
}

if (-not $pronto) {
    Write-Output "NON E' PARTITO -- ultime righe:"
    if (Test-Path $log) { Get-Content $log -Tail 30 -Encoding UTF8 | ForEach-Object { Write-Output $_ } }
    exit 1
}

Write-Output "pronto: $(Get-Date -Format 'HH:mm:ss')"

# CANCELLO: la VRAM a ctx 50000 sborda in condivisa?
$d = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
     Sort-Object CookedValue -Descending | Select-Object -First 1
$dedMB = [math]::Round($d.CookedValue/1MB)
$v = (nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) 2>$null
Write-Output "VRAM dedicata $dedMB MiB   nvidia-smi $v MiB   (scheda 12288)"
if ($dedMB -gt 11800) {
    Write-Output "ATTENZIONE: al limite della scheda. Se la chat va a scatti, rilanciare con -ub 32."
}
$m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
Write-Output "RAM disponibile $($m.AvailableMBytes) MB"
Write-Output ""
Write-Output "APRI:  http://127.0.0.1:$PORTA"
