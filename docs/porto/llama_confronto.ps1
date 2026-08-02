# Il confronto a variabile singola: STESSO modello, STESSO ctx, STESSO prompt,
# STESSA macchina. Cambia solo il motore -- DwarfStar contro llama.cpp.
#
# Nasce dalla domanda dell'utente il 2/8: abbiamo costruito il porto Windows su
# DwarfStar, che nel suo README si dichiara "optimized first for DeepSeek V4
# Flash... Metal, the PRIMARY target, on Macs with 96 GB or more" e pensato per
# "128 GB laptops and 512 GB workstations". Noi siamo su Windows, su CUDA (il
# backend secondario), con 64 GB. Tre passi fuori dal centro di progetto.
#
# La build b9646 che avevamo NON conosce `deepseek4`: serviva la b10227 (2/8).
param(
    [int]$Tokens = 1500,
    [int]$Ctx    = 10000,
    [int]$Port   = 8099,
    [int]$Ngl    = 0,          # strati su GPU. 0 = solo CPU+mmap, il caso base
    [string]$Exe = 'D:\llama-b10227\llama-server.exe',
    [string]$Model = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf',
    [string]$OutDir = 'D:\ds4_work\llama_run'
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$tag = "LLAMA_ngl{0}_{1}" -f $Ngl, (Get-Date -Format 'HHmmss')
$log = Join-Path $OutDir "$tag.server.log"

# IL PROMPT DELLA CAMPAGNA, identico a braccio.ps1:277. Se cambia, il confronto
# con i nostri numeri non vale piu'.
$prompt = 'Create a complete single-file HTML landing page for a cyberpunk AI programming shop. Include CSS, navigation, hero, request form, and a JavaScript confirmation popup. Return only the HTML document.'
$sha = [BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash(
    [Text.Encoding]::UTF8.GetBytes($prompt))).Replace('-','').ToLower()
if ($sha.Substring(0,16) -ne '38f6ec5e5f9d3d8f') {
    Write-Host "  ATTENZIONE: sha del prompt $($sha.Substring(0,16)), atteso 38f6ec5e5f9d3d8f"
}
Write-Host "  motore  llama.cpp b10227    ngl=$Ngl  ctx=$Ctx  token=$Tokens"
Write-Host "  prompt  sha $($sha.Substring(0,16))   modello $(Split-Path $Model -Leaf)"

$args = @('-m', $Model, '-c', "$Ctx", '-ngl', "$Ngl", '--port', "$Port",
          '--host', '127.0.0.1', '--no-warmup')
$srv = Start-Process -FilePath $Exe -ArgumentList $args -PassThru `
        -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

try {
    # attesa del caricamento: il modello e' 80,76 GiB, puo' volerci molto
    $pronto = $false
    for ($i = 0; $i -lt 240; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { Write-Host "  il server e' uscito (exit $($srv.ExitCode))"; break }
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3 -EA Stop
            $pronto = $true; break
        } catch { }
    }
    if (-not $pronto) { Write-Host "  server non pronto dopo 20 minuti"; return }
    Write-Host "  server pronto dopo $($i*5)s, invio la richiesta"

    $body = @{ model = 'ds4'; max_tokens = $Tokens; temperature = 0; stream = $false
               messages = @(@{ role = 'user'; content = $prompt }) } | ConvertTo-Json -Depth 5
    $req = Join-Path $OutDir "$tag.request.json"
    [IO.File]::WriteAllText($req, $body, [Text.UTF8Encoding]::new($false))

    $t0 = Get-Date
    $out = Join-Path $OutDir "$tag.response.json"
    & curl.exe -sS --max-time 7200 -X POST "http://127.0.0.1:$Port/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" -o $out
    $secondi = ((Get-Date) - $t0).TotalSeconds

    # llama.cpp riporta i tempi da solo, e sono piu' precisi dei nostri
    $r = Get-Content $out -Raw | ConvertFrom-Json
    $testo = $r.choices[0].message.content
    [IO.File]::WriteAllText((Join-Path $OutDir "$tag.output.html"), $testo,
        [Text.UTF8Encoding]::new($false))
    $tim = Select-String -LiteralPath $log -Pattern 'eval time =.*\(\s*([\d.]+) tokens per second\)' -AllMatches
    Write-Host ""
    Write-Host "  END2END  $([math]::Round($r.usage.completion_tokens / $secondi, 3)) t/s"
    Write-Host "  token    $($r.usage.completion_tokens) generati, $($r.usage.prompt_tokens) di prompt"
    Write-Host "  output   $($testo.Length) caratteri  -> $tag.output.html"
    if ($tim) { $tim.Matches | ForEach-Object { Write-Host "  llama:   $($_.Value)" } }
}
finally {
    if (-not $srv.HasExited) {
        Write-Host "  spengo il server"
        Stop-Process -Id $srv.Id -EA SilentlyContinue    # llama.cpp non ha endpoint di shutdown
    }
}
