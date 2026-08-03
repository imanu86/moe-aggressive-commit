# IL REGIME SUL BINARIO CORRENTE, E IL CANCELLO SULLE MODIFICHE AL CODICE
#
# Domanda dell'utente il 3/8: quanti t/s a regime con la configurazione di
# oggi? Risposta onesta: NIENTE di quello che e' stato fatto oggi migliora la
# configurazione migliore -- -cmoed e la riparazione di markov_w1 agiscono solo
# quando c'e' un draft, e col draft si perde. La configurazione buona resta
# quella del 2/8 sera:
#
#   -ngl 99 -ncmoe 42 -ub 64 -b 64   ->  regime 7,21 a ledger (LLAMA_fork_ub64)
#
# Ma quel 7,21 non e' piu' verificato, per due motivi:
#
#   1. IL BINARIO E' CAMBIATO DUE VOLTE. Il cancello DSPARK_NO_MARKOV (a68742a)
#      e la strumentazione DSPARK_PROF (236801b) sono entrambi spenti per
#      difetto, ma "spento per difetto" e' un'affermazione, non una misura.
#   2. I CONTROLLI DI OGGI BALLANO DEL 6% sulla stessa configurazione:
#      211,88 / 231,33 / 235,88 / 238,08 ms/token. Sono corse da 300 token,
#      dove la media cumulativa e' ancora dominata dal riscaldamento --
#      esattamente cio' contro cui esiste curva_run.py.
#
# Quindi: corsa LUNGA (1500 token, ctx 10000) per leggere il REGIME e non la
# media, su due bracci nello stesso momento:
#
#   A  fork corrente        D:\llama-dspark\build\bin\llama-server.exe  -ub 64
#   B  ufficiale b10227     D:\llama-b10227\llama-server.exe   (mai toccato)
#
# Il braccio B e' il cancello: l'ufficiale ha dato 7,18 e 7,37 di regime il
# 3/8 mattina. Se A resta appaiato a B, le due modifiche al codice sono
# gratis. Se A e' sotto, le ho pagate senza accorgermene.
#
# Il regime si legge dopo, con:
#   python docs/porto/curva_run.py <file .server.log>
# che prende la mediana di tg_3s nella finestra 500-800 token invece del
# numero finale cumulativo.

$ErrorActionPreference = 'Continue'
$BANCO = 'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\llama_confronto.ps1'
$out   = 'D:\ds4_work\llama_run\regime_dopo_codice.txt'
if (Test-Path $out) { Remove-Item $out -Force }

# la configurazione buona vuole anche questa: il run di riferimento del 2/8
# la impostava insieme a -ncmoe 42, e si riproduce identica.
$env:LLAMA_ARG_CPU_MOE = '1'

$bracci = @(
    @{ n='A_fork_corrente'; porta=8131
       exe='D:\llama-dspark\build\bin\llama-server.exe'
       extra=@('-ncmoe','42','-ub','64','-b','64') }

    @{ n='B_ufficiale_b10227'; porta=8132
       exe='D:\llama-b10227\llama-server.exe'
       extra=@('-ncmoe','42') }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    "exe:   $($b.exe)"                          | Out-File $out -Append -Encoding utf8
    "extra: $($b.extra -join ' ')"              | Out-File $out -Append -Encoding utf8

    $v0 = (nvidia-smi --query-gpu=memory.used --format=csv,noheader) 2>$null
    "VRAM prima: $v0 (base pulita ~750 MiB)" | Out-File $out -Append -Encoding utf8

    & $BANCO -Tokens 1500 -Ctx 10000 -Ngl 99 -Port $b.porta `
             -Exe $b.exe -Extra $b.extra -Etichetta $b.n `
             -Think $false -Temp 0 -Prompt 'campagna' 2>&1 |
        Out-File $out -Append -Encoding utf8

    # quiete fra i bracci: 20 s producono una tempesta di sfratti, 5 minuti
    # danno il run migliore (protocollo di igiene del 30/7)
    "--- quiete 300 s ---" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

'FINE' | Out-File $out -Append -Encoding utf8
