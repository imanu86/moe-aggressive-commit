# ncmoe41 RIFATTO, con sonda di consumo e di memoria condivisa.
#
# A ledger e' falsificato: "2o strato in CONDIVISA (+1,73GiB shared), travaso
# WDDM silenzioso", misurato il 2/8 alle 15:23. Ma quella giornata aveva due
# difetti che stanotte abbiamo trovato:
#   - ogni server veniva UCCISO (CTRL_BREAK ignorato da llama), quindi la VRAM
#     non veniva rilasciata e i residui si accumulavano run dopo run
#   - la stessa config mostrava 11,70 GB allora e 9,6 adesso: 2,1 GB di
#     differenza mai spiegati
# Oggi con ncmoe42 restano 2.685 MiB liberi e uno strato ne chiede 1.731.
#
# Serve per due cose:
#   1. se entra, e' uno strato di esperti in piu' GRATIS
#   2. e' il SECONDO PUNTO sopra il ginocchio della curva VRAM. Oggi il tasso
#      di 4,5 ms/GB poggia su un punto solo (ncmoe42 contro cmoe): con due si
#      sa se il rendimento regge o crolla, ed e' quello che decide se comprare
#      12 GB di VRAM ha senso.
#
# La sonda del consumo risponde alla domanda sull'alimentatore: con gli SM al
# 35-39% la 3060 dovrebbe stare ben sotto i 170 W nominali, ma non l'abbiamo
# mai misurato.

$ErrorActionPreference = 'Continue'
$env:LLAMA_ARG_CPU_MOE = '1'
foreach ($v in @('LLAMA_REAP','LLAMA_REAP_PROF','LLAMA_REAP_DUMP','GGML_SCHED_DEBUG')) {
    if (Test-Path "Env:$v") { Remove-Item -LiteralPath "Env:$v" }
}

$contDed = '\GPU Adapter Memory(*)\Dedicated Usage'
$contSha = '\GPU Adapter Memory(*)\Shared Usage'

$job = Start-Job -ScriptBlock {
    $env:LLAMA_ARG_CPU_MOE = '1'
    & 'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\llama_confronto.ps1' `
        -Ngl 99 -Tokens 900 -Ctx 10000 -Exe 'D:\llama-b10227\llama-server.exe' `
        -Extra @('-ncmoe','41') -Etichetta 'ncmoe41_rifatto'
}

$pot = @(); $ded = @(); $sha = @()
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 4
    $log = Get-ChildItem 'D:\ds4_work\llama_run\*ncmoe41_rifatto*.server.log' -EA SilentlyContinue |
           Select-Object -Last 1
    if ($log -and (Select-String -Path $log.FullName -Pattern 'n_decoded' -Quiet -EA SilentlyContinue)) {
        for ($k = 0; $k -lt 10; $k++) {
            $p = (nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits) 2>$null
            if ($p) { $pot += [double]$p }
            $d = (Get-Counter $contDed -EA SilentlyContinue).CounterSamples |
                 Sort-Object CookedValue -Descending | Select-Object -First 1
            $s = (Get-Counter $contSha -EA SilentlyContinue).CounterSamples |
                 Sort-Object CookedValue -Descending | Select-Object -First 1
            if ($d) { $ded += [math]::Round($d.CookedValue / 1MB) }
            if ($s) { $sha += [math]::Round($s.CookedValue / 1MB) }
            Start-Sleep -Seconds 3
        }
        break
    }
    if ($job.State -eq 'Completed') { break }
}

function Med($a) { if ($a.Count) { ($a | Sort-Object)[[int]($a.Count / 2)] } else { -1 } }

$out = 'D:\ds4_work\llama_run\ncmoe41_esito.txt'
@(
 "potenza GPU    mediana $(Med $pot) W   max $(($pot | Measure-Object -Maximum).Maximum) W"
 "VRAM dedicata  mediana $(Med $ded) MiB"
 "VRAM CONDIVISA mediana $(Med $sha) MiB   (>0 = travaso WDDM, la falsificazione del 2/8)"
) | Tee-Object -FilePath $out -Encoding utf8

Receive-Job $job -Wait | Out-File 'D:\ds4_work\llama_run\ncmoe41_banco.txt' -Encoding utf8
Remove-Job $job -Force -EA SilentlyContinue

$log = Get-ChildItem 'D:\ds4_work\llama_run\*ncmoe41_rifatto*.server.log' -EA SilentlyContinue |
       Select-Object -Last 1
if ($log) {
    (Select-String -Path $log.FullName -Pattern '        eval time' | Select-Object -Last 1).Line |
        Tee-Object -FilePath $out -Append
}
"FINE" | Out-File $out -Append -Encoding utf8
