param(
  [string]$File,
  [int[]]$Lines,
  [string]$Pattern,
  [int]$Before = 500,
  [int]$After = 900
)
$i = 0
$want = @{}
foreach ($n in $Lines) { $want[$n] = $true }
$sr = New-Object System.IO.StreamReader($File, [System.Text.Encoding]::UTF8)
while (($l = $sr.ReadLine()) -ne $null) {
  $i++
  if (-not $want.ContainsKey($i)) { continue }
  $ts = "?"
  if ($l -match '"timestamp":"([^"]+)"') { $ts = $matches[1] }
  Write-Output "########## LINEA $i  ts=$ts  len=$($l.Length)"
  $ms = [regex]::Matches($l, $Pattern)
  if ($ms.Count -eq 0) { Write-Output "(nessun match)" ; continue }
  $shown = 0
  foreach ($m in $ms) {
    if ($shown -ge 4) { break }
    $shown++
    $a = [Math]::Max(0, $m.Index - $Before)
    $len = [Math]::Min($l.Length - $a, $Before + $m.Length + $After)
    Write-Output "---- match@$($m.Index) ----"
    Write-Output $l.Substring($a, $len)
    Write-Output ""
  }
}
$sr.Close()
