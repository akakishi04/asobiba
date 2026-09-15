param(
    [Parameter(Mandatory = $true)][string]$C143Summary,
    [Parameter(Mandatory = $true)][string]$ExpectedHead
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = Join-Path (Get-Location) ".venv-py31315\Scripts\python.exe"
$manifest = Join-Path (Split-Path -Parent $C143Summary) "evaluation-manifest.json"
$out = Join-Path (Split-Path -Parent $C143Summary) "c144-factor-mismatch-attribution.json"

Write-Output "=== FOLD C144 V5-E factor mismatch attribution ==="

$branch = git branch --show-current
if ($LASTEXITCODE -ne 0) { throw "Failed to read branch" }
if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }

$commit = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw "Failed to read HEAD" }
if ($commit -ne $ExpectedHead) { throw "Unexpected HEAD: $commit; expected $ExpectedHead" }

$dirty = @(git status --porcelain --untracked-files=no)
if ($LASTEXITCODE -ne 0) { throw "Failed to check tracked tree" }
if ($dirty.Count -gt 0) { throw "Tracked working tree is not clean" }

foreach ($path in @($python, $C143Summary, $manifest)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file missing: $path" }
}

$summaryHashBefore = (Get-FileHash -LiteralPath $C143Summary -Algorithm SHA256).Hash
$manifestHashBefore = (Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash

Write-Output "branch = $branch"
Write-Output "commit = $commit"
Write-Output "stage = V5-E-FACTOR-MISMATCH-ATTRIBUTION"
Write-Output "analysis_only = True"
Write-Output "model_loading = False"
Write-Output "additional_scoring = False"
Write-Output "additional_training_steps = 0"
Write-Output "expected_focused_tests = 162"
Write-Output "C143_summary_sha256_before = $summaryHashBefore"
Write-Output "evaluation_manifest_sha256_before = $manifestHashBefore"

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
)
& $python -m unittest @tests -v
if ($LASTEXITCODE -ne 0) { throw "C144 focused regression failed" }

Write-Output "=== C144 analysis ==="
& $python -u -m fold_lm.v05_benchmarks.gate_e_c144_cli `
    --c143-summary $C143Summary `
    --manifest $manifest `
    --output $out
if ($LASTEXITCODE -ne 0) { throw "C144 analysis failed" }

$report = Get-Content -LiteralPath $out -Raw -Encoding UTF8 | ConvertFrom-Json
if ($report.experiment_id -ne "C144-v5e-factor-mismatch-attribution" -or $report.status -ne "PASS") {
    throw "C144 did not produce a valid attribution report"
}

$summaryHashAfter = (Get-FileHash -LiteralPath $C143Summary -Algorithm SHA256).Hash
$manifestHashAfter = (Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash
$dirtyAfter = @(git status --porcelain --untracked-files=no)
if ($LASTEXITCODE -ne 0) { throw "Failed postcheck tree" }
$headAfter = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw "Failed postcheck HEAD" }

Write-Output ""
Write-Output "=== C144 POSTCHECK ==="
Write-Output "C143_summary_preserved = $($summaryHashAfter -eq $summaryHashBefore)"
Write-Output "evaluation_manifest_preserved = $($manifestHashAfter -eq $manifestHashBefore)"
Write-Output "repository_tracked_clean = $($dirtyAfter.Count -eq 0)"
Write-Output "execution_HEAD_preserved = $($headAfter -eq $commit)"
Write-Output "production_runtime_modified = False"
Write-Output "gate_e_candidate = False"
Write-Output "output = $out"
Write-Output "run_execution_valid = True"
