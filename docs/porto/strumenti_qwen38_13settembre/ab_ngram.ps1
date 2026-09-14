# Confronto A/B: testa MTP da sola contro testa MTP piu' uno speculatore a n-grammi.
#
# ATTENZIONE alla semantica, verificata nel codice: NON si sommano. Gli n-grammi hanno
# PRECEDENZA sui tipi con modello di bozza (speculative.cpp:2672-2684) e in
# common_speculative_draft (2868-2903) chi abbozza per primo vince: la sequenza viene
# marcata drafting=false e gli implementatori successivi la saltano. Quindi l'n-grammo
# SCAVALCA la testa MTP ogni volta che aggancia, e la combinazione conviene solo se,
# quando spara, accetta piu' dello 0,75 della testa.
#
# Il carico e' a RIPETIZIONE (banco_ripetizione.py): il modello riproduce un file che ha
# nel prompt. Sul testo libero un n-grammo non aggancia quasi mai e si misurerebbe il nulla.
#
# L'attribuzione per implementatore la stampa il server a ogni richiesta, subito dopo la
# riga "draft acceptance" (server-context.cpp:713 dentro print_timings).
param(
    [string[]] $Tipi = @('draft-mtp', 'draft-mtp,ngram-mod')
)

$scratch = "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strumenti_qwen38_13settembre"
$tmp     = "C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\caacd61a-a05f-4e65-8c73-192af1c868f4\scratchpad"
$logdir  = "C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_server_logs_sperimentali"

foreach ($tipo in $Tipi) {
    $etichetta = ($tipo -replace '[^a-zA-Z0-9]', '_')
    Write-Output ("######## SPEC_TYPES=$tipo ########")

    $p = Get-Process llama-server -ErrorAction SilentlyContinue
    if ($p) { $p | Stop-Process -Force; Start-Sleep -Seconds 6 }

    $env:SPEC_TYPES         = $tipo
    $env:QWEN4EXP_SPARSE_FA = "0"
    $env:MOE_SLOTS          = "64"
    $env:DRAFT_EXPERTS      = "ram"

    # MTP acceso: e' il ramo che usa --spec-type
    $pr = Start-Process -FilePath "cmd.exe" `
        -ArgumentList '/c', '"C:\Users\imanu\Desktop\avvia Qwen38 SPERIMENTALE.bat" 1' `
        -RedirectStandardOutput "$tmp\ngram_$etichetta.out" -RedirectStandardError "$tmp\ngram_$etichetta.err" `
        -NoNewWindow -PassThru

    $deadline = (Get-Date).AddMinutes(9); $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:8100/v1/models" -Headers @{Authorization="Bearer Sticazzi86"} -TimeoutSec 4
            if ($r) { $ready = $true; break }
        } catch { }
        if ($pr.HasExited -and -not (Get-Process llama-server -ErrorAction SilentlyContinue)) {
            Write-Output "LANCIATORE USCITO:"; Get-Content "$tmp\ngram_$etichetta.err" -Tail 20; break
        }
        Start-Sleep -Seconds 5
    }
    if (-not $ready) { Write-Output "NON PRONTO, salto questo braccio"; continue }

    # conferma di quali speculatori sono stati davvero costruiti
    $log = Get-ChildItem "$logdir\*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Write-Output "-- speculatori dichiarati all'avvio:"
    Get-Content $log.FullName | Select-String -Pattern "speculative|spec type|adding speculative" | Select-Object -First 8 | ForEach-Object { $_.Line }

    & python "$scratch\banco_ripetizione.py" --label $etichetta

    Write-Output "-- statistiche per implementatore (dal log, dopo 'draft acceptance'):"
    Get-Content $log.FullName | Select-String -Pattern "draft acceptance|impl|n_call_draft|speculative" | Select-Object -Last 20 | ForEach-Object { $_.Line }
    Write-Output ""
}

$p = Get-Process llama-server -ErrorAction SilentlyContinue
if ($p) { $p | Stop-Process -Force; Write-Output "server fermato" }
