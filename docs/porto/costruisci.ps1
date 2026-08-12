# RICOSTRUZIONE DEL FORK, con il cancello sul PRODOTTO e non sull'exit code.
#
# Regola gia' pagata: "mai giudicare una build da un exit code passato
# attraverso un pipe -- cmake ... | tail restituisce l'exit di tail, e mi ha
# fatto riportare una build riuscita che non aveva ricompilato nulla.
# Si guarda l'SHA del prodotto."
#
# Percio' qui si prende l'impronta di OGNI dll prima e dopo, e alla fine si
# stampa quali sono davvero cambiate. Se non cambia niente, la build non ha
# fatto niente, qualunque cosa dica il codice di uscita.
#
# COSA C'E' DA COSTRUIRE OGGI (12/8, dopo il lavoro sul manifesto):
#   ggml/src/ggml-backend.cpp    us_dispatch + us_sched_sync (i due buchi)
#   tools/server/server.cpp      manifesto completo + gruppo orfane
#   tools/server/server-context.cpp   spec_replay, LLAMA_KV_RING
# NESSUN kernel CUDA e' cambiato: ggml-cuda.dll (207 MB) NON deve ricompilarsi.
# Se lo fa, qualcosa ha toccato un .cu e va capito prima di misurare.
#
# NIENTE CARATTERI NON-ASCII: PowerShell 5.1 legge il file in ANSI.
$ErrorActionPreference = 'Continue'
$BIN   = 'D:\llama-overlap\build\bin'
$BUILD = 'D:\llama-overlap\build'
$VCV   = 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
$REL   = 'D:\ds4_work\llama_run\costruisci.txt'
function Nota([string]$t) { ("[" + [DateTime]::Now.ToString('HH:mm:ss') + "] " + $t) | Tee-Object -FilePath $REL -Append }

function Impronte {
    $h = @{}
    Get-ChildItem $BIN -Filter *.dll -EA SilentlyContinue | ForEach-Object {
        $h[$_.Name] = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.Substring(0,12)
    }
    Get-ChildItem $BIN -Filter llama-server.exe -EA SilentlyContinue | ForEach-Object {
        $h[$_.Name] = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.Substring(0,12)
    }
    return $h
}

Nota "==================== COSTRUZIONE ===================="
Nota ("albero: " + (& git -C D:\llama-overlap rev-parse --short HEAD) + "  modifiche non committate:")
(& git -C D:\llama-overlap status --porcelain -- ggml/ src/ tools/) | ForEach-Object { Nota ("    " + $_) }

$prima = Impronte
Nota ("impronte prima: " + $prima.Count + " prodotti")

if (-not (Test-Path $VCV)) { Nota "*** vcvars64.bat non trovato: fermo ***"; exit 1 }
$t0 = Get-Date
# cmd perche' vcvars64 e' un .bat; niente pipe sull'exit code
& cmd /c "`"$VCV`" >nul 2>&1 && `"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe`" --build `"$BUILD`" --target llama-server 2>&1"
$uscita = $LASTEXITCODE
$durata = [math]::Round(((Get-Date)-$t0).TotalSeconds,1)
Nota ("cmake uscito con $uscita dopo $durata s  (l'exit code NON e' il cancello)")

$dopo = Impronte
$cambiati = @()
foreach ($k in $dopo.Keys) {
    if (-not $prima.ContainsKey($k)) { $cambiati += "$k  NUOVO -> $($dopo[$k])" }
    elseif ($prima[$k] -ne $dopo[$k]) { $cambiati += "$k  $($prima[$k]) -> $($dopo[$k])" }
}
Nota ""
Nota "--- PRODOTTI DAVVERO CAMBIATI ---"
if ($cambiati.Count -eq 0) {
    Nota "  NESSUNO. La build non ha prodotto niente: non misurare."
} else {
    foreach ($c in $cambiati) { Nota ("  " + $c) }
    if ($cambiati -match 'ggml-cuda\.dll') {
        Nota "  *** ATTENZIONE: ggml-cuda.dll e' cambiata. Nessun .cu doveva essere toccato:"
        Nota "      capire cosa l'ha mossa PRIMA di confrontare qualunque numero. ***"
    }
}
Nota ""
Nota "  Dopo questa build i numeri NON sono confrontabili con le corse precedenti."
Nota "  Il primo braccio da rifare e' il riferimento: dopo_il_riavvio.ps1 t512 512"
Nota "COSTRUZIONE FINITA"
