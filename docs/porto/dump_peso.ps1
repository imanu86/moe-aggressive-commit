# DUMP DEGLI ID E DEI PESI DEL ROUTER, per rispondere a una domanda sola:
#
#   il PESO con cui il router sceglie un esperto predice che lo riscegliera'?
#
# PERCHE'. Il 12/8 abbiamo acceso l'anticipo (DMA=1 + W>0) e i colpi non si sono
# mossi di un punto: 54,8-55,7% contro 54,9% del controllo, con il 25% delle
# prenotazioni arrivate in ritardo. Il meccanismo entra, la previsione non vale.
# Ed e' coerente con l'archivio: "il predittivo da finestra passata e' piatto a
# 44-47% da W=2 a W=100" -- il passato non predice, la sovrapposizione RUOTA.
#
# L'IDEA DELL'UTENTE, che e' diversa e non e' mai stata provata: non predire
# CHI servira', ma decidere CHI TENERE. Un esperto scelto con peso alto
# difficilmente viene scartato dal router al token dopo; i freddi sono quelli
# che devono circolare. E' una politica di RESIDENZA, non di previsione: essere
# sbagliati al 30% costa poco, mentre una previsione sbagliata al 30% costa
# banda.
#
# ATTENZIONE ALLA DIFFERENZA CON `massa`, che esiste gia' ed e' data per
# perdente: `massa` conta le BUSSATE (frequenza, con decadimento >>= 1 a
# :1858), cioe' il passato. Il peso del gate e' un'altra grandezza, e la cache
# oggi non lo riceve nemmeno -- tutte le firme sono `const int32_t * ids`.
#
# QUESTO SCRIPT NON CAMBIA NESSUNA POLITICA: registra e basta. La misura si fa
# offline, e solo se il segnale c'e' si scrive del codice.
#
# Il server non sa dumpare (cb_eval arriva solo da params.cb_eval): serve
# llama-eval-callback, come faceva docs/porto/oracolo_pista.py.
$ErrorActionPreference = 'Continue'
$bin = 'D:\llama-overlap\build\bin\llama-eval-callback.exe'
$out = 'D:\ds4_work\dump_peso'
$rel = 'D:\ds4_work\llama_run\dump_peso.txt'
function Nota([string]$t) { ("[" + [DateTime]::Now.ToString('HH:mm:ss') + "] " + $t) | Tee-Object -FilePath $rel -Append }

if (Test-Path $out) { Remove-Item $out -Recurse -Force -EA SilentlyContinue }
New-Item -ItemType Directory -Path $out -Force | Out-Null

$env:LLAMA_DEBUG_DUMP = $out
# ffn_moe_topk    = gli id scelti           [6, n_token] I32
# ffn_moe_weights = il peso del router      (e weights_norm, quello applicato)
$env:LLAMA_DEBUG_FILTER = 'ffn_moe_(topk|weights)'
# niente cache e niente lane: la domanda riguarda il ROUTER, non la residenza
[Environment]::SetEnvironmentVariable('LLAMA_CACHE_ESPERTI_SLOT', $null)
[Environment]::SetEnvironmentVariable('LLAMA_MAPPED_IBRIDO', $null)
[Environment]::SetEnvironmentVariable('LLAMA_OVERLAP_ASYNC', $null)
$env:LLAMA_DSV4_HC_FUSO = '5'

$msg = [IO.File]::ReadAllText('D:\ds4_work\llama_run\jprompt.txt', [Text.Encoding]::UTF8)
Nota "avvio del dump: 150 token, temperatura 0"
# --fit off: senza, common_fit_params aborta perche' -ngl 99 e' gia' imposto
# dall'utente. E' lo stesso flag che usa il banco.
# -f invece di -p: Start-Process unisce l'ArgumentList con spazi SENZA citare,
# quindi un prompt con spazi diventa dieci argomenti e il binario risponde
# "invalid argument: una".
$a = @('-m', 'C:/ds4-models/DS4-0731-IQ2XXS.gguf', '--fit', 'off',
       '-f', 'D:/ds4_work/llama_run/jprompt.txt', '-n', '150', '-c', '2048', '-ngl', '99',
       '-ot', 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped',
       '-t', '7', '--no-mmap', '--temp', '0')
$t0 = Get-Date
# Start-Process con redirezione: `*>` fa trattare a PowerShell 5.1 ogni riga di
# stderr come un errore terminante, e il processo sembra fallito anche quando
# sta solo stampando avvisi.
$p = Start-Process -FilePath $bin -ArgumentList $a -PassThru -NoNewWindow -Wait `
     -RedirectStandardError 'D:\ds4_work\llama_run\dump_peso.log' `
     -RedirectStandardOutput 'D:\ds4_work\llama_run\dump_peso.out'
Nota ("finito in " + [math]::Round(((Get-Date)-$t0).TotalSeconds,1) + " s, uscita " + $p.ExitCode)

$f = @(Get-ChildItem $out -Filter *.bin -EA SilentlyContinue)
Nota ("file prodotti: " + $f.Count)
if ($f.Count -gt 0) {
    Nota "esempi:"
    $f | Select-Object -First 4 | ForEach-Object { Nota ("   " + $_.Name + "  " + $_.Length + " byte") }
    $n = @($f | Group-Object { ($_.Name -split '-')[0] } | Select-Object Name, Count)
    foreach ($g in $n) { Nota ("   " + $g.Name + ": " + $g.Count + " file") }
} else {
    Nota "*** NESSUN FILE: il dump non e' partito, guardare dump_peso.log ***"
}
Nota "DUMP FINITO"
