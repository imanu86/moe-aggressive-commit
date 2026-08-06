# LA GPU E' AL LIMITE, O ASPETTA?
#
# LA DOMANDA, e perche' cambia forma
# -----------------------------------
# In coda c'era "sensibilita' al clock GPU con la cache accesa", sul modello
# della curva del clock CPU (che aveva dato A = 63,7 ms indipendenti e B/clock =
# 65,2 dipendenti, e quindi il tetto di quella strada). Ma bloccare i clock con
# `nvidia-smi -lgc` richiede privilegi che questa sessione non ha:
#
#     The current user does not have permission to change clocks
#
# La domanda pero' si puo' rispondere meglio senza forzare niente: invece di
# muovere il clock e guardare il tempo, si guarda **cosa fa la GPU mentre il
# decode gira**. Se e' vicina al limite (utilizzo alto, clock al tetto, potenza
# vicina al budget) allora il clock comprerebbe qualcosa; se sta ferma ad
# aspettare, il clock non c'entra e la leva e' altrove.
#
# E c'e' un motivo per aspettarsi la seconda: la sonda dice che nella
# configurazione cache **81 ms su 111 sono `sync`**, cioe' attesa dentro il
# ciclo degli split. Ma "attesa di sincronizzazione" non dice se la GPU stia
# CALCOLANDO in quel mentre o stia a sua volta ferma sul PCIe. Il campionamento
# lo distingue: utilizzo alto durante il sync = la GPU lavora e il sync e'
# onesto; utilizzo basso = si aspetta il trasporto, e il clock non serve.
#
# COME
# ----
# Un server con la cache, una richiesta lunga, e nvidia-smi campionato ogni
# secondo durante il decode. Si riportano mediana e massimo di utilizzo, clock,
# potenza e temperatura, piu' le ragioni di throttle se compaiono.
$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\gpu_decode.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$EXE = 'D:\llama-dspark\build\bin\llama-server.exe'
$MOD = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$R   = 'D:\ds4_work\llama_run'
$b   = [char]92
$ESP = 'ffn_(gate|up|down)_exps' + $b + '.weight=CUDA0_Mapped'

$env:LLAMA_MAPPED_IBRIDO         = '1'
$env:LLAMA_REAP                  = '0'
$env:LLAMA_CACHE_ESPERTI_SLOT    = '380'
$env:LLAMA_CACHE_ESPERTI_W       = '0'
$env:LLAMA_CACHE_ESPERTI_BATCH   = '8'
$env:LLAMA_CACHE_ESPERTI_BATTITO = '5'

$a = @('-m',$MOD,'-c','10000','-np','1','-ngl','99','-ot',$ESP,
       '-ub','64','-b','64','-t','8','--port','8661','--host','127.0.0.1',
       '--no-warmup','--no-mmap','--reasoning-budget','0')
$log = "$R\GPU_decode.log"
$srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -WindowStyle Minimized `
        -RedirectStandardError $log -RedirectStandardOutput ($log + '.out')
$pronto = $false
for ($i=0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 10
    if ($srv.HasExited) { break }
    try { Invoke-RestMethod "http://127.0.0.1:8661/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto=$true; break } catch {}
}
if (-not $pronto) { "NON PARTE" | Out-File $out -Encoding utf8; exit }

# la richiesta parte in background, il campionamento gira mentre decodifica
$req = Start-Process -FilePath 'curl.exe' -PassThru -WindowStyle Hidden -ArgumentList @(
    '-s','--max-time','900','-X','POST','http://127.0.0.1:8661/v1/chat/completions',
    '-H','Content-Type: application/json','--data-binary',"@$R\par_p1.req.json",
    '-o',"$R\gpu_decode.json")

# si salta il prefill: e' GPU-intensivo per costruzione e falserebbe la mediana
Start-Sleep -Seconds 8
$campioni = @()
while (-not $req.HasExited) {
    $q = (& nvidia-smi --query-gpu=utilization.gpu,utilization.memory,clocks.sm,clocks.mem,power.draw,temperature.gpu,clocks_throttle_reasons.active --format=csv,noheader,nounits) -split ','
    if ($q.Count -ge 7) {
        $campioni += [pscustomobject]@{
            util=[double]$q[0].Trim(); utilmem=[double]$q[1].Trim(); sm=[double]$q[2].Trim()
            mem=[double]$q[3].Trim(); pw=[double]$q[4].Trim(); t=[double]$q[5].Trim(); thr=$q[6].Trim()
        }
    }
    Start-Sleep -Milliseconds 700
}
$j = if (Test-Path "$R\gpu_decode.json") { Get-Content "$R\gpu_decode.json" -Raw | ConvertFrom-Json } else { $null }

function med($v) { if ($v.Count -eq 0) { return 0 }; ($v | Sort-Object)[[int]($v.Count/2)] }
"CAMPIONAMENTO DELLA GPU DURANTE IL DECODE ($($campioni.Count) campioni, ~0,7 s l'uno)" | Out-File $out -Encoding utf8
if ($j -and $j.timings) {
    "  decode {0:N2} t/s   {1:N2} ms/token" -f $j.timings.predicted_per_second, $j.timings.predicted_per_token_ms |
        Out-File $out -Append -Encoding utf8
}
"" | Out-File $out -Append -Encoding utf8
"{0,-22} {1,>8} {2,>8} {3,>8}" -f 'grandezza','mediana','minimo','massimo' | Out-File $out -Append -Encoding utf8
foreach ($c in @(
    @{n='utilizzo GPU %';    v=$campioni.util},
    @{n='utilizzo memoria %';v=$campioni.utilmem},
    @{n='clock SM MHz';      v=$campioni.sm},
    @{n='clock memoria MHz'; v=$campioni.mem},
    @{n='potenza W';         v=$campioni.pw},
    @{n='temperatura C';     v=$campioni.t})) {
    $s = $c.v | Sort-Object
    "{0,-22} {1,8:N0} {2,8:N0} {3,8:N0}" -f $c.n, (med $c.v), $s[0], $s[-1] | Out-File $out -Append -Encoding utf8
}
"" | Out-File $out -Append -Encoding utf8
"  tetti della scheda: SM 2115 MHz, memoria 7501 MHz, potenza 170 W" | Out-File $out -Append -Encoding utf8
$thr = $campioni.thr | Where-Object { $_ -ne '0x0000000000000000' } | Select-Object -Unique
"  ragioni di throttle non nulle: " + $(if ($thr) { $thr -join ' ' } else { 'NESSUNA' }) | Out-File $out -Append -Encoding utf8
Select-String -Path $log -Pattern 'cache-esperti: domanda' | Select-Object -Last 1 |
    ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8

if (-not $srv.HasExited) { $srv.Kill() }
Start-Sleep 5
Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
'FINE' | Out-File $out -Append -Encoding utf8
