$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repo = "M:\asobiba\fold"
$python = "$repo\.venv-py31315\Scripts\python.exe"
$log = "$repo\runs\chatgpt-last.log"

$expectedBranch = "feat/sft-target-loss"
$requiredBaseCommit = "af32ab690bbe7d4d2bc2b9bff12de1e726218b8d"

$resultPath = "$repo\runs\chatgpt-last-result.json"
$fixturePath = "$repo\runs\fixtures\v05-c-composition-20260921.pt"
$c74Summary = "$repo\runs\c74-condition-rank3-d8955161c52a4a83a32188a752c15f95\summary.json"
$c75Summary = "$repo\runs\c75-rank3-rank4-runtime-d0f994ca4e1c47dcad4e2ae5e28a1f0e\summary.json"

$expectedResultHash = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
$expectedFixtureHash = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"

$branch = ""
$head = ""
$before = ""
$after = ""
$fixtureBefore = ""
$fixtureAfter = ""
$outDir = ""
$runCode = -1
$failure = ""
$summaryExists = $false
$cleanAfter = $false
$resultPreserved = $false
$fixturePreserved = $false

New-Item -ItemType Directory -Force "$repo\runs" | Out-Null
"=== FOLD C76 prospective rank3 noninferiority: RUNNING ===" |
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
        throw "Required C76 base commit is not an ancestor of HEAD: $requiredBaseCommit"
    }

    foreach ($path in @($c74Summary, $c75Summary)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required summary missing: $path"
        }
    }

    $c74 = Get-Content -LiteralPath $c74Summary -Raw -Encoding UTF8 | ConvertFrom-Json
    $c75 = Get-Content -LiteralPath $c75Summary -Raw -Encoding UTF8 | ConvertFrom-Json

    if ($c74.experiment_id -ne "C74-shared-basis-condition-rank3-12seed-exhaustive" -or $c74.status -ne "PASS") {
        throw "C74 prerequisite invalid"
    }
    if ($c75.experiment_id -ne "C75-shared-basis-condition-rank3-rank4-runtime-bridge" -or $c75.status -ne "PASS") {
        throw "C75 prerequisite invalid"
    }

    $before = (Get-FileHash -LiteralPath $resultPath -Algorithm SHA256).Hash
    $fixtureBefore = (Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256).Hash
    if ($before -ne $expectedResultHash) {
        throw "Protected C37 hash changed before C76: $before"
    }
    if ($fixtureBefore -ne $expectedFixtureHash) {
        throw "Fixture hash changed before C76: $fixtureBefore"
    }

    @(
        ""
        "branch = $branch"
        "commit = $head"
        "required_base_commit = $requiredBaseCommit"
        "C74_summary = $c74Summary"
        "C75_summary = $c75Summary"
        "seeds = 20260923..20260946"
        "seed_count = 24"
        "rank3 = 3"
        "rank4 = 4"
        "steps = 260"
        "learning_rate = 0.01"
        "batch_size = 32"
        "exhaustive_examples_per_seed = 32512"
        "noninferiority_margin = -0.002"
        "bootstrap_resamples = 100000"
        "bootstrap_unit = seed"
        "bootstrap_one_sided_confidence = 0.95"
        ""
        "=== import preflight ==="
    ) | Tee-Object -FilePath $log -Append

    & $python -c "import fold_lm.v05_benchmarks.gate_c_shared_basis_condition_rank3_prospective_noninferiority as m; print('C76 import OK:', m.EXPERIMENT_ID, m.SEEDS, m.NONINFERIORITY_MARGIN)" 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "C76 import preflight failed"
    }

    $outDir = "$repo\runs\c76-rank3-noninferiority-$([guid]::NewGuid().ToString('N'))"

    @(
        ""
        "output_directory = $outDir"
        "C37_result_sha256_before = $before"
        "fixture_sha256_before = $fixtureBefore"
        ""
    ) | Tee-Object -FilePath $log -Append

    $devShell = "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\Launch-VsDevShell.ps1"
    & $devShell -Arch amd64 -HostArch amd64 2>&1 |
        Tee-Object -FilePath $log -Append

    Set-Location $repo
    Remove-Item Env:CUDA_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:CUDA_HOME -ErrorAction SilentlyContinue
    Remove-Item Env:CUDA_LAUNCH_BLOCKING -ErrorAction SilentlyContinue
    $env:CC = "cl"

    & $python -u -m fold_lm.v05_benchmarks.gate_c_shared_basis_condition_rank3_prospective_noninferiority `
        --c74-summary $c74Summary `
        --c75-summary $c75Summary `
        --output-dir $outDir 2>&1 |
        Tee-Object -FilePath $log -Append
    $runCode = $LASTEXITCODE
    if ($runCode -ne 0) {
        throw "C76 benchmark failed. exit_code=$runCode"
    }

    $summaryPath = Join-Path $outDir "summary.json"
    if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
        throw "C76 summary.json missing"
    }
    $summaryExists = $true

    $check = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($check.experiment_id -ne "C76-shared-basis-condition-rank3-prospective-noninferiority") {
        throw "Wrong experiment executed: $($check.experiment_id)"
    }
    if ($check.status -ne "PASS") {
        throw "C76 experiment execution was not PASS"
    }
    if ([int]$check.summary.seed_count -ne 24) {
        throw "C76 seed count mismatch"
    }
    if ([math]::Abs([double]$check.summary.noninferiority_margin_absolute_accuracy - 0.002) -gt 1e-12) {
        throw "C76 margin changed"
    }
    if ($check.summary.prospective_seeds_disjoint_from_c74 -ne $true) {
        throw "C76 seed independence check failed: value=$($check.summary.prospective_seeds_disjoint_from_c74)"
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

    $resultPreserved = ($after -eq $expectedResultHash)
    $fixturePreserved = ($fixtureAfter -eq $expectedFixtureHash)
    if ($outDir -and (Test-Path -LiteralPath "$outDir\summary.json" -PathType Leaf)) {
        $summaryExists = $true
    }

    $gate = "not_available"
    $meanDelta = "not_available"
    $medianDelta = "not_available"
    $lower95 = "not_available"
    $minimum = "not_available"
    $maximum = "not_available"
    $r3Wins = "not_available"
    $r4Wins = "not_available"
    $ties = "not_available"
    $signP = "not_available"
    $pairedNet = "not_available"
    $independent = "not_available"

    if ($summaryExists) {
        try {
            $science = Get-Content -LiteralPath "$outDir\summary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
            $gate = [string]$science.summary.noninferiority_gate_passed
            $meanDelta = [string]$science.summary.rank3_minus_rank4_exact_delta.mean
            $medianDelta = [string]$science.summary.rank3_minus_rank4_exact_delta.median
            $minimum = [string]$science.summary.rank3_minus_rank4_exact_delta.min
            $maximum = [string]$science.summary.rank3_minus_rank4_exact_delta.max
            $lower95 = [string]$science.summary.rank3_minus_rank4_mean_bootstrap_lower_95
            $r3Wins = [string]$science.summary.rank3_win_seed_count
            $r4Wins = [string]$science.summary.rank4_win_seed_count
            $ties = [string]$science.summary.tie_seed_count
            $signP = [string]$science.summary.rank3_vs_rank4_sign_test_two_sided_p
            $pairedNet = [string]$science.summary.total_paired_net_rank3_advantage
            $independent = [string]$science.summary.prospective_seeds_disjoint_from_c74
        }
        catch {
            $failure += ($_ | Out-String)
        }
    }

    $status = if (
        $runCode -eq 0 -and
        $summaryExists -and
        $resultPreserved -and
        $fixturePreserved -and
        $cleanAfter -and
        [string]::IsNullOrWhiteSpace($failure)
    ) { "PASS" } else { "NOT_PASS" }

    @(
        ""
        "=== C76 SUMMARY ==="
        "status = $status"
        "branch = $branch"
        "commit = $head"
        "exit_code = $runCode"
        "summary_json_created = $summaryExists"
        "C37_result_json_preserved = $resultPreserved"
        "fixture_preserved = $fixturePreserved"
        "repository_tracked_clean = $cleanAfter"
        "prospective_seeds_disjoint_from_c74 = $independent"
        ""
        "noninferiority_margin = -0.002"
        "noninferiority_gate_passed = $gate"
        "rank3_minus_rank4_mean = $meanDelta"
        "rank3_minus_rank4_median = $medianDelta"
        "rank3_minus_rank4_min = $minimum"
        "rank3_minus_rank4_max = $maximum"
        "bootstrap_lower_95 = $lower95"
        "rank3_win_seed_count = $r3Wins"
        "rank4_win_seed_count = $r4Wins"
        "tie_seed_count = $ties"
        "sign_test_two_sided_p = $signP"
        "total_paired_net_rank3_advantage = $pairedNet"
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

if ($runCode -eq 0 -and $summaryExists -and [string]::IsNullOrWhiteSpace($failure)) {
    exit 0
}
exit 1
