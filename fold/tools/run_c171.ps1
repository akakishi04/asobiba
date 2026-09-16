param(
    [Parameter(Mandatory = $true)][string]$C170Summary,
    [Parameter(Mandatory = $true)][string]$ExpectedHead
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) ".venv-py31315\Scripts\python.exe"
$before = @{}
$commit = $null
$executionError = $null
$completed = $false
$postcheckOk = $false
function Assert-NativeExit([string]$Context) {
    if ($LASTEXITCODE -ne 0) { throw "$Context failed; exit code = $LASTEXITCODE" }
}
try {
    Write-Output "=== FOLD C171 V5-E bounded derived result contract ==="
    $branch = git branch --show-current
    Assert-NativeExit "Reading branch"
    $commit = git rev-parse HEAD
    Assert-NativeExit "Reading HEAD"
    if ($branch -ne "feat/sft-target-loss" -or $commit -ne $ExpectedHead) { throw "Unexpected branch/HEAD" }
    $dirty = @(git status --porcelain --untracked-files=no)
    Assert-NativeExit "Checking tracked tree"
    if ($dirty.Count -gt 0) { throw "Tracked tree is not clean" }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python environment missing" }
    $required = @{}
    $required[$C170Summary] = "A1858CD65A56B5CAD09B1E339500F7F8A9011C4F1DE721300C3A77EE11F1183E"
    $required["runs\chatgpt-last-result.json"] = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
    $required["runs\fixtures\v05-c-composition-20260921.pt"] = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
    foreach ($path in $required.Keys) {
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($before[$path] -ne $required[$path]) { throw "Protected/prerequisite hash mismatch: $path" }
    }
    & $python -c "import sys; from pathlib import Path; from fold_lm.v05_benchmarks import gate_e_c171_derived_result as b; b.protect_sources(Path.cwd(),b.validate_parent(sys.argv[1])); print('source_precheck = PASS')" $C170Summary
    Assert-NativeExit "Source precheck"
    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-BOUNDED-DERIVED-RESULT-CONTRACT"
    Write-Output "proof_checks = 600; reference = 504; malformed = 48; unusable = 14; rebound = 16; resources = 8; capacity = 8; rule_scope = 2"
    Write-Output "maximum_proof_steps = 7; verifier = hand-written; candidate_producer = symbolic fixture"
    Write-Output "training = 0; learned_forwards = 0; real_acquisitions = 0; evidence_writes = 0; Gate_E = NOT_PASSED"
    Write-Output "expected_focused_tests = 845 (809 existing + 36 new)"
    $tests = @(& $python -c "from pathlib import Path; from fold_lm.v05_benchmarks import gate_e_c171_derived_result as b; print('\n'.join(b.regression_modules(Path.cwd())))")
    Assert-NativeExit "Reading test modules"
    if ($tests.Count -ne 55) { throw "Expected 55 test modules" }
    $count = & $python -c "import sys,unittest; print(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]).countTestCases())" @tests
    Assert-NativeExit "Counting tests"
    if ($count -ne "845") { throw "Expected 845 focused tests, got $count" }
    Write-Output "=== focused regression ==="
    & $python -m unittest @tests -v
    Assert-NativeExit "C171 regression"
    $out = Join-Path "runs" ("c171-v5e-derived-result-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c171_derived_result `
        --c170-summary $C170Summary --output-dir $out --expected-head $ExpectedHead
    Assert-NativeExit "C171 execution"
    $summary = Join-Path $out "summary.json"
    $report = Get-Content -LiteralPath $summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C171-v5e-bounded-derived-result-contract" -or $report.stage -ne "V5-E-BOUNDED-DERIVED-RESULT-CONTRACT" -or $report.commit_sha -ne $commit -or $report.status -notin @("PASS", "FAIL")) { throw "Wrong report identity" }
    if ($report.diagnostic_execution_valid -ne $true -or $report.production_runtime_modified -ne $false -or $report.gate_e_candidate -ne $false) { throw "Wrong execution scope" }
    foreach ($name in @("training_steps", "fresh_seed_count", "learned_forward_calls", "adapter_calls", "evidence_writes")) {
        if ($report.$name -ne 0) { throw "Unexpected activity: $name" }
    }
    $judged = & $python -c "import json,sys; from fold_lm.v05_benchmarks import gate_e_c171_derived_result as b; p=json.load(open(sys.argv[1],encoding='utf-8')); print('PASS' if b.gate(p['summary']) else 'FAIL')" $summary
    Assert-NativeExit "Rechecking report gate"
    if ($judged -ne $report.status) { throw "Gate/status disagreement" }
    foreach ($item in $report.input_sha256.PSObject.Properties) {
        if ((Get-FileHash -LiteralPath $item.Name -Algorithm SHA256).Hash -ne $item.Value) { throw "Input changed: $($item.Name)" }
    }
    if ($report.plan.file -ne "derived-result-plan.json" -or $report.records.file -ne "proof-results.json" -or $report.records.rows -ne 600) { throw "Wrong output declarations" }
    foreach ($artifact in @($report.plan, $report.records)) {
        $path = Join-Path $out $artifact.file
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $artifact.sha256) { throw "Output hash mismatch" }
    }
    if ((Get-Item -LiteralPath (Join-Path $out $report.records.file)).Length -ne $report.records.serialized_bytes) { throw "Output size mismatch" }
    Write-Output "summary = $summary"
    Write-Output "summary_sha256 = $((Get-FileHash -LiteralPath $summary -Algorithm SHA256).Hash)"
    Write-Output "scientific_status = $($report.status)"
    $completed = $true
} catch {
    $executionError = $_
    Write-Output "execution_error = $_"
} finally {
    Write-Output "=== C171 POSTCHECK ==="
    try {
        foreach ($path in $before.Keys) {
            if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $before[$path]) { throw "Protected file changed: $path" }
        }
        $afterHead = git rev-parse HEAD
        Assert-NativeExit "Postcheck HEAD"
        $dirty = @(git status --porcelain --untracked-files=no)
        Assert-NativeExit "Postcheck tree"
        $afterBranch = git branch --show-current
        Assert-NativeExit "Postcheck branch"
        if ($afterHead -ne $commit -or $afterBranch -ne "feat/sft-target-loss" -or $dirty.Count -gt 0) { throw "Repository changed" }
        $postcheckOk = $true
        Write-Output "protected_inputs = preserved; tracked_tree = clean; execution_HEAD = preserved"
    } catch {
        if ($null -eq $executionError) { $executionError = $_ }
        Write-Output "postcheck_error = $_"
    }
    Write-Output "run_execution_valid = $($completed -and $postcheckOk -and $null -eq $executionError)"
}
if ($null -ne $executionError) { throw $executionError }
