# LA KV IN RAM COSTA? — quattro bracci, due contesti.
#
# La domanda che decide se il ring KV va scritto. llama.cpp ha gia' -nkvo, che
# mette la KV in memoria host senza nessun ring. Se costa poco, il divario fra
# cio' che e' ALLOCATO (tutto n_ctx) e cio' che viene LETTO (~640 righe per
# token: finestra 128 + top-512 dell'indexer) e' gia' sfruttabile e il ring non
# ha un lavoro da fare. Se costa molto, e' perche' si copia piu' del necessario,
# e la finestra scorrevole e' esattamente la cura.
#
# I due contesti danno anche la PENDENZA, cioe' quanto varrebbe a 150k senza
# doverci arrivare. E la VRAM misurata durante il decode da', per differenza,
# la dimensione vera della KV -- numero che finora e' stato solo stimato
# (88-176 MB a 10k, con un'incertezza di fattore 2).
#
# Perche' quattro bracci e non due: la KV cresce col contesto, il resto no. Solo
# avendo entrambi i contesti si separa "quanto pesa la KV" da "quanto costa
# spostarla".

$ErrorActionPreference = 'Continue'
$base  = 'D:\ds4_work\llama_run'
$banco = Join-Path $PSScriptRoot 'llama_confronto.ps1'
$exe   = 'D:\llama-b10227\llama-server.exe'
$esiti = Join-Path $base 'nkvo_esiti.txt'
if (Test-Path $esiti) { Remove-Item $esiti -Force }

$env:LLAMA_ARG_CPU_MOE = '1'
'LLAMA_REAP','LLAMA_REAP_PROF','LLAMA_REAP_DUMP' | ForEach-Object {
    if (Test-Path "Env:$_") { Remove-Item "Env:$_" }
}

function VramOra {
    $d = (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    if ($d) { [math]::Round($d.CookedValue/1MB) } else { -1 }
}

$bracci = @(
    @{ n='A'; ctx=10000; nkvo=$false; tag='nkvo_A_10k_base' }
    @{ n='B'; ctx=10000; nkvo=$true;  tag='nkvo_B_10k_host' }
    @{ n='C'; ctx=20000; nkvo=$false; tag='nkvo_C_20k_base' }
    @{ n='D'; ctx=20000; nkvo=$true;  tag='nkvo_D_20k_host' }
)

foreach ($b in $bracci) {
    "=============== BRACCIO $($b.n)  ctx $($b.ctx)  nkvo=$($b.nkvo) ===============" |
        Tee-Object -FilePath $esiti -Append

    $extra = @('-ncmoe','42')
    if ($b.nkvo) { $extra += '-nkvo' }

    # il banco in un job, cosi' si campiona la VRAM mentre genera
    $job = Start-Job -ScriptBlock {
        param($banco,$ctx,$extra,$tag,$exe)
        $env:LLAMA_ARG_CPU_MOE='1'
        & $banco -Ngl 99 -Tokens 900 -Ctx $ctx -Exe $exe -Extra $extra -Etichetta $tag
    } -ArgumentList $banco,$b.ctx,$extra,$b.tag,$exe

    # attesa dell'inizio della generazione, poi campiona la VRAM
    $vram = @()
    for ($i = 0; $i -lt 150; $i++) {
        Start-Sleep -Seconds 4
        $log = Get-ChildItem "$base\*$($b.tag)*.server.log" -EA SilentlyContinue | Select-Object -Last 1
        if ($log -and (Select-String -Path $log.FullName -Pattern 'n_decoded' -Quiet -EA SilentlyContinue)) {
            for ($k = 0; $k -lt 8; $k++) { $vram += (VramOra); Start-Sleep -Seconds 3 }
            break
        }
        if ($job.State -eq 'Completed') { break }
    }

    Receive-Job $job -Wait | Out-File "$base\$($b.tag).banco.txt" -Encoding utf8
    Remove-Job $job -Force -EA SilentlyContinue

    $log = Get-ChildItem "$base\*$($b.tag)*.server.log" -EA SilentlyContinue | Select-Object -Last 1
    $ev  = if ($log) { (Select-String -Path $log.FullName -Pattern '        eval time' | Select-Object -Last 1).Line }
    $vm  = if ($vram.Count) { ($vram | Sort-Object)[[int]($vram.Count/2)] } else { -1 }

    "  VRAM dedicata durante il decode: $vm MiB  (mediana su $($vram.Count) campioni)" |
        Tee-Object -FilePath $esiti -Append
    "  $ev" | Tee-Object -FilePath $esiti -Append
    "" | Tee-Object -FilePath $esiti -Append

    if ($b.n -ne 'D') { Start-Sleep -Seconds 90 }
}

"=============== FINE ===============" | Tee-Object -FilePath $esiti -Append
Get-Content $esiti
