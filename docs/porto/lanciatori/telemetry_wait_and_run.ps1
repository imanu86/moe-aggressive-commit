# telemetry_wait_and_run.ps1 -- shim generico e riusabile: aspetta che llama-server.exe
# compaia (polling attivo, fino a -TimeoutMin), poi lancia sample_hw.ps1 con -Tag/-OutDir.
# Nessun parametro booleano: sicuro da invocare via Start-Process/-File senza il rischio
# di conversione stringa->bool di PowerShell.
param(
    [Parameter(Mandatory = $true)][string] $Tag,
    [Parameter(Mandatory = $true)][string] $OutDir,
    [int] $TimeoutMin = 10,
    [string] $SampleHwPath = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\sample_hw.ps1'
)
$deadline = (Get-Date).AddMinutes($TimeoutMin)
$found = $false
while ((Get-Date) -lt $deadline) {
    if (Get-Process -Name llama-server -ErrorAction SilentlyContinue) { $found = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $found) {
    "$(Get-Date -Format 'HH:mm:ss') telemetry_wait_and_run: TIMEOUT, llama-server mai comparso entro $TimeoutMin min. Nessuna telemetria avviata." |
        Out-File (Join-Path $OutDir "$Tag.telemetry_wait.log") -Encoding utf8
    exit 1
}
"$(Get-Date -Format 'HH:mm:ss') telemetry_wait_and_run: llama-server rilevato, avvio sample_hw.ps1 tag=$Tag" |
    Out-File (Join-Path $OutDir "$Tag.telemetry_wait.log") -Encoding utf8
& $SampleHwPath -Tag $Tag -OutDir $OutDir -IntervalSeconds 2 *>> (Join-Path $OutDir "$Tag.telemetry_wait.log")
