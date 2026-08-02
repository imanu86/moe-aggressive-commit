# PREFILL LUNGO: il test che decide se spostarsi su llama.cpp.
#
# Il bersaglio dell'utente non e' generare 1500 token su un prompt da 43: e'
# lavorare su contesti larghi (kv150k, 2 prompt). Nel confronto del 2/8
# llama.cpp ha fatto il prefill di 43 token in 34 secondi -- 1,26 t/s. Se quel
# numero non e' solo cache fredda, su un contesto lungo e' squalificante.
#
# Stesso prompt, stessa richiesta, due motori. Il prompt e' DETERMINISTICO:
# i primi N caratteri di ds4_cuda.cu, cosi' il test si ripete identico.
param(
    [int]$PromptChars = 32000,     # ~8000 token
    [int]$Tokens      = 200,       # generazione corta: qui misuriamo il PREFILL
    [int]$Ctx         = 16384,
    [ValidateSet('llama','ds4','entrambi')][string]$Motore = 'entrambi',
    [string]$OutDir   = 'D:\ds4_work\prefill_lungo'
)
$ErrorActionPreference = 'Continue'
$R = 'C:\Users\imanu\source\repos\moe-aggressive-commit'
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

# --- il prompt, deterministico e verificabile ---
$sorgente = Get-Content "$R\ds4-port\ds4_cuda.cu" -Raw
$contesto = $sorgente.Substring(0, [Math]::Min($PromptChars, $sorgente.Length))
$prompt = "Here is a fragment of a CUDA inference runtime:`n`n$contesto`n`n" +
          "In three sentences, what does this code do?"
$sha = [BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash(
    [Text.Encoding]::UTF8.GetBytes($prompt))).Replace('-','').ToLower().Substring(0,16)
Write-Host "  prompt: $($prompt.Length) caratteri, sha $sha"

function Prova($nome, $porta, $exe, $argomenti) {
    Write-Host ""
    Write-Host "=== $nome ==="
    $tag = "{0}_{1}" -f $nome, (Get-Date -Format 'HHmmss')
    $log = Join-Path $OutDir "$tag.log"
    $srv = Start-Process -FilePath $exe -ArgumentList $argomenti -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow
    try {
        $pronto = $false
        for ($i = 0; $i -lt 300; $i++) {
            Start-Sleep -Seconds 5
            if ($srv.HasExited) { Write-Host "  uscito, exit $($srv.ExitCode)"; return }
            # NON usare /health: ce l'ha llama.cpp ma il nostro server NO, e il
            # 2/8 ha atteso 25 minuti invano mentre il server era gia' in ascolto
            # ("listening on http://127.0.0.1:8097"). /v1/models lo servono
            # entrambi; se anche quello mancasse, basta che la porta risponda.
            try { Invoke-RestMethod "http://127.0.0.1:$porta/v1/models" -TimeoutSec 3 -EA Stop | Out-Null
                  $pronto = $true; break }
            catch {
                try { (New-Object Net.Sockets.TcpClient).Connect('127.0.0.1', $porta)
                      $pronto = $true; break } catch { }
            }
        }
        if (-not $pronto) { Write-Host "  non pronto dopo 25 min"; return }
        Write-Host "  pronto dopo $($i*5)s"

        $body = @{ model='ds4'; max_tokens=$Tokens; temperature=0; stream=$false; think=$false
                   messages=@(@{role='user'; content=$prompt}) } | ConvertTo-Json -Depth 5 -Compress
        $req = Join-Path $OutDir "$tag.request.json"
        [IO.File]::WriteAllText($req, $body, [Text.UTF8Encoding]::new($false))

        $t0 = Get-Date
        & curl.exe -sS --max-time 7200 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
            -H 'Content-Type: application/json' --data-binary "@$req" `
            -o (Join-Path $OutDir "$tag.response.json")
        $sec = ((Get-Date) - $t0).TotalSeconds
        # -Encoding UTF8: senza, PS 5.1 legge in ANSI e storpia i multibyte (2/8)
        $r = Get-Content (Join-Path $OutDir "$tag.response.json") -Raw -Encoding UTF8 | ConvertFrom-Json
        $pt = $r.usage.prompt_tokens; $ct = $r.usage.completion_tokens
        Write-Host "  prompt $pt token, generati $ct, totale $([math]::Round($sec,1))s"
        # il prefill si ricava per differenza usando il decode misurato dal log
        $dec = Select-String -LiteralPath $log -Pattern 'eval time =\s+([\d.]+) ms /\s+(\d+) tokens' -AllMatches
        if ($dec) { $dec.Matches | ForEach-Object { Write-Host "  llama: $($_.Value)" } }
        $adec = Select-String -LiteralPath $log -Pattern 'avg=([\d.]+) t/s' -AllMatches
        if ($adec) { Write-Host "  ds4 avg decode: $($adec.Matches[-1].Groups[1].Value) t/s" }
    } finally {
        if (-not $srv.HasExited) { Stop-Process -Id $srv.Id -EA SilentlyContinue }
        Start-Sleep -Seconds 15
    }
}

if ($Motore -in 'llama','entrambi') {
    $env:LLAMA_ARG_CPU_MOE = '1'
    Prova 'LLAMA' 8098 'D:\llama-b10227\llama-server.exe' `
        @('-m','C:\ds4-models\DS4-0731-IQ2XXS.gguf','-c',"$Ctx",'-ngl','99',
          '--port','8098','--host','127.0.0.1','--no-warmup')
    Remove-Item Env:LLAMA_ARG_CPU_MOE -EA SilentlyContinue
}
if ($Motore -in 'ds4','entrambi') {
    Get-ChildItem Env: | Where-Object Name -Like 'DS4_*' |
        ForEach-Object { Remove-Item -LiteralPath ("Env:{0}" -f $_.Name) -EA SilentlyContinue }
    $env:DS4_METAL_PREFILL_CHUNK           = '256'
    $env:DS4_CUDA_Q8_F16_CACHE_MB          = '0'
    $env:DS4_CUDA_STREAMING_EXPERT_CACHE_N = '320'
    $env:DS4_EXPERT_TIERING                = 'enforce'
    $env:DS4_EXPERT_TIER_POLICY            = 'mass-lfru'
    $env:DS4_EXPERT_TIER_CLOCK_CALLS       = '1000'
    $env:DS4_CUDA_MOE_IO_QD                = '4'
    $env:DS4_CUDA_MOE_CACHE_POLICY         = 'lru'
    Prova 'DS4' 8097 "$R\ds4-port\build-verify\ds4-server.exe" `
        @('-m','C:\ds4-models\DS4-0731-IQ2XXS.gguf','--cuda','-c',"$Ctx",
          '-n',"$Tokens",'--host','127.0.0.1','--port','8097','--ssd-streaming')
}
Write-Host ""
Write-Host "=== FINITO ==="
