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
"=== FOLD C87 V5-D supervised variable-step router ===" | Set-Content $log -Encoding UTF8
Set-Location $repo

"=== syncing repository ===" | Tee-Object -FilePath $log -Append
git pull --rebase origin feat/sft-target-loss 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

$branch = (git branch --show-current).Trim()
$head = (git rev-parse HEAD).Trim()
@("branch = $branch", "commit = $head", "stage = V5-D", "task = composition", "rank = 2", "fresh_seeds = 20261121,20261122,20261123", "actions = ANSWER,ADD1,ADD2,SUB1,SUB2", "minimum_action_accuracy = 0.995", "minimum_class_recall = 0.99", "minimum_trajectory_exact = 0.99", "maximum_steps_per_event = 1.05", "minimum_compute_reduction_vs_fixed_max = 0.45", "") | Tee-Object -FilePath $log -Append
if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }

$dirty = (git status --porcelain --untracked-files=no | Out-String).Trim()
if ($dirty) { throw "Tracked working tree is not clean:`n$dirty" }

$resultBefore = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
if ($resultBefore -ne $expectedResult -or $fixtureBefore -ne $expectedFixture) { throw "Protected artifact mismatch before C87" }

$c86 = Get-ChildItem "$repo\runs" -Directory -Filter "c86-v5d-variable-step-*" | Sort-Object LastWriteTime -Descending | Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } | Select-Object -First 1
if ($null -eq $c86) { throw "C86 summary not found" }
$c86Summary = Join-Path $c86.FullName "summary.json"

"=== import preflight ===" | Tee-Object -FilePath $log -Append
& $py -c "import fold_lm.v05.benchmarks.gate_d_composition_supervised_variable_step_router as m; print('C87 import OK:', m.EXPERIMENT_ID, m.SEEDS, m.RANK)" 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C87 import failed" }

"=== focused regression ===" | Tee-Object -FilePath $log -Append
& $py -m unittest tests_lm.test_v05_controller tests_lm.test_v05_composition_task tests_lm.test_v05_shared_basis_core -v 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C87 focused regression failed" }

$outDir = "$repo\runs\c87-v5d-variable-router-$([guid]::NewGuid().ToString('N'))"
@("", "output_directory = $outDir", "C37_result_sha256_before = $resultBefore", "fixture_sha256_before = $fixtureBefore", "=== C87 benchmark ===") | Tee-Object -FilePath $log -Append

& $py -u -m fold_lm.v05.benchmarks.gate_d_composition_supervised_variable_step_router --c86-summary $c86Summary --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
$code = $LASTEXITCODE
if ($code -ne 0) { throw "C87 benchmark failed: $code" }

$s = Get-Content (Join-Path $outDir "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$resultAfter = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
$dirtyAfter = (git status --porcelain --untracked-files=no | Out-String).Trim()

@(
"", "=== C87 SUMMARY ===",
"status = $($s.status)",
"supervised_variable_step_router_gate_passed = $($s.summary.supervised_variable_step_router_gate_passed)",
"action_accuracy_min = $($s.summary.action_accuracy.min)",
"class_recall_min = $($s.summary.minimum_per_seed_class_recall.min)",
"trajectory_exact_min = $($s.summary.learned_trajectory_exact_accuracy.min)",
"mean_exact_delta_vs_c86_oracle = $($s.summary.exact_delta_vs_c86_oracle.mean)",
"all_learned_vs_oracle_outputs_allclose = $($s.summary.all_learned_vs_oracle_outputs_allclose)",
"logical_steps_per_event_mean = $($s.summary.logical_compute_steps_per_event.mean)",
"zero_step_rate_min = $($s.summary.zero_step_event_rate.min)",
"two_step_rate_min = $($s.summary.two_step_event_rate.min)",
"compute_reduction_vs_fixed_max_min = $($s.summary.logical_compute_reduction_vs_fixed_max.min)",
"C37_preserved = $($resultAfter -eq $expectedResult)",
"fixture_preserved = $($fixtureAfter -eq $expectedFixture)",
"repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))",
"output_directory = $outDir",
"production_runtime_modified = True",
"gate_d_candidate = False",
"", "=== script error, if any ==="
) | Tee-Object -FilePath $log -Append
