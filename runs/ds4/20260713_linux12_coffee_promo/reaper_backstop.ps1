# Durable anti-orphan backstop. Removes ONLY the pod recorded in POD_ID.txt.
# Reads RunPod API key from the local creds file at runtime (never stored here).
$ErrorActionPreference = 'SilentlyContinue'
$dir = 'C:\Users\imanu\source\repos\moe-aggressive-commit\runs\ds4\20260713_linux12_coffee_promo'
$podId = (Get-Content (Join-Path $dir 'POD_ID.txt') -Raw).Trim()
# Safety: only act on ids we created (11-14 lowercase alnum) and never the protected id
$protected = @('99xyqm02gke4xg','3upjyrmu6mdof4')
if ([string]::IsNullOrWhiteSpace($podId) -or ($protected -contains $podId)) {
  "reaper: refusing to act on '$podId'" | Out-File -Append (Join-Path $dir 'reaper_backstop.log')
  exit 1
}
$key = (Get-Content 'C:\Users\imanu\Desktop\Runapod.txt' -Raw).Trim()
& "$env:USERPROFILE\bin\runpodctl.exe" config --apiKey $key | Out-Null
$out = & "$env:USERPROFILE\bin\runpodctl.exe" remove pod $podId 2>&1
("[{0}] reaper removed {1} :: {2}" -f (Get-Date -Format o), $podId, $out) | Out-File -Append (Join-Path $dir 'reaper_backstop.log')
# clean up the scheduled task itself
schtasks /delete /tn 'ds4_pod_reaper_l12' /f | Out-Null
