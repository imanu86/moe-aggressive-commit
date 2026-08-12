$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$cudaPath = Join-Path $repo 'ds4-p4a/ds4_cuda.cu'
$cuda = [System.IO.File]::ReadAllText($cudaPath)

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) {
        throw "QD gate static contract failed: $Message"
    }
}

function Slice-TextBetween(
        [string]$Text, [string]$Start, [string]$End) {
    $startIndex = $Text.IndexOf($Start, [StringComparison]::Ordinal)
    Assert-True ($startIndex -ge 0) "missing start marker: $Start"
    $endIndex = $Text.IndexOf(
        $End, $startIndex + $Start.Length, [StringComparison]::Ordinal)
    Assert-True ($endIndex -gt $startIndex) "missing end marker: $End"
    return $Text.Substring($startIndex, $endIndex - $startIndex)
}

$beforeProcesses = @(Get-Process -Name 'ds4_server' -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Id)

$parser = Slice-TextBetween $cuda `
    'static int cuda_route_io_qd_allow_no_g73_requested(void)' `
    'static int cuda_moe_prefill_vram_seed_per_layer_requested(void)'
foreach ($needle in @(
        'getenv("DS4_CUDA_ROUTE_IO_QD_ALLOW_NO_G73")',
        'strcmp(env, "0") == 0',
        'strcmp(env, "1") == 0',
        'using disabled')) {
    Assert-True ($parser.Contains($needle)) "flag parser contract missing: $needle"
}

foreach ($needle in @(
        'uint32_t route_io_qd_allow_no_g73;',
        'g_moe_expert_cache.route_io_qd_allow_no_g73 = 0u;',
        'cuda_route_io_qd_allow_no_g73_requested();',
        'g_moe_expert_cache.route_io_qd_allow_no_g73 ==',
        'route_io_qd_allow_no_g73 ? 1u : 0u;')) {
    Assert-True ($cuda.Contains($needle)) `
        "cached OFF-default configuration marker missing: $needle"
}

$enforce = Slice-TextBetween $cuda `
    'static int cuda_moe_tiering_enforce_request(' `
    'static void *cuda_moe_route_worker(void *arg)'
Assert-True ($enforce.Contains(
    'if (G73 || cache->route_io_qd_allow_no_g73) {')) `
    'QD planning is not opt-in reachable from the G73-off specialization'
Assert-True (-not $enforce.Contains(
    "if constexpr (G73) {`r`n        if (cache->route_io_qd_requested == 4u") `
    -and -not $enforce.Contains(
    "if constexpr (G73) {`n        if (cache->route_io_qd_requested == 4u")) `
    'historical compile-time G73 QD gate is still present'
foreach ($needle in @(
        'cache->route_io_qd_requested == 4u',
        'g_model_file_valid',
        'g_moe_tiering.compose_router_open',
        '!cuda_nested_residual_layer_required(request.layer_index)',
        'plan_valid && span_count > 0u',
        'cuda_moe_route_io_qd_read(')) {
    Assert-True ($enforce.Contains($needle)) `
        "real QD precondition/path marker missing: $needle"
}

$qdRead = Slice-TextBetween $cuda `
    'static int cuda_moe_route_io_qd_read(' `
    '#endif'
foreach ($forbidden in @(
        'g_cuda_g73_terminal',
        'cuda_g73_terminal',
        'route_g73_outcomes',
        'cuda_g73_classify')) {
    Assert-True (-not $qdRead.Contains($forbidden)) `
        "QD reader unexpectedly depends on G73-only state: $forbidden"
}

$afterProcesses = @(Get-Process -Name 'ds4_server' -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Id)
Assert-True (($beforeProcesses -join ',') -eq ($afterProcesses -join ',')) `
    'static test changed ds4_server process state'

Write-Output (
    'test_qdgate_static.ps1: PASS ' +
    'default=off allow_no_g73=opt-in qd=4 nested=blocked')
