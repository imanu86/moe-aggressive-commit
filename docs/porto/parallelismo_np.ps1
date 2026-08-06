# QUANTO PAGA GENERARE PIU' TOKEN NELLO STESSO PASSAGGIO?
#
# LA DOMANDA, e perche' e' la piu' importante non misurata
# --------------------------------------------------------
# Del nostro token di decode (108 ms, 9,26 t/s) solo il trasporto scala col
# numero di token: 52,7 ms di pavimento (lanci, confini, attenzione, densi) si
# pagano UNA VOLTA PER PASSAGGIO. Se due richieste concorrenti finiscono nello
# stesso forward pass, quel pavimento si divide.
#
# Abbiamo i due estremi misurati e NIENTE in mezzo:
#     B=1    decode    9,26 t/s
#     B=128  prefill  19,2  t/s
# Tutto il valore dell'idea "dividere una risposta fra piu' worker" vive nel
# buco fra questi due punti, e finora l'abbiamo solo stimato:
#     B=2 pessimista (zero condivisione di route)   12,25 t/s   +32%
#     B=2 con la condivisione della curva W=2       14,04       +52%
#
# IL DISEGNO: la condivisione delle route si misura da sola
# ----------------------------------------------------------
# Due richieste IDENTICHE instradano identico (temperatura 0): l'unione delle
# route e' quella di un token solo, condivisione massima. Due richieste DIVERSE
# condividono solo gli esperti popolari. La DIFFERENZA fra i due bracci e'
# l'effetto della condivisione misurato end-to-end, senza modelli.
#
#     B1      -np 1, una richiesta            <- il metro, controllo
#     B2u     -np 2, due richieste UGUALI     <- condivisione massima
#     B2d     -np 2, due richieste DIVERSE    <- il caso realistico
#     B4d     -np 4, quattro DIVERSE          <- la curva continua a salire?
#
# IL NUMERO CHE CONTA e' l'AGGREGATO da orologio da muro (token totali diviso
# il tempo dell'intero gruppo), non il t/s per richiesta: quello di llama.cpp
# include l'attesa in coda e non dice quanto lavoro fa la macchina.
#
# CANCELLI: RAM >= 10 GiB all'avvio di ogni braccio; un solo processo pesante;
# VRAM libera campionata (sotto ~400 MiB la scheda si strozza e il braccio non
# vale, cfr. K2/K4c).
$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\parallelismo.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$EXE = 'D:\llama-dspark\build\bin\llama-server.exe'
$MOD = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$R   = 'D:\ds4_work\llama_run'
$b   = [char]92
$ESP = 'ffn_(gate|up|down)_exps' + $b + '.weight=CUDA0_Mapped'

$bracci = @(
    @{ n='B1';   np=1; req=@('par_p1');                             d='una richiesta -- IL METRO' },
    @{ n='B2u';  np=2; req=@('par_p1','par_p1');                    d='DUE UGUALI -- condivisione massima delle route' },
    @{ n='B2d';  np=2; req=@('par_p1','par_p3');                    d='DUE DIVERSE (codice + prosa) -- il caso realistico' },
    @{ n='B4d';  np=4; req=@('par_p1','par_p2','par_p3','par_p4');  d='QUATTRO DIVERSE -- la curva sale ancora?' }
)
$porta = 8501
foreach ($x in $bracci) {
    "=============== $($x.n) -- $($x.d) ===============" | Out-File $out -Append -Encoding utf8
    $log = "$R\PAR_$($x.n).log"
    $ram = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB
    "  [condizione] RAM libera {0:N1} GiB, np={1}, richieste={2}" -f $ram,$x.np,$x.req.Count |
        Out-File $out -Append -Encoding utf8
    if ($ram -lt 10) { "  SCARTATO: sotto 10 GiB liberi" | Out-File $out -Append -Encoding utf8; continue }

    $env:LLAMA_MAPPED_IBRIDO      = '1'
    $env:LLAMA_REAP               = '0'
    $env:LLAMA_CACHE_ESPERTI_SLOT = '380'
    $env:LLAMA_CACHE_ESPERTI_W    = '0'

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
    if (-not $pronto) {
        "  NON E' PARTITO:" | Out-File $out -Append -Encoding utf8
        Select-String -Path $log -Pattern 'failed|error|out of memory' | Select-Object -Last 3 |
            ForEach-Object { "    " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
        Start-Sleep 45; $porta++; continue
    }
    $d = (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    $liberi = 12288 - $d.CookedValue/1MB
    "  VRAM {0:N0} MiB, liberi {1:N0}" -f ($d.CookedValue/1MB), $liberi | Out-File $out -Append -Encoding utf8

    # --- le N richieste PARTONO INSIEME: e' l'unico modo perche' finiscano
    #     nello stesso forward pass. Un ritardo fra i lanci le serializzerebbe.
    $proc = @()
    $t0 = Get-Date
    for ($k=0; $k -lt $x.req.Count; $k++) {
        $risp = "$R\par_$($x.n)_$k.json"
        $args = @('-s','--max-time','1800','-X','POST',"http://127.0.0.1:$porta/v1/chat/completions",
                  '-H','Content-Type: application/json','--data-binary',"@$R\$($x.req[$k]).req.json",'-o',$risp)
        $proc += Start-Process -FilePath 'curl.exe' -ArgumentList $args -PassThru -WindowStyle Hidden
    }
    $proc | Wait-Process -Timeout 1900
    $muro = ((Get-Date) - $t0).TotalSeconds

    $tokens = 0; $dettaglio = @()
    for ($k=0; $k -lt $x.req.Count; $k++) {
        $risp = "$R\par_$($x.n)_$k.json"
        if (Test-Path $risp) {
            $j = Get-Content $risp -Raw | ConvertFrom-Json
            $tokens += $j.usage.completion_tokens
            $dettaglio += "    req{0}: {1,4} tok  prefill {2,6:N2}  decode {3,6:N2} t/s" -f `
                $k, $j.usage.completion_tokens, $j.timings.prompt_per_second, $j.timings.predicted_per_second
            $j.choices[0].message.content | Out-File "$R\par_$($x.n)_$k.output.html" -Encoding utf8
        }
    }
    $dettaglio | Out-File $out -Append -Encoding utf8
    "  --> {0} token in {1:N1} s di orologio = {2:N2} t/s AGGREGATO  ({3:N2} per richiesta)" -f `
        $tokens, $muro, ($tokens/$muro), ($tokens/$muro/$x.req.Count) | Out-File $out -Append -Encoding utf8

    Select-String -Path $log -Pattern 'cache-esperti: domanda' | Select-Object -Last 1 |
        ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8
    # prova che il server ha davvero FUSO le richieste in un solo passaggio
    Select-String -Path $log -Pattern 'n_tokens|batch|slot .* release' | Select-Object -Last 3 |
        ForEach-Object { "  [log] " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8

    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep 10
    Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
    Start-Sleep 60
    "" | Out-File $out -Append -Encoding utf8
    $porta++
}
'FINE' | Out-File $out -Append -Encoding utf8
