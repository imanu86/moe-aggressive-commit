# Tre bracci sulla STESSA build (llama-dspark + reap, 2026-08-02 sera).
#
#   A1  osservatore SPENTO   <- controllo che mancava: isola la build dal reap
#   B   osservatore ACCESO   <- il costo vero della sezione critica, cronometrato
#   A2  osservatore SPENTO   <- secondo controllo: da' la varianza dentro la sessione
#
# A1 e A2 valgono anche come misure 3 e 4 del riferimento ncmoe42 (6,86 / 6,75),
# cioe' chiudono il punto 2 della coda.
#
# L'ordine A-B-A mette il trattamento FRA i due controlli: se la page cache si
# scalda run dopo run, il confronto B-contro-media(A) non ne e' falsato.

$ErrorActionPreference = 'Continue'
$env:LLAMA_ARG_CPU_MOE = '1'
$exe    = 'D:\llama-dspark\build\bin\llama-server.exe'
$banco  = 'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\llama_confronto.ps1'
$comuni = @{ Ngl = 99; Tokens = 1500; Ctx = 10000; Exe = $exe; Extra = @('-ncmoe','42') }

function Spegni-Reap {
    'LLAMA_REAP','LLAMA_REAP_PROF','LLAMA_REAP_DUMP' | ForEach-Object {
        if (Test-Path "Env:$_") { Remove-Item "Env:$_" }
    }
}

function Quiete($s) {
    Write-Host ""
    Write-Host "  --- quiete $s s, VRAM $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) ---"
    Start-Sleep -Seconds $s
}

Write-Host "=============== A1  osservatore SPENTO (controllo) ==============="
Spegni-Reap
& $banco @comuni -Etichetta 'reapoff_A1'
Quiete 120

Write-Host "=============== B   osservatore ACCESO ==============="
$env:LLAMA_REAP      = '1'
$env:LLAMA_REAP_PROF = '1'
$env:LLAMA_REAP_DUMP = 'D:\ds4_work\llama_run\reap_calore.tsv'
& $banco @comuni -Etichetta 'reapon_B'
Quiete 120

Write-Host "=============== A2  osservatore SPENTO (controllo) ==============="
Spegni-Reap
& $banco @comuni -Etichetta 'reapoff_A2'

Write-Host ""
Write-Host "=============== FINE tre bracci ==============="
