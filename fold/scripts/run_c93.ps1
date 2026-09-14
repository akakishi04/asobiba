$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repo = "M:\asobiba\fold"
$py = "$repo\.venv-py31315\Scripts\python.exe"
$log = "$repo\runs\chatgpt-last.log"
$resultPath = "$repo\runs\chatgpt-last-result.json"
$fixturePath = "$repo\runs\fixtures\v05-c-composition-20260921.pt"
$expectedResult = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
$expectedFixture = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"

New-Item -ItemType Directory -Force "$repo\runs" | Out-Null
"=== FOLD C93 V5-D router control-lane diagnosis ===" | Set-Content $log -Encoding UTF8
Set-Location $repo

"=== syncing repository ===" | Tee-Object -FilePath $log -Append
git pull --rebase origin feat/sft-target-loss 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

$branch = (git branch --show-current).Trim()
$head = (git rev-parse HEAD).Trim()
@(
"branch = $branch",
"commit = $head",
"stage = V5-D",
"diagnosis = width-coupled router input vs fixed control lane",
"widths = 3072,5120",
"hidden_width = 4",
"control_width = 4",
"seeds = 20261141,20261142,20261143",
"training_steps = 240",
"minimum_action_accuracy = 0.995",
"minimum_class_recall = 0.99",
""
) | Tee-Object -FilePath $log -Append
if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }

$dirty = (git status --porcelain --untracked-files=no | Out-String).Trim()
if ($dirty) { throw "Tracked working tree is not clean:`n$dirty" }

$resultBefore = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
if ($resultBefore -ne $expectedResult -or $fixtureBefore -ne $expectedFixture) {
    throw "Protected artifact mismatch before C93"
}

$c92 = Get-ChildItem "$repo\runs" -Directory -Filter "c92-v5d-router-convergence-*" |
    Sort-Object LastWriteTime -Descending |
    Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } |
    Select-Object -First 1
if ($null -eq $c92) { throw "C92 summary not found" }
$c92Summary = Join-Path $c92.FullName "summary.json"

"=== import preflight ===" | Tee-Object -FilePath $log -Append
& $py -c "import fold_lm.v05_benchmarks.gate_d_router_control_lane_diagnosis as m; print('C93 import OK:', m.EXPERIMENT_ID, m.WIDTHS, m.CONTROL_WIDTH)" 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C93 import failed" }

"=== focused regression ===" | Tee-Object -FilePath $log -Append
& $py -m unittest tests_lm.test_v05_controller tests_lm.test_v05_shared_basis_core -v 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C93 focused regression failed" }

$outDir = "$repo\runs\c93-v5d-control-lane-$([guid]::NewGuid().ToString('N'))"
@(
"",
"output_directory = $outDir",
"C37_result_sha256_before = $resultBefore",
"fixture_sha256_before = $fixtureBefore",
"=== C93 benchmark ==="
) | Tee-Object -FilePath $log -Append

& $py -u -m fold_lm.v05_benchmarks.gate_d_router_control_lane_diagnosis `
    --c92-summary $c92Summary `
    --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
$code = $LASTEXITCODE
if ($code -ne 0) { throw "C93 benchmark failed: $code" }

$s = Get-Content (Join-Path $outDir "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$resultAfter = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
$dirtyAfter = (git status --porcelain --untracked-files=no | Out-String).Trim()

@(
"",
"=== C93 SUMMARY ===",
"status = $($s.status)",
"full_width_all_pass = $($s.summary.full_width_all_pass)",
"control_lane_all_pass = $($s.summary.control_lane_all_pass)",
"full_width_action_min = $($s.summary.full_width_action_accuracy.min)",
"control_lane_action_min = $($s.summary.control_lane_action_accuracy.min)",
"full_width_recall_min = $($s.summary.full_width_minimum_class_recall.min)",
"control_lane_recall_min = $($s.summary.control_lane_minimum_class_recall.min)",
"control_lane_over_full_width_bytes_mean = $($s.summary.control_lane_over_full_width_bytes.mean)",
"width_coupled_representation_problem_supported = $($s.summary.width_coupled_representation_problem_supported)",
"C37_preserved = $($resultAfter -eq $expectedResult)",
"fixture_preserved = $($fixtureAfter -eq $expectedFixture)",
"repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))",
"output_directory = $outDir",
"production_runtime_modified = False",
"gate_d_candidate = False",
"",
"=== script error, if any ==="
) | Tee-Object -FilePath $log -Append
