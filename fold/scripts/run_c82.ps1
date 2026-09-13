$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repo = "M:\asobiba\fold"
$python = "$repo\.venv-py31315\Scripts\python.exe"
$log = "$repo\runs\chatgpt-last.log"
$resultPath = "$repo\runs\chatgpt-last-result.json"
$fixturePath = "$repo\runs\fixtures\v05-c-composition-20260921.pt"
$expectedResultHash = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
$expectedFixtureHash = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
$requiredBaseCommit = "14d29899161665755b0738b81f4d2f0d1c909cfb"

New-Item -ItemType Directory -Force "$repo\runs" | Out-Null
"=== FOLD C82 production serialized-artifact gate ===" |
    Set-Content -LiteralPath $log -Encoding UTF8

try {
    Set-Location $repo
    $branch = (& git branch --show-current | Out-String).Trim()
    if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }
    $dirty = (& git status --porcelain --untracked-files=no | Out-String).Trim()
    if (-not [string]::IsNullOrWhiteSpace($dirty)) { throw "Tracked working tree is not clean" }

    "=== syncing repository ===" | Tee-Object -FilePath $log -Append
    & git pull --rebase origin feat/sft-target-loss 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

    $head = (& git rev-parse HEAD | Out-String).Trim()
    & git merge-base --is-ancestor $requiredBaseCommit $head
    if ($LASTEXITCODE -ne 0) { throw "Required C82 base commit is not an ancestor of HEAD" }

    $c81Dir = Get-ChildItem -LiteralPath "$repo\runs" -Directory -Filter "c81-production-runtime-*" |
        Sort-Object LastWriteTime -Descending |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "summary.json") } |
        Select-Object -First 1
    if ($null -eq $c81Dir) { throw "C81 summary not found" }
    $c81Summary = Join-Path $c81Dir.FullName "summary.json"
    $c81 = Get-Content -LiteralPath $c81Summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($c81.experiment_id -ne "C81-shared-basis-production-large-shape-runtime") {
        throw "Wrong C81 summary"
    }
    if ($c81.status -ne "PASS" -or -not [bool]$c81.summary.production_runtime_gate_passed) {
        throw "C81 runtime gate is not accepted"
    }

    $before = (Get-FileHash -LiteralPath $resultPath -Algorithm SHA256).Hash
    $fixtureBefore = (Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256).Hash
    if ($before -ne $expectedResultHash) { throw "Protected C37 hash mismatch" }
    if ($fixtureBefore -ne $expectedFixtureHash) { throw "Fixture hash mismatch" }

    @(
        "branch = $branch"
        "commit = $head"
        "C81_summary = $c81Summary"
        "width = 3072"
        "profiles = lean:1/16,medium:1/8,rank3_bridge:3/16"
        "serialized_ratio_ceiling = 0.83"
        "artifact_flow = torch.save -> size/hash -> torch.load(weights_only=True) -> exact check -> delete"
        ""
        "=== import preflight ==="
    ) | Tee-Object -FilePath $log -Append

    & $python -c "import fold_lm.v05_benchmarks.gate_c_shared_basis_production_serialized_artifact as m; print('C82 import OK:', m.EXPERIMENT_ID, m.WIDTH, m.MAX_SERIALIZED_RATIO)" 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "C82 import failed" }

    $outDir = "$repo\runs\c82-production-artifact-$([guid]::NewGuid().ToString('N'))"
    "output_directory = $outDir" | Tee-Object -FilePath $log -Append
    "=== C82 benchmark ===" | Tee-Object -FilePath $log -Append

    & $python -u -m fold_lm.v05_benchmarks.gate_c_shared_basis_production_serialized_artifact `
        --c81-summary $c81Summary `
        --output-dir $outDir 2>&1 |
        Tee-Object -FilePath $log -Append
    $runCode = $LASTEXITCODE
    if ($runCode -ne 0) { throw "C82 benchmark failed: $runCode" }

    $summaryPath = Join-Path $outDir "summary.json"
    if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) { throw "C82 summary missing" }
    $s = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json

    $after = (Get-FileHash -LiteralPath $resultPath -Algorithm SHA256).Hash
    $fixtureAfter = (Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256).Hash
    $dirtyAfter = (& git status --porcelain --untracked-files=no | Out-String).Trim()

    @(
        ""
        "=== C82 SUMMARY ==="
        "status = $($s.status)"
        "production_serialized_artifact_gate_passed = $($s.summary.production_serialized_artifact_gate_passed)"
        "all_serialized_ratios_within_ceiling = $($s.summary.all_serialized_ratios_within_ceiling)"
        "all_state_dict_roundtrips_exact = $($s.summary.all_state_dict_roundtrips_exact)"
        "no_materialized_effective_weight_keys = $($s.summary.no_materialized_effective_weight_keys)"
        "dense_serialized_bytes = $($s.summary.dense_serialized_bytes)"
    ) | Tee-Object -FilePath $log -Append

    foreach ($row in $s.summary.records) {
        "profile=$($row.profile) rank=$($row.rank) serialized_ratio=$($row.serialized_ratio) resident_ratio=$($row.resident_ratio) roundtrip=$($row.shared_roundtrip_exact)" |
            Tee-Object -FilePath $log -Append
    }

    @(
        "C37_preserved = $($after -eq $expectedResultHash)"
        "fixture_preserved = $($fixtureAfter -eq $expectedFixtureHash)"
        "repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))"
        "output_directory = $outDir"
        "production_runtime_modified = False"
        "default_dense_runtime_changed = False"
        "gate_c_candidate = False"
        ""
        "=== script error, if any ==="
    ) | Tee-Object -FilePath $log -Append
}
catch {
    ($_ | Out-String) | Tee-Object -FilePath $log -Append
    throw
}
