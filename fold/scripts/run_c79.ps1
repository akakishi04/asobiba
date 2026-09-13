$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repo = "M:\asobiba\fold"
$python = "$repo\.venv-py31315\Scripts\python.exe"
$log = "$repo\runs\chatgpt-last.log"
$expectedBranch = "feat/sft-target-loss"
$requiredBaseCommit = "9ded20e371b581796e3fad2a2cbf50e9e2d39616"
$resultPath = "$repo\runs\chatgpt-last-result.json"
$fixturePath = "$repo\runs\fixtures\v05-c-composition-20260921.pt"
$expectedResultHash = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
$expectedFixtureHash = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"

$branch = ""
$head = ""
$c78Summary = ""
$outDir = ""
$runCode = "not_run"
$failure = ""
$before = ""
$after = ""
$fixtureBefore = ""
$fixtureAfter = ""

New-Item -ItemType Directory -Force "$repo\runs" | Out-Null
"=== FOLD C79 training arithmetic drift diagnosis: RUNNING ===" |
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
        throw "Required C79 base commit is not an ancestor of HEAD: $requiredBaseCommit"
    }

    $c78Dir = Get-ChildItem -LiteralPath "$repo\runs" -Directory -Filter "c78-production-integration-*" |
        Sort-Object LastWriteTime -Descending |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "summary.json") } |
        Select-Object -First 1
    if ($null -eq $c78Dir) {
        throw "C78 summary directory not found"
    }
    $c78Summary = Join-Path $c78Dir.FullName "summary.json"
    $c78 = Get-Content -LiteralPath $c78Summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($c78.experiment_id -ne "C78-shared-basis-production-optin-integration") {
        throw "Wrong C78 summary: $($c78.experiment_id)"
    }
    if ($c78.status -ne "PASS") {
        throw "C79 requires valid C78 execution"
    }
    if ([bool]$c78.summary.production_integration_gate_passed) {
        throw "C79 diagnosis is not applicable because C78 integration gate passed"
    }
    if (-not [bool]$c78.summary.all_validation_scores_equal) {
        throw "C79 expected C78 validation score equality"
    }
    if (-not [bool]$c78.summary.all_validation_semantic_equal) {
        throw "C79 expected C78 validation semantic equality"
    }
    if ([bool]$c78.summary.all_validation_outputs_allclose) {
        throw "C79 expected C78 tensor-allclose failure"
    }

    $before = (Get-FileHash -LiteralPath $resultPath -Algorithm SHA256).Hash
    $fixtureBefore = (Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256).Hash
    if ($before -ne $expectedResultHash) {
        throw "Protected C37 hash changed before C79: $before"
    }
    if ($fixtureBefore -ne $expectedFixtureHash) {
        throw "Fixture hash changed before C79: $fixtureBefore"
    }

    @(
        ""
        "branch = $branch"
        "commit = $head"
        "required_base_commit = $requiredBaseCommit"
        "C78_summary = $c78Summary"
        "task = language"
        "rank = 4"
        "seeds = 20261011,20261012,20261013"
        "paths = reference_materialized,production_native,production_layout_materialized"
        "checkpoints = 1,10,50,150,300,450,600"
        "production_runtime_modified = False"
        ""
        "=== import preflight ==="
    ) | Tee-Object -FilePath $log -Append

    & $python -c "import fold_lm.v05_benchmarks.gate_c_shared_basis_training_arithmetic_drift_diagnosis as m; print('C79 import OK:', m.EXPERIMENT_ID, m.SEEDS, m.CHECKPOINTS)" 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "C79 import preflight failed"
    }

    & "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\Launch-VsDevShell.ps1" `
        -Arch amd64 -HostArch amd64 2>&1 |
        Tee-Object -FilePath $log -Append

    Set-Location $repo
    Remove-Item Env:CUDA_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:CUDA_HOME -ErrorAction SilentlyContinue
    Remove-Item Env:CUDA_LAUNCH_BLOCKING -ErrorAction SilentlyContinue
    $env:CC = "cl"

    $outDir = "$repo\runs\c79-training-drift-$([guid]::NewGuid().ToString('N'))"
    @(
        ""
        "output_directory = $outDir"
        "C37_result_sha256_before = $before"
        "fixture_sha256_before = $fixtureBefore"
        ""
        "=== C79 benchmark ==="
    ) | Tee-Object -FilePath $log -Append

    & $python -u -m fold_lm.v05_benchmarks.gate_c_shared_basis_training_arithmetic_drift_diagnosis `
        --c78-summary $c78Summary `
        --output-dir $outDir 2>&1 |
        Tee-Object -FilePath $log -Append
    $runCode = $LASTEXITCODE
    if ($runCode -ne 0) {
        throw "C79 benchmark failed. exit_code=$runCode"
    }

    $summaryPath = Join-Path $outDir "summary.json"
    if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
        throw "C79 summary missing"
    }
    $check = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($check.experiment_id -ne "C79-shared-basis-training-arithmetic-drift-diagnosis") {
        throw "Wrong C79 experiment: $($check.experiment_id)"
    }
    if ($check.status -ne "PASS") {
        throw "C79 execution status was not PASS"
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
        $fixturePreserved -and $cleanAfter -and [string]::IsNullOrWhiteSpace($failure)
    ) { "PASS" } else { "NOT_PASS" }

    $supported = "not_available"
    $nativeAllclose = "not_available"
    $matAllclose = "not_available"
    $nativeOut = "not_available"
    $matOut = "not_available"
    $nativeParam = "not_available"
    $matParam = "not_available"

    if ($summaryExists) {
        try {
            $science = Get-Content -LiteralPath "$outDir\summary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
            $supported = [string]$science.summary.training_arithmetic_order_drift_supported
            $nativeAllclose = [string]$science.summary.all_native_final_outputs_allclose
            $matAllclose = [string]$science.summary.all_materialized_layout_final_outputs_allclose
            $nativeOut = [string]$science.summary.native_final_output_max_abs_gap.max
            $matOut = [string]$science.summary.materialized_layout_final_output_max_abs_gap.max
            $nativeParam = [string]$science.summary.native_final_parameter_max_abs_gap.max
            $matParam = [string]$science.summary.materialized_layout_final_parameter_max_abs_gap.max
        }
        catch {
            $failure += ($_ | Out-String)
        }
    }

    @(
        ""
        "=== C79 SUMMARY ==="
        "runner_status = $runnerStatus"
        "branch = $branch"
        "commit = $head"
        "exit_code = $runCode"
        "summary_json_created = $summaryExists"
        "C37_result_json_preserved = $resultPreserved"
        "fixture_preserved = $fixturePreserved"
        "repository_tracked_clean = $cleanAfter"
        ""
        "training_arithmetic_order_drift_supported = $supported"
        "all_native_final_outputs_allclose = $nativeAllclose"
        "all_materialized_layout_final_outputs_allclose = $matAllclose"
        "native_final_output_max_abs_gap_max = $nativeOut"
        "materialized_layout_final_output_max_abs_gap_max = $matOut"
        "native_final_parameter_max_abs_gap_max = $nativeParam"
        "materialized_layout_final_parameter_max_abs_gap_max = $matParam"
        ""
        "result_sha256_before = $before"
        "result_sha256_after = $after"
        "fixture_sha256_before = $fixtureBefore"
        "fixture_sha256_after = $fixtureAfter"
        "output_directory = $outDir"
        "production_runtime_modified = False"
        "gate_c_candidate = False"
        ""
        "=== script error, if any ==="
        $failure
    ) | Tee-Object -FilePath $log -Append
}
