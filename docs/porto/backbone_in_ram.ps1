# QUANTO COSTA IL BACKBONE IN RAM — spazzata su -ngl
#
# L'idea dell'utente: spostare il backbone in RAM per liberare VRAM, e metterci
# dentro il draft di DSpark residente. Attacca il punto giusto -- il costo FISSO
# della speculazione, 110,6 ms/token secondo il handoff, che e' "draft caricato
# piu' una passata".
#
# E c'e' una simmetria che la rende plausibile:
#   backbone   DENSO, per intero a ogni passata  ->  la speculazione lo AMMORTIZZA
#   esperti    SPARSI, 5 token = 5 insiemi       ->  la speculazione li MOLTIPLICA
# Oggi il backbone sta in VRAM dov'e' quasi gratis, quindi la speculazione puo'
# solo perdere. Spostandolo dove costa ma dove e' ammortizzabile, una delle due
# voci cambia segno.
#
# PRIMA di quantizzare il draft e prima di toccare la speculazione, serve UNA
# cosa: quanto costa il backbone in RAM da solo. Questa spazzata la misura.
#
# -ngl N = quanti strati hanno il backbone in VRAM. Con -cmoe gli esperti sono
# su CPU comunque, quindi -ngl muove SOLO backbone e attenzione. Ogni punto da'
# una coppia (VRAM occupata, velocita'), cioe' il tasso di cambio.
#
# Riferimenti gia' in archivio:  -ngl 99 -> 7,37 di regime, 9.793 MiB
#                                -ngl  0 -> 3,05 di regime  (ma li' anche la KV
#                                           e l'attenzione vanno su CPU)
#
# Il draft quantizzato a 2 bit starebbe intorno ai 5 GB: serve sapere quanto
# costa liberarne altrettanti.

$ErrorActionPreference = 'Continue'
$base  = 'D:\ds4_work\llama_run'
$banco = Join-Path $PSScriptRoot 'llama_confronto.ps1'
$exe   = 'D:\llama-b10227\llama-server.exe'
$esiti = Join-Path $base 'backbone_esiti.txt'
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

foreach ($ngl in @(32, 22, 12)) {
    $tag = "bb_ngl$ngl"
    "=============== -ngl $ngl ===============" | Out-File $esiti -Append -Encoding utf8

    $job = Start-Job -ScriptBlock {
        param($banco,$ngl,$tag,$exe)
        $env:LLAMA_ARG_CPU_MOE='1'
        & $banco -Ngl $ngl -Tokens 900 -Ctx 10000 -Exe $exe -Extra @('-ncmoe','42') -Etichetta $tag
    } -ArgumentList $banco,$ngl,$tag,$exe

    $vram = @()
    for ($i = 0; $i -lt 150; $i++) {
        Start-Sleep -Seconds 4
        $log = Get-ChildItem "$base\*$tag*.server.log" -EA SilentlyContinue | Select-Object -Last 1
        if ($log -and (Select-String -Path $log.FullName -Pattern 'n_decoded' -Quiet -EA SilentlyContinue)) {
            for ($k = 0; $k -lt 8; $k++) { $vram += (VramOra); Start-Sleep -Seconds 3 }
            break
        }
        if ($job.State -eq 'Completed') { break }
    }

    Receive-Job $job -Wait | Out-File "$base\$tag.banco.txt" -Encoding utf8
    Remove-Job $job -Force -EA SilentlyContinue

    $log = Get-ChildItem "$base\*$tag*.server.log" -EA SilentlyContinue | Select-Object -Last 1
    $ev  = if ($log) { (Select-String -Path $log.FullName -Pattern '        eval time' | Select-Object -Last 1).Line }
    # BUG CORRETTO (16/8): [int]($vram.Count/2) col banker's rounding cadeva un passo sopra il centro per Count dispari 3,7,11,... (con Count=3 era il MASSIMO); v. RUNBOOK par. 7.3
    $vm  = if ($vram.Count) { ($vram | Sort-Object)[[math]::Floor(($vram.Count-1)/2)] } else { -1 }

    "  VRAM $vm MiB" | Out-File $esiti -Append -Encoding utf8
    "  $ev"          | Out-File $esiti -Append -Encoding utf8

    Start-Sleep -Seconds 60
}

"=============== FINE ===============" | Out-File $esiti -Append -Encoding utf8
