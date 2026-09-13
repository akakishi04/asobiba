$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repo = "M:\asobiba\fold"
$python = "$repo\.venv-py31315\Scripts\python.exe"
$log = "$repo\runs\chatgpt-last.log"

$expectedBranch = "feat/sft-target-loss"
$requiredBaseCommit = "6a81c7fb5a29a818cc75aa50fe3379f71b42619c"

$resultPath = "$repo\runs\chatgpt-last-result.json"
$fixturePath = "$repo\runs\fixtures\v05-c-composition-20260921.pt"
$c76Summary = "$repo\runs\c76-rank3-noninferiority-2cd41a1574154914a7cb47525c9419c7\summary.json"

$expectedResultHash = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
$expectedFixtureHash = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"

$branch = ""
$head = ""
$before = ""
$after = ""
$fixtureBefore = ""
$fixtureAfter = ""
$outDir = ""
$runCode = "not_run"
$failure = ""

New-Item -ItemType Directory -Force "$repo\runs" | Out-Null
"=== FOLD C77 final selected-rank recurrence equivalence: RUNNING ===" |
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
        throw "git pull --rebase failed."
    }

    $head = (& git rev-parse HEAD | Out-String).Trim()
    & git merge-base --is-ancestor $requiredBaseCommit $head
    if ($LASTEXITCODE -ne 0) {
        throw "Current HEAD does not contain required C77 base commit: $requiredBaseCommit"
    }

    if (-not (Test-Path -LiteralPath $c76Summary -PathType Leaf)) {
        throw "C76 summary missing: $c76Summary"
    }

    $c76 = Get-Content -LiteralPath $c76Summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($c76.experiment_id -ne "C76-shared-basis-condition-rank3-prospective-noninferiority") {
        throw "Wrong C76 prerequisite."
    }
    if ($c76.status -ne "PASS") {
        throw "C76 prerequisite is not PASS."
    }
    if (-not [bool]$c76.summary.noninferiority_gate_passed) {
        throw "C76 non-inferiority gate did not pass."
    }
    if ([int]$c76.summary.seed_count -ne 24) {
        throw "C76 seed count mismatch."
    }
    if ([math]::Abs([double]$c76.summary.noninferiority_margin_absolute_accuracy - 0.002) -gt 1e-12) {
        throw "C76 prospective margin mismatch."
    }

    $benchmark = "$repo\fold_lm\v05_benchmarks\gate_c_shared_basis_final_selected_rank_recurrence_equivalence.py"
    if (-not (Test-Path -LiteralPath $benchmark -PathType Leaf)) {
        throw "C77 benchmark missing: $benchmark"
    }

    $before = (Get-FileHash -LiteralPath $resultPath -Algorithm SHA256).Hash
    $fixtureBefore = (Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256).Hash
    if ($before -ne $expectedResultHash) {
        throw "Protected C37 hash changed: $before"
    }
    if ($fixtureBefore -ne $expectedFixtureHash) {
        throw "Fixture hash changed: $fixtureBefore"
    }

    @(
        ""
        "branch = $branch"
        "commit = $head"
        "required_base_commit = $requiredBaseCommit"
        "C76_summary = $c76Summary"
        "tasks = condition,composition,language"
        "selected_ranks = condition:3,composition:2,language:4"
        "seeds = 20261001,20261002,20261003"
        "recurrence_depths = 1,2,4,8,16,32,64"
        "rtol = 0.0005"
        "atol = 0.0001"
        ""
        "=== import preflight ==="
    ) | Tee-Object -FilePath $log -Append

    & $python -c `
        "import fold_lm.v05_benchmarks.gate_c_shared_basis_final_selected_rank_recurrence_equivalence as m; print('C77 import OK:', m.EXPERIMENT_ID, m.SELECTED_RANKS, m.SEEDS)" 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "C77 import preflight failed."
    }

    $outDir = "$repo\runs\c77-final-selected-rank-$([guid]::NewGuid().ToString('N'))"

    @(
        ""
        "output_directory = $outDir"
        "C37_result_sha256_before = $before"
        "fixture_sha256_before = $fixtureBefore"
        ""
    ) | Tee-Object -FilePath $log -Append

    & "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\Launch-VsDevShell.ps1" `
        -Arch amd64 `
        -HostArch amd64 2>&1 |
        Tee-Object -FilePath $log -Append

    Set-Location $repo
    Remove-Item Env:CUDA_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:CUDA_HOME -ErrorAction SilentlyContinue
    Remove-Item Env:CUDA_LAUNCH_BLOCKING -ErrorAction SilentlyContinue
    $env:CC = "cl"

    & $python -u -m fold_lm.v05_benchmarks.gate_c_shared_basis_final_selected_rank_recurrence_equivalence `
        --c76-summary $c76Summary `
        --output-dir $outDir 2>&1 |
        Tee-Object -FilePath $log -Append

    $runCode = $LASTEXITCODE
    if ($runCode -ne 0) {
        throw "C77 benchmark failed. exit_code = $runCode"
    }

    $summaryPath = Join-Path $outDir "summary.json"
    if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
        throw "C77 summary.json missing."
    }

    $check = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($check.experiment_id -ne "C77-shared-basis-final-selected-rank-recurrence-equivalence") {
        throw "Wrong experiment executed: $($check.experiment_id)"
    }
    if ($check.status -ne "PASS") {
        throw "C77 execution status was not PASS."
    }
    if ([int]$check.summary.run_count -ne 9) {
        throw "C77 run count mismatch."
    }
    if (-not [bool]$check.summary.seeds_disjoint_from_c76) {
        throw "C77 seed independence check failed."
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

    $summaryExists = (
        $outDir -and
        (Test-Path -LiteralPath "$outDir\summary.json" -PathType Leaf)
    )
    $resultPreserved = ($after -eq $expectedResultHash)
    $fixturePreserved = ($fixtureAfter -eq $expectedFixtureHash)

    $status = if (
        $runCode -eq 0 -and
        $summaryExists -and
        $resultPreserved -and
        $fixturePreserved -and
        $cleanAfter -and
        [string]::IsNullOrWhiteSpace($failure)
    ) { "PASS" } else { "NOT_PASS" }

    $allScores = "not_available"
    $allSemantic = "not_available"
    $allOutputs = "not_available"
    $allRecurrence = "not_available"
    $allFormula = "not_available"
    $valMax = "not_available"
    $recMax = "not_available"
    $recRel = "not_available"

    if ($summaryExists) {
        try {
            $science = Get-Content -LiteralPath "$outDir\summary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
            $allScores = [string]$science.summary.all_validation_scores_equal
            $allSemantic = [string]$science.summary.all_validation_semantic_equal
            $allOutputs = [string]$science.summary.all_validation_outputs_allclose
            $allRecurrence = [string]$science.summary.all_recurrence_allclose
            $allFormula = [string]$science.summary.all_runtime_formula_equivalent
            $valMax = [string]$science.summary.validation_max_abs_gap.max
            $recMax = [string]$science.summary.recurrence_max_abs_gap.max
            $recRel = [string]$science.summary.recurrence_max_relative_l2_gap.max
        }
        catch {
            $failure += ($_ | Out-String)
        }
    }

    @(
        ""
        "=== C77 SUMMARY ==="
        "status = $status"
        "branch = $branch"
        "commit = $head"
        "exit_code = $runCode"
        "summary_json_created = $summaryExists"
        "C37_result_json_preserved = $resultPreserved"
        "fixture_preserved = $fixturePreserved"
        "repository_tracked_clean = $cleanAfter"
        ""
        "all_validation_scores_equal = $allScores"
        "all_validation_semantic_equal = $allSemantic"
        "all_validation_outputs_allclose = $allOutputs"
        "all_recurrence_allclose = $allRecurrence"
        "all_runtime_formula_equivalent = $allFormula"
        "validation_max_abs_gap_max = $valMax"
        "recurrence_max_abs_gap_max = $recMax"
        "recurrence_max_relative_l2_gap_max = $recRel"
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
