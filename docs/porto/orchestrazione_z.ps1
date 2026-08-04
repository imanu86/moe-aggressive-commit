# ORCHESTRAZIONE: i thread e la speculazione GRATIS
#
# Il conto che ha motivato questo run (4/8, pomeriggio):
#
#   byte letti per token        1,70 GiB   (258 attivazioni x 6,76 MiB)
#   banda aggregata usata       10,8 GiB/s
#   di cui dalla RAM             6,6 GB/s  su ~40 disponibili = 16%
#
# Non e' trasporto. E non e' nemmeno "le macchine hanno margine": CPU e GPU
# stanno al 50% A TURNO, perche' dentro un token i 43 strati sono una catena
# seriale e a ogni strato la GPU aspetta i sei esperti della CPU e viceversa.
# Sommate fanno il 100% di UNA macchina, ed e' il throughput che vediamo.
#
# Da li' due leve, quelle scelte dall'utente (la terza, quantizzazione mista,
# e' stata scartata da lui).
#
# LEVA 1 -- I THREAD. n_threads = -1 significa auto, che su AMD prende i core
# FISICI: 8 su 16. Se la fase CPU e' il palo lungo, i it 8 thread SMT non usati
# sono lavoro gratis. Puo' anche PEGGIORARE: su matmul quantizzata memory-bound
# l'SMT spesso litiga sulle stesse cache L2. Mai provato, costa un braccio.
#
# LEVA 2 -- LA SPECULAZIONE GRATIS. I 43 rendezvous si pagano per PASSAGGIO IN
# AVANTI, non per token: verificarne N insieme li ammortizza per N. Il fork ha
# cinque speculatori n-gram gia' dentro, che NON hanno pesi e NON fanno
# passaggi in avanti -- copiano dal testo gia' generato. Su HTML, dove la
# struttura si ripete, e' il caso migliore possibile.
#
# E su MoE c'e' un secondo guadagno che DSpark non poteva avere: verificando N
# token insieme gli esperti si SOVRAPPONGONO (misurato: il 90,3% degli accessi
# sono riletture), quindi scendono anche i byte per token.
#
# Perche' questo non e' DSpark rifatto: DSpark perdeva perche' il drafter e' un
# modello da 19,85 miliardi di parametri con il suo MoE, e costava piu' di
# quanto risparmiasse. Qui il drafter costa circa zero. Economia opposta.
#
# IL CAPPIO SUL DRAFT: size_m di default e' 48 token proposti. Su questo
# modello 48 token in una passata attivano troppi esperti distinti e la RAM non
# regge. Capato a 8 con --spec-draft-n-max, e -ub 64 cosi' la verifica entra in
# UNA ubatch (se il draft non ci sta, l'ammortamento non avviene ed e' come non
# averla fatta).
#
# ORDINE DEI BRACCI: le TESI PER PRIME, sulla macchina appena riavviata, e il
# RIFERIMENTO PER ULTIMO con la cache piu' calda di tutti. Cosi' l'ordine
# lavora CONTRO cio' che voglio dimostrare. Il contrario -- riferimento per
# primo e freddo -- gonfierebbe le tesi, ed e' l'errore gia' fatto due volte
# oggi.
#
# CONFIGURAZIONE DI BASE: 17 strati mappati, che e' il SOTA misurato due volte
# (6,37 con -ub 64 il 4/8 mattina, 6,35 con -ub 32 il 4/8 pomeriggio: 0,3% di
# scarto, la config piu' riproducibile della campagna). NIENTE strato in VRAM:
# Y1 lo ha falsificato, costa il 12%.

$ErrorActionPreference = 'Continue'
$out  = 'D:\ds4_work\llama_run\orchz.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$camp = 'D:\ds4_work\llama_run\orchz_camp.tsv'
"ora`tbraccio`tpage_reads`tram_disp_MB`tvram_MB`tgpu_pct`twatt" | Out-File $camp -Encoding utf8

$MODELLO = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$EXE     = 'D:\llama-dspark\build\bin\llama-server.exe'
$req     = 'D:\ds4_work\llama_run\neuraforge8k.req.json'

Add-Type -Namespace '' -Name CVP -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

$ESP = 'ffn_(gate|up|down)_exps\.weight'
$OT  = "blk\.([0-9]|1[0-6])\.$ESP=CUDA0_Mapped,$ESP=CPU"

$bracci = @(
    @{ n='Z2_ngram_cache'; porta=8281; extra=@('--spec-type','ngram-cache','--spec-draft-n-max','8') }
    @{ n='Z3_ngram_k4v';   porta=8282; extra=@('--spec-type','ngram-map-k4v','--spec-draft-n-max','8') }
    @{ n='Z1_thread16';    porta=8283; extra=@('-t','16') }
    @{ n='Z0_riferimento'; porta=8284; extra=@() }
)

foreach ($b in $bracci) {
    "=============== $($b.n) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\LLAMA_$($b.n).server.log"
    "extra: $($b.extra -join ' ')   $(Get-Date -Format 'HH:mm:ss')" | Out-File $out -Append -Encoding utf8

    Remove-Item Env:LLAMA_ARG_CPU_MOE -EA SilentlyContinue
    $env:LLAMA_REAP             = '1'
    $env:LLAMA_REAP_PROF        = '1'
    $env:LLAMA_REAP_LOCK        = '1'
    $env:LLAMA_REAP_TOPK        = '1200'
    $env:LLAMA_REAP_PESO        = 'ripida'
    $env:LLAMA_REAP_DECADIMENTO = '1.0'
    Remove-Item Env:LLAMA_REAP_AMMISSIONE -EA SilentlyContinue
    Remove-Item Env:LLAMA_REAP_PREFETCH   -EA SilentlyContinue

    $argomenti = @('-m', $MODELLO, '-c','10000', '-ngl','99', '-ot', $OT,
                   '-ub','64', '-b','64', '--port', "$($b.porta)", '--host','127.0.0.1',
                   '--no-warmup', '--reasoning-budget','0') + $b.extra

    $srv = Start-Process -FilePath $EXE -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    Start-Sleep -Milliseconds 700
    if ($srv.HasExited) {
        "IL SERVER E' MORTO SUBITO (argomento rifiutato?) -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 20 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        continue
    }

    $pronto = $false
    for ($i = 0; $i -lt 300; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if (-not $pronto) {
        "IL SERVER NON E' PARTITO -- ultime righe:" | Out-File $out -Append -Encoding utf8
        if (Test-Path $log) { Get-Content $log -Tail 25 -Encoding UTF8 | Out-File $out -Append -Encoding utf8 }
        continue
    }

    # quanti thread ha deciso di usare: la risposta alla leva 1 sta nel log
    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'n_threads|system_info' |
            Select-Object -First 2 | ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Out-File $out -Append -Encoding utf8
    }

    $c = Start-Process -FilePath 'curl.exe' -PassThru -NoNewWindow -ArgumentList @(
            '-sS','--max-time','14400','-X','POST',
            "http://127.0.0.1:$($b.porta)/v1/chat/completions",
            '-H','Content-Type: application/json',
            '--data-binary', "@$req", '-o', "D:\ds4_work\llama_run\oz_$($b.n).resp.json")

    while (-not $c.HasExited) {
        Start-Sleep -Seconds 15
        $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
        $g = (nvidia-smi --query-gpu=memory.used,utilization.gpu,power.draw --format=csv,noheader,nounits) 2>$null
        "{0}`t{1}`t{2}`t{3}`t{4}" -f (Get-Date -Format 'HH:mm:ss'), $b.n,
            $m.PageReadsPerSec, $m.AvailableMBytes, ($g -replace ',\s*', "`t") | Out-File $camp -Append -Encoding utf8
    }

    if (-not $srv.HasExited) {
        [void][CVP]::FreeConsole()
        if ([CVP]::AttachConsole([uint32]$srv.Id)) {
            [void][CVP]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
            [void][CVP]::GenerateConsoleCtrlEvent(0, 0)
            Start-Sleep -Seconds 15
            [void][CVP]::FreeConsole(); [void][CVP]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
        }
        $srv.WaitForExit(120000) | Out-Null
    }

    # 'draft acceptance rate' e' la riga che dice se la speculazione ha agganciato:
    # senza quella un guadagno o una perdita non sono attribuibili
    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'eval time =|draft|accept|reap: politica|n_threads' |
            ForEach-Object { $_.Line -replace '^[0-9.]+ +[A-Z] +','' } |
            Select-Object -Last 12 | Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 300
}

Remove-Item Env:LLAMA_REAP_LOCK -EA SilentlyContinue
'FINE' | Out-File $out -Append -Encoding utf8
