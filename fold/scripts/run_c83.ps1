$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repo = "M:\asobiba\fold"
$python = "$repo\.venv-py31315\Scripts\python.exe"
$log = "$repo\runs\chatgpt-last.log"
$branchExpected = "feat/sft-target-loss"
$resultPath = "$repo\runs\chatgpt-last-result.json"
$fixturePath = "$repo\runs\fixtures\v05-c-composition-20260921.pt"
$resultHash = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
$fixtureHash = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"

Set-Location $repo
"=== FOLD C83 production VRAM/headroom priority gate ===" | Set-Content $log -Encoding UTF8
"=== syncing repository ===" | Tee-Object -FilePath $log -Append
& git pull --rebase origin $branchExpected 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

$branch = (& git branch --show-current | Out-String).Trim()
$head = (& git rev-parse HEAD | Out-String).Trim()
if ($branch -ne $branchExpected) { throw "Unexpected branch: $branch" }
$dirty = (& git status --porcelain --untracked-files=no | Out-String).Trim()
if (-not [string]::IsNullOrWhiteSpace($dirty)) { throw "Tracked tree dirty" }

$c82Dir = Get-ChildItem "$repo\runs" -Directory -Filter "c82-production-artifact-*" |
    Sort-Object LastWriteTime -Descending |
    Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } |
    Select-Object -First 1
if ($null -eq $c82Dir) { throw "C82 summary not found" }
$c82Summary = Join-Path $c82Dir.FullName "summary.json"
$c82 = Get-Content $c82Summary -Raw -Encoding UTF8 | ConvertFrom-Json
if ($c82.experiment_id -ne "C82-shared-basis-production-serialized-artifact") { throw "Wrong C82" }
if ($c82.status -ne "PASS" -or -not [bool]$c82.summary.production_serialized_artifact_gate_passed) { throw "C82 not accepted" }

$before = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
if ($before -ne $resultHash) { throw "C37 hash changed" }
if ($fixtureBefore -ne $fixtureHash) { throw "fixture hash changed" }

@(
    "branch = $branch"
    "commit = $head"
    "C82_summary = $c82Summary"
    "width = 5120"
    "batches = 1,8"
    "profiles = lean:1/16,medium:1/8,rank3_bridge:3/16"
    "fresh_process_repeats = 3"
    "primary_metric = incremental device VRAM consumed"
    "minimum_headroom_gain_gib = 0.15"
    ""
    "=== import preflight ==="
) | Tee-Object -FilePath $log -Append

& $python -c "import fold_lm.v05_benchmarks.gate_c_shared_basis_production_vram_headroom as m; print('C83 import OK:', m.EXPERIMENT_ID, m.WIDTH, m.REPEATS, m.MIN_HEADROOM_GAIN_GIB)" 2>&1 |
    Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C83 import failed" }

$outDir = "$repo\runs\c83-vram-headroom-$([guid]::NewGuid().ToString('N'))"
"output_directory = $outDir" | Tee-Object -FilePath $log -Append
"=== C83 benchmark ===" | Tee-Object -FilePath $log -Append

& $python -u -m fold_lm.v05_benchmarks.gate_c_shared_basis_production_vram_headroom `
    --c82-summary $c82Summary `
    --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C83 benchmark failed" }

$summary = Get-Content (Join-Path $outDir "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$after = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
$dirtyAfter = (& git status --porcelain --untracked-files=no | Out-String).Trim()

@(
    ""
    "=== C83 SUMMARY ==="
    "status = $($summary.status)"
    "production_vram_headroom_gate_passed = $($summary.summary.production_vram_headroom_gate_passed)"
    "all_shared_headroom_gains_meet_minimum = $($summary.summary.all_shared_headroom_gains_meet_minimum)"
    "all_shared_peak_allocated_below_dense = $($summary.summary.all_shared_peak_allocated_below_dense)"
    "all_shared_peak_reserved_below_dense = $($summary.summary.all_shared_peak_reserved_below_dense)"
) | Tee-Object -FilePath $log -Append

foreach ($row in $summary.summary.comparisons) {
    "profile=$($row.profile) batch=$($row.batch) headroom_gain_gib=$($row.headroom_gain_gib) dense_ready_gib=$([double]$row.dense_ready_vram_consumed_bytes / 1GB) shared_ready_gib=$([double]$row.shared_ready_vram_consumed_bytes / 1GB)" |
        Tee-Object -FilePath $log -Append
}

@(
    "C37_preserved = $($after -eq $resultHash)"
    "fixture_preserved = $($fixtureAfter -eq $fixtureHash)"
    "repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))"
    "output_directory = $outDir"
) | Tee-Object -FilePath $log -Append
