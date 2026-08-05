# DUE DOMANDE, DUE MODELLI, E OGNUNO RISPONDE ALLA SUA
#
# Scritto il 5/8 sera dopo che il banco dei kernel ha ribaltato la tesi MXFP4.
# Il ragionamento sta in PIANO_GATE_MODELLO_CHE_NON_ENTRA.md e nel ledger
# (LLAMA_KERNEL_DEQUANT, LLAMA_MXFP4_M3_GATE).
#
# DOMANDA A -- IL KERNEL
# ----------------------
# Misurato su tensori sintetici, senza modello e senza disco:
#     q2_K 748 GFLOPS · q4_K 569 · mxfp4 392 · iq2_xxs 234 · iq2_xs 231 · iq3_xxs 188
# La divisione non e' "quanti bit" ma CODEBOOK contro BLOCCHI, e sono 3,2x.
# Il nostro modello ha down gia' in q2_K ma gate e up in iq2_xxs -- cioe' il 61%
# dei byte degli esperti dalla parte lenta senza motivo.
#     tempo per esperto oggi   1/234 + 1/234 + 1/748 = 0,00989
#     tutto q2_K               3 x 1/748             = 0,00401     -> 2,46x
# Non si tradurra' in 2,46x end-to-end (il decode non e' solo dequantizzazione)
# ma tre misure dicono che quella e' la parte dominante.
#
# Modello: ggml-org Q2_K_S, 91,82 GiB, gate/up/down TUTTI q2_K, attenzione q8_0,
# dai pesi FP8 originali. Scelto leggendo i tipi dall'intestazione GGUF, non
# dalla scheda: unsloth "UD-Q2_K_XL" ha gli esperti in iq2_xs/iq3_xxs (i kernel
# lenti) e Preyazz/teamblobfish hanno l'attenzione a q2_K.
#
# DOMANDA B -- L'ISTERESI
# -----------------------
# Il Q2_K_S ENTRA in RAM, quindi li' il gate non ha niente da sfrattare e
# l'isteresi non e' misurabile. Serve un modello che NON entra, e il misto da
# 112 GiB serve esattamente a quello.
#     vecchia politica: classifica 11.008 esperti, scambia tutta la differenza
#                       (misurato: 2010, 1098, 757, 666, 511 per passata)
#     isteresi:         bussi >= SOGLIA, entri sfrattando il piu' freddo, e solo
#                       se sei MARGINE volte piu' caldo di lui; al massimo
#                       MAX_SCAMBI per passata
# Variabile singola: LLAMA_REAP_ISTERESI 1 contro 0, tutto il resto identico.
#
# CONFIGURAZIONE COMUNE: -ot=CPU con mmap, niente ibrido. Non e' una scelta ma
# un vincolo: gli esperti del Q2_K_S sono ~83 GiB e il pool di memoria condivisa
# GPU e' 76,7 GB, quindi cudaHostAlloc non li tiene. Per questo serve il metro
# A0 -- l'IQ2_XXS nella STESSA configurazione. Confrontarlo col 7,45 storico
# (che era ibrido, --no-mmap, 43 strati mappati) sarebbe confondere due variabili.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\q2k.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$EXE  = 'D:\llama-dspark\build\bin\llama-server.exe'
$req  = 'D:\ds4_work\llama_run\neuraforge1200.req.json'
$esp  = 'ffn_(gate|up|down)_exps' + [char]92 + '.weight'
$OT   = $esp + '=CPU'

$Q2KS    = 'C:\ds4-models\q2ks\DeepSeek-V4-Flash-0731-Q2_K_S-00001-of-00002.gguf'
$IQ2     = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$MIO     = 'D:\ds4-models\DS4-0731-Q2K-GateUp.gguf'
$MISTO   = 'C:\ds4-models\DS4-0731-GateUp-MXFP4Down.gguf'

# A0 per PRIMO su macchina fredda: e' il metro, e l'ordine deve lavorare contro
# la tesi, non a favore.
$bracci = @(
    @{ n='A0_iq2_metro';    m=$IQ2;   gate=$false; ist=$null; d='IQ2_XXS, il metro nella stessa configurazione' }
    @{ n='A1_q2ks';         m=$Q2KS;  gate=$false; ist=$null; d='Q2_K_S 91,82 GiB, tutti gli esperti a blocchi' }
    @{ n='A2_mio_riquant';  m=$MIO;   gate=$false; ist=$null; d='il mio ri-quantizzato da IQ2 -- quanto costa la doppia quantizzazione' }
    @{ n='B1_isteresi_on';  m=$MISTO; gate=$true;  ist='1';   d='112 GiB, ammissione a soglia' }
    @{ n='B2_isteresi_off'; m=$MISTO; gate=$true;  ist='0';   d='112 GiB, vecchia politica in blocco' }
)

$porta = 8351
foreach ($b in $bracci) {
    "=============== $($b.n) -- $($b.d) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_$($b.n).server.log"

    $env:LLAMA_MAPPED_IBRIDO = '0'
    $env:LLAMA_REAP      = '1'      # l'osservatore SEMPRE acceso: anche i bracci
    $env:LLAMA_REAP_PROF = '1'      # senza gate devono dire quanto ERA copribile
    if ($b.gate) {
        $env:LLAMA_REAP_LOCK = '1'
        $env:LLAMA_REAP_TOPK = '7500'
        $env:LLAMA_REAP_PESO = 'ripida'
        $env:LLAMA_REAP_DECADIMENTO = '1.0'
        $env:LLAMA_REAP_THREADS = '8'
        $env:LLAMA_REAP_PERIODO = '2752'
        $env:LLAMA_REAP_ISTERESI = $b.ist
        $env:LLAMA_REAP_SOGLIA = '3'
        $env:LLAMA_REAP_MARGINE = '1.25'
        $env:LLAMA_REAP_MAX_SCAMBI = '64'
    } else {
        $env:LLAMA_REAP_LOCK = '0'
        Remove-Item Env:\LLAMA_REAP_ISTERESI -EA SilentlyContinue
    }

    $a = @('-m',$b.m,'-c','10000','-ngl','99','-ot',$OT,'-ub','64','-b','64',
           '-t','8','--port',"$porta",'--host','127.0.0.1',
           '--no-warmup','--reasoning-budget','0')

    $srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -WindowStyle Minimized `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out"

    $pronto = $false
    for ($i = 0; $i -lt 120; $i++) {
        Start-Sleep -Seconds 10
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "NON E' PARTITO:" | Out-File $out -Append -Encoding utf8
        Select-String -Path $log -Pattern 'failed|error' | Select-Object -Last 3 |
            ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Start-Sleep -Seconds 60; $porta++; continue
    }

    $m0 = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
    "  RAM disp {0:N1} GiB" -f ($m0.AvailableMBytes/1024) | Out-File $out -Append -Encoding utf8

    $risp = "D:\ds4_work\llama_run\q2k_$($b.n).resp.json"
    & curl.exe -s --max-time 2400 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" -o $risp | Out-Null

    if (Test-Path $risp) {
        $j = Get-Content $risp -Raw | ConvertFrom-Json
        $t = $j.timings
        $cc = $j.choices[0].message.content
        $r = ($cc -split "`n") | Where-Object { $_.Trim().Length -gt 20 } | ForEach-Object { $_.Trim() }
        $rip = if ($r.Count) { ($r | Group-Object | Sort-Object Count -Desc | Select-Object -First 1).Count } else { 0 }
        "  prefill {0,7:N2} ms/tok  {1,6:N2} t/s" -f $t.prompt_per_token_ms, $t.prompt_per_second | Out-File $out -Append -Encoding utf8
        "  decode  {0,7:N2} ms/tok  {1,6:N2} t/s  ({2} tok)" -f $t.predicted_per_token_ms, $t.predicted_per_second, $t.predicted_n | Out-File $out -Append -Encoding utf8
        "  {0} car, ripetizione {1} -- {2}" -f $cc.Length, $rip, $(if ($rip -lt 8) {'SANO'} else {'DEGENERATO'}) | Out-File $out -Append -Encoding utf8
        $cc | Out-File "D:\ds4_work\llama_run\q2k_$($b.n).output.html" -Encoding utf8
        # lo SHA serve al confronto di qualita': A0 e A2 sono lo stesso modello
        # ri-codificato, quindi un'uscita diversa misura la doppia quantizzazione
        $h = (Get-FileHash "D:\ds4_work\llama_run\q2k_$($b.n).output.html" -Algorithm SHA256).Hash
        "  sha256 $h" | Out-File $out -Append -Encoding utf8
    }

    # IL REGIME, non la media della corsa: i cumulativi mentono quando c'e' un
    # transitorio (misurato il 5/8: cumulativo 3,26 con mediane 5,13/2,08/2,12)
    $tg = Select-String -Path $log -Pattern 'tg_3s = *([0-9.]+)' -AllMatches |
          ForEach-Object { $_.Matches } | ForEach-Object { [double]$_.Groups[1].Value }
    if ($tg.Count -gt 6) {
        $n = $tg.Count; $ter = [int]($n/3)
        $u = $tg[(2*$ter)..($n-1)] | Sort-Object
        "  tg_3s: {0} campioni, mediana ultimo terzo {1:N2}, p10 {2:N2}, p90 {3:N2}, min {4:N2}" -f `
            $n, $u[[int]($u.Count/2)], $u[[int]($u.Count/10)], $u[[int]($u.Count*9/10)], $u[0] |
            Out-File $out -Append -Encoding utf8
    }

    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep -Seconds 10
    $pass = Select-String -Path $log -Pattern 'reap: passata'
    if ($pass) {
        @($pass)[0].Line -replace '^[0-9.]+ +[A-Z] +','  prima: ' | Out-File $out -Append -Encoding utf8
        @($pass)[-1].Line -replace '^[0-9.]+ +[A-Z] +','  ultima: ' | Out-File $out -Append -Encoding utf8
        $sb = @($pass) | ForEach-Object { if ($_.Line -match '(\d+) sbloccati') { [int]$Matches[1] } else { 0 } }
        "  {0} passate, {1} sfratti totali, {2:N1} per passata" -f $pass.Count, ($sb | Measure-Object -Sum).Sum, ($sb | Measure-Object -Average).Average |
            Out-File $out -Append -Encoding utf8
    }
    Select-String -Path $log -Pattern 'COPERTURA non|quota' | Select-Object -Last 2 |
        ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8

    Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
    Start-Sleep -Seconds 90
    "" | Out-File $out -Append -Encoding utf8
    $porta++
}

'FINE' | Out-File $out -Append -Encoding utf8
