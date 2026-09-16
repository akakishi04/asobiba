param(
    [Parameter(Mandatory = $true)][string]$C162Summary,
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
$report = $null
function Assert-NativeExit([string]$Context) {
    if ($LASTEXITCODE -ne 0) { throw "$Context failed; exit code = $LASTEXITCODE" }
}
try {
    Write-Output "=== FOLD C163 V5-E live evidence-container bridge ==="
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
    $required[$C162Summary] = "0DA31284AF3A58BA052BA9629E321520F7F2DBB9352A32C52C3892ADFF65CDAC"
    $required[$C160Summary] = "1C99AB5395E67C859A7730E1A9111D4595E2668B85CB56D0A31DFFF79AEA4BBD"
    $required["runs\chatgpt-last-result.json"] = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
    $required["runs\fixtures\v05-c-composition-20260921.pt"] = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
    foreach ($path in $required.Keys) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required input missing: $path" }
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($before[$path] -ne $required[$path]) { throw "Protected/prerequisite hash mismatch: $path" }
    }
    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-LIVE-EVIDENCE-CONTAINER-BRIDGE"
    Write-Output "rankers = 24 CUDA float32/highest; routers = 3 CPU; threads = 2"
    Write-Output "episodes = 82944; streams = 48; queries_per_stream = 1728; expected_focused_tests = 614"
    Write-Output "decisions = 165888; acquisitions = 82944; restored_refs = 82944; reads = 165888; vectors = 10616832"
    Write-Output "native_control_calls = 82944; adapted_output_calls = 82944; guard_calls = 768"
    Write-Output "training = 0; fresh_seeds = 0; source_checkpoints_and_semantic_boundary_unchanged = True"
    Write-Output "historical_emitter_modified = False; production_runtime_modified = False; Gate_E = NOT_PASSED"
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
        "tests_lm.test_v05_c162_evidence_container"
        "tests_lm.test_v05_c163_live_container_bridge"
    )
    $count = & $python -c "import sys,unittest; print(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]).countTestCases())" @tests
    Assert-NativeExit "Counting focused tests"
    if ($count -ne "614") { throw "Expected 614 focused tests, got $count" }
    & $python -m unittest @tests -v
    Assert-NativeExit "C163 focused regression"
    Write-Output "=== C163 live container-adapted composition ==="
    $out = Join-Path "runs" ("c163-v5e-live-container-bridge-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c163_live_container_bridge `
        --c162-summary $C162Summary --c160-summary $C160Summary --output-dir $out
    Assert-NativeExit "C163 integration execution"
    $summary = Join-Path $out "summary.json"
    $report = Get-Content -LiteralPath $summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C163-v5e-live-evidence-container-bridge" -or $report.stage -ne "V5-E-LIVE-EVIDENCE-CONTAINER-BRIDGE" -or $report.status -notin @("PASS", "FAIL")) { throw "Wrong experiment/result" }
    if ($report.commit_sha -ne $commit) { throw "Result HEAD mismatch" }
    if ($report.diagnostic_execution_valid -ne $true -or $report.production_runtime_modified -ne $false -or $report.gate_e_candidate -ne $false) { throw "Invalid result controls" }
    $s = $report.summary
    if ($s.training_steps -ne 0 -or $s.fresh_seed_count -ne 0 -or $s.live_query_selection -ne $true -or $s.live_cycle_exercised -ne $true -or $s.structured_result_exercised -ne $true -or $s.answer_generation_exercised -ne $false -or $s.production_state_commit -ne $false -or $s.new_evidence_epoch -ne $false) { throw "Unexpected scope" }
    if (($report.status -eq "PASS") -ne ($s.live_container_bridge_gate_passed -eq $true)) { throw "Status/gate mismatch" }
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
    Write-Output "=== C163 POSTCHECK ==="
    try {
        $postcheckOk = $before.Count -eq 4
        foreach ($path in $before.Keys) {
            $ok = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $before[$path]
            Write-Output "$path preserved = $ok"
            $postcheckOk = $postcheckOk -and $ok
        }
        if ($null -ne $report) {
            $allInputs = $true
            $inputCount = 0
            foreach ($property in $report.input_sha256.PSObject.Properties) {
                $actual = (Get-FileHash -LiteralPath $property.Name -Algorithm SHA256).Hash
                $allInputs = $allInputs -and ($actual -eq $property.Value)
                $inputCount++
            }
            Write-Output "all_consumed_inputs_preserved = $allInputs; checked = $inputCount"
            $postcheckOk = $postcheckOk -and $allInputs
            foreach ($property in $report.source_blobs.PSObject.Properties) {
                $actual = git rev-parse ("HEAD:" + $property.Name)
                Assert-NativeExit "Checking historical blob"
                if ($actual -ne $property.Value) { throw "Historical source changed: $($property.Name)" }
            }
            Write-Output "historical_source_blobs_preserved = True"
        }
        else { $postcheckOk = $false }
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
if (-not $postcheckOk) { throw "C163 postcheck failed; do not accept result" }
Write-Output "run_execution_valid = True"
