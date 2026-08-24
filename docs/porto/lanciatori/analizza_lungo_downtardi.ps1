# analizza_lungo_downtardi.ps1 -- estrae dal log grezzo del braccio B-LUNGO lungo_downtardi
# tutti i dati richiesti dai cancelli del mandato (a-f). Solo lettura, nessuna scrittura sui
# file del banco. Da eseguire DOPO che il launcher.out mostra "DONE tag=...".

$runDir = 'D:\ds4_work\llama_run'
$tag    = 'sota_ctx150000_densefa_stage_hc5_lungo_downtardi_f2_b2048'
$log    = Join-Path $runDir "$tag.server.log"
$summary = Join-Path $runDir 'sota100k_ctx150k_densefa_stage_hc5_lungo_downtardi.summary.txt'

Write-Output "=== log = $log ==="
Write-Output "=== summary = $summary ==="

Write-Output "`n--- riga cache-esperti (identita') ---"
Select-String -LiteralPath $log -Pattern '^cache-esperti: \d+ slot' | Select-Object -First 1 -ExpandProperty Line

Write-Output "`n--- sfratto_par ---"
Select-String -LiteralPath $log -Pattern 'sfratto_par=([0-9])' | Select-Object -First 1 -ExpandProperty Line

Write-Output "`n--- semina control block ---"
Select-String -LiteralPath $log -Pattern 'porto-cb: epoca=\d+ semina da ambiente' | Select-Object -First 1 -ExpandProperty Line

Write-Output "`n--- TUTTI i cambi control-block (testimoni epoca/ricattura) ---"
Select-String -LiteralPath $log -Pattern 'control-block ->' | ForEach-Object { $_.Line }

Write-Output "`n--- TUTTE le righe porto-cb IN VIGORE / RIFIUTATA ---"
Select-String -LiteralPath $log -Pattern 'porto-cb: epoca=\d+ (IN VIGORE|richiesta)' -Context 0,0 | ForEach-Object { $_.Line }
Select-String -LiteralPath $log -Pattern 'RIFIUTATA' | ForEach-Object { $_.Line }

Write-Output "`n--- checkpoint di coda creato ---"
Select-String -LiteralPath $log -Pattern 'created context checkpoint' | ForEach-Object { $_.Line }

Write-Output "`n--- checkpoint ripristinato (per replica) ---"
Select-String -LiteralPath $log -Pattern 'restored context checkpoint' | ForEach-Object { $_.Line }

Write-Output "`n--- ASSENTI attesi (reprocessing forzato / checkpoint invalidato) ---"
Select-String -LiteralPath $log -Pattern 'forcing full prompt re-processing|erased invalidated context checkpoint' | ForEach-Object { $_.Line }
Write-Output '(vuoto = PASS)'

Write-Output "`n--- TUTTE le prompt eval (prefill), in ordine ---"
Select-String -LiteralPath $log -Pattern 'prompt eval time =.*tokens per second' | ForEach-Object { $_.Line }

Write-Output "`n--- TUTTE le eval time (decode), in ordine ---"
Select-String -LiteralPath $log -Pattern '\|\s+eval time =.*tokens per second' | ForEach-Object { $_.Line }

Write-Output "`n--- TUTTE le draft acceptance (p1), in ordine ---"
Select-String -LiteralPath $log -Pattern 'draft acceptance = ([0-9.]+)' | ForEach-Object { $_.Line }

Write-Output "`n--- finish_reason per replica (dal summary, poi verificare dal response.json) ---"
Select-String -LiteralPath $summary -Pattern 'finish=' -Encoding Unicode | ForEach-Object { $_.Line }

Write-Output "`n--- build ---"
Select-String -LiteralPath $log -Pattern 'common_params_print_info: build' | Select-Object -First 1 -ExpandProperty Line

Write-Output "`n--- sched-profilo conteggio ---"
(Select-String -LiteralPath $log -Pattern 'sched-profilo').Count

Write-Output "`n--- manifesto GGML_SCHED_PROFILO / GGML_CUDA_DISABLE_GRAPHS ---"
Select-String -LiteralPath $log -Pattern 'GGML_SCHED_PROFILO=[01]\([ED]\)' | Select-Object -First 1 -ExpandProperty Line
Select-String -LiteralPath $log -Pattern 'GGML_CUDA_DISABLE_GRAPHS' | Select-Object -First 1 -ExpandProperty Line

Write-Output "`n--- errori / divergenze / OOM ---"
Select-String -LiteralPath $log -Pattern 'GGML_ASSERT|CUDA error|invalid index|out of memory' | Select-Object -Last 20 | ForEach-Object { $_.Line }
Select-String -LiteralPath $log -Pattern 'divergenze' | Select-Object -Last 10 | ForEach-Object { $_.Line }

Write-Output "`n--- copie/buchi cache-esperti (ultima riga = totale cumulativo) ---"
Select-String -LiteralPath $log -Pattern '^cache-esperti: domanda \d+' | Select-Object -Last 1 -ExpandProperty Line

Write-Output "`n--- shutdown / DONE ---"
Select-String -LiteralPath $summary -Pattern 'shutdown:|DONE tag=' -Encoding Unicode | ForEach-Object { $_.Line }

Write-Output "`n--- SHA output per replica (dal summary) ---"
Select-String -LiteralPath $summary -Pattern 'output sha256=' -Encoding Unicode | ForEach-Object { $_.Line }

Write-Output "`n--- output chars per replica (dal summary) ---"
Select-String -LiteralPath $summary -Pattern 'output chars=' -Encoding Unicode | ForEach-Object { $_.Line }
