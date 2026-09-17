param(
    [Parameter(Mandatory = $true)][string]$C171Summary,
    [Parameter(Mandatory = $true)][string]$ExpectedHead
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) ".venv-py31315\Scripts\python.exe"
$before = @{}
$report = $null
$commit = $null
$executionError = $null
$postcheckOk = $false
function Assert-NativeExit([string]$Context) {
    if ($LASTEXITCODE -ne 0) { throw "$Context failed; exit code = $LASTEXITCODE" }
}
try {
    Write-Output "=== FOLD C172 V5-E typed action runtime boundary ==="
    $branch = git branch --show-current
    Assert-NativeExit "Reading branch"
    $commit = git rev-parse HEAD
    Assert-NativeExit "Reading HEAD"
    if ($branch -ne "feat/sft-target-loss" -or $commit -ne $ExpectedHead) { throw "Unexpected branch/HEAD" }
    $dirty = @(git status --porcelain --untracked-files=no)
    Assert-NativeExit "Checking tracked tree"
    if ($dirty.Count -gt 0) { throw "Tracked tree is not clean" }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Authoritative Python environment missing" }
    $required = @{}
    $required[$C171Summary] = "4509A1E9FA5BF2072AF18AC633FD2EE95BA2DA35AF4AB0DC3BC661437FC9853C"
    $required["runs\chatgpt-last-result.json"] = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
    $required["runs\fixtures\v05-c-composition-20260921.pt"] = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
    foreach ($path in $required.Keys) {
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($before[$path] -ne $required[$path]) { throw "Protected/prerequisite hash mismatch: $path" }
    }
    & $python -c "from pathlib import Path; import sys; from fold_lm.v05_benchmarks import gate_e_c172_action_runtime as b; b.preflight(Path.cwd(),Path(sys.argv[1]),sys.argv[2]); print('source_precheck = PASS')" $C171Summary $ExpectedHead
    Assert-NativeExit "Source and parent precheck"
    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-TYPED-ACTION-RUNTIME-BOUNDARY"
    Write-Output "attempts = 197; groups = 8; named_actions = 6"
    Write-Output "internal_charged = 147 expected; acquisition_reserved = 27 expected; verifier_calls = 46; checked_steps = 28"
    Write-Output "PENDING is reservation only; provider IO = 0; observation writes = 0"
    Write-Output "COMPUTE stages an unverified supplied candidate; no learned model or solver"
    Write-Output "training = 0; fresh_seeds = 0; Gate_E = NOT_PASSED"
    Write-Output "expected_focused_tests = 885 (845 existing + 40 new)"
    $tests = @(& $python -c "from pathlib import Path; from fold_lm.v05_benchmarks import gate_e_c172_action_runtime as b; print('\n'.join(b.regression_modules(Path.cwd())))" 2>&1)
    Assert-NativeExit "Loading focused module list"
    if ($tests.Count -ne 56) { throw "Expected 56 focused test modules" }
    $count = & $python -c "import sys,unittest; print(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]).countTestCases())" @tests
    Assert-NativeExit "Counting focused tests"
    if ($count -ne "885") { throw "Expected 885 tests, got $count" }
    Write-Output "=== focused regression ==="
    & $python -m unittest @tests -v
    Assert-NativeExit "Focused regression"
    $out = Join-Path "runs" ("c172-v5e-action-runtime-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c172_action_runtime `
        --c171-summary $C171Summary --output-dir $out --expected-head $ExpectedHead
    Assert-NativeExit "C172 execution"
    $summary = Join-Path $out "summary.json"
    $report = Get-Content -LiteralPath $summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C172-v5e-typed-action-runtime-boundary" -or $report.stage -ne "V5-E-TYPED-ACTION-RUNTIME-BOUNDARY" -or $report.commit_sha -ne $commit) { throw "Wrong experiment identity" }
    if ($report.status -notin @("PASS", "FAIL") -or $report.diagnostic_execution_valid -ne $true -or $report.production_runtime_modified -ne $false -or $report.gate_e_candidate -ne $false) { throw "Invalid result controls" }
    foreach ($field in @("learned_forward_calls", "real_provider_calls", "actual_acquisitions", "evidence_writes", "training_steps", "fresh_seed_count")) {
        if ($report.$field -ne 0) { throw "Unexpected work: $field" }
    }
    if ($report.summary.calls -ne 197 -or $report.records.rows -ne 197) { throw "Incomplete attempted coverage" }
    & $python -c "from pathlib import Path; import json,sys; from fold_lm.v05_benchmarks import gate_e_c172_action_runtime as b; p=json.loads(Path(sys.argv[1]).read_text()); assert (p['status']=='PASS') == b.gate(p['summary'])" $summary
    Assert-NativeExit "Status/gate consistency"
    foreach ($prop in $report.input_sha256.PSObject.Properties) {
        if ((Get-FileHash -LiteralPath $prop.Name -Algorithm SHA256).Hash -ne $prop.Value) { throw "Consumed input changed: $($prop.Name)" }
    }
    if ($report.plan.file -ne "action-runtime-plan.json" -or $report.records.file -ne "action-results.json") { throw "Unexpected output paths" }
    $plan = Join-Path $out "action-runtime-plan.json"
    $rows = Join-Path $out "action-results.json"
    if ((Get-FileHash -LiteralPath $plan -Algorithm SHA256).Hash -ne $report.plan.sha256) { throw "Plan hash mismatch" }
    if ((Get-FileHash -LiteralPath $rows -Algorithm SHA256).Hash -ne $report.records.sha256 -or (Get-Item -LiteralPath $rows).Length -ne $report.records.serialized_bytes) { throw "Records integrity mismatch" }
    Write-Output "summary = $summary"
    Write-Output "summary_sha256 = $((Get-FileHash -LiteralPath $summary -Algorithm SHA256).Hash)"
    Write-Output "scientific_status = $($report.status)"
} catch {
    $executionError = $_
    Write-Output "=== C172 execution error ==="
    Write-Output $_
} finally {
    Write-Output "=== C172 POSTCHECK ==="
    try {
        foreach ($path in $before.Keys) {
            if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $before[$path]) { throw "Protected input changed: $path" }
        }
        $afterHead = git rev-parse HEAD
        Assert-NativeExit "Reading postcheck HEAD"
        $afterBranch = git branch --show-current
        Assert-NativeExit "Reading postcheck branch"
        $dirty = @(git status --porcelain --untracked-files=no)
        Assert-NativeExit "Postcheck tracked tree"
        if ($afterHead -ne $commit -or $afterBranch -ne "feat/sft-target-loss" -or $dirty.Count -gt 0) { throw "Repository changed during execution" }
        $postcheckOk = $true
        Write-Output "protected_inputs = preserved; tracked_tree = clean; execution_HEAD = preserved"
    } catch {
        if ($null -eq $executionError) { $executionError = $_ }
        Write-Output $_
    }
    $valid = ($null -eq $executionError -and $postcheckOk -and $null -ne $report)
    Write-Output "run_execution_valid = $valid"
}
if ($null -ne $executionError) { throw $executionError }
