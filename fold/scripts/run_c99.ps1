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
"=== FOLD C99 V5-E acquire/reobserve/answer cycle ===" | Set-Content $log -Encoding UTF8
Set-Location $repo

"=== syncing repository ===" | Tee-Object -FilePath $log -Append
git pull --rebase origin feat/sft-target-loss 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

$branch = (git branch --show-current).Trim()
$head = (git rev-parse HEAD).Trim()
@(
"branch = $branch",
"commit = $head",
"stage = V5-E",
"task = learned acquisition closed loop",
"actions = ANSWER,ACQUIRE",
"fresh_seeds = 20261181,20261182,20261183",
"train_bases = 0,1,2",
"validation_base = 3 (unseen)",
"acquisition_budget = 1",
"authority = model proposes; runtime mutates evidence state",
"required path = ACQUIRE -> evidence update -> reobserve -> ANSWER",
"negative control = answerable rows acquire zero times",
""
) | Tee-Object -FilePath $log -Append
if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }

$dirty = (git status --porcelain --untracked-files=no | Out-String).Trim()
if ($dirty) { throw "Tracked working tree is not clean:`n$dirty" }

$resultBefore = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
if ($resultBefore -ne $expectedResult -or $fixtureBefore -ne $expectedFixture) { throw "Protected artifact mismatch before C99" }

$c98 = Get-ChildItem "$repo\runs" -Directory -Filter "c98-v5e-supervised-sufficiency-*" | Sort-Object LastWriteTime -Descending | Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } | Select-Object -First 1
if ($null -eq $c98) { throw "C98 summary not found" }
$c98Summary = Join-Path $c98.FullName "summary.json"

"=== import preflight ===" | Tee-Object -FilePath $log -Append
& $py -c "import fold_lm.v05_benchmarks.gate_e_acquire_reobserve_answer_cycle as m; print('C99 import OK:', m.EXPERIMENT_ID, m.SEEDS, m.ACQUISITION_BUDGET)" 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C99 import failed" }

"=== focused regression ===" | Tee-Object -FilePath $log -Append
& $py -m unittest tests_lm.test_v05_controller -v 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C99 focused regression failed" }

$outDir = "$repo\runs\c99-v5e-acquire-cycle-$([guid]::NewGuid().ToString('N'))"
@("", "output_directory = $outDir", "C37_result_sha256_before = $resultBefore", "fixture_sha256_before = $fixtureBefore", "=== C99 benchmark ===") | Tee-Object -FilePath $log -Append

& $py -u -m fold_lm.v05_benchmarks.gate_e_acquire_reobserve_answer_cycle --c98-summary $c98Summary --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
$code = $LASTEXITCODE
if ($code -ne 0) { throw "C99 benchmark failed: $code" }

$s = Get-Content (Join-Path $outDir "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$resultAfter = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
$dirtyAfter = (git status --porcelain --untracked-files=no | Out-String).Trim()

@(
"", "=== C99 SUMMARY ===",
"status = $($s.status)",
"acquire_reobserve_answer_cycle_gate_passed = $($s.summary.acquire_reobserve_answer_cycle_gate_passed)",
"required_acquisition_recall_min = $($s.summary.required_acquisition_recall.min)",
"unnecessary_acquisition_rate_max = $($s.summary.unnecessary_acquisition_rate.max)",
"required_exactly_one_acquisition_rate_min = $($s.summary.required_exactly_one_acquisition_rate.min)",
"answerable_zero_acquisition_rate_min = $($s.summary.answerable_zero_acquisition_rate.min)",
"post_acquisition_answer_rate_min = $($s.summary.post_acquisition_answer_rate.min)",
"repeat_acquisition_count_sum = $($s.summary.repeat_acquisition_count.sum)",
"budget_violation_count_sum = $($s.summary.budget_violation_count.sum)",
"ambiguous_direct_answer_attempt_count_sum = $($s.summary.ambiguous_direct_answer_attempt_count.sum)",
"post_cycle_final_accuracy_min = $($s.summary.post_cycle_final_accuracy.min)",
"model_proposes_runtime_mutates_evidence = $($s.summary.model_proposes_runtime_mutates_evidence)",
"C37_preserved = $($resultAfter -eq $expectedResult)",
"fixture_preserved = $($fixtureAfter -eq $expectedFixture)",
"repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))",
"output_directory = $outDir",
"production_runtime_modified = False",
"gate_e_candidate = False",
"", "=== script error, if any ==="
) | Tee-Object -FilePath $log -Append
