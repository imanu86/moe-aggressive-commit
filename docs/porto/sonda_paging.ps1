# Campionamento indipendente dalla lingua: le classi CIM hanno nomi inglesi
# fissi anche su Windows italiano, a differenza dei percorsi Get-Counter.
#
# La colonna che risponde alla domanda "sono esperti freddi?" e' page_reads:
# PageReadsPerSec conta le operazioni di lettura da disco per risolvere un
# fault duro. Se il buco della GPU coincide con un picco di page_reads, sono
# pagine del modello che non erano in cache.
$out = 'D:\ds4_work\llama_run\sonda_disco.tsv'
"ora`tbraccio`tdisk_read_MBs`tpage_reads`tpages_in`tram_libera_MB`tvram_MB" |
    Out-File $out -Encoding utf8

for ($i = 0; $i -lt 400; $i++) {
    $stato = Get-Content 'D:\ds4_work\llama_run\dspark_lunga.txt' -Tail 40 -Encoding UTF8 -EA SilentlyContinue
    $br = ($stato | Select-String -Pattern 'L[01]_\w+' -AllMatches |
           ForEach-Object { $_.Matches } | Select-Object -Last 1).Value
    if (-not $br) { $br = '?' }

    $d = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -EA SilentlyContinue |
         Where-Object { $_.Name -eq '_Total' }
    $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -EA SilentlyContinue
    $v = (nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) 2>$null

    "{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}" -f (Get-Date -Format 'HH:mm:ss'), $br,
        [math]::Round($d.DiskReadBytesPerSec/1MB,1), $m.PageReadsPerSec,
        $m.PagesInputPerSec, $m.AvailableMBytes, $v |
        Out-File $out -Append -Encoding utf8

    if (Select-String -Path 'D:\ds4_work\llama_run\dspark_lunga.txt' -Pattern '^FINE' -Quiet -EA SilentlyContinue) { break }
    Start-Sleep -Seconds 10
}
