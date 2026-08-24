$ErrorActionPreference = 'Stop'
$tag = 't21_conf_s3_b1200_r1_20260818'
$outDir = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs'
for ($i = 0; $i -lt 240; $i++) {
    if (Get-Process -Name llama-server -ErrorAction SilentlyContinue) {
        Write-Output "server rilevato dopo $i controlli, avvio sample_hw"
        break
    }
    Start-Sleep -Seconds 2
}
& 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\sample_hw.ps1' -Tag $tag -OutDir $outDir -IntervalSeconds 2
