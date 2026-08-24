param(
  [string]$File,
  [int]$Start,
  [int]$End,
  [int]$Max = 3000
)
$i = 0
$sr = New-Object System.IO.StreamReader($File, [System.Text.Encoding]::UTF8)
while (($line = $sr.ReadLine()) -ne $null) {
  $i++
  if ($i -lt $Start) { continue }
  if ($i -gt $End) { break }
  try { $o = $line | ConvertFrom-Json } catch { Write-Output "### [$i] <unparsable>"; continue }
  $ts = $o.timestamp
  $t  = $o.type
  $p  = $o.payload
  $ptype = $null; $prole = $null
  if ($p) { $ptype = $p.type; $prole = $p.role }
  Write-Output "=== [$i] ts=$ts type=$t ptype=$ptype role=$prole"
  $txt = ""
  if ($p.content) {
    foreach ($c in $p.content) {
      if ($c.text) { $txt += $c.text + "`n" }
      elseif ($c.PSObject.Properties['type'] -and $c.type -eq 'input_text') { $txt += $c.text + "`n" }
    }
  }
  if (-not $txt -and $p.text) { $txt = $p.text }
  if (-not $txt -and $p.message) { $txt = $p.message }
  if (-not $txt -and $p.arguments) { $txt = "ARGS: " + $p.arguments }
  if (-not $txt -and $p.output) { $txt = "OUT: " + ($p.output | Out-String) }
  if (-not $txt) { $txt = ($p | ConvertTo-Json -Depth 6 -Compress) }
  if ($txt.Length -gt $Max) { $txt = $txt.Substring(0,$Max) + " ...[TRONCATO len=$($txt.Length)]" }
  Write-Output $txt
  Write-Output ""
}
$sr.Close()
