# DOVE ESEGUONO I PESI DI GATING: la meta' che manca alla soglia per massa
#
# L'utente il 3/8 definisce la massa su cui tarare il gate SSD->RAM:
#
#   massa = peso di gating x frequenza di bussata
#
# L'osservatore reap oggi da' solo la frequenza: e' agganciato dentro
# ggml_compute_forward_mul_mat_id (ggml-cpu.c:1646) dove arrivano gli `ids`,
# e i pesi non passano di li'.
#
# In llama.cpp il percorso MoE e':
#
#   logits  = mul_mat(ffn_gate_inp, cur)         "ffn_moe_logits"
#   probs   = softmax/sigmoid(logits)            "ffn_moe_probs"
#   topk    = ggml_top_k(probs, n_expert_used)   "ffn_moe_topk"     <- gli ids
#   weights = get_rows(probs, topk)              "ffn_moe_weights"  <- i pesi
#   experts = mul_mat_id(down_exps, ..., topk)                      <- su CPU
#   out     = mul(experts, weights)                                 <- DOVE?
#
# Con -ncmoe 42 gli esperti sono su CPU (il regex prende ffn_*_exps) e il
# gating resta su GPU, perche' ffn_gate_inp non e' un tensore di esperti.
# Ma `out = mul(experts, weights)` ha un operando enorme su CPU e uno minuscolo
# su GPU: se lo scheduler lo assegna alla CPU, i pesi vengono copiati li' e
# sono agganciabili NELLO STESSO PUNTO degli id, gia' appaiati.
#
# Se invece esegue su GPU, prendere i pesi costa una lettura sincrona
# device->host per strato -- il disegno gia' scartato nella testata di reap.h,
# misurato a -18% sul prefill.
#
# GGML_SCHED_DEBUG=2 stampa l'assegnazione di ogni nodo al suo backend.
# Bastano pochi token: la struttura del grafo non dipende dalla lunghezza.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\pesi_moe.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$log = 'D:\ds4_work\llama_run\pesi_moe.sched.log'

$req = 'D:\ds4_work\llama_run\sonda4.req.json'
'{"temperature":0,"stream":false,"messages":[{"content":"Say hello.","role":"user"}],"model":"ds4","max_tokens":4}' |
    Out-File $req -Encoding ascii -NoNewline

$env:LLAMA_ARG_CPU_MOE = '1'
$env:GGML_SCHED_DEBUG  = '2'

Add-Type -Namespace '' -Name CP -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@

$argomenti = @('-m','C:\ds4-models\DS4-0731-IQ2XXS.gguf','-c','1024','-ngl','99','-ncmoe','42',
               '-ub','64','-b','64','--port','8151','--host','127.0.0.1',
               '--no-warmup','--reasoning-budget','0',
               # SENZA questo GGML_SCHED_DEBUG non stampa: il suo output passa
               # da GGML_LOG_DEBUG, che la verbosita' 3 sopprime.
               '-lv','10')

$srv = Start-Process -FilePath 'D:\llama-dspark\build\bin\llama-server.exe' -ArgumentList $argomenti `
        -PassThru -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

Start-Sleep -Milliseconds 700
if ($srv.PriorityClass -ne 'Normal') {
    "FERMO: priorita' $($srv.PriorityClass)" | Out-File $out -Append -Encoding utf8
} else {
    $pronto = $false
    for ($i = 0; $i -lt 180; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri 'http://127.0.0.1:8151/health' -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }
    if ($pronto) {
        & curl.exe -sS --max-time 900 -X POST 'http://127.0.0.1:8151/v1/chat/completions' `
            -H 'Content-Type: application/json' --data-binary "@$req" `
            -o 'D:\ds4_work\llama_run\pesi_moe.resp.json' | Out-Null
    } else {
        "il server non e' partito" | Out-File $out -Append -Encoding utf8
    }
}

if (-not $srv.HasExited) {
    [void][CP]::FreeConsole()
    if ([CP]::AttachConsole([uint32]$srv.Id)) {
        [void][CP]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
        [void][CP]::GenerateConsoleCtrlEvent(0, 0)
        Start-Sleep -Seconds 10
        [void][CP]::FreeConsole(); [void][CP]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
    }
    $srv.WaitForExit(60000) | Out-Null
}

Remove-Item Env:GGML_SCHED_DEBUG -EA SilentlyContinue

# l'assegnazione dei nodi MoE al backend
"=== nodi MoE e loro backend ===" | Out-File $out -Append -Encoding utf8
Select-String -LiteralPath $log -Pattern 'ffn_moe_weights|ffn_moe_topk|ffn_moe_probs|ffn_moe_out|ffn_moe_down' -EA SilentlyContinue |
    ForEach-Object { $_.Line } | Select-Object -First 60 | Out-File $out -Append -Encoding utf8

"" | Out-File $out -Append -Encoding utf8
"=== conteggio per backend (nodi ffn_moe_*) ===" | Out-File $out -Append -Encoding utf8
Select-String -LiteralPath $log -Pattern 'ffn_moe' -EA SilentlyContinue |
    ForEach-Object { if ($_.Line -match '(CUDA0|CPU)') { $matches[1] } } |
    Group-Object | ForEach-Object { "$($_.Name): $($_.Count)" } | Out-File $out -Append -Encoding utf8

'FINE' | Out-File $out -Append -Encoding utf8
