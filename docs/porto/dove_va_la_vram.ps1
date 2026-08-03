# DOVE VANNO GLI 11,4 GB IN PIU' DEL FORK
#
# Misurato il 3/8, stessa configurazione (-ngl 99 -ncmoe 42 -cmoe, ctx 10000):
#
#                  dedicata      condivisa     totale indirizzabile
#   ufficiale       9.793 MiB       156 MiB          9.949 MiB
#   FORK           12.029 MiB     9.590 MiB         21.619 MiB
#                                                   +11.670 MiB
#
# E il fork rende 3,70 di regime contro 7,37: meta'.
#
# Cosa NON e':
#   - non carica DSpark da se' (il log mostra un solo modello)
#   - supporta --cpu-moe con la stessa variabile d'ambiente
#   - llm_ffn_exps_cpu_override() e' identico nei due alberi
#     (stesso regex, stesso ggml_backend_cpu_buffer_type())
#
# Quindi la differenza sta piu' in basso. llama.cpp stampa la ripartizione dei
# buffer al caricamento, ma la verbosita' del banco la sopprime: qui si alza a
# 10 e si cattura, per entrambi i binari, con pochissimi token generati.

$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\dove_va_vram.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$env:LLAMA_ARG_CPU_MOE = '1'

$binari = @(
    @{ nome='UFFICIALE'; exe='D:\llama-b10227\llama-server.exe';                 porta=8096 }
    @{ nome='FORK';      exe='D:\llama-dspark\build\bin\llama-server.exe';        porta=8095 }
)

foreach ($b in $binari) {
    "=============== $($b.nome) ===============" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\dove_va_$($b.nome).log"

    $args = @('-m','C:\ds4-models\DS4-0731-IQ2XXS.gguf','-c','10000','-ngl','99',
              '-ncmoe','42','--port',"$($b.porta)",'--host','127.0.0.1',
              '--no-warmup','--reasoning-budget','0','-lv','10')
    $srv = Start-Process -FilePath $b.exe -ArgumentList $args -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out" -NoNewWindow

    $pronto = $false
    for ($i = 0; $i -lt 120; $i++) {
        Start-Sleep -Seconds 5
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($b.porta)/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto = $true; break } catch {}
    }

    if ($pronto) {
        $d = (Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
             Sort-Object CookedValue -Descending | Select-Object -First 1
        $s = (Get-Counter -Counter '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue).CounterSamples |
             Sort-Object CookedValue -Descending | Select-Object -First 1
        "dedicata  $([math]::Round($d.CookedValue/1MB)) MiB" | Out-File $out -Append -Encoding utf8
        "condivisa $([math]::Round($s.CookedValue/1MB)) MiB" | Out-File $out -Append -Encoding utf8
    } else {
        "il server non e' partito" | Out-File $out -Append -Encoding utf8
    }

    if (-not $srv.HasExited) {
        Add-Type -Namespace '' -Name C7 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint e, uint g);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint p);
[DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h, bool a);
'@
        [void][C7]::FreeConsole()
        if ([C7]::AttachConsole([uint32]$srv.Id)) {
            [void][C7]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
            [void][C7]::GenerateConsoleCtrlEvent(0, 0)
            Start-Sleep -Seconds 10
            [void][C7]::FreeConsole(); [void][C7]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
        }
        $srv.WaitForExit(30000) | Out-Null
    }

    # le righe di allocazione: buffer, KV, compute, offload
    if (Test-Path $log) {
        Select-String -LiteralPath $log -Pattern 'buffer size|KV self|kv cache|compute buffer|model buffer|offloaded|cells|CPU_Mapped|CUDA_Host|repeating|non-repeating' |
            ForEach-Object { ($_.Line -replace '^\S+\s+\S\s+','') } | Select-Object -First 30 |
            Out-File $out -Append -Encoding utf8
    }
    "" | Out-File $out -Append -Encoding utf8
    Start-Sleep -Seconds 30
}
'FINE' | Out-File $out -Append -Encoding utf8
