# IL COSTO PER CHIAMATA E' ROBUSTO ALL'ATTRATTORE?
#
# Ipotesi dell'arbitro (7/8/2026): la degenerazione cambia la COMPOSIZIONE del
# passo -- quante chiamate, con che batch -- non cosa fa UNA chiamata. Se e'
# vero, dur(g)/chiamata e dur(p)/chiamata concordano fra bracci sani e
# degenerati, e il costo del proponente si estrae anche dai degenerati: ~14
# bracci di macchina risparmiati.
$ris = @()
Get-ChildItem "D:\ds4_work\llama_run\*.resp.json" | ForEach-Object {
  $tag = $_.Name -replace '\.resp\.json',''
  $j = Get-Content $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  if ([string]::IsNullOrEmpty($j.content) -or $j.timings.draft_n -le 0) { return }
  $tok = $j.content -split '\s+' | Where-Object { $_.Length -gt 0 }
  if ($tok.Count -lt 50) { return }
  $g5 = New-Object System.Collections.Generic.List[string]
  for ($i = 0; $i -lt ($tok.Count - 5); $i++) { $g5.Add(($tok[$i..($i+4)] -join ' ')) }
  $rip = ($g5 | Group-Object | Sort-Object Count -Descending | Select-Object -First 1).Count
  $log = "D:\ds4_work\llama_run\" + $tag + "_server.log"
  if (-not (Test-Path $log)) { return }

  # riga statistics dell'ULTIMA richiesta vera (non il flush): si prende
  # l'ultima con #calls(b,g,a) e si legge dur(g) e i conteggi.
  $st = Select-String -Path $log -Pattern "#calls\(b,g,a\) =\s+\d+\s+(\d+)\s+\d+.*dur\(b,g,a[^)]*\) = [\d\.]+, ([\d\.]+), [\d\.]+" | Select-Object -Last 1
  if (-not $st) { return }
  $ndraft = [double]$st.Matches[0].Groups[1].Value
  $tg     = [double]$st.Matches[0].Groups[2].Value
  if ($ndraft -le 0) { return }

  # dur(p): due formati -- "dur(p) = X ms, #call p = N" (albero dspark)
  # e "dur(b,g,a,PROC) = a, b, c, X ms" (nostro).
  $tp = $null; $np = $null
  $mp = Select-String -Path $log -Pattern "dur\(p\) = ([\d\.]+) ms, #call p = (\d+)" | Select-Object -Last 1
  if ($mp) { $tp = [double]$mp.Matches[0].Groups[1].Value; $np = [double]$mp.Matches[0].Groups[2].Value }

  $v = if ($rip -le 2) { "SANO" } elseif ($rip -ge 8) { "DEGENERE" } else { "sospetto" }
  $ris += [pscustomobject]@{
    tag = $tag; v = $v; g5 = $rip
    genPerCall = [math]::Round($tg / $ndraft, 2)
    procPerCall = if ($np -gt 0) { [math]::Round($tp / $np, 2) } else { $null }
  }
}
"=== costo PER CHIAMATA, raggruppato per verdetto del testo ==="
$ris | Sort-Object v, genPerCall | ForEach-Object {
  "   {0,-26} {1,-9} 5gr={2,-5} gen/chiamata={3,-7} proc/chiamata={4}" -f $_.tag, $_.v, $_.g5, $_.genPerCall, $(if ($_.procPerCall) { $_.procPerCall } else { '-' })
}
""
foreach ($g in "SANO", "sospetto", "DEGENERE") {
  $sg = @($ris | Where-Object { $_.v -eq $g -and $_.genPerCall -gt 0 } | Select-Object -ExpandProperty genPerCall)
  $sp = @($ris | Where-Object { $_.v -eq $g -and $_.procPerCall -gt 0 } | Select-Object -ExpandProperty procPerCall)
  $mg = if ($sg.Count) { (@($sg | Sort-Object))[[math]::Floor($sg.Count/2)] } else { 'n/d' }
  $mp2 = if ($sp.Count) { (@($sp | Sort-Object))[[math]::Floor($sp.Count/2)] } else { 'n/d' }
  "{0,-10} gen/chiamata mediana={1,-8} (n={2})   proc/chiamata mediana={3,-8} (n={4})" -f $g, $mg, $sg.Count, $mp2, $sp.Count
}
