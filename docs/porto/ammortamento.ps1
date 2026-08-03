# QUANTO C'E' DA AMMORTIZZARE — il test che decide se DSpark vale la seconda GPU
#
# La speculazione verifica K token in UNA passata. Guadagna solo se una parte
# grossa del costo e' PER PASSATA invece che PER TOKEN.
#
# Il prefill e' esattamente quello scenario: elabora molti token in una passata.
# Quindi il rapporto fra il costo per token in prefill e quello in decode misura
# direttamente la frazione ammortizzabile, senza comprare niente.
#
#   prefill molto piu' veloce per token  ->  il grosso e' PER PASSATA, DSpark ha
#                                            un premio, e la seconda GPU serve
#                                            per il DRAFT (non per gli esperti)
#   prefill simile al decode             ->  non c'e' niente da ammortizzare,
#                                            DSpark resta morto anche con la GPU
#
# La scomposizione stimata era: ~102 ms per passata, ~34 ms per token. Se regge,
# con 5 token verificati e 4,4 accettati si passerebbe da 136 a ~54 ms/token.
# Questo test la conferma o la demolisce.
#
# ATTENZIONE alla trappola gia' vista: il prefill dei run brevi di stanotte
# faceva 1,0-2,8 t/s, ma era dominato dal primo tocco delle pagine su un modello
# freddo. Qui si scalda PRIMA con una richiesta normale, poi si misura.

$ErrorActionPreference = 'Continue'
$porta = 8099
$out   = 'D:\ds4_work\llama_run\ammortamento.txt'
if (Test-Path $out) { Remove-Item $out -Force }

$env:LLAMA_ARG_CPU_MOE = '1'
$log = 'D:\ds4_work\llama_run\ammortamento.server.log'

$args = @('-m','C:\ds4-models\DS4-0731-IQ2XXS.gguf','-c','10000','-ngl','99',
          '--port',"$porta",'--host','127.0.0.1','--no-warmup',
          '-ncmoe','42','--reasoning-budget','0')
$srv = Start-Process -FilePath 'D:\llama-b10227\llama-server.exe' -ArgumentList $args -PassThru `
        -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow
Start-Sleep -Milliseconds 500
if ($srv.PriorityClass -ne 'Normal') { "FERMO: priorita' $($srv.PriorityClass)" | Out-File $out; return }

for ($i = 0; $i -lt 240; $i++) {
    Start-Sleep -Seconds 5
    try { Invoke-RestMethod -Uri "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; break } catch {}
}

function Chiedi($prompt, $ntok, $etichetta) {
    $body = @{ model='ds4'; max_tokens=$ntok; temperature=0; stream=$false
               messages=@(@{role='user'; content=$prompt}) } | ConvertTo-Json -Depth 5 -Compress
    $req = "D:\ds4_work\llama_run\amm_$etichetta.json"
    [IO.File]::WriteAllText($req, $body, [Text.UTF8Encoding]::new($false))
    & curl.exe -sS --max-time 3600 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary "@$req" -o "D:\ds4_work\llama_run\amm_$etichetta.resp.json" | Out-Null
}

# 1) RISCALDAMENTO: prompt corto, 600 token. Serve solo a far entrare le pagine.
Chiedi 'Create a complete single-file HTML landing page for a cyberpunk AI programming shop. Include CSS, navigation, hero, request form, and a JavaScript confirmation popup. Return only the HTML document.' 600 'caldo'

# 2) LA MISURA: prompt LUNGO, pochi token generati.
#    Il prompt lungo si costruisce ripetendo un paragrafo, cosi' il conto dei
#    token e' prevedibile e il contenuto non cambia la difficolta'.
$par = 'The quantization of large mixture-of-experts language models introduces a tension between memory footprint and numerical fidelity that becomes acute below three bits per weight. '
$lungo = 'Summarize the following text in one sentence. ' + ($par * 120)
Chiedi $lungo 24 'lungo'

# spegnimento pulito: CTRL_C, non CTRL_BREAK (llama rifiuta il secondo)
if (-not $srv.HasExited) {
    Add-Type -Namespace '' -Name C4 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@
    [void][C4]::FreeConsole()
    if ([C4]::AttachConsole([uint32]$srv.Id)) {
        [void][C4]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][C4]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][C4]::FreeConsole(); [void][C4]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $srv.WaitForExit(30000) | Out-Null
}

# le righe di timing: la SECONDA coppia e' quella del prompt lungo
$t = Select-String -LiteralPath $log -Pattern 'prompt eval time =|        eval time =' |
     ForEach-Object { $_.Line -replace '.*\| ','' }
$t | Out-File $out -Append -Encoding utf8
'FINE' | Out-File $out -Append -Encoding utf8
