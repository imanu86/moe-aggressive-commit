param(
  [string]$File,
  [int]$Start = 1,
  [int]$End = 999999,
  [int]$Max = 2500,
  [string]$Match = ""
)
$i = 0
$sr = New-Object System.IO.StreamReader($File, [System.Text.Encoding]::UTF8)
while (($line = $sr.ReadLine()) -ne $null) {
  $i++
  if ($i -lt $Start) { continue }
  if ($i -gt $End) { break }
  if ($line -notmatch '"(agent_message|user_message|agent_reasoning|agent_reasoning_section_break)"') { continue }
  try { $o = $line | ConvertFrom-Json } catch { continue }
  if ($o.type -ne 'event_msg') { continue }
  $pt = $o.payload.type
  if ($pt -notin @('agent_message','user_message','agent_reasoning')) { continue }
  $txt = $o.payload.message
  if (-not $txt) { $txt = $o.payload.text }
  if (-not $txt) { continue }
  if ($Match -and ($txt -notmatch $Match)) { continue }
  if ($txt.Length -gt $Max) { $txt = $txt.Substring(0,$Max) + " ...[TRONC len=$($txt.Length)]" }
  Write-Output "=== [$i] $($o.timestamp) $pt"
  Write-Output $txt
  Write-Output ""
}
$sr.Close()
