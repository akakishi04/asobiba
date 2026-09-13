$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repo = "M:\asobiba\fold"
$python = "$repo\.venv-py31315\Scripts\python.exe"
$log = "$repo\runs\chatgpt-last.log"
$resultPath = "$repo\runs\chatgpt-last-result.json"
$fixturePath = "$repo\runs\fixtures\v05-c-composition-20260921.pt"
$expectedResultHash = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
$expectedFixtureHash = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
$branchExpected = "feat/sft-target-loss"
$requiredBase = "41b76ccad3a5d1f8cd3000b147b0c44a798386bf"

New-Item -ItemType Directory -Force "$repo\runs" | Out-Null
"=== FOLD C84 V5-D ANSWER/no-op oracle baseline ===" | Set-Content -LiteralPath $log -Encoding UTF8

$failure = ""
$outDir = ""
$runCode = "not_run"
$branch = ""
$head = ""

try {
    Set-Location $repo
    $branch = (& git branch --show-current | Out-String).Trim()
    if ($branch -ne $branchExpected) { throw "Unexpected branch: $branch" }

    $dirty = (& git status --porcelain --untracked-files=no | Out-String).Trim()
    if (-not [string]::IsNullOrWhiteSpace($dirty)) { throw "Tracked tree is dirty:`n$dirty" }

    "=== syncing repository ===" | Tee-Object -FilePath $log -Append
    & git pull --rebase origin $branchExpected 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

    $head = (& git rev-parse HEAD | Out-String).Trim()
    & git merge-base --is-ancestor $requiredBase $head
    if ($LASTEXITCODE -ne 0) { throw "Required C84 base is not an ancestor: $requiredBase" }

    $c83Dir = Get-ChildItem "$repo\runs" -Directory -Filter "c83-vram-headroom-*" |
        Sort-Object LastWriteTime -Descending |
        Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } |
        Select-Object -First 1
    if ($null -eq $c83Dir) { throw "Accepted C83 summary not found" }
    $c83Summary = Join-Path $c83Dir.FullName "summary.json"
    $c83 = Get-Content $c83Summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($c83.experiment_id -ne "C83-shared-basis-production-vram-headroom" -or $c83.status -ne "PASS" -or $c83.summary.production_vram_headroom_gate_passed -ne $true) {
        throw "C83 prerequisite is not accepted"
    }

    $resultBefore = (Get-FileHash $resultPath -Algorithm SHA256).Hash
    $fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
    if ($resultBefore -ne $expectedResultHash) { throw "C37 protected hash changed" }
    if ($fixtureBefore -ne $expectedFixtureHash) { throw "fixture protected hash changed" }

    @(
        "branch = $branch"
        "commit = $head"
        "C83_summary = $c83Summary"
        "stage = V5-D"
        "task = condition"
        "rank = 3"
        "actions = ANSWER/no-op, COMPUTE(update,1)"
        "fresh_seeds = 20261031,20261032,20261033"
        "minimum_mean_exact_delta = -0.002"
        "maximum_compute_actions_per_event = 0.55"
        "minimum_answer_rate = 0.45"
        ""
        "=== import preflight ==="
    ) | Tee-Object -FilePath $log -Append

    & $python -c "import fold_lm.v05_benchmarks.gate_d_condition_answer_noop_oracle_baseline as m; print('C84 import OK:', m.EXPERIMENT_ID, m.SEEDS, m.RANK)" 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "C84 import preflight failed" }

    $outDir = "$repo\runs\c84-v5d-answer-noop-$([guid]::NewGuid().ToString('N'))"
    @(
        ""
        "output_directory = $outDir"
        "C37_result_sha256_before = $resultBefore"
        "fixture_sha256_before = $fixtureBefore"
        "=== C84 benchmark ==="
    ) | Tee-Object -FilePath $log -Append

    & $python -u -m fold_lm.v05_benchmarks.gate_d_condition_answer_noop_oracle_baseline `
        --c83-summary $c83Summary `
        --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
    $runCode = $LASTEXITCODE
    if ($runCode -ne 0) { throw "C84 benchmark failed: exit=$runCode" }
}
catch {
    $failure = $_ | Out-String
    $failure | Tee-Object -FilePath $log -Append
}
finally {
    $resultAfter = (Get-FileHash $resultPath -Algorithm SHA256).Hash
    $fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
    Set-Location $repo
    $dirtyAfter = (& git status --porcelain --untracked-files=no | Out-String).Trim()
    $cleanAfter = [string]::IsNullOrWhiteSpace($dirtyAfter)
    $summaryPath = if ($outDir) { Join-Path $outDir "summary.json" } else { "" }
    $summaryExists = $summaryPath -and (Test-Path $summaryPath)

    $status = "not_available"
    $gate = "not_available"
    $delta = "not_available"
    $compute = "not_available"
    $answer = "not_available"
    if ($summaryExists) {
        $s = Get-Content $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $status = $s.status
        $gate = $s.summary.answer_noop_oracle_gate_passed
        $delta = $s.summary.exact_delta.mean
        $compute = $s.summary.logical_compute_actions_per_event.mean
        $answer = $s.summary.logical_answer_noop_rate.mean
    }

    @(
        ""
        "=== C84 SUMMARY ==="
        "status = $status"
        "branch = $branch"
        "commit = $head"
        "exit_code = $runCode"
        "summary_json_created = $summaryExists"
        "answer_noop_oracle_gate_passed = $gate"
        "mean_exact_delta = $delta"
        "mean_logical_compute_actions_per_event = $compute"
        "mean_logical_answer_noop_rate = $answer"
        "C37_preserved = $($resultAfter -eq $expectedResultHash)"
        "fixture_preserved = $($fixtureAfter -eq $expectedFixtureHash)"
        "repository_tracked_clean = $cleanAfter"
        "output_directory = $outDir"
        "production_runtime_modified = False"
        "gate_d_candidate = False"
        ""
        "=== script error, if any ==="
        $failure
    ) | Tee-Object -FilePath $log -Append
}
