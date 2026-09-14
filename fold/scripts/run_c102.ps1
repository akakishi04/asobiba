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
"=== FOLD C102 V5-E learned acquisition outcome closed loop ===" | Set-Content $log -Encoding UTF8
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
"task = learned acquisition success/failure closed loop",
"actions = ANSWER,ACQUIRE,STOP_UNRESOLVED",
"outcomes = SUCCESS,UNAVAILABLE,DENIED,INVALID",
"fresh_seeds = 20261201,20261202,20261203",
"train_bases = 0,1,2",
"validation_base = 3 (unseen)",
"acquisition_budget = 1",
"authority = model proposes; runtime owns outcome and evidence mutation",
"required success path = ACQUIRE -> SUCCESS commit -> reobserve -> ANSWER",
"required failure path = ACQUIRE -> no commit -> reobserve -> STOP_UNRESOLVED",
""
) | Tee-Object -FilePath $log -Append
if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }

$dirty = (git status --porcelain --untracked-files=no | Out-String).Trim()
if ($dirty) { throw "Tracked working tree is not clean:`n$dirty" }

$resultBefore = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
if ($resultBefore -ne $expectedResult -or $fixtureBefore -ne $expectedFixture) { throw "Protected artifact mismatch before C102" }

$c101 = Get-ChildItem "$repo\runs" -Directory -Filter "c101-v5e-supervised-outcome-*" | Sort-Object LastWriteTime -Descending | Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } | Select-Object -First 1
if ($null -eq $c101) { throw "C101 summary not found" }
$c101Summary = Join-Path $c101.FullName "summary.json"

"=== import preflight ===" | Tee-Object -FilePath $log -Append
& $py -c "import fold_lm.v05_benchmarks.gate_e_learned_acquisition_outcome_closed_loop as m; print('C102 import OK:', m.EXPERIMENT_ID, m.SEEDS)" 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C102 import failed" }

"=== focused regression ===" | Tee-Object -FilePath $log -Append
& $py -m unittest tests_lm.test_v05_controller -v 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C102 focused regression failed" }

$outDir = "$repo\runs\c102-v5e-learned-outcome-cycle-$([guid]::NewGuid().ToString('N'))"
@("", "output_directory = $outDir", "C37_result_sha256_before = $resultBefore", "fixture_sha256_before = $fixtureBefore", "=== C102 benchmark ===") | Tee-Object -FilePath $log -Append

& $py -u -m fold_lm.v05_benchmarks.gate_e_learned_acquisition_outcome_closed_loop --c101-summary $c101Summary --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
$code = $LASTEXITCODE
if ($code -ne 0) { throw "C102 benchmark failed: $code" }

$s = Get-Content (Join-Path $outDir "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$resultAfter = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
$dirtyAfter = (git status --porcelain --untracked-files=no | Out-String).Trim()

@(
"", "=== C102 SUMMARY ===",
"status = $($s.status)",
"learned_acquisition_outcome_closed_loop_gate_passed = $($s.summary.learned_acquisition_outcome_closed_loop_gate_passed)",
"initial_required_acquisition_recall_min = $($s.summary.initial_required_acquisition_recall.min)",
"initial_answerable_answer_rate_min = $($s.summary.initial_answerable_answer_rate.min)",
"initial_unnecessary_acquisition_rate_max = $($s.summary.initial_unnecessary_acquisition_rate.max)",
"success_evidence_commit_rate_min = $($s.summary.success_evidence_commit_rate.min)",
"success_answer_rate_min = $($s.summary.success_post_acquisition_answer_rate.min)",
"success_final_accuracy_min = $($s.summary.success_final_accuracy.min)",
"failure_stop_rate_min = $($s.summary.failure_stop_unresolved_rate.min)",
"failure_no_commit_rate_min = $($s.summary.failure_no_evidence_commit_rate.min)",
"failure_no_guess_rate_min = $($s.summary.failure_no_guessed_answer_rate.min)",
"premature_stop_count_sum = $($s.summary.premature_stop_count.sum)",
"repeat_acquisition_count_sum = $($s.summary.repeat_acquisition_count.sum)",
"budget_violation_count_sum = $($s.summary.budget_violation_count.sum)",
"C37_preserved = $($resultAfter -eq $expectedResult)",
"fixture_preserved = $($fixtureAfter -eq $expectedFixture)",
"repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))",
"output_directory = $outDir",
"production_runtime_modified = False",
"gate_e_candidate = False",
"", "=== script error, if any ==="
) | Tee-Object -FilePath $log -Append
