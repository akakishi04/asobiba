param(
    [Parameter(Mandatory = $true)][string]$C167Summary,
    [Parameter(Mandatory = $true)][string]$ExpectedHead
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) ".venv-py31315\Scripts\python.exe"
$before = @{}
$executionError = $null
$postcheckOk = $false
$report = $null
$commit = $null
function Assert-NativeExit([string]$Context) {
    if ($LASTEXITCODE -ne 0) { throw "$Context failed; exit code = $LASTEXITCODE" }
}
try {
    Write-Output "=== FOLD C168 V5-E task-necessity input observability ==="
    $branch = git branch --show-current
    Assert-NativeExit "Reading branch"
    $commit = git rev-parse HEAD
    Assert-NativeExit "Reading HEAD"
    if ($branch -ne "feat/sft-target-loss" -or $commit -ne $ExpectedHead) { throw "Unexpected branch/HEAD" }
    $dirty = @(git status --porcelain --untracked-files=no)
    Assert-NativeExit "Checking tracked tree"
    if ($dirty.Count -gt 0) { throw "Tracked working tree is not clean" }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Authoritative Python environment missing" }
    $required = @{}
    $required[$C167Summary] = "5907D4B2DD4E66A9A2D8A6017B68AB8461A9BFCA6BD90DD01C1774F5C3E020E9"
    $required["runs\chatgpt-last-result.json"] = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
    $required["runs\fixtures\v05-c-composition-20260921.pt"] = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
    foreach ($path in $required.Keys) {
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($before[$path] -ne $required[$path]) { throw "Protected/prerequisite hash mismatch: $path" }
    }
    $sourceJson = & $python -c "import json; from pathlib import Path; from fold_lm.v05_benchmarks.gate_e_c168_necessity_observability import check_sources; print(json.dumps(check_sources(Path.cwd())[1]))"
    Assert-NativeExit "Checking historical source pins"
    $sources = $sourceJson | ConvertFrom-Json
    foreach ($p in $sources.PSObject.Properties) { $before[$p.Name] = $p.Value }
    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-TASK-NECESSITY-INPUT-OBSERVABILITY"
    Write-Output "benchmark: 8 challenge rows (4 semantic cases x 2 stale bits), 4 source controls"
    Write-Output "benchmark: 12 pre-forward captures; no checkpoint/model forward/training/retrieval/live cycle"
    Write-Output "post-selection interface only; logical text is NOT run through C151"
    Write-Output "production_runtime_modified = False; Gate_E = NOT_PASSED"
    Write-Output "expected_focused_tests = 749 (725 existing + 24 new)"
    $tests = @(& $python -c "from pathlib import Path; from fold_lm.v05_benchmarks.gate_e_c168_necessity_observability import regression_modules; print('\n'.join(regression_modules(Path.cwd())))")
    Assert-NativeExit "Reading pinned regression list"
    $count = & $python -c "import sys,unittest; print(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]).countTestCases())" @tests
    Assert-NativeExit "Counting focused tests"
    if ($count -ne "749") { throw "Expected 749 focused tests, got $count" }
    Write-Output "=== focused regression ==="
    & $python -m unittest @tests -v
    Assert-NativeExit "C168 focused regression"
    $out = Join-Path "runs" ("c168-v5e-necessity-observability-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c168_necessity_observability `
        --c167-summary $C167Summary --output-dir $out --expected-head $ExpectedHead
    Assert-NativeExit "C168 diagnostic execution"
    $summary = Join-Path $out "summary.json"
    $report = Get-Content -LiteralPath $summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C168-v5e-task-necessity-input-observability" -or $report.stage -ne "V5-E-TASK-NECESSITY-INPUT-OBSERVABILITY" -or $report.status -notin @("PASS", "FAIL")) { throw "Wrong C168 result" }
    if ($report.commit_sha -ne $commit -or $report.diagnostic_execution_valid -ne $true -or $report.production_runtime_modified -ne $false -or $report.gate_e_candidate -ne $false) { throw "Invalid result scope/identity" }
    if (($report.status -eq "PASS") -ne $report.passed) { throw "Status/gate mismatch" }
    $s = $report.summary
    if ($s.cases -ne 8 -or $s.source_control_cases -ne 4 -or $s.capture_callbacks -ne 12 -or $s.model_forward_calls -ne 0 -or $s.retrieval_calls -ne 0 -or $s.training_steps -ne 0 -or $s.fresh_seed_count -ne 0 -or $s.live_cycle_executions -ne 0) { throw "Unregistered scope" }
    $plan = Join-Path $out $report.plan.file
    if ((Get-FileHash -LiteralPath $plan -Algorithm SHA256).Hash -ne $report.plan.sha256) { throw "Plan output changed" }
    Write-Output "summary = $summary"
    Write-Output "summary_sha256 = $((Get-FileHash -LiteralPath $summary -Algorithm SHA256).Hash)"
    Write-Output "scientific_status = $($report.status)"
} catch {
    $executionError = $_
    Write-Output "=== C168 EXECUTION ERROR ==="
    Write-Output $_
} finally {
    Write-Output "=== C168 POSTCHECK ==="
    try {
        foreach ($path in $before.Keys) {
            if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $before[$path]) { throw "Protected bytes changed: $path" }
        }
        $afterHead = git rev-parse HEAD
        Assert-NativeExit "Postcheck HEAD"
        $dirtyAfter = @(git status --porcelain --untracked-files=no)
        Assert-NativeExit "Postcheck tree"
        if ($afterHead -ne $commit -or $dirtyAfter.Count -gt 0) { throw "HEAD/tree changed" }
        $postcheckOk = $true
        Write-Output "protected_inputs = preserved; tracked_tree = clean; execution_HEAD = preserved"
    } catch {
        Write-Output $_
        if ($null -eq $executionError) { $executionError = $_ }
    }
    $valid = ($null -eq $executionError -and $postcheckOk -and $null -ne $report)
    Write-Output "run_execution_valid = $valid"
}
if ($null -ne $executionError) { throw $executionError }
