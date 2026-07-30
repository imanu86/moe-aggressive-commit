# CANCELLO DELLE LEVE -- rifiuta di partire se il manifest contraddice un verdetto
# gia' documentato.
#
# PERCHE' ESISTE (30/7). Sei volte in cinque giorni ho ottimizzato una leva contro
# un verdetto scritto: G73_OPEN (25/7), chunk256 (25/7), maschere (27/7),
# trasporto (27/7), il turno 2 (30/7), l'invalidate su miss fallito (30/7). In tre
# casi su sei un AGENTE con il documento nel mandato aveva deciso giusto: il collo
# non e' il corpus, e' il momento della consultazione. Quindi non serve ricordarsi
# di guardare: serve non poter partire senza aver guardato. Stesso schema con cui
# preflight_clean si rifiuta di misurare su macchina sporca.
#
# Uso:
#   powershell -File cancello_leve.ps1 -Manifest <file>            # verifica
#   powershell -File cancello_leve.ps1 -Manifest <file> -Fondi     # rigenera l'indice e verifica
#
# Exit code: 0 = si puo' partire; 2 = leve bloccate senza riconoscimento;
#            3 = indice assente o illeggibile.
#
# RICONOSCIMENTO: per usare deliberatamente una leva con verdetto negativo, il
# manifest deve contenere una riga di riconoscimento esplicita:
#   # RICONOSCIUTO: DS4_X -- <perche' la si usa comunque>
# Non e' burocrazia: e' la differenza fra una scelta e una dimenticanza, e finisce
# nel log del run.
#
# ASCII ONLY: PowerShell 5.1 legge i .ps1 come ANSI e un carattere non-ASCII
# rompe il parsing (mi e' costato tre tentativi il 29/7).

param(
    [Parameter(Mandatory=$true)][string]$Manifest,
    [switch]$Fondi,
    [string]$Indice = "C:\Users\imanu\source\repos\moe-aggressive-commit\.microbench\leve_stato\LEVE_STATO.tsv"
)

$SRC = "C:\Users\imanu\source\repos\moe-aggressive-commit\.microbench\leve_stato"

# --- stati che BLOCCANO: la leva e' documentata come inutile, morta o contesa ---
$BLOCCANTI = @{
    "FALS"        = "falsificata con un numero"
    "MORTA-COSTR" = "irraggiungibile per costruzione in questa config"
    "INERTE"      = "nessun effetto nel regime misurato"
    "CONTESA"     = "due fonti in conflitto: risolvi prima di misurare"
}
# SPORCA non blocca: significa 'il segno regge, la grandezza no'. Avvisa.

function Fondi-Indice {
    $out = @()
    $visti = @{}
    foreach ($f in @("PARTE_A.tsv","PARTE_B.tsv")) {
        $p = Join-Path $SRC $f
        if (-not (Test-Path $p)) { continue }
        # -Encoding UTF8: gli agenti scrivono UTF-8 e PS 5.1 altrimenti legge ANSI,
        # trasformando le frecce in mojibake dentro l'indice.
        $righe = Get-Content $p -Encoding UTF8
        foreach ($r in $righe) {
            if ($r.Trim() -eq "") { continue }
            if ($r -like "leva`tstato*") { continue }
            $campi = $r -split "`t"
            $nome = $campi[0].Trim()
            if ($nome -eq "") { continue }
            # Deduplica: fra due righe per la stessa leva tiene quella con piu'
            # campi compilati (piu' informazione), non la prima incontrata.
            $peso = ($campi | Where-Object { $_.Trim() -ne "" }).Count
            if ($visti.ContainsKey($nome)) {
                if ($peso -gt $visti[$nome].Peso) { $visti[$nome] = @{ Riga=$r; Peso=$peso } }
            } else {
                $visti[$nome] = @{ Riga=$r; Peso=$peso }
            }
        }
    }
    $out += "leva`tstato`tvalore_attivo`tnumero`trun_prova`tdata`tprova`tnota"
    $out += ($visti.Keys | Sort-Object | ForEach-Object { $visti[$_].Riga })
    Set-Content -Path $Indice -Value $out -Encoding utf8
    "[cancello] indice fuso: {0} leve -> {1}" -f $visti.Count, $Indice
}

if ($Fondi) { Fondi-Indice }

if (-not (Test-Path $Indice)) {
    "[cancello] INDICE ASSENTE: $Indice"
    "[cancello] rigeneralo con -Fondi (serve PARTE_A.tsv e PARTE_B.tsv in $SRC)"
    exit 3
}
if (-not (Test-Path $Manifest)) { "[cancello] MANIFEST ASSENTE: $Manifest"; exit 3 }

# --- carica l'indice ---
$idx = @{}
foreach ($r in (Get-Content $Indice | Select-Object -Skip 1)) {
    if ($r.Trim() -eq "") { continue }
    $c = $r -split "`t"
    $idx[$c[0].Trim()] = [pscustomobject]@{
        Stato = if ($c.Count -gt 1) { $c[1].Trim() } else { "" }
        Numero = if ($c.Count -gt 3) { $c[3].Trim() } else { "" }
        Prova  = if ($c.Count -gt 6) { $c[6].Trim() } else { "" }
        Nota   = if ($c.Count -gt 7) { $c[7].Trim() } else { "" }
    }
}

# --- estrai le leve dal manifest e i riconoscimenti ---
$testo = Get-Content $Manifest
$impostate = @{}
$riconosciute = @{}
foreach ($r in $testo) {
    if ($r -match '^\s*#\s*RICONOSCIUTO:\s*(DS4_[A-Z0-9_]+)') { $riconosciute[$matches[1]] = $true; continue }
    # righe tipo "DS4_X=valore", "DS4_X = valore", "export DS4_X=valore", "$env:DS4_X='v'"
    if ($r -match '(DS4_[A-Z0-9_]+)\s*=\s*(.*)$') {
        $v = $matches[2].Trim().Trim('"').Trim("'")
        $impostate[$matches[1]] = $v
    }
}

"[cancello] manifest: $Manifest"
"[cancello] indice:   $Indice ($($idx.Count) leve)"
"[cancello] leve DS4_* impostate: $($impostate.Count) | riconoscimenti espliciti: $($riconosciute.Count)"
""

$bloccate = @()
$avvisi = @()
$ignote = @()

foreach ($k in ($impostate.Keys | Sort-Object)) {
    if (-not $idx.ContainsKey($k)) { $ignote += $k; continue }
    $e = $idx[$k]
    if ($BLOCCANTI.ContainsKey($e.Stato)) {
        if ($riconosciute.ContainsKey($k)) {
            $avvisi += "  RICONOSCIUTA  {0,-46} [{1}] {2}" -f $k, $e.Stato, $e.Numero
        } else {
            $bloccate += [pscustomobject]@{ Leva=$k; Valore=$impostate[$k]; Stato=$e.Stato; Numero=$e.Numero; Prova=$e.Prova; Nota=$e.Nota }
        }
    } elseif ($e.Stato -eq "SPORCA") {
        $avvisi += "  SPORCA        {0,-46} grandezza non isolata: {1}" -f $k, $e.Nota
    }
}

if ($avvisi.Count -gt 0) { "[cancello] AVVISI (non bloccano):"; $avvisi | ForEach-Object { $_ }; "" }
if ($ignote.Count -gt 0) {
    "[cancello] LEVE NON NELL'INDICE ($($ignote.Count)) -- se ne stai provando una nuova, aggiungila all'indice DOPO il run:"
    $ignote | ForEach-Object { "  ignota       $_" }
    ""
}

if ($bloccate.Count -eq 0) {
    "[cancello] OK: nessuna leva del manifest contraddice un verdetto documentato."
    exit 0
}

"[cancello] *** BLOCCATO: $($bloccate.Count) leve hanno un verdetto documentato e nessun riconoscimento ***"
""
foreach ($b in $bloccate) {
    "  {0} = {1}" -f $b.Leva, $b.Valore
    "     stato:  {0} ({1})" -f $b.Stato, $BLOCCANTI[$b.Stato]
    if ($b.Numero) { "     numero: {0}" -f $b.Numero }
    if ($b.Prova)  { "     prova:  {0}" -f $b.Prova }
    if ($b.Nota)   { "     nota:   {0}" -f $b.Nota }
    ""
}
"[cancello] Per procedere comunque, aggiungi al manifest una riga per ciascuna:"
foreach ($b in $bloccate) { "  # RICONOSCIUTO: {0} -- <perche' la usi comunque>" -f $b.Leva }
exit 2
