param(
    [Parameter(Mandatory = $true)][string]$C151Summary,
    [Parameter(Mandatory = $true)][string]$ExpectedHead
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) ".venv-py31315\Scripts\python.exe"
$before = @{}
$commit = $null
$executionError = $null
$postcheckOk = $false
function Assert-NativeExit([string]$Context) {
    if ($LASTEXITCODE -ne 0) { throw "$Context failed; exit code = $LASTEXITCODE" }
}
try {
    Write-Output "=== FOLD C152 V5-E frozen persisted retrieval bridge ==="
    $branch = git branch --show-current
    Assert-NativeExit "Reading branch"
    if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }
    $commit = git rev-parse HEAD
    Assert-NativeExit "Reading HEAD"
    if ($commit -ne $ExpectedHead) { throw "Unexpected HEAD: $commit" }
    $dirty = @(git status --porcelain --untracked-files=no)
    Assert-NativeExit "Checking tracked tree"
    if ($dirty.Count -gt 0) { throw "Tracked working tree is not clean" }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python environment missing: $python" }
    $sourceDir = Split-Path -Parent $C151Summary
    $protected = @{
        $C151Summary = "D2B48ACB36D28F0422D09067CC23AF882C812D020A00CCFC8C6E8286FD896AFA"
        (Join-Path $sourceDir "evaluation-manifest.json") = "5A19DE10D8152AC262846682A79A13BB942EEACD7DCA979AFB09B70170EBDD65"
        (Join-Path $sourceDir "split-plan.json") = "DB65D4754E465C55BFC19438F9D50324BB49E928911A53643DEDDC531625F4C0"
        "runs\chatgpt-last-result.json" = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
        "runs\fixtures\v05-c-composition-20260921.pt" = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
    }
    foreach ($path in $protected.Keys) {
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($before[$path] -ne $protected[$path]) { throw "Protected/prerequisite hash mismatch: $path" }
    }
    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-FROZEN-PERSISTED-RETRIEVAL-BRIDGE"
    Write-Output "source_seeds = 20261721..20261732; loaded_heads = 24; fresh_seeds = 0"
    Write-Output "additional_training_steps = 0; orders = CANONICAL,PERMUTED"
    Write-Output "replay_full_cases = 41472; replay_original12_cases = 288"
    Write-Output "actual_retrieval_calls = 82944; exact_records_per_call = 64"
    Write-Output "retrieval = True; provenance = True; controller = False; commit = False; ANSWER = False"
    Write-Output "expected_focused_tests = 322"
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
        "tests_lm.test_v05_c147_composition_order"
        "tests_lm.test_v05_c148_train_consistent_composition"
        "tests_lm.test_v05_c149_margin_accounting"
        "tests_lm.test_v05_c150_global_negatives"
        "tests_lm.test_v05_c151_cross_split"
        "tests_lm.test_v05_c152_persisted_bridge"
    )
    & $python -m unittest @tests -v
    Assert-NativeExit "C152 focused regression"
    Write-Output "=== C152 integration ==="
    $outDir = Join-Path "runs" ("c152-v5e-persisted-bridge-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c152_cli --c151-summary $C151Summary --output-dir $outDir
    Assert-NativeExit "C152 execution"
    $summaryPath = Join-Path $outDir "summary.json"
    $report = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C152-v5e-frozen-persisted-retrieval-bridge") { throw "Wrong experiment result" }
    if ($report.status -notin @("PASS", "FAIL") -or $report.diagnostic_execution_valid -ne $true) {
        throw "C152 did not produce a valid scientific result"
    }
    if ($report.production_runtime_modified -ne $false -or $report.gate_e_candidate -ne $false) {
        throw "Unexpected production/Gate flags"
    }
    if ($report.summary.persisted_retrieval_exercised -ne $true -or
        $report.summary.evidence_commit_exercised -ne $false -or $report.summary.answer_exercised -ne $false) {
        throw "Unexpected integration scope"
    }
    Write-Output "scientific_status = $($report.status)"
    Write-Output "summary_path = $summaryPath"
    Write-Output "summary_sha256 = $((Get-FileHash -LiteralPath $summaryPath -Algorithm SHA256).Hash)"
}
catch {
    $executionError = $_.Exception.Message
    Write-Output "=== script error ==="
    Write-Output $executionError
}
finally {
    Write-Output "=== C152 POSTCHECK ==="
    try {
        $postcheckOk = ($before.Count -eq 5)
        foreach ($path in $before.Keys) {
            $ok = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $before[$path]
            Write-Output "$path preserved = $ok"
            $postcheckOk = $postcheckOk -and $ok
        }
        $dirty = @(git status --porcelain --untracked-files=no)
        Assert-NativeExit "Postcheck tracked tree"
        $headAfter = git rev-parse HEAD
        Assert-NativeExit "Postcheck HEAD"
        $treeOk = $dirty.Count -eq 0
        $headOk = $null -ne $commit -and $headAfter -eq $commit
        $postcheckOk = $postcheckOk -and $treeOk -and $headOk
        Write-Output "repository_tracked_clean = $treeOk"
        Write-Output "execution_HEAD_preserved = $headOk"
        Write-Output "production_runtime_modified = False"
        Write-Output "gate_e_candidate = False"
    }
    catch { $postcheckOk = $false; Write-Output "postcheck_error = $($_.Exception.Message)" }
}
if ($executionError) { throw $executionError }
if (-not $postcheckOk) { throw "C152 postcheck failed; do not accept result" }
Write-Output "run_execution_valid = True"
