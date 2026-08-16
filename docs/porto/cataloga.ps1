# Cataloga un run a posteriori, dal solo log del server.
# Serve quando l'harness muore prima di scrivere meta+ledger: il log resta,
# e da quello si ricostruisce tutto tranne il testo generato.
#   .\cataloga.ps1 -Log D:\ds4_work\porto_run\C_234337.server.log [-Nota "interrotto"]
param(
    [Parameter(Mandatory)][string]$Log,
    [string]$Nota = ''
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Log)) { throw "log assente: $Log" }
$dir = Split-Path $Log -Parent
$tag = (Split-Path $Log -Leaf) -replace '\.server\.log$',''
$txt = Get-Content -LiteralPath $Log -Raw

function Ultimo([string]$pattern, [int]$grp = 1) {
    $m = [regex]::Matches($txt, $pattern)
    if ($m.Count) { $m[$m.Count-1].Groups[$grp].Value } else { $null }
}

$chunks = @([regex]::Matches($txt, 'gen=(\d+) .*?chunk=([0-9.]+)') |
    Where-Object { [int]$_.Groups[1].Value -gt 300 } |
    ForEach-Object { [double]$_.Groups[2].Value } | Sort-Object)
# BUG CORRETTO (16/8): $chunks[[int]($chunks.Count/2)] col banker's rounding cadeva un passo sopra il centro per Count dispari 3,7,11,... (con Count=3 era il MASSIMO); v. RUNBOOK par. 7.4
$regime = if ($chunks.Count) { $chunks[[math]::Floor(($chunks.Count-1)/2)] } else { $null }
$gen    = Ultimo 'gen=(\d+) .*?chunk='
$avg    = Ultimo 'avg=([0-9.]+) t/s'
$wall   = Ultimo 'avg=[0-9.]+ t/s ([0-9.]+)s'
$evict  = @([regex]::Matches($txt,'evict_backbone=(\d+)') | ForEach-Object { [int]$_.Groups[1].Value } |
            Measure-Object -Maximum).Maximum

# l'output. Se l'harness non e' arrivato a scriverlo ma lo stream e' su disco,
# lo si ricostruisce dai delta: e' il motivo per cui la richiesta va in streaming.
$htmlPath   = Join-Path $dir "$tag.output.html"
$streamPath = Join-Path $dir "$tag.stream.ndjson"
if ((-not (Test-Path $htmlPath)) -and (Test-Path $streamPath)) {
    # Il modello emette DUE flussi: reasoning_content (la fase THINKING) e content
    # (la risposta). Vanno tenuti separati: il cancello di neutralita' si verifica
    # sulla risposta, ma il ragionamento e' quello che consuma i token e va contato.
    $sbR = [Text.StringBuilder]::new(); $sbC = [Text.StringBuilder]::new()
    foreach ($line in [IO.File]::ReadLines($streamPath)) {
        if (-not $line.StartsWith('data: ')) { continue }
        $payload = $line.Substring(6)
        if ($payload -eq '[DONE]') { continue }
        try { $o = $payload | ConvertFrom-Json } catch { continue }
        $d = $o.choices[0].delta
        if ($d.reasoning_content) { [void]$sbR.Append([string]$d.reasoning_content) }
        if ($d.content)           { [void]$sbC.Append([string]$d.content) }
    }
    if ($sbR.Length -gt 0) {
        [IO.File]::WriteAllText((Join-Path $dir "$tag.thinking.txt"), $sbR.ToString(), [Text.UTF8Encoding]::new($false))
        "  ragionamento ricostruito: {0:N0} caratteri" -f $sbR.Length
    }
    if ($sbC.Length -gt 0) {
        [IO.File]::WriteAllText($htmlPath, $sbC.ToString(), [Text.UTF8Encoding]::new($false))
        "  output RICOSTRUITO dallo stream: {0:N0} caratteri" -f $sbC.Length
    } else {
        "  nessun 'content': il run si e' fermato in fase THINKING, pagina mai iniziata"
    }
}
$hasHtml  = (Test-Path $htmlPath) -and ((Get-Item $htmlPath).Length -gt 0)
$sha = if ($hasHtml) {
    [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash(
        [IO.File]::ReadAllBytes($htmlPath))).Replace('-','').ToLower()
} else { 'PERSO' }

$meta = [ordered]@{
    id = $tag; catalogato_a_posteriori = $true; nota = $Nota
    log = $Log; output_html = $(if ($hasHtml) { $htmlPath } else { $null })
    output_sha256 = $sha
    tokens_generated = $gen; seconds = $wall
    end2end_tps = $(if ($gen -and $wall) { [math]::Round([double]$gen/[double]$wall,3) })
    dec_avg_tps = $avg; regime_tps = $regime; regime_n = $chunks.Count
    evict_backbone = $evict
    no_expert_victim = ([regex]::Matches($txt,'no-expert-victim')).Count
    expert_cache_capacity = (Ultimo 'result=sized requested=\d+ capacity=(\d+)')
    free_at_size_mib = (Ultimo 'free_at_size_mib=([0-9.]+)')
    arena_pinned_gib = (Ultimo 'mapped-pinned=([0-9.]+) GiB')
    arena_slots = (Ultimo 'mapped-pinned=[0-9.]+ GiB slots=(\d+)')
    arena_resident = (Ultimo 'snapshot=\d+ resident=(\d+)')
    ricarichi_modello = ([regex]::Matches($txt,'CUDA loading model tensors ')).Count
    prefill_chunk = (Ultimo 'prefill_chunk=(\d+)')
    ctx = (Ultimo 'context buffers [0-9.]+ MiB \(ctx=(\d+)')
}
$metaPath = Join-Path $dir "$tag.meta.json"
$meta | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $metaPath -Encoding UTF8

$ledger = Join-Path $dir 'LEDGER_RUN.tsv'
if (-not (Test-Path $ledger)) {
    "id`tdata`tbraccio`tmodello`tctx`ttoken`tEND2END`tREGIME`tn`tcapacity`tevict_bb`tno_victim`toutput_sha256`tnota" |
        Set-Content -LiteralPath $ledger -Encoding UTF8
}
"{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}`t{7}`t{8}`t{9}`t{10}`t{11}`t{12}`t{13}" -f `
    $tag, (Get-Item $Log).LastWriteTime.ToString('yyyy-MM-dd HH:mm'), $tag.Substring(0,1),
    '?', $meta.ctx, $gen, $meta.end2end_tps, $regime, $chunks.Count,
    $meta.expert_cache_capacity, $evict, $meta.no_expert_victim,
    $(if ($sha -eq 'PERSO') { 'PERSO' } else { $sha.Substring(0,16) }), $Nota |
    Add-Content -LiteralPath $ledger -Encoding UTF8

"catalogato $tag"
$meta | ConvertTo-Json -Depth 5
