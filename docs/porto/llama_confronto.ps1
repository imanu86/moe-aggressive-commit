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
    [string]$Etichetta = '',
    # RAGIONAMENTO. braccio.ps1:291 passa think=false esplicito perche' "SENZA
    # questo il modello entra in fase di ragionamento e brucia [token]". Questo
    # banco non passava niente, e llama.cpp lo tiene ACCESO di default: il run
    # sota8k del 2/8 ha restituito 634 caratteri di `reasoning_content`.
    # Quindi tutti i confronti llama-contro-DwarfStar fatti finora hanno
    # paragonato un motore che pensava contro uno che non pensava.
    # --reasoning-budget 0 = "immediate end" (common/arg.cpp:3565).
    [bool]$Think = $false,
    # 'campagna' (default), 'neuraforge', o il testo completo di un prompt.
    # Qualunque cosa non sia il prompt di campagna viene DICHIARATA a schermo
    # col suo sha, perche' un prompt cambiato in silenzio invalida l'archivio.
    [string]$Prompt = 'campagna',
    # Temperatura. 0 = deterministico: lo stesso prompt da' SEMPRE lo stesso
    # output, quindi ripetere un run non aggiunge informazione ma i confronti
    # sono a variabile singola. Sopra zero si esplora, ma due run della stessa
    # configurazione non sono piu' confrontabili fra loro.
    [double]$Temp = 0
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$tag = "LLAMA_ngl{0}{1}_{2}" -f $Ngl, $(if($Etichetta){"_$Etichetta"}else{''}), (Get-Date -Format 'HHmmss')
$log = Join-Path $OutDir "$tag.server.log"

# IL PROMPT DELLA CAMPAGNA, identico a braccio.ps1:277. Se cambia, il confronto
# con i nostri numeri non vale piu'.
# Prompt alternativi noti, per -Prompt neuraforge:
#   neuraforge = il brief del 25/7, MOLTO piu' ricco del nostro (3 feature card
#   + 3 tier di prezzo = 6 schede, e chiede "CSS interno" e "single-file"
#   esplicitamente). Ha prodotto la pagina migliore mai vista, 6529 token e
#   24 KB: C:\Users\imanu\Documents\Codex\2026-07-25\legg\outputs\
#   NeuraForge_initial_6529_keepkv.html
$prompti = @{
    campagna = 'Create a complete single-file HTML landing page for a cyberpunk AI programming shop. Include CSS, navigation, hero, request form, and a JavaScript confirmation popup. Return only the HTML document.'
    neuraforge = 'Genera una pagina HTML completa single-file per una startup AI NeuraForge, stile cyberpunk neon: head con CSS interno, header con nav, hero, 3 feature card, tabella prezzi 3 tier, form contatti con validazione JS, footer. Codice completo e commentato, molto dettagliato.'
}
$prompt = if ($prompti.ContainsKey($Prompt)) { $prompti[$Prompt] } else { $Prompt }
$sha = [BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash(
    [Text.Encoding]::UTF8.GetBytes($prompt))).Replace('-','').ToLower()
# La costante era 38f6ec5e5f9d3d8f, che non e' lo sha del prompt qui sotto: il
# guardiano ha suonato a ogni run del 2/8 e ci siamo abituati a ignorarlo, che e'
# il modo in cui un controllo muore. Il valore vero, verificato il 2/8 sera, e'
# lo stesso che il prompt ha in braccio.ps1:277 e dspark.ps1:31 -- le tre stringhe
# sono identiche byte per byte, quindi il confronto fra motori regge.
if ($sha.Substring(0,16) -eq '38f6ec5ee5403f59') {
    Write-Host "  prompt   DI CAMPAGNA, sha $($sha.Substring(0,16))"
} else {
    Write-Host ""
    Write-Host "  ATTENZIONE: prompt NON di campagna."
    Write-Host "  sha $($sha.Substring(0,16))  ($($prompt.Length) caratteri)"
    Write-Host "  I numeri di questo run NON sono confrontabili con l'archivio."
    Write-Host ""
}
Write-Host "  motore  llama.cpp b10227    ngl=$Ngl  ctx=$Ctx  token=$Tokens"
Write-Host "  prompt  sha $($sha.Substring(0,16))   modello $(Split-Path $Model -Leaf)"

$args = @('-m', $Model, '-c', "$Ctx", '-ngl', "$Ngl", '--port', "$Port",
          '--host', '127.0.0.1', '--no-warmup')
if (-not $Think) { $args += @('--reasoning-budget', '0') }
$args += $Extra
Write-Host "  pensiero $(if($Think){'ACCESO'}else{'spento (--reasoning-budget 0)'})"
if ($Extra.Count) { Write-Host "  extra:  $($Extra -join ' ')" }
$srv = Start-Process -FilePath $Exe -ArgumentList $args -PassThru `
        -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

# GUARDIANO DELLA PRIORITA'. Il 2/8 sera ho lanciato la scala via Task Scheduler
# per farla sopravvivere alla caduta della sessione: New-ScheduledTaskSettingsSet
# mette Priority=7 per default, che mappa su BELOW_NORMAL_PRIORITY_CLASS, e
# llama-server l'ha ereditata. Risultato: 3,99 t/s contro i 5,67 dello stesso
# identico binario lanciato dalla sessione. Un -30% che non era ne' la build ne'
# la macchina, ma il modo di lanciare.
#
# Da una sessione interattiva la priorita' e' Normal (base 8). Se non lo e', il
# run NON e' confrontabile con l'archivio e va fermato subito, non catalogato.
Start-Sleep -Milliseconds 500
try {
    $prio = $srv.PriorityClass
    if ($prio -ne 'Normal') {
        Write-Host ""
        Write-Host "  FERMO: llama-server gira a priorita' $prio, non Normal."
        Write-Host "  Un run a priorita' diversa non e' confrontabile con l'archivio."
        Write-Host "  (Task Scheduler? imposta -Priority 4, o lancia dalla sessione.)"
        $srv | Stop-Process -Force -ErrorAction SilentlyContinue
        return
    }
    Write-Host "  priorita' $prio (base $($srv.BasePriority))"
} catch { Write-Host "  priorita' non leggibile: $($_.Exception.Message)" }

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

    if ($Temp -ne 0) {
        Write-Host "  ATTENZIONE: temperatura $Temp, non 0. Questo run NON e' riproducibile"
        Write-Host "  e due esecuzioni della stessa configurazione daranno output diversi."
    }
    $body = @{ model = 'ds4'; max_tokens = $Tokens; temperature = $Temp; stream = $false
               messages = @(@{ role = 'user'; content = $prompt }) } | ConvertTo-Json -Depth 5
    $req = Join-Path $OutDir "$tag.request.json"
    [IO.File]::WriteAllText($req, $body, [Text.UTF8Encoding]::new($false))

    $t0 = Get-Date
    $out = Join-Path $OutDir "$tag.response.json"
    & curl.exe -sS --max-time 7200 -X POST "http://127.0.0.1:$Port/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" -o $out
    $secondi = ((Get-Date) - $t0).TotalSeconds

    # llama.cpp riporta i tempi da solo, e sono piu' precisi dei nostri
    # -Encoding UTF8 OBBLIGATORIO. In Windows PowerShell 5.1 Get-Content senza
    # encoding legge con la codepage ANSI: la risposta di curl e' UTF-8, quindi
    # ogni carattere multibyte veniva letto come windows-1252 e riscritto come
    # UTF-8, cioe' storpiato. Provato il 2/8 confrontando col JSON grezzo:
    #   JSON  U+2014 (trattino lungo)  ->  file  U+00E2 U+20AC U+201D
    # Riguardava OGNI documento della campagna: trattini, frecce, emoji. Il
    # modello scriveva giusto, lo rovinavamo noi nel salvataggio.
    $r = Get-Content $out -Raw -Encoding UTF8 | ConvertFrom-Json
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
