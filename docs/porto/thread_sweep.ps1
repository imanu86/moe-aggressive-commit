# QUANTI THREAD SERVONO AL DECODE -- e chiude una discussione da 450 EUR
#
# Con l'ibrido acceso i matmul degli esperti in DECODE girano sulla CPU. Quindi
# il numero di thread e' diventato rilevante, e non l'abbiamo mai misurato.
#
# SCOPERTA CHE RENDE IL TEST URGENTE: su Windows llama.cpp cade su
# common_cpu_get_num_physical_cores() (common.cpp:203, tutte le #if sono per
# Linux/PowerPC), quindi usa 8 thread sui 16 disponibili. Se -t 16 rendesse,
# sarebbe velocita' GRATIS.
#
# LA DISCUSSIONE CHE DEVE CHIUDERE
# --------------------------------
# Un'altra sessione sostiene che siamo bandwidth-bound: 1,83 GB per token a
# ~41,5 GB/s darebbero un tetto di ~22,7 t/s, e nessuna quantita' di core lo
# supera. La sua conclusione: il 5950X vale il 5-12% (due CCD, due link
# Infinity Fabric) e i soldi vanno in una GPU piu' grande.
#
# I nostri due dati dicono il contrario:
#     banda usata a 2933      13,6 GB/s  =  33% del tetto pratico
#     +37,5% di frequenza     ->  +6,6% di velocita', non +37%
#
# La mia spiegazione: il collo non e' ne' banda ne' FLOP (siamo al 5% del picco
# AVX2) ma il THROUGHPUT DI ISTRUZIONI sulla dequantizzazione IQ2_XXS, che non
# compare in nessuno dei due contatori -- spacchettare un codebook e' accessi a
# tabella e shift, non moltiplicazioni.
#
# COME SI DECIDE
#     scala da 4 a 8 a 16   ->  e' CALCOLO, il 5950X ha senso
#     piatto gia' da 4 a 8  ->  e' BANDA, ha ragione l'altra sessione
#
# ORDINE DEI BRACCI: -t 16 per PRIMO su macchina appena liberata (la tesi paga
# la cache fredda), il metro -t 8 per ULTIMO con la cache piu' calda. L'ordine
# lavora CONTRO cio' che mi aspetto.
#
# NOTA sull'SMT: su matmul quantizzata due thread logici si contendono le stesse
# unita' AVX2 e la stessa L2, quindi -t 16 potrebbe andare PEGGIO di -t 8. Se
# succede e' comunque informativo: indicherebbe le unita' di esecuzione come
# collo, cioe' calcolo e non memoria.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\thread.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$req     = 'D:\ds4_work\llama_run\neuraforge1200.req.json'
$esp     = 'ffn_(gate|up|down)_exps' + [char]92 + '.weight'
$OT      = $esp + '=CUDA0_Mapped'

$bracci = @(
    @{ n='T16'; t=16; porta=8321 }
    @{ n='T04'; t=4;  porta=8322 }
    @{ n='T08'; t=8;  porta=8323 }
)

foreach ($b in $bracci) {
    "=============== $($b.n) -- $($b.t) thread ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_$($b.n).server.log"

    $env:LLAMA_MAPPED_IBRIDO = '1'
    $env:LLAMA_REAP = '0'

    $a = @('-m',$MODELLO,'-c','10000','-ngl','99','-ot',$OT,'-ub','64','-b','64',
           '-t',"$($b.t)",'--port',"$($b.porta)",'--host','127.0.0.1',
           '--no-warmup','--no-mmap','--reasoning-budget','0')

    # staccato: se la sessione viene interrotta il server non muore con lei
    $srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -WindowStyle Minimized `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out"

    $pronto = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 10
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "NON E' PARTITO" | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Start-Sleep -Seconds 30
        continue
    }

    $risp = "D:\ds4_work\llama_run\th_$($b.n).resp.json"
    & curl.exe -s --max-time 900 -X POST "http://127.0.0.1:$($b.porta)/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" -o $risp | Out-Null

    if (Test-Path $risp) {
        $d = Get-Content $risp -Raw | ConvertFrom-Json
        $t = $d.timings
        $c = $d.choices[0].message.content
        $r = ($c -split "`n") | Where-Object { $_.Trim().Length -gt 20 } | ForEach-Object { $_.Trim() }
        $rip = if ($r.Count) { ($r | Group-Object | Sort-Object Count -Desc | Select-Object -First 1).Count } else { 0 }
        "  prefill {0,7:N2} ms/tok  {1,6:N2} t/s" -f $t.prompt_per_token_ms, $t.prompt_per_second | Out-File $out -Append -Encoding utf8
        "  decode  {0,7:N2} ms/tok  {1,6:N2} t/s  ({2} tok)" -f $t.predicted_per_token_ms, $t.predicted_per_second, $t.predicted_n | Out-File $out -Append -Encoding utf8
        "  degenerazione: {0} car, ripetizione {1} -- {2}" -f $c.Length, $rip, $(if ($rip -lt 8) {'SANO'} else {'DEGENERATO, IL t/s NON VALE'}) | Out-File $out -Append -Encoding utf8
    }

    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep -Seconds 25
    $resti = Get-Process llama-server -EA SilentlyContinue
    if ($resti) { $resti | ForEach-Object { $_.Kill() }; Start-Sleep -Seconds 15 }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 60
}

'FINE' | Out-File $out -Append -Encoding utf8
