$ErrorActionPreference = 'Stop'
$scratch = 'C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\4b4c0194-0c4f-4f6b-8e2c-cb939d8d7daa\scratchpad'
$enc = [System.Text.Encoding]::GetEncoding(28591)   # ISO-8859-1: 1 byte = 1 char, biiettiva

# ---- carica i blocchi -------------------------------------------------------
$raw = [System.IO.File]::ReadAllText("$scratch\blocchi.txt", $enc) -replace "`r`n", "`n"
$sez = @{}
$nome = $null
$buf = New-Object System.Collections.Generic.List[string]
foreach ($riga in ($raw -split "`n")) {
    if ($riga -match '^#### ([A-Z0-9]+) ####$') {
        if ($nome) { $sez[$nome] = ($buf -join "`n") }
        $nome = $Matches[1]
        $buf = New-Object System.Collections.Generic.List[string]
    } elseif ($nome) {
        $buf.Add($riga)
    }
}
if ($nome) { $sez[$nome] = ($buf -join "`n") }
# ogni sezione termina con una riga vuota dovuta allo split: la sezione e' un
# blocco di righe COMPLETE, quindi deve finire con un terminatore.
foreach ($k in @($sez.Keys)) {
    $v = $sez[$k]
    if ($v.EndsWith("`n")) { } else { $v = $v + "`n" }
    # rimuove l'eventuale riga vuota finale in eccesso
    while ($v.EndsWith("`n`n")) { $v = $v.Substring(0, $v.Length - 1) }
    $sez[$k] = $v
}

# ---- tabella delle operazioni ----------------------------------------------
$ops = @(
    @{ f='cu';  a='A1';  b='B1';  m='INS' },
    @{ f='cu';  a='A2';  b='B2';  m='INS' },
    @{ f='cu';  a='A3';  b='B3';  m='INS' },
    @{ f='cu';  a='A4';  b='B4';  m='INS' },
    @{ f='cu';  a='A5';  b='B5';  m='INS' },
    @{ f='cu';  a='A6';  b='B6';  m='INS' },
    @{ f='cu';  a='A7';  b='B7';  m='INS' },
    @{ f='cu';  a='A8';  b='B8';  m='REP' },
    @{ f='cu';  a='A9';  b='B9';  m='INS' },
    @{ f='cu';  a='A10'; b='B10'; m='REP' },
    @{ f='cu';  a='A11'; b='B11'; m='INS' },
    @{ f='cu';  a='A12'; b='B12'; m='INS' },
    @{ f='cu';  a='A13'; b='B13'; m='INS' },
    @{ f='cu';  a='A14'; b='B14'; m='INS' },
    @{ f='cu';  a='A15'; b='B15'; m='REP' },
    @{ f='cu';  a='A16'; b='B16'; m='REP' },
    @{ f='cu';  a='A17'; b='B17'; m='REP' },
    @{ f='cu';  a='A18'; b='B18'; m='REP' },
    @{ f='cu';  a='A19'; b='B19'; m='INS' },
    @{ f='cuh'; a='A20'; b='B20'; m='INS' },
    @{ f='cuh'; a='A21'; b='B21'; m='REP' },
    @{ f='gg';  a='A22'; b='B22'; m='REP' },
    @{ f='gg';  a='A23'; b='B23'; m='REP' }
)

$percorsi = @{
    cu  = 'D:\llama-subtract\ggml\src\ggml-cuda\cache-esperti.cu'
    cuh = 'D:\llama-subtract\ggml\src\ggml-cuda\cache-esperti.cuh'
    gg  = 'D:\llama-subtract\ggml\src\ggml-cuda\ggml-cuda.cu'
}

function Conta([string]$hay, [string]$needle) {
    $n = 0; $i = 0
    while (($i = $hay.IndexOf($needle, $i, [System.StringComparison]::Ordinal)) -ge 0) { $n++; $i += 1 }
    return $n
}

$testi = @{}
foreach ($k in $percorsi.Keys) {
    $testi[$k] = $enc.GetString([System.IO.File]::ReadAllBytes($percorsi[$k]))
}

$errori = 0
foreach ($op in $ops) {
    $t = $testi[$op.f]
    $aLF = $sez[$op.a]
    $bLF = $sez[$op.b]
    if ($null -eq $aLF -or $null -eq $bLF) { Write-Host ("MANCA sezione {0}/{1}" -f $op.a, $op.b); $errori++; continue }
    $aCR = $aLF -replace "`n", "`r`n"
    $bCR = $bLF -replace "`n", "`r`n"
    $nCR = Conta $t $aCR
    $nLF = Conta $t $aLF
    # un'ancora LF puo' essere sottostringa di una CRLF solo se non contiene \n
    if ($aLF -eq $aCR) { $nLF = $nCR }
    $eol = $null
    if ($nCR -eq 1 -and ($nLF -eq 0 -or $aLF -eq $aCR)) { $eol = 'CRLF'; $anc = $aCR; $blo = $bCR }
    elseif ($nLF -eq 1 -and $nCR -eq 0) { $eol = 'LF'; $anc = $aLF; $blo = $bLF }
    if ($null -eq $eol) {
        Write-Host ("AMBIGUA/ASSENTE {0}: occorrenze CRLF={1} LF={2}" -f $op.a, $nCR, $nLF)
        $errori++
        continue
    }
    $nuovo = if ($op.m -eq 'INS') { $anc + $blo } else { $blo }
    $testi[$op.f] = $t.Replace($anc, $nuovo)
    $righe = ($blo -split "`n").Count - 1
    Write-Host ("OK  {0,-4} {1,-4} {2,-4} righe nuove={3}" -f $op.a, $op.f, $eol, $righe)
}

if ($errori -gt 0) { Write-Host "ERRORI: $errori -- NIENTE SCRITTO"; exit 1 }

foreach ($k in $percorsi.Keys) {
    [System.IO.File]::WriteAllBytes($percorsi[$k], $enc.GetBytes($testi[$k]))
}
Write-Host "scritti 3 file"
