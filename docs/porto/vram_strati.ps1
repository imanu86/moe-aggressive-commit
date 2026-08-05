# QUANTI STRATI CONVIENE METTERE IN VRAM VERA -- con ripetizioni
#
# LA DOMANDA
# ----------
# L'unica misura che abbiamo di "esperti in VRAM vera" e' il braccio Y1 del 4/8:
# UN solo strato, -12%, con 341 MiB di margine sulla scheda e un meccanismo mai
# spiegato. Su quel numero poggia il verdetto su qualsiasi acquisto di GPU.
#
# Adesso possiamo rifarlo bene: con 96 GB di RAM si puo' scendere di contesto e
# lasciare respiro alla scheda, invece dei 341 MiB di allora.
#
# IL DISEGNO
# ----------
# ctx 4096 e ub 32 riducono il buffer di calcolo e liberano VRAM. Il resto
# resta la configurazione ibrida di oggi (43 strati mappati, -t 16).
#
#   V0   0 strati in CUDA0    tutto mappato          <- il metro
#   V1   1 strato  in CUDA0   blk.42
#   V2   2 strati  in CUDA0   blk.41-42
#
# RIPETUTI DUE VOLTE, ALTERNATI: V0 V1 V2 V0 V1 V2.
# Non tre bracci di fila: se la macchina derivasse nel tempo (cache, termica),
# un ordine a blocchi lo attribuirebbe alla configurazione. Alternando, la
# deriva si distribuisce su tutti.
#
# SIGNIFICATIVITA'
# ----------------
# Ogni braccio da 1200 token produce ~30 campioni di tg_3s a regime. Si
# confrontano le MEDIANE e si guarda la sovrapposizione fra p10 e p90: se gli
# intervalli si sovrappongono, la differenza non e' distinguibile dal rumore e
# va detto, invece di leggere il secondo decimale.
#
# Riferimento di rumore misurato in questa campagna: la stessa configurazione
# ripetuta ha dato 6,37 e 6,35 (0,3%) quando non c'erano crolli, e +-7,6% quando
# ce n'erano. Adesso non ce ne sono, quindi ci si aspetta il regime stretto.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\vramstrati.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$req     = 'D:\ds4_work\llama_run\neuraforge1200.req.json'
$esp     = 'ffn_(gate|up|down)_exps' + [char]92 + '.weight'

# blk.42 e blk.41-42 in CUDA0 VERA, il resto mappato
$otV0 = $esp + '=CUDA0_Mapped'
$otV1 = 'blk' + [char]92 + '.42' + [char]92 + '.' + $esp + '=CUDA0,' + $esp + '=CUDA0_Mapped'
$otV2 = 'blk' + [char]92 + '.4[12]' + [char]92 + '.' + $esp + '=CUDA0,' + $esp + '=CUDA0_Mapped'

$giro = @(
    @{ n='V0a'; ot=$otV0; d='0 strati in VRAM' }
    @{ n='V1a'; ot=$otV1; d='1 strato in VRAM (blk.42)' }
    @{ n='V2a'; ot=$otV2; d='2 strati in VRAM (blk.41-42)' }
    @{ n='V0b'; ot=$otV0; d='0 strati -- ripetizione' }
    @{ n='V1b'; ot=$otV1; d='1 strato -- ripetizione' }
    @{ n='V2b'; ot=$otV2; d='2 strati -- ripetizione' }
)

$porta = 8331
foreach ($b in $giro) {
    "=============== $($b.n) -- $($b.d) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_$($b.n).server.log"
    $env:LLAMA_MAPPED_IBRIDO = '1'
    $env:LLAMA_REAP = '0'

    $a = @('-m',$MODELLO,'-c','4096','-ngl','99','-ot',$b.ot,'-ub','32','-b','32',
           '-t','16','--port',"$porta",'--host','127.0.0.1',
           '--no-warmup','--no-mmap','--reasoning-budget','0')

    $srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -WindowStyle Minimized `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out"

    $pronto = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 10
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "NON E' PARTITO -- probabilmente la VRAM non basta:" | Out-File $out -Append -Encoding utf8
        Select-String -Path $log -Pattern 'failed to allocate|cudaMalloc' | Select-Object -Last 2 |
            ForEach-Object { "  " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Start-Sleep -Seconds 30
        $porta++
        continue
    }

    # quanta VRAM resta libera: il numero che Y1 non aveva
    $d = (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "  VRAM usata {0:N0} MiB, liberi {1:N0}" -f ($d.CookedValue/1MB), (12288 - $d.CookedValue/1MB) |
        Out-File $out -Append -Encoding utf8

    $risp = "D:\ds4_work\llama_run\vs_$($b.n).resp.json"
    & curl.exe -s --max-time 900 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" -o $risp | Out-Null

    if (Test-Path $risp) {
        $j = Get-Content $risp -Raw | ConvertFrom-Json
        $t = $j.timings
        $c = $j.choices[0].message.content
        $r = ($c -split "`n") | Where-Object { $_.Trim().Length -gt 20 } | ForEach-Object { $_.Trim() }
        $rip = if ($r.Count) { ($r | Group-Object | Sort-Object Count -Desc | Select-Object -First 1).Count } else { 0 }
        "  prefill {0,7:N2} ms/tok  {1,6:N2} t/s" -f $t.prompt_per_token_ms, $t.prompt_per_second | Out-File $out -Append -Encoding utf8
        "  decode  {0,7:N2} ms/tok  {1,6:N2} t/s" -f $t.predicted_per_token_ms, $t.predicted_per_second | Out-File $out -Append -Encoding utf8
        "  {0} car, ripetizione {1} -- {2}" -f $c.Length, $rip, $(if ($rip -lt 8) {'SANO'} else {'DEGENERATO'}) | Out-File $out -Append -Encoding utf8
    }

    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep -Seconds 20
    Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
    Start-Sleep -Seconds 40
    "" | Out-File $out -Append -Encoding utf8
    $porta++
}

'FINE' | Out-File $out -Append -Encoding utf8
