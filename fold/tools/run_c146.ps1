param(
    [Parameter(Mandatory = $true)][string]$C145Summary,
    [Parameter(Mandatory = $true)][string]$ExpectedHead
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) ".venv-py31315\Scripts\python.exe"
$c37 = "runs\chatgpt-last-result.json"
$fixture = "runs\fixtures\v05-c-composition-20260921.pt"
$before = @{}
$commit = $null
$executionError = $null
$postcheckOk = $false
function Assert-NativeExit([string]$Context) {
    if ($LASTEXITCODE -ne 0) { throw "$Context failed; exit code = $LASTEXITCODE" }
}
try {
    Write-Output "=== FOLD C146 V5-E all-factor supervised reference ==="
    $branch = git branch --show-current
    Assert-NativeExit "Reading branch"
    if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }
    $commit = git rev-parse HEAD
    Assert-NativeExit "Reading HEAD"
    if ($commit -ne $ExpectedHead) { throw "Unexpected HEAD: $commit; expected $ExpectedHead" }
    $dirty = @(git status --porcelain --untracked-files=no)
    Assert-NativeExit "Checking tracked tree"
    if ($dirty.Count -gt 0) { throw "Tracked working tree is not clean" }
    foreach ($path in @($python,$c37,$fixture,$C145Summary)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file missing: $path" }
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    if ($before[$c37] -ne "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931") { throw "Protected C37 mismatch" }
    if ($before[$fixture] -ne "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E") { throw "Protected fixture mismatch" }
    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-ALL-FACTOR-SUPERVISED-REFERENCE"
    Write-Output "fresh_seeds = 20261661..20261672"
    Write-Output "arms = COLOR_MATERIAL_AUX,ALL_FACTOR_AUX"
    Write-Output "changed_variable = shape_alignment_coefficient_0_to_1"
    Write-Output "train_steps_per_arm = 600"
    Write-Output "full_candidates = 64; queries_per_model = 1728"
    Write-Output "full_cases_per_arm = 20736; original12_cases_per_arm = 144"
    Write-Output "expected_focused_tests = 194"
    Write-Output "runtime_path_exercised = False; inference_oracle_used = False"
    Write-Output "C145_summary_sha256_before = $($before[$C145Summary])"
    Write-Output "=== focused regression ==="
    $tests = @(
        "tests_lm.test_v05_controller"
        "tests_lm.test_v05_reconciliation"
        "tests_lm.test_v05_receipt_scope"
        "tests_lm.test_v05_commit_context"
        "tests_lm.test_v05_receipt_replay"
        "tests_lm.test_v05_receipt_atomic_claim"
        "tests_lm.test_v05_receipt_recovery"
        "tests_lm.test_v05_receipt_recovery_serialization"
        "tests_lm.test_v05_post_transition_recovery"
        "tests_lm.test_v05_c127_negative_control"
        "tests_lm.test_v05_recovery_ownership"
        "tests_lm.test_v05_recovery_fencing"
        "tests_lm.test_v05_recovery_lease_renewal"
        "tests_lm.test_v05_sqlite_recovery_fencing"
        "tests_lm.test_v05_c132_process_fencing"
        "tests_lm.test_v05_retrieval_adapter"
        "tests_lm.test_v05_retrieval_miss_semantics"
        "tests_lm.test_v05_retrieval_bounded_recovery"
        "tests_lm.test_v05_retrieval_query"
        "tests_lm.test_v05_retrieval_content"
        "tests_lm.test_v05_c138_compositional_alias_fixture"
        "tests_lm.test_v05_c139_hash_collision_diagnostic"
        "tests_lm.test_v05_c140_collision_free_multiseed_robustness"
        "tests_lm.test_v05_c141_color_alias_localization"
        "tests_lm.test_v05_c142_color_alignment"
        "tests_lm.test_v05_c143_frozen_factorial_audit"
        "tests_lm.test_v05_c144_factor_mismatch_attribution"
        "tests_lm.test_v05_c145_material_alignment_intervention"
        "tests_lm.test_v05_c146_all_factor_alignment"
    )
    & $python -m unittest @tests -v
    Assert-NativeExit "C146 focused regression"
    Write-Output "=== C146 benchmark ==="
    $out = Join-Path "runs" ("c146-v5e-all-factor-reference-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c146_cli --c145-summary $C145Summary --output-dir $out
    Assert-NativeExit "C146 benchmark execution"
    $summaryPath = Join-Path $out "summary.json"
    $report = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C146-v5e-all-factor-supervised-reference") { throw "Wrong C146 result" }
    if ($report.status -notin @("PASS","FAIL")) { throw "Invalid scientific result" }
    if ($report.diagnostic_execution_valid -ne $true) { throw "C146 execution invalid" }
    if ($report.commit_sha -ne $commit) { throw "Execution commit changed" }
    if ($report.production_runtime_modified -ne $false -or $report.gate_e_candidate -ne $false) { throw "Unexpected production/Gate flag" }
    if ($report.summary.inference_oracle_used -ne $false -or $report.summary.runtime_path_exercised -ne $false) { throw "Unexpected runtime/oracle" }
    if ($report.C145_summary_sha256 -ne $before[$C145Summary]) { throw "Wrong prerequisite identity" }
    Write-Output "scientific_status = $($report.status)"
    Write-Output "summary_path = $summaryPath"
}
catch {
    $executionError = $_.Exception.Message
    Write-Output "=== script error ==="
    Write-Output $executionError
}
finally {
    Write-Output "=== C146 POSTCHECK ==="
    try {
        $filesOk = $true
        foreach ($path in @($c37,$fixture,$C145Summary)) {
            $after = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
            $ok = ($before.ContainsKey($path) -and $after -eq $before[$path])
            if (-not $ok) { $filesOk = $false }
            Write-Output "$path preserved = $ok"
        }
        $dirtyAfter = @(git status --porcelain --untracked-files=no)
        Assert-NativeExit "Postcheck tracked tree"
        $headAfter = git rev-parse HEAD
        Assert-NativeExit "Postcheck HEAD"
        $treeOk = ($dirtyAfter.Count -eq 0)
        $headOk = ($null -ne $commit -and $headAfter -eq $commit)
        $postcheckOk = ($filesOk -and $treeOk -and $headOk)
        Write-Output "repository_tracked_clean = $treeOk"
        Write-Output "execution_HEAD_preserved = $headOk"
        Write-Output "production_runtime_modified = False"
        Write-Output "gate_e_candidate = False"
    } catch {
        Write-Output "postcheck_error = $($_.Exception.Message)"
        $postcheckOk = $false
    }
}
if ($executionError) { throw $executionError }
if (-not $postcheckOk) { throw "C146 postcheck failed; do not accept the result" }
Write-Output "run_execution_valid = True"
