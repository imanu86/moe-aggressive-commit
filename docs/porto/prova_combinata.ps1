# I TRE SEGNALI NELLO STESSO RUN.
#
# Il 2/8 sera avevamo tre misure che non stanno insieme, prese da run diversi e
# da due binari diversi:
#
#   mul_mat_id sul backend CPU     0 chiamate     (vanilla, -ngl 99 -ncmoe 42)
#   traffico PCIe                  66 MB/s        (UFFICIALE, -ngl 99 -ncmoe 42)
#   SM occupati                    39%
#   esperti da servire             ~1,7 GiB/token, e in VRAM non ci stanno
#
# Se il MoE non gira sulla CPU, non arriva dal bus, e la GPU e' occupata al 39%,
# manca un pezzo. Ma le misure vengono da run e binari diversi, quindi il primo
# sospetto e' che non siano confrontabili.
#
# Questo script le prende TUTTE E TRE dallo stesso processo:
#   - binario VANILLA (l'unico che ha il reap compilato)
#   - -ngl 99 -ncmoe 42, cioe' la configurazione promossa
#   - osservatore acceso col cronometro
#   - sonda PCIe campionata DURANTE la generazione
#
# Esito atteso, e cosa vuol dire:
#   chiamate > 0  -> lo zero di prima era un artefatto di quel run
#   chiamate = 0 con PCIe fermo -> il paradosso e' reale, si scava nel codice

$ErrorActionPreference = 'Continue'
$base = 'D:\ds4_work\llama_run'
$tagf = Join-Path $base 'prova_combinata'

$env:LLAMA_ARG_CPU_MOE = '1'
$env:LLAMA_REAP        = '1'
$env:LLAMA_REAP_PROF   = '1'
$env:LLAMA_REAP_DUMP   = "$tagf.calore.tsv"
if (Test-Path $env:LLAMA_REAP_DUMP) { Remove-Item $env:LLAMA_REAP_DUMP -Force }

# il banco in un job, cosi' possiamo campionare mentre gira
$job = Start-Job -ScriptBlock {
    param($b)
    $env:LLAMA_ARG_CPU_MOE='1'; $env:LLAMA_REAP='1'; $env:LLAMA_REAP_PROF='1'
    $env:LLAMA_REAP_DUMP="$b\prova_combinata.calore.tsv"
    & 'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\llama_confronto.ps1' `
        -Ngl 99 -Tokens 900 -Ctx 10000 `
        -Exe 'D:\llama-vanilla\build\bin\llama-server.exe' `
        -Extra @('-ncmoe','42') -Etichetta 'combinata'
} -ArgumentList $base

# attesa dell'inizio della generazione
$log = $null
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 5
    $log = Get-ChildItem "$base\*combinata*.server.log" -EA SilentlyContinue | Select-Object -Last 1
    if ($log -and (Select-String -Path $log.FullName -Pattern 'n_decoded' -Quiet -EA SilentlyContinue)) { break }
    $log = $null
}
if (-not $log) { "PROVA: la generazione non e' mai partita" | Out-File "$tagf.txt" -Encoding utf8; Receive-Job $job -Wait; return }

# sonda PCIe durante il decode
$dmon = & nvidia-smi dmon -s tu -c 30 2>&1
$dmon | Out-File "$tagf.dmon.txt" -Encoding utf8

$rx=@(); $tx=@(); $sm=@()
foreach ($r in ($dmon | Where-Object { $_ -notmatch '^#' -and $_.Trim() -ne '' })) {
    $c = ($r -split '\s+') | Where-Object { $_ -ne '' }
    if ($c.Count -ge 4) { $rx += [double]$c[1]; $tx += [double]$c[2]; $sm += [double]$c[3] }
}
function Med($a) { if ($a.Count) { ($a | Sort-Object)[[int]($a.Count/2)] } else { -1 } }

Receive-Job $job -Wait | Out-File "$tagf.banco.txt" -Encoding utf8
Remove-Job $job -Force -EA SilentlyContinue

$reap = Select-String -Path $log.FullName -Pattern '^reap:' -EA SilentlyContinue | ForEach-Object { $_.Line }
$ev   = (Select-String -Path $log.FullName -Pattern '        eval time' | Select-Object -Last 1).Line

@(
 "=== PROVA COMBINATA, tutti i segnali dallo stesso run ==="
 "log:  $($log.Name)"
 ""
 "--- osservatore reap ---"
 ($reap -join "`n")
 ""
 "--- PCIe durante il decode (mediane su $($rx.Count) campioni) ---"
 ("RX  {0} MB/s     TX  {1} MB/s     SM  {2}%" -f (Med $rx), (Med $tx), (Med $sm))
 ""
 "--- velocita' ---"
 $ev
) | Out-File "$tagf.txt" -Encoding utf8

Get-Content "$tagf.txt"
