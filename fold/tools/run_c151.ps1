param(
    [Parameter(Mandatory=$true)][string]$C150Summary,
    [Parameter(Mandatory=$true)][string]$ExpectedHead
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) ".venv-py31315\Scripts\python.exe"
$manifest = Join-Path (Split-Path -Parent $C150Summary) "evaluation-manifest.json"
$before = @{}
$executionError = $null
$postcheckOk = $false
function Check-Exit([string]$Context) {
    if ($LASTEXITCODE -ne 0) { throw "$Context failed: exit $LASTEXITCODE" }
}
try {
    Write-Output "=== FOLD C151 V5-E cross-split replication ==="
    $branch = git branch --show-current
    Check-Exit "Reading branch"
    $commit = git rev-parse HEAD
    Check-Exit "Reading HEAD"
    $dirty = @(git status --porcelain --untracked-files=no)
    Check-Exit "Checking tracked files"
    if ($branch -ne "feat/sft-target-loss" -or $commit -ne $ExpectedHead -or $dirty.Count -gt 0) {
        throw "Unexpected branch/HEAD or dirty tracked tree"
    }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python missing: $python" }
    $required = @{
        "runs\chatgpt-last-result.json" = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
        "runs\fixtures\v05-c-composition-20260921.pt" = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
        $C150Summary = "7E87A93E60AD334A9077FA132A0DC73DA07A3DA159C6F572D81190B66C8B95E7"
        $manifest = "5A19DE10D8152AC262846682A79A13BB942EEACD7DCA979AFB09B70170EBDD65"
    }
    foreach ($p in $required.Keys) {
        $hash = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
        if ($hash -ne $required[$p]) { throw "Protected/prerequisite mismatch: $p" }
        $before[$p] = $hash
    }
    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-CROSS-SPLIT-REPLICATION"
    Write-Output "new_splits = 4; seeds_per_split = 3; fresh_seeds = 20261721..20261732"
    Write-Output "arms = WITHIN_FACTOR,GLOBAL_CONCEPT; trained_heads = 24"
    Write-Output "training_main_queries = 24; training_main_candidates = 8; updates = 600"
    Write-Output "full_cases_per_arm = 20736; original12_cases_per_arm = 144"
    Write-Output "same_synthetic_task = True; recipe_changed = False; runtime_path_exercised = False"
    Write-Output "expected_focused_tests = 298"
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
    )
    & $python -m unittest @tests -v
    Check-Exit "Focused regression"
    Write-Output "=== C151 benchmark ==="
    $out = Join-Path "runs" ("c151-v5e-cross-split-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c151_cli --c150-summary $C150Summary --output-dir $out
    Check-Exit "C151 execution"
    $summary = Join-Path $out "summary.json"
    $r = Get-Content -LiteralPath $summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($r.experiment_id -ne "C151-v5e-cross-split-replication" -or $r.status -notin @("PASS","FAIL") -or $r.diagnostic_execution_valid -ne $true) {
        throw "Wrong experiment or invalid result"
    }
    if ($r.production_runtime_modified -ne $false -or $r.gate_e_candidate -ne $false -or $r.summary.runtime_path_exercised -ne $false) {
        throw "Unexpected scope flags"
    }
    Write-Output "scientific_status = $($r.status)"
    Write-Output "summary_path = $summary"
    Write-Output "summary_sha256 = $((Get-FileHash -LiteralPath $summary -Algorithm SHA256).Hash)"
}
catch {
    $executionError = $_.Exception.Message
    Write-Output "=== script error ==="
    Write-Output $executionError
}
finally {
    Write-Output "=== C151 POSTCHECK ==="
    try {
        $postcheckOk = $true
        foreach ($p in $before.Keys) {
            $ok = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -eq $before[$p]
            Write-Output "$p preserved = $ok"
            $postcheckOk = $postcheckOk -and $ok
        }
        $dirtyAfter = @(git status --porcelain --untracked-files=no)
        Check-Exit "Postcheck tree"
        $headAfter = git rev-parse HEAD
        Check-Exit "Postcheck HEAD"
        $treeOk = $dirtyAfter.Count -eq 0
        $headOk = $headAfter -eq $ExpectedHead
        $postcheckOk = $postcheckOk -and $treeOk -and $headOk
        Write-Output "repository_tracked_clean = $treeOk"
        Write-Output "execution_HEAD_preserved = $headOk"
        Write-Output "production_runtime_modified = False"
        Write-Output "gate_e_candidate = False"
    }
    catch { $postcheckOk = $false; Write-Output "postcheck_error = $($_.Exception.Message)" }
}
if ($executionError) { throw $executionError }
if (-not $postcheckOk) { throw "C151 postcheck failed" }
Write-Output "run_execution_valid = True"
