# Durable anti-orphan dead-man for POD A (chripell ref).
# Removes ONLY the pod recorded in POD_ID.txt. Reads key at runtime (never stored here).
$ErrorActionPreference = 'SilentlyContinue'
$dir = 'C:\Users\imanu\source\repos\moe-aggressive-commit\runs\ds4\20260713_podA_chripell_ref'
$podId = (Get-Content (Join-Path $dir 'POD_ID.txt') -Raw).Trim()
$protected = @('99xyqm02gke4xg','3upjyrmu6mdof4','i9vl406tmclevz')
if ([string]::IsNullOrWhiteSpace($podId) -or ($protected -contains $podId)) {
  "reaper: refusing to act on '$podId'" | Out-File -Append (Join-Path $dir 'reaper_podA.log')
  schtasks /delete /tn 'ds4_podA_reaper' /f | Out-Null
  exit 1
}
$key = (Get-Content 'C:\Users\imanu\Desktop\Runapod.txt' -Raw).Trim()
& "$env:USERPROFILE\bin\runpodctl.exe" config --apiKey $key | Out-Null
$out = & "$env:USERPROFILE\bin\runpodctl.exe" remove pod $podId 2>&1
("[{0}] reaper removed {1} :: {2}" -f (Get-Date -Format o), $podId, $out) | Out-File -Append (Join-Path $dir 'reaper_podA.log')
schtasks /delete /tn 'ds4_podA_reaper' /f | Out-Null
