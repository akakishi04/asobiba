param(
    [Parameter(Mandatory = $true)][string]$C154Summary,
    [Parameter(Mandatory = $true)][string]$C153Summary,
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
    Write-Output "=== FOLD C155 V5-E provenance-bound payload dereference ==="
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
    $required[$C154Summary] = "4814C9489B76BFB124E7134336611A3F513EB922083B0ECA251BE533820C4284"
    $required[$C153Summary] = "CDDF360FC2211302D1DAB0ABD8D96038BB3D39AB273F9DEA336DA348D70D3A78"
    $required["runs\chatgpt-last-result.json"] = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
    $required["runs\fixtures\v05-c-composition-20260921.pt"] = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
    foreach ($path in $required.Keys) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file missing: $path" }
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($before[$path] -ne $required[$path]) { throw "Protected/prerequisite hash mismatch: $path" }
    }
    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-PROVENANCE-BOUND-PAYLOAD-DEREFERENCE"
    Write-Output "source_states = 48; references = 3072; resolver_calls = 12288"
    Write-Output "expected_exact_retrieval_calls = 3072; expected_vectors_scored = 196608"
    Write-Output "model_loading = False; training_steps = 0; fresh_seed_count = 0"
    Write-Output "payload_dereference = True; new_observation_commit = False; Controller = False; ANSWER = False"
    Write-Output "expected_focused_tests = 388"
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
    )
    & $python -m unittest @tests -v
    Assert-NativeExit "C155 focused regression"
    Write-Output "=== C155 payload dereference integration ==="
    $out = Join-Path "runs" ("c155-v5e-payload-dereference-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c155_cli `
        --c154-summary $C154Summary --c153-summary $C153Summary --output-dir $out
    Assert-NativeExit "C155 integration execution"
    $summary = Join-Path $out "summary.json"
    $report = Get-Content -LiteralPath $summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C155-v5e-provenance-bound-payload-dereference" -or $report.status -notin @("PASS", "FAIL")) { throw "Wrong experiment/result" }
    if ($report.commit_sha -ne $commit) { throw "Result HEAD mismatch" }
    if ($report.diagnostic_execution_valid -ne $true -or $report.production_runtime_modified -ne $false -or $report.gate_e_candidate -ne $false) { throw "Invalid result controls" }
    if ($report.summary.payload_dereference_exercised -ne $true -or $report.summary.new_observation_committed -ne $false -or $report.summary.answer_exercised -ne $false) { throw "Unexpected execution scope" }
    if (($report.status -eq "PASS") -ne ($report.summary.payload_dereference_gate_passed -eq $true)) { throw "Status/gate flag mismatch" }
    # Preserve scientific FAIL as a valid measured result, not an execution error.
    Write-Output "scientific_status = $($report.status)"
    Write-Output "summary_path = $summary"
    Write-Output "summary_sha256 = $((Get-FileHash -LiteralPath $summary -Algorithm SHA256).Hash)"
}
catch {
    $executionError = $_.Exception.Message
    Write-Output "=== script error ==="
    Write-Output $executionError
}
finally {
    Write-Output "=== C155 POSTCHECK ==="
    try {
        $postcheckOk = $before.Count -eq 4
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
    catch { $postcheckOk = $false; Write-Output "postcheck_error = $($_.Exception.Message)" }
}
if ($executionError) { throw $executionError }
if (-not $postcheckOk) { throw "C155 postcheck failed; do not accept result" }
Write-Output "run_execution_valid = True"
