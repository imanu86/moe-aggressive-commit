# DSpark su llama.cpp: il test rapido.
#
# Il numero che decide non e' t/s, e' l'ACCETTAZIONE. Dal model card di
# YanissAmz, misurato su Strix Halo:
#     0,72 -> +17%      0,90 -> +79%      1,00 -> +91%
#     a 176k di contesto crolla a 0,54 ed e' perdita netta
# Il nostro banco (prompt 43 token, pagina HTML lunga) e' il regime buono.
#
# Salta la quantizzazione: se l'accettazione col BF16 e' bassa, quantizzare non
# la salva. Prima il verdetto, poi l'ottimizzazione della collocazione.
param(
    [int]$Tokens = 800,
    [int]$Ctx    = 10000,
    [int]$Port   = 8096,
    [ValidateSet('cpu','gpu','moecpu','fit','draftcpu','zerocopy')][string]$Dove = 'zerocopy',
    [int]$NMax   = 5,            # block size del draft: 5, clampato dal modello
    [string]$Exe   = 'D:\llama-dspark\build\bin\llama-server.exe',
    [string]$Model = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf',
    [string]$Draft = 'C:\ds4-models\DSV4-Flash-DSpark-draft-bf16.gguf',
    [string]$OutDir = 'D:\ds4_work\dspark'
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
foreach ($f in @($Exe, $Model, $Draft)) {
    if (-not (Test-Path $f)) { Write-Host "  MANCA: $f"; return }
}
$tag = "DSPARK_{0}_{1}" -f $Dove, (Get-Date -Format 'HHmmss')
$log = Join-Path $OutDir "$tag.log"

# stesso prompt della campagna: i numeri restano confrontabili con tutto il resto
$prompt = 'Create a complete single-file HTML landing page for a cyberpunk AI programming shop. Include CSS, navigation, hero, request form, and a JavaScript confirmation popup. Return only the HTML document.'

$env:LLAMA_ARG_CPU_MOE = '1'          # gli esperti del TARGET su CPU, come nel banco
$a = @('-m',$Model,'-md',$Draft,'--spec-type','draft-dspark',
       '--spec-draft-n-max',"$NMax",'-c',"$Ctx",'-fa','on','--jinja',
       '--port',"$Port",'--host','127.0.0.1','--no-warmup')
switch ($Dove) {
    # --fit e' l'adattatore automatico: colloca target e draft nella memoria
    # disponibile. Forzare -ngl 99 lo ABORTISCE ("n_gpu_layers already set by
    # user to 99, abort") ed e' l'errore che ha fatto fallire i primi due
    # tentativi del 2/8. Con due modelli che si dividono 12 GB serve lui.
    # draftcpu: target come nel banco (-ngl 99, esperti su CPU), draft INTERO su
    # CPU con -ngld 0. E' la combinazione mai provata: da solo con ngl 0 il draft
    # SI CARICA, quindi il subscript esplode nello split GPU del draft MoE.
    'draftcpu' { $a += @('-ngl','99','-ngld','0') }
    # zerocopy (proposta utente): il draft resta in RAM ma lo LEGGE LA GPU.
    # -otd manda gli esperti del draft in CUDA_Host = memoria pinnata mappata,
    # i kernel girano su GPU leggendo via PCIe -- che in llama.cpp e' FERMO.
    # Cosi' il draft smette di contendere la CPU al target (la causa del 3,19).
    # E il percorso dello split GPU che crashava non si tocca proprio.
    # Costo: ~10 GB pinnati non paginabili col draft MXFP4 com'e'.
    # -ngld 99 + qualunque opzione crasha (subscript: sospetto target_layers[41..43]
    # usati per indicizzare un vettore da 3 nel percorso GPU del draft). Con -ngld 0
    # il caricamento PASSA: gli strati restano alla CPU ma gli esperti vanno in
    # CUDA_Host, che il backend CUDA sa leggere -> zerocopy senza il percorso rotto.
    'zerocopy' { $a += @('-ngl','99','-ngld','0','-otd','.ffn_.*_exps.=CUDA_Host') }
    'fit'    { $a += @('--fit','on') }
    'cpu'    { $a += @('-ngl','99','-devd','none') }   # FALLISCE: output.weight resta su CUDA0
    'moecpu' { $a += @('-ngl','99','-cmoed') }         # FALLISCE: invalid vector subscript
    'gpu'    { $a += @('-ngl','99') }
}
Write-Host "  draft: $Dove   n-max: $NMax   ctx: $Ctx"
$srv = Start-Process -FilePath $Exe -ArgumentList $a -PassThru -NoNewWindow `
        -RedirectStandardError $log -RedirectStandardOutput "$log.out"
try {
    $pronto = $false
    for ($i=0; $i -lt 300; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) {
            Write-Host "  uscito (exit $($srv.ExitCode)). Ultime righe:"
            Get-Content $log -Tail 8 | ForEach-Object { Write-Host "    $_" }
            return
        }
        try { Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 3 -EA Stop | Out-Null
              $pronto = $true; break } catch { }
    }
    if (-not $pronto) { Write-Host "  non pronto dopo 25 min"; return }
    Write-Host "  pronto dopo $($i*5)s"

    $body = @{ model='ds4'; max_tokens=$Tokens; temperature=0; stream=$false
               messages=@(@{role='user'; content=$prompt}) } | ConvertTo-Json -Depth 5
    $req = Join-Path $OutDir "$tag.request.json"
    [IO.File]::WriteAllText($req, $body, [Text.UTF8Encoding]::new($false))
    $t0 = Get-Date
    & curl.exe -sS --max-time 7200 -X POST "http://127.0.0.1:$Port/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" `
        -o (Join-Path $OutDir "$tag.response.json")
    $sec = ((Get-Date)-$t0).TotalSeconds
    # -Encoding UTF8: senza, PS 5.1 legge in ANSI e storpia i multibyte (2/8)
    $r = Get-Content (Join-Path $OutDir "$tag.response.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host ""
    Write-Host "  END2END  $([math]::Round($r.usage.completion_tokens/$sec,3)) t/s   ($($r.usage.completion_tokens) token)"
    # IL numero: accettazione e statistiche della speculativa
    Select-String -LiteralPath $log -Pattern 'accept|draft|spec' -AllMatches |
        Select-Object -Last 8 | ForEach-Object { Write-Host "  $($_.Line.Trim())" }
    Select-String -LiteralPath $log -Pattern 'eval time' -AllMatches |
        ForEach-Object { Write-Host "  $($_.Line.Trim())" }
} finally {
    if (-not $srv.HasExited) { Stop-Process -Id $srv.Id -EA SilentlyContinue }
    Start-Sleep -Seconds 5
    Write-Host "  VRAM dopo: $((nvidia-smi --query-gpu=memory.used --format=csv,noheader) 2>$null)   (base ~750 MiB)"
}
