param(
    [Parameter(Mandatory = $true)][string]$C160Summary,
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
    Write-Output "=== FOLD C161 V5-E C160 failure-boundary localization ==="
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
    $required[$C160Summary] = "1C99AB5395E67C859A7730E1A9111D4595E2668B85CB56D0A31DFFF79AEA4BBD"
    foreach ($path in $required.Keys) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required input missing: $path" }
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($before[$path] -ne $required[$path]) { throw "Protected/prerequisite hash mismatch: $path" }
    }

    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-C160-FAILURE-BOUNDARY-LOCALIZATION"
    Write-Output "source = preserved C160 summary + 48 gzip traces"
    Write-Output "episodes = 82944; model_execution = 0; retrieval_execution = 0; live_cycle_execution = 0"
    Write-Output "fresh_seeds = 0; training_steps = 0; thresholds_changed = False; checkpoints_changed = False"
    Write-Output "hypothesis = all C160 cycles passed; one common post-cycle terminal rejection reason"
    Write-Output "expected_focused_tests = 558"

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
        "tests_lm.test_v05_c153_evidence_admission"
        "tests_lm.test_v05_state"
        "tests_lm.test_v05_c154_evidence_state_projection"
        "tests_lm.test_v05_c155_payload_dereference"
        "tests_lm.test_v05_c156_request_reobservation"
        "tests_lm.test_v05_c157_controller_bridge"
        "tests_lm.test_v05_c158_live_recovery"
        "tests_lm.test_v05_c159_terminal_result"
        "tests_lm.test_v05_c160_live_query_result"
        "tests_lm.test_v05_c161_failure_localization"
    )
    & $python -m unittest @tests -v
    Assert-NativeExit "C161 focused regression"

    Write-Output "=== C161 preserved-trace diagnostic ==="
    $out = Join-Path "runs" ("c161-v5e-c160-failure-localization-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c161_failure_localization `
        --c160-summary $C160Summary --output-dir $out
    Assert-NativeExit "C161 diagnostic execution"

    $summary = Join-Path $out "summary.json"
    $report = Get-Content -LiteralPath $summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C161-v5e-c160-failure-boundary-localization" -or $report.status -notin @("PASS", "FAIL")) {
        throw "Wrong experiment/result"
    }
    if ($report.commit_sha -ne $commit) { throw "Result HEAD mismatch" }
    if ($report.diagnostic_execution_valid -ne $true -or $report.production_runtime_modified -ne $false -or $report.gate_e_candidate -ne $false) {
        throw "Invalid result controls"
    }
    if ($report.C160_summary_sha256 -ne "1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd") {
        throw "Wrong C160 source"
    }
    if ($report.model_execution -ne $false -or $report.retrieval_execution -ne $false -or $report.live_cycle_execution -ne $false `
        -or $report.training_steps -ne 0 -or $report.fresh_seed_count -ne 0) {
        throw "Unexpected C161 scope"
    }
    if (($report.status -eq "PASS") -ne ($report.summary.single_post_cycle_rejection -eq $true)) {
        throw "Status/hypothesis mismatch"
    }
    Write-Output "scientific_status = $($report.status)"
    Write-Output "localized_reason = $($report.summary.localized_reason)"
    Write-Output "summary_path = $summary"
    Write-Output "summary_sha256 = $((Get-FileHash -LiteralPath $summary -Algorithm SHA256).Hash)"
}
catch {
    $executionError = $_.Exception.Message
    Write-Output "=== script error ==="
    Write-Output $executionError
}
finally {
    Write-Output "=== C161 POSTCHECK ==="
    try {
        $postcheckOk = $before.Count -eq 1
        foreach ($path in $before.Keys) {
            $ok = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $before[$path]
            Write-Output "$path preserved = $ok"
            $postcheckOk = $postcheckOk -and $ok
        }
        $dirtyAfter = @(git status --porcelain --untracked-files=no)
        Assert-NativeExit "Postcheck tracked tree"
        $headAfter = git rev-parse HEAD
        Assert-NativeExit "Postcheck HEAD"
        $treeOk = $dirtyAfter.Count -eq 0
        $headOk = $null -ne $commit -and $headAfter -eq $commit
        $postcheckOk = $postcheckOk -and $treeOk -and $headOk
        Write-Output "repository_tracked_clean = $treeOk"
        Write-Output "execution_HEAD_preserved = $headOk"
        Write-Output "production_runtime_modified = False"
        Write-Output "gate_e_candidate = False"
    }
    catch {
        $postcheckOk = $false
        Write-Output "postcheck_error = $($_.Exception.Message)"
    }
}
if ($executionError) { throw $executionError }
if (-not $postcheckOk) { throw "C161 postcheck failed; do not accept result" }
Write-Output "run_execution_valid = True"
