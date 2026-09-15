param(
    [Parameter(Mandatory = $true)][string]$C142Summary,
    [Parameter(Mandatory = $true)][string]$ExpectedHead
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) ".venv-py31315\Scripts\python.exe"
$c37 = "runs\chatgpt-last-result.json"
$fixture = "runs\fixtures\v05-c-composition-20260921.pt"
$executionError = $null
$before = @{}
$commit = $null
$postcheckOk = $false

function Assert-NativeExit([string]$Context) {
    if ($LASTEXITCODE -ne 0) { throw "$Context failed; exit code = $LASTEXITCODE" }
}

try {
    Write-Output "=== FOLD C143 V5-E frozen factorial ranking audit ==="
    $branch = git branch --show-current
    Assert-NativeExit "Reading branch"
    if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }
    $commit = git rev-parse HEAD
    Assert-NativeExit "Reading HEAD"
    if ($commit -ne $ExpectedHead) { throw "Unexpected HEAD: $commit; expected $ExpectedHead" }
    $dirty = @(git status --porcelain --untracked-files=no)
    Assert-NativeExit "Checking tracked tree"
    if ($dirty.Count -ne 0) { throw "Tracked working tree is not clean" }
    foreach ($path in @($python, $c37, $fixture, $C142Summary)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file missing: $path" }
    }
    foreach ($path in @($c37, $fixture, $C142Summary)) {
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    if ($before[$c37] -ne "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931") {
        throw "Protected C37 mismatch"
    }
    if ($before[$fixture] -ne "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E") {
        throw "Protected fixture mismatch"
    }
    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-FROZEN-FACTORIAL-RANKING-AUDIT"
    Write-Output "source_seeds = 20261621..20261632; fresh_seed_count = 0"
    Write-Output "reused_checkpoints = 24; additional_training_steps = 0"
    Write-Output "candidates = 64; combinations = 64; new_combinations = 52"
    Write-Output "alias_variants_per_combination = 27; queries_per_model = 1728"
    Write-Output "total_ranking_cases = 41472; original12_replay_cases = 288"
    Write-Output "expected_focused_tests = 152"
    Write-Output "runtime_path_exercised = False; inference_oracle_used = False"
    Write-Output "C37_result_sha256_before = $($before[$c37])"
    Write-Output "fixture_sha256_before = $($before[$fixture])"
    Write-Output "C142_summary_sha256_before = $($before[$C142Summary])"
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
    )
    & $python -m unittest @tests -v
    Assert-NativeExit "C143 focused regression"
    Write-Output "=== C143 benchmark ==="
    $outDir = Join-Path "runs" ("c143-v5e-frozen-factorial-audit-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c143_cli --c142-summary $C142Summary --output-dir $outDir
    Assert-NativeExit "C143 benchmark execution"
    $summaryPath = Join-Path $outDir "summary.json"
    $report = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C143-v5e-frozen-factorial-ranking-audit" -or
        $report.status -notin @("PASS", "FAIL") -or $report.diagnostic_execution_valid -ne $true) {
        throw "Wrong or invalid C143 result"
    }
    if ($report.production_runtime_modified -ne $false -or $report.gate_e_candidate -ne $false -or
        $report.summary.runtime_path_exercised -ne $false -or $report.summary.inference_oracle_used -ne $false) {
        throw "Unexpected C143 scope flags"
    }
    if ($report.commit_sha -ne $commit) { throw "C143 result commit mismatch" }
    Write-Output "scientific_status = $($report.status)"
    Write-Output "summary_path = $summaryPath"
}
catch {
    $executionError = $_.Exception.Message
    Write-Output "=== script error ==="
    Write-Output $executionError
}
finally {
    Write-Output "=== C143 POSTCHECK ==="
    try {
        $c37Ok = $before.ContainsKey($c37) -and (Get-FileHash -LiteralPath $c37 -Algorithm SHA256).Hash -eq $before[$c37]
        $fixtureOk = $before.ContainsKey($fixture) -and (Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash -eq $before[$fixture]
        $priorOk = $before.ContainsKey($C142Summary) -and (Get-FileHash -LiteralPath $C142Summary -Algorithm SHA256).Hash -eq $before[$C142Summary]
        $dirtyAfter = @(git status --porcelain --untracked-files=no)
        Assert-NativeExit "Postcheck tracked tree"
        $headAfter = git rev-parse HEAD
        Assert-NativeExit "Postcheck HEAD"
        $treeOk = $dirtyAfter.Count -eq 0
        $headOk = $null -ne $commit -and $headAfter -eq $commit
        $postcheckOk = $c37Ok -and $fixtureOk -and $priorOk -and $treeOk -and $headOk
        Write-Output "C37_preserved = $c37Ok"
        Write-Output "fixture_preserved = $fixtureOk"
        Write-Output "C142_summary_preserved = $priorOk"
        Write-Output "repository_tracked_clean = $treeOk"
        Write-Output "execution_HEAD_preserved = $headOk"
        Write-Output "production_runtime_modified = False"
        Write-Output "gate_e_candidate = False"
    }
    catch { Write-Output "postcheck_error = $($_.Exception.Message)"; $postcheckOk = $false }
}
if ($executionError) { throw $executionError }
if (-not $postcheckOk) { throw "C143 postcheck failed; do not accept the result" }
Write-Output "run_execution_valid = True"
Write-Output "=== script error, if any ==="
