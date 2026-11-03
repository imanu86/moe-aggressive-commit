# Avvia un comando fuori dall'albero dei processi della sessione Claude: lo crea WMI, il genitore e' WmiPrvSE.
# Se la sessione cade, la coda continua; se la coda si incastra, la sessione resta libera. Uscita e errori su file.
#   powershell -NoProfile -File lancia_staccato.ps1 -Nome f28 -Comando "python -u coda_notte.py F28"
param([Parameter(Mandatory)][string]$Nome, [Parameter(Mandatory)][string]$Comando)
$qui = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $qui "$Nome.out"
$riga = "cmd.exe /c $Comando > `"$out`" 2>&1"
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $riga; CurrentDirectory = $qui }
if ($r.ReturnValue -ne 0) { throw "Win32_Process.Create ha risposto $($r.ReturnValue)" }
$p = Get-CimInstance Win32_Process -Filter "ProcessId=$($r.ProcessId)"
$g = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)"
"avviato pid $($r.ProcessId), genitore $($g.Name) $($p.ParentProcessId), uscita in $out"
