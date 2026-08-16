# LA RESIDENZA PIENA, SU SCALA RIDOTTA.
# Gli esperti di N strati in VRAM VERA: residenza al 100% per costruzione, zero
# miss, zero copie, calcolo su GPU. Il delta per strato x 43 e' il TETTO del
# progetto -- e dice quanto dei 63,7 ms "fissi" e' in realta' amministrazione.
# ctx 2048 e ub 32 per liberare VRAM al posto dei buffer di calcolo.
$ErrorActionPreference = 'Continue'
$out = 'D:\ds4_work\llama_run\residenza.txt'
if (Test-Path $out) { Remove-Item $out -Force }
$EXE = 'D:\llama-dspark\build\bin\llama-server.exe'
$IQ2 = 'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
$b = [char]92
$esp = 'ffn_(gate|up|down)_exps' + $b + '.weight'
$V0 = $esp + '=CUDA0_Mapped'
$V1 = 'blk' + $b + '.42' + $b + '.' + $esp + '=CUDA0,' + $esp + '=CUDA0_Mapped'
$V2 = 'blk' + $b + '.4[12]' + $b + '.' + $esp + '=CUDA0,' + $esp + '=CUDA0_Mapped'
$bracci = @(
    @{ n='R0'; ot=$V0; d='0 strati residenti -- il metro' },
    @{ n='R1'; ot=$V1; d='1 strato in VRAM vera (blk.42)' },
    @{ n='R2'; ot=$V2; d='2 strati in VRAM vera (blk.41-42)' },
    @{ n='R0b'; ot=$V0; d='0 strati -- ripetizione, per il rumore' }
)
$porta = 8421
foreach ($x in $bracci) {
    "=== $($x.n) -- $($x.d) ===" | Out-File $out -Append -Encoding utf8
    $log = "D:\ds4_work\llama_run\RES_$($x.n).log"
    $env:LLAMA_MAPPED_IBRIDO = '1'; $env:LLAMA_REAP = '0'; $env:LLAMA_REAP_LOCK = '0'
    $a = @('-m',$IQ2,'-c','2048','-ngl','99','-ot',$x.ot,'-ub','32','-b','32',
           '-t','8','--port',"$porta",'--host','127.0.0.1','--no-warmup','--no-mmap','--reasoning-budget','0')
    $srv = Start-Process -FilePath $EXE -ArgumentList $a -PassThru -WindowStyle Minimized `
            -RedirectStandardError $log -RedirectStandardOutput ($log + '.out')
    $pronto = $false
    for ($i=0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 10
        if ($srv.HasExited) { break }
        try { Invoke-RestMethod "http://127.0.0.1:$porta/health" -TimeoutSec 3 -EA Stop | Out-Null; $pronto=$true; break } catch {}
    }
    if (-not $pronto) {
        "  NON PARTE (VRAM insufficiente?):" | Out-File $out -Append -Encoding utf8
        Select-String -Path $log -Pattern 'failed to allocate|cudaMalloc|out of memory' | Select-Object -Last 2 |
            ForEach-Object { "    " + ($_.Line -replace '^[0-9.]+ +[A-Z] +','') } | Out-File $out -Append -Encoding utf8
        if (-not $srv.HasExited) { $srv.Kill() }
        Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
        Start-Sleep 40; $porta++; continue
    }
    $d = (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -EA SilentlyContinue).CounterSamples |
         Sort-Object CookedValue -Descending | Select-Object -First 1
    "  VRAM dedicata {0:N0} MiB, liberi {1:N0}" -f ($d.CookedValue/1MB), (12288 - $d.CookedValue/1MB) |
        Out-File $out -Append -Encoding utf8
    $risp = "D:\ds4_work\llama_run\res_$($x.n).json"
    & curl.exe -s --max-time 900 -X POST "http://127.0.0.1:$porta/v1/chat/completions" `
        -H 'Content-Type: application/json' --data-binary '@D:\ds4_work\llama_run\sonda300.req.json' -o $risp | Out-Null
    if (Test-Path $risp) {
        $j = Get-Content $risp -Raw | ConvertFrom-Json
        "  prefill {0,6:N2} t/s   decode {1,6:N2} t/s   {2:N2} ms/token" -f `
            $j.timings.prompt_per_second, $j.timings.predicted_per_second, $j.timings.predicted_per_token_ms |
            Out-File $out -Append -Encoding utf8
    }
    $tg = Select-String -Path $log -Pattern 'tg_3s = *([0-9.]+)' -AllMatches |
          ForEach-Object { $_.Matches } | ForEach-Object { [double]$_.Groups[1].Value }
    if ($tg.Count -ge 4) {
        # BUG CORRETTO (16/8): qui le due espressioni NON sono la stessa cosa e non prendono la stessa correzione.
        # [int]($tg.Count/2) e' l'INIZIO della fetta "seconda meta'", non una mediana: col banker's rounding il confine
        # ballava fra i Count dispari (5 -> 2, il campione centrale dentro; 7 -> 4, il centrale fuori). Floor lo rende
        # deterministico -- la finestra include sempre il centrale e non si restringe mai sotto la meta'; sui Count pari
        # non cambia nulla. La seconda invece e' il bug pieno: [int]($u.Count/2) cade un passo sopra il centro per Count
        # 3,7,11,... (con Count=3 e' il MASSIMO), e qui $u puo' avere 3 campioni. v. RUNBOOK par. 7.4
        $u = ($tg[[math]::Floor($tg.Count/2)..($tg.Count-1)] | Sort-Object)
        "  tg_3s seconda meta': mediana {0:N2} ({1} campioni, min {2:N2} max {3:N2})" -f `
            $u[[math]::Floor(($u.Count-1)/2)], $u.Count, $u[0], $u[-1] | Out-File $out -Append -Encoding utf8
    }
    if (-not $srv.HasExited) { $srv.Kill() }
    Start-Sleep 8
    Get-Process llama-server -EA SilentlyContinue | ForEach-Object { $_.Kill() }
    Start-Sleep 40
    "" | Out-File $out -Append -Encoding utf8
    $porta++
}
'FINE' | Out-File $out -Append -Encoding utf8
