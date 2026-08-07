# CANCELLO DEL TESTO — strutturale, non disciplinare.
#
# STORIA, perche' la calibrazione non e' arbitraria (7/8/2026):
#  - un braccio catena (ovl_k2_CRONO) e' uscito DEGENERATO e i suoi numeri sono
#    stati adottati per un'ora prima che qualcuno guardasse il testo;
#  - la PRIMA versione di questo cancello contava righe uniche, e falliva su
#    DUE casi noti: il degenere puro (coda 'code','code','code' DENTRO una riga
#    -> 5 righe tutte uniche) e il ciclo a coda variabile (43 righe tutte
#    "uniche" perche' cambia l'ultima parola: 'label', 'header', 'footer'...).
#    Un cancello cieco sulla forma peggiore e' peggio di nessun cancello.
#
# Percio' la misura PRIMARIA e' il 5-gramma di token piu' ripetuto, che non
# dipende dagli a capo, e la secondaria e' il rapporto di token unici.
#
#   uso:  .\cancello_testo.ps1 -Path <file.resp.json | file_text.txt>
#
# Calibrazione sui bracci misurati:
#   SANO      5-gramma <= 2, token unici >= 0,50   (NOGRAPH 1/0,665; BINDSP 2/0,511)
#   DEGENERE  5-gramma >= 8                        (NOASYNC 8; RILEVATORE 10;
#                                                   CRONO 32; GRIGLIA 39; nmax1 375)
#   in mezzo: SOSPETTO, e il numero non si adotta senza guardare il testo.
param([Parameter(Mandatory=$true)][string]$Path)

if (-not (Test-Path $Path)) { "CANCELLO TESTO: FILE ASSENTE ($Path) -> NUMERO NON ADOTTABILE"; exit 2 }

if ($Path -like "*.json") {
  $txt = (Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json).content
} else {
  # I _text.txt di llama-cli contengono il BANNER ascii e l'eco del prompt.
  # Senza toglierli la misura li conta e restituisce lo STESSO valore per ogni
  # file (misurato: 5-gramma = 3 su 28 file diversi) -- cioe' non misura piu'
  # il testo generato. Trovato calibrando, prima di riportare i numeri.
  $txt = Get-Content $Path -Raw -Encoding UTF8
  $pf = Join-Path (Split-Path $Path -Parent) "jprompt.txt"
  if (Test-Path $pf) {
    $pr = (Get-Content $pf -Raw -Encoding UTF8).Trim()
    $coda = $pr.Substring([Math]::Max(0, $pr.Length - 40))
    $i = $txt.IndexOf($coda)
    if ($i -ge 0) { $txt = $txt.Substring($i + $coda.Length) }
  }
  $txt = ($txt -split "\[ Prompt:")[0]   # via il footer dei tempi
}
if ([string]::IsNullOrEmpty($txt)) { "CANCELLO TESTO: TESTO VUOTO -> NUMERO NON ADOTTABILE"; exit 2 }

$tok = $txt -split '\s+' | Where-Object { $_.Length -gt 0 }
if ($tok.Count -lt 50) { "CANCELLO TESTO: TROPPO CORTO ($($tok.Count) token) -> NON DECIDIBILE"; exit 2 }

$unici = ($tok | Select-Object -Unique).Count
$rapTok = $unici / $tok.Count

$g5 = New-Object System.Collections.Generic.List[string]
for ($i = 0; $i -lt ($tok.Count - 5); $i++) { $g5.Add(($tok[$i..($i+4)] -join ' ')) }
$rip = ($g5 | Group-Object | Sort-Object Count -Descending | Select-Object -First 1).Count

$righe  = $txt -split "`n"
$uniche = ($righe | Select-Object -Unique).Count

$verdetto = if ($rip -le 2 -and $rapTok -ge 0.45) { "SANO" }
            elseif ($rip -ge 8 -or $rapTok -le 0.20) { "DEGENERE -> NUMERI NON ADOTTABILI" }
            else { "SOSPETTO -> guardare il testo prima di adottare" }

"CANCELLO TESTO: 5-gramma-max=$rip token-unici=$([math]::Round($rapTok,3)) (righe=$($righe.Count) uniche=$uniche) -> $verdetto"
if ($verdetto -like "DEGENERE*") { exit 1 } elseif ($verdetto -like "SOSPETTO*") { exit 3 } else { exit 0 }
