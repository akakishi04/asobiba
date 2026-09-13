$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repo = "M:\asobiba\fold"
$python = "$repo\.venv-py31315\Scripts\python.exe"
$log = "$repo\runs\chatgpt-last.log"

$expectedBranch = "feat/sft-target-loss"
$requiredBaseCommit = "57bf064e00545691e0c69effed89d962faeeb5db"
$resultPath = "$repo\runs\chatgpt-last-result.json"
$fixturePath = "$repo\runs\fixtures\v05-c-composition-20260921.pt"
$expectedResultHash = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
$expectedFixtureHash = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"

$branch = ""
$head = ""
$c77Summary = ""
$before = ""
$after = ""
$fixtureBefore = ""
$fixtureAfter = ""
$outDir = ""
$runCode = "not_run"
$failure = ""
$compilePass = $false
$unitPass = $false
$regressionPass = $false

New-Item -ItemType Directory -Force "$repo\runs" | Out-Null
"=== FOLD C78 production Shared-Basis integration: RUNNING ===" |
    Set-Content -LiteralPath $log -Encoding UTF8

try {
    Set-Location $repo
    $branch = (& git branch --show-current | Out-String).Trim()
    if ($branch -ne $expectedBranch) {
        throw "Unexpected branch: $branch"
    }

    $dirty = (& git status --porcelain --untracked-files=no | Out-String).Trim()
    if (-not [string]::IsNullOrWhiteSpace($dirty)) {
        throw "Tracked working tree is not clean:`n$dirty"
    }

    "=== syncing repository ===" | Tee-Object -FilePath $log -Append
    & git pull --rebase origin $expectedBranch 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "git pull --rebase failed"
    }

    $head = (& git rev-parse HEAD | Out-String).Trim()
    & git merge-base --is-ancestor $requiredBaseCommit $head
    if ($LASTEXITCODE -ne 0) {
        throw "Required C78 base commit is not an ancestor of HEAD: $requiredBaseCommit"
    }

    $c77Dir = Get-ChildItem -LiteralPath "$repo\runs" -Directory -Filter "c77-final-selected-rank-*" |
        Sort-Object LastWriteTime -Descending |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "summary.json") } |
        Select-Object -First 1
    if ($null -eq $c77Dir) {
        throw "Accepted C77 summary directory not found"
    }
    $c77Summary = Join-Path $c77Dir.FullName "summary.json"
    $c77 = Get-Content -LiteralPath $c77Summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($c77.experiment_id -ne "C77-shared-basis-final-selected-rank-recurrence-equivalence") {
        throw "Wrong C77 summary: $($c77.experiment_id)"
    }
    if ($c77.status -ne "PASS" -or -not [bool]$c77.summary.all_runtime_formula_equivalent) {
        throw "C77 prerequisite is not accepted"
    }

    $before = (Get-FileHash -LiteralPath $resultPath -Algorithm SHA256).Hash
    $fixtureBefore = (Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256).Hash
    if ($before -ne $expectedResultHash) {
        throw "Protected C37 hash changed before C78: $before"
    }
    if ($fixtureBefore -ne $expectedFixtureHash) {
        throw "Fixture hash changed before C78: $fixtureBefore"
    }

    @(
        ""
        "branch = $branch"
        "commit = $head"
        "required_base_commit = $requiredBaseCommit"
        "C77_summary = $c77Summary"
        "selected_ranks = condition:3,composition:2,language:4"
        "production_class = fold_lm.v05.modules.SharedBasisFixedRoutingCore"
        "default_dense_runtime_changed = False"
        ""
        "=== import preflight ==="
    ) | Tee-Object -FilePath $log -Append

    & $python -c "from fold_lm.v05.modules import SharedBasisFixedRoutingCore; import fold_lm.v05_benchmarks.gate_c_shared_basis_production_optin_integration as m; print('C78 import OK:', SharedBasisFixedRoutingCore.__name__, m.EXPERIMENT_ID, m.SELECTED_RANKS)" 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "C78 import preflight failed"
    }

    & "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\Launch-VsDevShell.ps1" `
        -Arch amd64 -HostArch amd64 2>&1 |
        Tee-Object -FilePath $log -Append

    Set-Location $repo
    Remove-Item Env:CUDA_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:CUDA_HOME -ErrorAction SilentlyContinue
    Remove-Item Env:CUDA_LAUNCH_BLOCKING -ErrorAction SilentlyContinue
    $env:CC = "cl"

    "" | Tee-Object -FilePath $log -Append
    "=== C78 compileall ===" | Tee-Object -FilePath $log -Append
    & $python -m compileall -q "$repo\fold_lm\v05" 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "C78 compileall failed"
    }
    $compilePass = $true

    "" | Tee-Object -FilePath $log -Append
    "=== C78 focused unit tests ===" | Tee-Object -FilePath $log -Append
    & $python -m unittest tests_lm.test_v05_shared_basis_core -v 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "C78 focused Shared-Basis unit tests failed"
    }
    $unitPass = $true

    "" | Tee-Object -FilePath $log -Append
    "=== C78 V5 regression tests ===" | Tee-Object -FilePath $log -Append
    & $python -m unittest discover -s tests_lm -p "test_v05_*.py" -v 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "C78 V5 regression tests failed"
    }
    $regressionPass = $true

    $outDir = "$repo\runs\c78-production-integration-$([guid]::NewGuid().ToString('N'))"
    @(
        ""
        "output_directory = $outDir"
        "C37_result_sha256_before = $before"
        "fixture_sha256_before = $fixtureBefore"
        ""
        "=== C78 benchmark ==="
    ) | Tee-Object -FilePath $log -Append

    & $python -u -m fold_lm.v05_benchmarks.gate_c_shared_basis_production_optin_integration `
        --c77-summary $c77Summary `
        --output-dir $outDir 2>&1 |
        Tee-Object -FilePath $log -Append
    $runCode = $LASTEXITCODE
    if ($runCode -ne 0) {
        throw "C78 benchmark failed. exit_code=$runCode"
    }

    $summaryPath = Join-Path $outDir "summary.json"
    if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
        throw "C78 summary missing"
    }
    $check = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($check.experiment_id -ne "C78-shared-basis-production-optin-integration") {
        throw "Wrong C78 experiment: $($check.experiment_id)"
    }
    if ($check.status -ne "PASS") {
        throw "C78 execution status was not PASS"
    }
}
catch {
    $failure = $_ | Out-String
    $failure | Tee-Object -FilePath $log -Append
}
finally {
    try {
        $after = (Get-FileHash -LiteralPath $resultPath -Algorithm SHA256).Hash
        $fixtureAfter = (Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256).Hash
        Set-Location $repo
        $dirtyAfter = (& git status --porcelain --untracked-files=no | Out-String).Trim()
        $cleanAfter = [string]::IsNullOrWhiteSpace($dirtyAfter)
    }
    catch {
        $failure += ($_ | Out-String)
        $cleanAfter = $false
    }

    $summaryExists = ($outDir -and (Test-Path -LiteralPath "$outDir\summary.json" -PathType Leaf))
    $resultPreserved = ($after -eq $expectedResultHash)
    $fixturePreserved = ($fixtureAfter -eq $expectedFixtureHash)

    $runnerStatus = if (
        $runCode -eq 0 -and $summaryExists -and $resultPreserved -and
        $fixturePreserved -and $cleanAfter -and $compilePass -and $unitPass -and
        $regressionPass -and [string]::IsNullOrWhiteSpace($failure)
    ) { "PASS" } else { "NOT_PASS" }

    $gate = "not_available"
    $initWeights = "not_available"
    $grads = "not_available"
    $scores = "not_available"
    $semantics = "not_available"
    $outputs = "not_available"
    $recurrence = "not_available"
    $roundtrips = "not_available"
    $validationGap = "not_available"
    $recurrenceGap = "not_available"

    if ($summaryExists) {
        try {
            $science = Get-Content -LiteralPath "$outDir\summary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
            $gate = [string]$science.summary.production_integration_gate_passed
            $initWeights = [string]$science.summary.all_initial_effective_weights_allclose
            $grads = [string]$science.summary.all_gradients_allclose
            $scores = [string]$science.summary.all_validation_scores_equal
            $semantics = [string]$science.summary.all_validation_semantic_equal
            $outputs = [string]$science.summary.all_validation_outputs_allclose
            $recurrence = [string]$science.summary.all_production_materialized_recurrence_allclose
            $roundtrips = [string]$science.summary.all_state_dict_roundtrips_exact
            $validationGap = [string]$science.summary.validation_output_max_abs_gap.max
            $recurrenceGap = [string]$science.summary.recurrence_max_abs_gap.max
        }
        catch {
            $failure += ($_ | Out-String)
        }
    }

    @(
        ""
        "=== C78 SUMMARY ==="
        "runner_status = $runnerStatus"
        "branch = $branch"
        "commit = $head"
        "exit_code = $runCode"
        "compileall_passed = $compilePass"
        "focused_unit_tests_passed = $unitPass"
        "v5_regression_tests_passed = $regressionPass"
        "summary_json_created = $summaryExists"
        "C37_result_json_preserved = $resultPreserved"
        "fixture_preserved = $fixturePreserved"
        "repository_tracked_clean = $cleanAfter"
        ""
        "production_integration_gate_passed = $gate"
        "all_initial_effective_weights_allclose = $initWeights"
        "all_gradients_allclose = $grads"
        "all_validation_scores_equal = $scores"
        "all_validation_semantic_equal = $semantics"
        "all_validation_outputs_allclose = $outputs"
        "all_production_materialized_recurrence_allclose = $recurrence"
        "all_state_dict_roundtrips_exact = $roundtrips"
        "validation_output_max_abs_gap_max = $validationGap"
        "recurrence_max_abs_gap_max = $recurrenceGap"
        ""
        "result_sha256_before = $before"
        "result_sha256_after = $after"
        "fixture_sha256_before = $fixtureBefore"
        "fixture_sha256_after = $fixtureAfter"
        "output_directory = $outDir"
        "production_runtime_modified = True"
        "default_dense_runtime_changed = False"
        "gate_c_candidate = False"
        ""
        "=== script error, if any ==="
        $failure
    ) | Tee-Object -FilePath $log -Append
}
