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
    [string]$OutDir = 'D:\ds4_work\llama_run',
    # argomenti extra, per provare la speculativa senza toccare il resto:
    #   -Extra @('--spec-type','draft-dspark','-md','D:\ds4-models\DSpark-support-Q2K-w2Q4K.gguf')
    [string[]]$Extra = @(),
    [string]$Etichetta = ''
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$tag = "LLAMA_ngl{0}{1}_{2}" -f $Ngl, $(if($Etichetta){"_$Etichetta"}else{''}), (Get-Date -Format 'HHmmss')
$log = Join-Path $OutDir "$tag.server.log"

# IL PROMPT DELLA CAMPAGNA, identico a braccio.ps1:277. Se cambia, il confronto
# con i nostri numeri non vale piu'.
$prompt = 'Create a complete single-file HTML landing page for a cyberpunk AI programming shop. Include CSS, navigation, hero, request form, and a JavaScript confirmation popup. Return only the HTML document.'
$sha = [BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash(
    [Text.Encoding]::UTF8.GetBytes($prompt))).Replace('-','').ToLower()
# La costante era 38f6ec5e5f9d3d8f, che non e' lo sha del prompt qui sotto: il
# guardiano ha suonato a ogni run del 2/8 e ci siamo abituati a ignorarlo, che e'
# il modo in cui un controllo muore. Il valore vero, verificato il 2/8 sera, e'
# lo stesso che il prompt ha in braccio.ps1:277 e dspark.ps1:31 -- le tre stringhe
# sono identiche byte per byte, quindi il confronto fra motori regge.
if ($sha.Substring(0,16) -ne '38f6ec5ee5403f59') {
    Write-Host "  ATTENZIONE: sha del prompt $($sha.Substring(0,16)), atteso 38f6ec5ee5403f59"
}
Write-Host "  motore  llama.cpp b10227    ngl=$Ngl  ctx=$Ctx  token=$Tokens"
Write-Host "  prompt  sha $($sha.Substring(0,16))   modello $(Split-Path $Model -Leaf)"

$args = @('-m', $Model, '-c', "$Ctx", '-ngl', "$Ngl", '--port', "$Port",
          '--host', '127.0.0.1', '--no-warmup') + $Extra
if ($Extra.Count) { Write-Host "  extra:  $($Extra -join ' ')" }
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
        # SPEGNIMENTO GRAZIOSO. Il 2/8 ho ucciso llama con Stop-Process e ha
        # lasciato ~2,2 GB di VRAM non rilasciata, che ho poi inseguito per ore
        # nel nostro bilancio credendola nostra. llama-server non ha endpoint di
        # shutdown (/metrics, /slots, /v1/* e basta): la via giusta su Windows e'
        # CTRL_BREAK_EVENT, la stessa che l'igiene di campagna prescrive per il
        # nostro server quando manca il token.
        Write-Host "  spengo il server con CTRL_BREAK"
        if (-not ([Management.Automation.PSTypeName]'Ctrl').Type) {
            Add-Type -Namespace '' -Name Ctrl -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)]
public static extern bool GenerateConsoleCtrlEvent(uint dwCtrlEvent, uint dwProcessGroupId);
[DllImport("kernel32.dll", SetLastError=true)]
public static extern bool AttachConsole(uint dwProcessId);
[DllImport("kernel32.dll", SetLastError=true)]
public static extern bool FreeConsole();
[DllImport("kernel32.dll")]
public static extern bool SetConsoleCtrlHandler(IntPtr handler, bool add);
'@
        }
        $inviato = $false
        try {
            [void][Ctrl]::FreeConsole()
            if ([Ctrl]::AttachConsole([uint32]$srv.Id)) {
                [void][Ctrl]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
                $inviato = [Ctrl]::GenerateConsoleCtrlEvent(1, 0)   # 1 = CTRL_BREAK_EVENT
                Start-Sleep -Seconds 8
                [void][Ctrl]::FreeConsole()
                [void][Ctrl]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
            }
        } catch { }
        if (-not $srv.HasExited) {
            Write-Host ("  CTRL_BREAK {0}; attendo l'uscita" -f $(if($inviato){'inviato'}else{'non riuscito'}))
            if (-not $srv.WaitForExit(30000)) {
                Write-Host "  non e' uscito in 30s: Stop-Process (la VRAM potrebbe restare sporca)"
                Stop-Process -Id $srv.Id -EA SilentlyContinue
            }
        }
        Start-Sleep -Seconds 5
        $v = (nvidia-smi --query-gpu=memory.used --format=csv,noheader) 2>$null
        Write-Host "  VRAM dopo lo spegnimento: $v   (base pulita ~750 MiB)"
    }
}
