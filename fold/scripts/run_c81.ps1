$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repo = "M:\asobiba\fold"
$python = "$repo\.venv-py31315\Scripts\python.exe"
$log = "$repo\runs\chatgpt-last.log"
$expectedBranch = "feat/sft-target-loss"
$requiredBaseCommit = "66a365631b621c828cc3152d8d8a89791211da53"
$resultPath = "$repo\runs\chatgpt-last-result.json"
$fixturePath = "$repo\runs\fixtures\v05-c-composition-20260921.pt"
$expectedResultHash = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
$expectedFixtureHash = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"

New-Item -ItemType Directory -Force "$repo\runs" | Out-Null
"=== FOLD C81 production large-shape runtime/resident gate ===" |
    Set-Content -LiteralPath $log -Encoding UTF8

$failure = ""
$outDir = ""
$runCode = "not_run"
$branch = ""
$head = ""
$before = ""
$after = ""
$fixtureBefore = ""
$fixtureAfter = ""

try {
    Set-Location $repo
    $branch = (& git branch --show-current | Out-String).Trim()
    if ($branch -ne $expectedBranch) { throw "Unexpected branch: $branch" }

    $dirty = (& git status --porcelain --untracked-files=no | Out-String).Trim()
    if (-not [string]::IsNullOrWhiteSpace($dirty)) {
        throw "Tracked working tree is not clean:`n$dirty"
    }

    "=== syncing repository ===" | Tee-Object -FilePath $log -Append
    & git pull --rebase origin $expectedBranch 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "git pull --rebase failed" }

    $head = (& git rev-parse HEAD | Out-String).Trim()
    & git merge-base --is-ancestor $requiredBaseCommit $head
    if ($LASTEXITCODE -ne 0) { throw "Required C81 base commit is not an ancestor of HEAD" }

    $before = (Get-FileHash -LiteralPath $resultPath -Algorithm SHA256).Hash
    $fixtureBefore = (Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256).Hash
    if ($before -ne $expectedResultHash) { throw "Protected C37 hash mismatch" }
    if ($fixtureBefore -ne $expectedFixtureHash) { throw "Fixture hash mismatch" }

    @(
        ""
        "branch = $branch"
        "commit = $head"
        "widths = 1024,3072,5120"
        "profiles = lean:1/16,medium:1/8,rank3_bridge:3/16"
        "batches = 1,8"
        "endpoint_persistent_ratio_ceiling = 0.82"
        "endpoint_latency_ratio_ceiling = 1.20"
        "production_class = fold_lm.v05.modules.SharedBasisFixedRoutingCore"
        "execution_mode = gemm_native"
        ""
        "=== import preflight ==="
    ) | Tee-Object -FilePath $log -Append

    & $python -c "import fold_lm.v05_benchmarks.gate_c_shared_basis_production_large_shape_runtime as m; print('C81 import OK:', m.EXPERIMENT_ID, m.WIDTHS, m.PROFILES)" 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "C81 import preflight failed" }

    "" | Tee-Object -FilePath $log -Append
    "=== focused production tests ===" | Tee-Object -FilePath $log -Append
    & $python -m unittest tests_lm.test_v05_shared_basis_core tests_lm.test_v05_shared_basis_execution_mode -v 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "C81 focused tests failed" }

    $outDir = "$repo\runs\c81-production-runtime-$([guid]::NewGuid().ToString('N'))"
    @(
        ""
        "output_directory = $outDir"
        "C37_result_sha256_before = $before"
        "fixture_sha256_before = $fixtureBefore"
        ""
        "=== C81 benchmark ==="
    ) | Tee-Object -FilePath $log -Append

    & $python -u -m fold_lm.v05_benchmarks.gate_c_shared_basis_production_large_shape_runtime `
        --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
    $runCode = $LASTEXITCODE
    if ($runCode -ne 0) { throw "C81 benchmark failed: exit_code=$runCode" }
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

    $summaryPath = if ($outDir) { Join-Path $outDir "summary.json" } else { "" }
    $summaryExists = $summaryPath -and (Test-Path -LiteralPath $summaryPath -PathType Leaf)
    $resultPreserved = ($after -eq $expectedResultHash)
    $fixturePreserved = ($fixtureAfter -eq $expectedFixtureHash)

    $status = "NOT_PASS"
    $gate = "not_available"
    $outputs = "not_available"
    $memory = "not_available"
    $latency = "not_available"
    $endpointLines = @()

    if ($summaryExists) {
        try {
            $s = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $gate = [string]$s.summary.production_runtime_gate_passed
            $outputs = [string]$s.summary.all_outputs_allclose
            $memory = [string]$s.summary.all_width5120_persistent_ratios_within_ceiling
            $latency = [string]$s.summary.all_width5120_latency_ratios_within_ceiling
            foreach ($row in $s.summary.width5120) {
                $endpointLines += "width5120 profile=$($row.profile) batch=$($row.batch) persistent=$($row.full_core_persistent_ratio) latency=$($row.shared_over_dense_latency.median) allclose=$($row.output_allclose)"
            }
            if ($s.status -eq "PASS" -and $runCode -eq 0 -and $resultPreserved -and $fixturePreserved -and $cleanAfter -and [string]::IsNullOrWhiteSpace($failure)) {
                $status = "PASS"
            }
        }
        catch { $failure += ($_ | Out-String) }
    }

    @(
        ""
        "=== C81 SUMMARY ==="
        "status = $status"
        "branch = $branch"
        "commit = $head"
        "exit_code = $runCode"
        "summary_json_created = $summaryExists"
        "C37_result_json_preserved = $resultPreserved"
        "fixture_preserved = $fixturePreserved"
        "repository_tracked_clean = $cleanAfter"
        ""
        "production_runtime_gate_passed = $gate"
        "all_outputs_allclose = $outputs"
        "all_width5120_persistent_ratios_within_ceiling = $memory"
        "all_width5120_latency_ratios_within_ceiling = $latency"
        $endpointLines
        ""
        "output_directory = $outDir"
        "production_runtime_modified = False"
        "default_dense_runtime_changed = False"
        "gate_c_candidate = False"
        ""
        "=== script error, if any ==="
        $failure
    ) | Tee-Object -FilePath $log -Append
}
