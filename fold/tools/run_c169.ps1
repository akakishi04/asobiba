param(
    [Parameter(Mandatory = $true)][string]$C168Summary,
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
    Write-Output "=== FOLD C169 V5-E frozen interface-readiness batch ==="
    $branch = git branch --show-current
    Assert-NativeExit "Reading branch"
    $commit = git rev-parse HEAD
    Assert-NativeExit "Reading HEAD"
    if ($branch -ne "feat/sft-target-loss" -or $commit -ne $ExpectedHead) { throw "Unexpected branch/HEAD" }
    $dirty = @(git status --porcelain --untracked-files=no)
    Assert-NativeExit "Checking tracked tree"
    if ($dirty.Count -gt 0) { throw "Tracked working tree is not clean" }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python environment missing" }
    $required = @{}
    $required[$C168Summary] = "3EF1433D0F2678237F70D1DDDF8B3DE4783BA676FBA15B607281B97F7839124C"
    $required["runs\chatgpt-last-result.json"] = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
    $required["runs\fixtures\v05-c-composition-20260921.pt"] = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
    foreach ($path in $required.Keys) {
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($before[$path] -ne $required[$path]) { throw "Protected/prerequisite hash mismatch: $path" }
    }
    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-FROZEN-INTERFACE-READINESS-BATCH"
    Write-Output "sections = 6; all independent finite-negative sections are collected"
    Write-Output "learned_weights = 0; training = 0; checkpoints = 0; real_adapter_calls = 0"
    Write-Output "scripted_cycles = 8; scripted_policy_calls = 9; fixture_resolver_calls = 6"
    Write-Output "feature_prefix_captures = 19; context_captures = 8; authority_probes = 8; terminal_emissions = 4"
    Write-Output "production_runtime_modified = False; Gate_E = NOT_PASSED"
    Write-Output "expected_focused_tests = 773 (749 existing + 24 new)"
    Write-Output "=== focused regression ==="
    $tests = @(& $python -c "from pathlib import Path; from fold_lm.v05_benchmarks.gate_e_c169_interface_batch import regression_modules; print('\n'.join(regression_modules(Path('.'))))")
    Assert-NativeExit "Reading focused modules"
    if ($tests.Count -ne 53) { throw "Expected 53 test modules, got $($tests.Count)" }
    $count = & $python -c "import sys,unittest; print(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]).countTestCases())" @tests
    Assert-NativeExit "Counting focused tests"
    if ($count -ne "773") { throw "Expected 773 tests, got $count" }
    & $python -m unittest @tests -v
    Assert-NativeExit "C169 focused regression"
    $out = Join-Path "runs" ("c169-v5e-interface-batch-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c169_interface_batch `
        --c168-summary $C168Summary --output-dir $out --expected-head $ExpectedHead
    Assert-NativeExit "C169 diagnostic execution"
    $summary = Join-Path $out "summary.json"
    $report = Get-Content -LiteralPath $summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C169-v5e-frozen-interface-readiness-batch" -or $report.stage -ne "V5-E-FROZEN-INTERFACE-READINESS-BATCH" -or $report.commit_sha -ne $commit) { throw "Wrong experiment/HEAD" }
    if ($report.status -notin @("PASS", "FAIL") -or $report.diagnostic_execution_valid -ne $true -or $report.production_runtime_modified -ne $false -or $report.gate_e_candidate -ne $false) { throw "Invalid result controls" }
    if ($report.summary.sections_completed -ne 6 -or $report.sections.Count -ne 6) { throw "Incomplete batch" }
    if (($report.status -eq "PASS") -ne ($report.summary.interface_ready -eq $true)) { throw "Status/summary mismatch" }
    foreach ($key in @("learned_forward_calls", "checkpoint_loads", "adapter_calls", "training_steps", "fresh_seed_count")) {
        if ($null -eq $report.$key -or $report.$key -ne 0) { throw "Unexpected learned/external work: $key" }
    }
    $planPath = Join-Path $out "diagnostic-plan.json"
    if ($report.plan.file -ne "diagnostic-plan.json" -or (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash -ne $report.plan.sha256) { throw "Plan integrity failure" }
    foreach ($entry in $report.input_sha256.PSObject.Properties) {
        if ((Get-FileHash -LiteralPath $entry.Name -Algorithm SHA256).Hash -ne $entry.Value) { throw "Input changed: $($entry.Name)" }
    }
    Write-Output "summary = $summary"
    Write-Output "summary_sha256 = $((Get-FileHash -LiteralPath $summary -Algorithm SHA256).Hash)"
    Write-Output "scientific_status = $($report.status)"
    foreach ($item in $report.sections) {
        Write-Output "section = $($item.section_id); status = $($item.status); gaps = $($item.gaps.Count); violations = $($item.violations.Count)"
    }
} catch {
    $executionError = $_
    Write-Output "=== C169 EXECUTION ERROR ==="
    Write-Output ($_ | Out-String)
} finally {
    Write-Output "=== C169 POSTCHECK ==="
    try {
        foreach ($path in $before.Keys) {
            if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $before[$path]) { throw "Protected file changed: $path" }
        }
        $after = git rev-parse HEAD
        Assert-NativeExit "Postcheck HEAD"
        $dirty = @(git status --porcelain --untracked-files=no)
        Assert-NativeExit "Postcheck tracked tree"
        if ($null -eq $commit -or $after -ne $commit -or $dirty.Count -ne 0) { throw "HEAD/tree protection failure" }
        $postcheckOk = $true
        Write-Output "protected_inputs = preserved; tracked_tree = clean; execution_HEAD = preserved"
    } catch {
        Write-Output ($_ | Out-String)
        if ($null -eq $executionError) { $executionError = $_ }
    }
    $valid = $postcheckOk -and ($null -eq $executionError) -and ($null -ne $report)
    Write-Output "run_execution_valid = $valid"
}
if ($null -ne $executionError) { throw $executionError }
