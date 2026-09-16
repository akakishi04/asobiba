param(
    [Parameter(Mandatory = $true)][string]$C169Summary,
    [Parameter(Mandatory = $true)][string]$ExpectedHead
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) ".venv-py31315\Scripts\python.exe"
$before = @{}
$report = $null
$executionError = $null
$postcheckOk = $false
function Assert-NativeExit([string]$Context) {
    if ($LASTEXITCODE -ne 0) { throw "$Context failed; exit=$LASTEXITCODE" }
}
try {
    Write-Output "=== FOLD C170 V5-E structured task input contract ==="
    $branch = git branch --show-current
    Assert-NativeExit "Reading branch"
    $head = git rev-parse HEAD
    Assert-NativeExit "Reading HEAD"
    if ($branch -ne "feat/sft-target-loss" -or $head -ne $ExpectedHead) { throw "Unexpected branch/HEAD" }
    $dirty = @(git status --porcelain --untracked-files=no)
    Assert-NativeExit "Checking tracked tree"
    if ($dirty.Count -gt 0) { throw "Tracked tree dirty" }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Authoritative Python missing" }
    $required = @{}
    $required[$C169Summary] = "1A509646A01C26306F6A41B0DFACA968BE39500D12E21BEF7D04B98B82FD2AE6"
    $required["runs\chatgpt-last-result.json"] = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
    $required["runs\fixtures\v05-c-composition-20260921.pt"] = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
    foreach ($path in $required.Keys) {
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($before[$path] -ne $required[$path]) { throw "Protected/prerequisite mismatch: $path" }
    }
    Write-Output "branch = $branch"
    Write-Output "commit = $head"
    Write-Output "stage = V5-E-STRUCTURED-TASK-INPUT-CONTRACT"
    Write-Output "new_schema = fold-structured-task-input-v1; numeric_features = 72; legacy_controller_reuse = False"
    Write-Output "captures = 532 (necessity8 + templates252 + statuses16 + resources256); malformed_controls = 40"
    Write-Output "training = 0; learned_forwards = 0; acquisitions = 0; historical_runtime_modified = False"
    Write-Output "expected_focused_tests = 809 (773 existing + 36 new); Gate_E = NOT_PASSED"
    $tests = @(& $python -c "from pathlib import Path; from fold_lm.v05_benchmarks.gate_e_c170_structured_task_input import regression_modules; print('\n'.join(regression_modules(Path.cwd())))")
    Assert-NativeExit "Reading test list"
    if ($tests.Count -ne 54) { throw "Expected 54 test modules" }
    $count = & $python -c "import sys,unittest; print(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]).countTestCases())" @tests
    Assert-NativeExit "Counting tests"
    if ($count -ne "809") { throw "Expected 809 tests, got $count" }
    Write-Output "=== focused regression ==="
    & $python -m unittest @tests -v
    Assert-NativeExit "C170 focused regression"
    $out = Join-Path "runs" ("c170-v5e-structured-task-input-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c170_structured_task_input `
        --c169-summary $C169Summary --output-dir $out --expected-head $ExpectedHead
    Assert-NativeExit "C170 contract execution"
    $summary = Join-Path $out "summary.json"
    $report = Get-Content -LiteralPath $summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C170-v5e-structured-task-input-contract" -or $report.stage -ne "V5-E-STRUCTURED-TASK-INPUT-CONTRACT" -or $report.commit_sha -ne $ExpectedHead -or $report.status -notin @("PASS", "FAIL")) { throw "Wrong experiment/result" }
    if ($report.diagnostic_execution_valid -ne $true -or $report.production_runtime_modified -ne $false -or $report.gate_e_candidate -ne $false) { throw "Invalid report scope" }
    if ($report.training_steps -ne 0 -or $report.fresh_seed_count -ne 0 -or $report.learned_forward_calls -ne 0 -or $report.adapter_calls -ne 0) { throw "Unexpected learned/acquisition work" }
    if ($report.summary.capture_attempts -ne 532 -or $report.captures.rows -ne 532) { throw "Incomplete captures" }
    foreach ($entry in $report.input_sha256.PSObject.Properties) {
        if ((Get-FileHash -LiteralPath $entry.Name -Algorithm SHA256).Hash -ne $entry.Value) { throw "Input changed: $($entry.Name)" }
    }
    foreach ($entry in @($report.plan, $report.captures)) {
        if ([IO.Path]::GetFileName($entry.file) -ne $entry.file -or $entry.file -match '[\\/]') { throw "Unsafe output filename" }
        $path = Join-Path $out $entry.file
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $entry.sha256) { throw "Output hash mismatch: $path" }
    }
    if ((Get-Item -LiteralPath (Join-Path $out $report.captures.file)).Length -ne $report.captures.serialized_bytes) { throw "Capture size mismatch" }
    Write-Output "summary = $summary"
    Write-Output "summary_sha256 = $((Get-FileHash -LiteralPath $summary -Algorithm SHA256).Hash)"
    Write-Output "scientific_status = $($report.status)"
} catch {
    $executionError = $_
    Write-Output "execution_error = $($_.Exception.Message)"
} finally {
    try {
        foreach ($path in $before.Keys) {
            if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $before[$path]) { throw "Protected file changed: $path" }
        }
        $endHead = git rev-parse HEAD
        Assert-NativeExit "Postcheck HEAD"
        $endBranch = git branch --show-current
        Assert-NativeExit "Postcheck branch"
        $dirty = @(git status --porcelain --untracked-files=no)
        Assert-NativeExit "Postcheck tracked tree"
        if ($endHead -ne $ExpectedHead -or $endBranch -ne "feat/sft-target-loss" -or $dirty.Count -gt 0) { throw "Repository postcheck failed" }
        $postcheckOk = $true
        Write-Output "=== C170 POSTCHECK ==="
        Write-Output "protected_inputs = preserved; tracked_tree = clean; execution_HEAD = preserved"
    } catch {
        if ($null -eq $executionError) { $executionError = $_ }
        Write-Output "postcheck_error = $($_.Exception.Message)"
    }
    $valid = ($null -eq $executionError -and $postcheckOk -and $null -ne $report)
    Write-Output "run_execution_valid = $valid"
}
if ($null -ne $executionError) { throw $executionError }
