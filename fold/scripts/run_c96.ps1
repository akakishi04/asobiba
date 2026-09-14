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
"=== FOLD C96 V5-D production control-lane runtime/VRAM gate ===" | Set-Content $log -Encoding UTF8
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
"validation = production ControlLaneActionRouter",
"widths = 3072,5120",
"fresh_seeds = 20261161,20261162,20261163",
"control_width = 4",
"hidden_width = 4",
"training_steps = 480",
"maximum_runtime_ratio = 0.80",
"maximum_router_core_persistent_ratio = 0.001",
"maximum_router_vram_cost_gib = 0.05",
""
) | Tee-Object -FilePath $log -Append
if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }

$dirty = (git status --porcelain --untracked-files=no | Out-String).Trim()
if ($dirty) { throw "Tracked working tree is not clean:`n$dirty" }

$resultBefore = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
if ($resultBefore -ne $expectedResult -or $fixtureBefore -ne $expectedFixture) { throw "Protected artifact mismatch before C96" }

$c95 = Get-ChildItem "$repo\runs" -Directory -Filter "c95-v5d-control-lane-fresh-*" | Sort-Object LastWriteTime -Descending | Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } | Select-Object -First 1
if ($null -eq $c95) { throw "C95 summary not found" }
$c95Summary = Join-Path $c95.FullName "summary.json"

"=== import preflight ===" | Tee-Object -FilePath $log -Append
& $py -c "import fold_lm.v05_benchmarks.gate_d_control_lane_production_gate as m; print('C96 import OK:', m.EXPERIMENT_ID, m.SEEDS, m.WIDTHS)" 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C96 import failed" }

"=== focused regression ===" | Tee-Object -FilePath $log -Append
& $py -m unittest tests_lm.test_v05_controller tests_lm.test_v05_shared_basis_core -v 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C96 focused regression failed" }

$outDir = "$repo\runs\c96-v5d-production-control-lane-$([guid]::NewGuid().ToString('N'))"
@("", "output_directory = $outDir", "C37_result_sha256_before = $resultBefore", "fixture_sha256_before = $fixtureBefore", "=== C96 benchmark ===") | Tee-Object -FilePath $log -Append

& $py -u -m fold_lm.v05_benchmarks.gate_d_control_lane_production_gate --c95-summary $c95Summary --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
$code = $LASTEXITCODE
if ($code -ne 0) { throw "C96 benchmark failed: $code" }

$s = Get-Content (Join-Path $outDir "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$resultAfter = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
$dirtyAfter = (git status --porcelain --untracked-files=no | Out-String).Trim()

@(
"", "=== C96 SUMMARY ===",
"status = $($s.status)",
"production_control_lane_gate_passed = $($s.summary.production_control_lane_gate_passed)",
"heldout_action_accuracy_min = $($s.summary.heldout_action_accuracy.min)",
"heldout_class_recall_min = $($s.summary.heldout_minimum_class_recall.min)",
"runtime_action_accuracy_min = $($s.summary.runtime_action_accuracy.min)",
"runtime_class_recall_min = $($s.summary.runtime_minimum_class_recall.min)",
"compute_reduction_min = $($s.summary.logical_compute_reduction_vs_fixed_max.min)",
"device_ratio_max = $($s.summary.learned_over_fixed_device.max)",
"wall_ratio_max = $($s.summary.learned_over_fixed_wall.max)",
"router_core_ratio_max = $($s.summary.router_over_core_persistent_ratio.max)",
"router_vram_cost_gib_max = $($s.summary.router_device_free_vram_cost_gib.max)",
"all_outputs_allclose = $($s.summary.all_outputs_allclose)",
"C37_preserved = $($resultAfter -eq $expectedResult)",
"fixture_preserved = $($fixtureAfter -eq $expectedFixture)",
"repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))",
"output_directory = $outDir",
"production_runtime_modified = True",
"gate_d_candidate = $($s.gate_d_candidate)",
"", "=== script error, if any ==="
) | Tee-Object -FilePath $log -Append
