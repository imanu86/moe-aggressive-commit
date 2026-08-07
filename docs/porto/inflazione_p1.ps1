# QUANTO VALE L'ATTRATTORE: p1 dei run SANI contro p1 dei run DEGENERATI.
# Stessa configurazione, unica differenza l'attrattore di ripetizione. La
# differenza fra le due mediane e' la TAGLIA DELL'INFLAZIONE, misurata invece
# che stimata (idea dell'arbitro, 7/8/2026).
$ris = @()
Get-ChildItem "D:\ds4_work\llama_run\*.resp.json" | ForEach-Object {
  $tag = $_.Name -replace '\.resp\.json',''
  $j = Get-Content $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  if ([string]::IsNullOrEmpty($j.content)) { return }
  if ($j.timings.draft_n -le 0) { return }
  $tok = $j.content -split '\s+' | Where-Object { $_.Length -gt 0 }
  if ($tok.Count -lt 50) { return }
  $g5 = New-Object System.Collections.Generic.List[string]
  for ($i = 0; $i -lt ($tok.Count - 5); $i++) { $g5.Add(($tok[$i..($i+4)] -join ' ')) }
  $rip = ($g5 | Group-Object | Sort-Object Count -Descending | Select-Object -First 1).Count
  $log = "D:\ds4_work\llama_run\" + $tag + "_server.log"
  if (-not (Test-Path $log)) { return }
  # SOLO task 0: l'ultima riga "acc per pos" del log appartiene al FLUSH
  # ("ciao", 8 token) e vale 0,000-0,333. Senza questo filtro si legge quella
  # e si riporta il p1 della richiesta di scarico invece che della misura.
  $m = Select-String -Path $log -Pattern "task 0 \|\s+acc per pos = \(([0-9\.]+)" | Select-Object -Last 1
  if (-not $m) { return }
  $p1 = [double]$m.Matches[0].Groups[1].Value
  if ($p1 -le 0) { return }
  $v = if ($rip -le 2) { "SANO" } elseif ($rip -ge 8) { "DEGENERE" } else { "sospetto" }
  $ris += [pscustomobject]@{ tag = $tag; g5 = $rip; p1 = $p1; v = $v; tok = $j.tokens_predicted }
}
"=== p1 contro verdetto del testo (soli bracci spec) ==="
$ris | Sort-Object v, p1 | ForEach-Object { "   {0,-26} 5gr={1,-5} p1={2,-7} tok={3,-5} {4}" -f $_.tag, $_.g5, $_.p1, $_.tok, $_.v }
""
foreach ($g in "SANO", "sospetto", "DEGENERE") {
  $s = @($ris | Where-Object { $_.v -eq $g } | Select-Object -ExpandProperty p1)
  if ($s.Count -gt 0) {
    $sorted = @($s | Sort-Object)
    $med = $sorted[[math]::Floor($s.Count / 2)]
    "{0,-10} n={1,-3} mediana={2,-8} forbice {3} - {4}" -f $g, $s.Count, $med, ($s | Measure-Object -Minimum).Minimum, ($s | Measure-Object -Maximum).Maximum
  }
}
